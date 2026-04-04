"""
System router — ISO 27001 A.8.17 (Time synchronization) & Live Log Viewer.
Exposes NTP status and real-time FreeRADIUS log streaming for admin/superadmin roles.
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone

import docker
from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
import jwt
from jwt.exceptions import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limiter import limiter
from app.core.rbac import Role, require_roles
from app.core.security import (
    ALGORITHM,
    SECRET_KEY,
    get_current_active_user,
)
from app.db.session import SessionLocal, get_db
from app.models.models import AdminUser
from app.schemas.schemas import NTPStatusResponse
from app.services.ntp_status import get_status as get_ntp_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system", tags=["system"])

# ---------------------------------------------------------------------------
# Container name for radius service (matches docker-compose.yml)
# ---------------------------------------------------------------------------
RADIUS_CONTAINER_NAME = "radius-server"

# Max lines per request block to prevent unbounded accumulation
MAX_BLOCK_LINES = 500

# Regex patterns for FreeRADIUS -X debug output
_RE_REQUEST_START = re.compile(r"^\((\d+)\)\s+Received\s+Access-Request", re.IGNORECASE)
_RE_VERDICT = re.compile(
    r"^\((\d+)\)\s+Sent\s+(Access-Accept|Access-Reject)", re.IGNORECASE
)
_RE_REQUEST_LINE = re.compile(r"^\((\d+)\)\s+")


# ---------------------------------------------------------------------------
# NTP Status endpoint (existing)
# ---------------------------------------------------------------------------
@router.get("/ntp-status", response_model=NTPStatusResponse)
@limiter.limit("60/minute")
async def ntp_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.ADMIN, Role.SUPERADMIN),
):
    """
    Returns current NTP synchronization status.
    Requires admin or superadmin role.
    """
    status = get_ntp_status()
    return NTPStatusResponse(
        synchronized=status.synchronized,
        offset_ms=status.offset_ms,
        stratum=status.stratum,
        reference_server=status.reference_server,
        last_sync=status.last_sync,
        alert=status.alert,
    )


# ---------------------------------------------------------------------------
# WebSocket log streaming
# ---------------------------------------------------------------------------


async def _authenticate_ws(token: str) -> AdminUser | None:
    """
    Validate a JWT token outside the normal Depends() chain (WebSocket has no
    OAuth2 header support).  Returns the AdminUser if valid & authorized, else None.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub", "")
        if not username:
            return None
    except InvalidTokenError:
        return None

    async with SessionLocal() as db:
        result = await db.execute(
            select(AdminUser).where(AdminUser.username == username)
        )
        user = result.scalars().first()

    if user is None or not bool(user.is_active):
        return None

    # Role gate: only admin / superadmin may stream logs
    if user.role not in (Role.ADMIN.value, Role.SUPERADMIN.value):
        return None

    return user


@router.websocket("/logs/stream")
async def stream_radius_logs(websocket: WebSocket):
    """
    Real-time FreeRADIUS log streamer (WebSocket).

    Protocol:
      1. Client sends JWT token as the first text message.
      2. Server validates and replies {"status": "connected"}.
      3. Server starts streaming filtered Access-Request blocks as JSON.
      4. Each block contains { request_id, verdict, timestamp, lines[] }.

    Only Access-Request → Accept/Reject blocks are forwarded;
    all other debug noise is dropped.
    """
    await websocket.accept()

    # --- Step 1: Authenticate via first message ---
    try:
        token = await asyncio.wait_for(websocket.receive_text(), timeout=10)
    except (asyncio.TimeoutError, WebSocketDisconnect):
        await websocket.close(code=4001, reason="Authentication timeout")
        return

    user = await _authenticate_ws(token)
    if user is None:
        await websocket.send_text(json.dumps({"error": "Unauthorized"}))
        await websocket.close(code=4003, reason="Unauthorized")
        return

    await websocket.send_text(json.dumps({"status": "connected"}))
    logger.info("Log stream opened by %s", user.username)

    # --- Step 2: Connect to Docker and stream logs ---
    try:
        client = docker.from_env()
        container = client.containers.get(RADIUS_CONTAINER_NAME)
    except docker.errors.NotFound:
        await websocket.send_text(
            json.dumps({"error": f"Container '{RADIUS_CONTAINER_NAME}' not found"})
        )
        await websocket.close(code=4004, reason="Container not found")
        return
    except docker.errors.DockerException as exc:
        await websocket.send_text(json.dumps({"error": f"Docker error: {str(exc)}"}))
        await websocket.close(code=4005, reason="Docker error")
        return

    # Stateful accumulator: { request_id: [lines] }
    blocks: dict[int, list[str]] = {}

    try:
        log_gen = container.logs(
            stream=True,
            follow=True,
            tail=0,  # Only new lines from now on
            timestamps=True,
        )

        loop = asyncio.get_event_loop()

        # Docker SDK logs() is a blocking generator — run in a thread
        def _next_line():
            try:
                return next(log_gen)
            except StopIteration:
                return None

        while True:
            chunk = await loop.run_in_executor(None, _next_line)
            if chunk is None:
                break

            line = chunk.decode("utf-8", errors="replace").rstrip("\n\r")
            if not line:
                continue

            # Separate Docker timestamp from log content if present
            # Docker timestamps look like: 2026-03-30T22:44:51.123456789Z
            ts = ""
            content = line
            if len(line) > 31 and line[0].isdigit() and "Z " in line[:35]:
                ts_end = line.index("Z ") + 1
                ts = line[:ts_end].strip()
                content = line[ts_end:].strip()

            # --- Check if this line starts a new Access-Request ---
            m_start = _RE_REQUEST_START.match(content)
            if m_start:
                req_id = int(m_start.group(1))
                blocks[req_id] = [content]
                continue

            # --- Check if this line is a verdict (end of block) ---
            m_verdict = _RE_VERDICT.match(content)
            if m_verdict:
                req_id = int(m_verdict.group(1))
                verdict = m_verdict.group(2)  # Access-Accept or Access-Reject

                block_lines = blocks.pop(req_id, [])
                block_lines.append(content)

                event = {
                    "request_id": req_id,
                    "verdict": verdict.replace("Access-", ""),
                    "timestamp": ts or datetime.now(timezone.utc).isoformat(),
                    "lines": block_lines,
                }

                await websocket.send_text(json.dumps(event))
                continue

            # --- Accumulate lines belonging to an active request ---
            m_req = _RE_REQUEST_LINE.match(content)
            if m_req:
                req_id = int(m_req.group(1))
                if req_id in blocks:
                    if len(blocks[req_id]) < MAX_BLOCK_LINES:
                        blocks[req_id].append(content)
                continue

            # Lines not matching any request ID prefix are dropped (noise)

    except WebSocketDisconnect:
        logger.info("Log stream closed by %s", user.username)
    except Exception as exc:
        logger.error("Log stream error: %s", exc)
        try:
            await websocket.send_text(json.dumps({"error": str(exc)}))
        except Exception:
            pass
    finally:
        try:
            log_gen.close()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass
