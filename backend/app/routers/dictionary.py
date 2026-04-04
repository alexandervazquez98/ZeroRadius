from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from app.db.session import get_db
from app.models.models import AdminUser
from app.services.dictionary_loader import (
    dictionary_service,
    _parse_builtin_attr_grep_output,
)
from app.services.audit import log_audit
from app.core.security import get_current_active_user
from app.core.rbac import require_roles, Role
from app.core.limiter import limiter
import logging
import docker as docker_sdk

logger = logging.getLogger(__name__)

# Module-level cache for built-in RADIUS attributes.
# Populated lazily on first request; survives for the process lifetime because
# built-in dictionaries never change while the container is running.
_builtin_attr_cache: Optional[List] = None

router = APIRouter(prefix="/dictionary", tags=["dictionary"])


def _get_builtin_attributes_cached() -> List:
    """Return RADIUS attributes from FreeRADIUS built-in vendor dictionaries.

    Uses Docker exec to grep the radius-server container once; subsequent calls
    return the in-memory result without touching Docker again.

    Gracefully returns an empty list when the container is unavailable (e.g.
    in unit-test environments or during local development without Docker).
    """
    global _builtin_attr_cache
    if _builtin_attr_cache is not None:
        return _builtin_attr_cache

    try:
        grep_output = _exec_in_radius(
            [
                "grep",
                "-rE",
                "^(ATTRIBUTE|VENDOR|BEGIN-VENDOR|END-VENDOR)",
                "/usr/share/freeradius/",
            ]
        )
        _builtin_attr_cache = _parse_builtin_attr_grep_output(grep_output)
        logger.info(
            "Loaded %d built-in RADIUS attributes from radius-server container",
            len(_builtin_attr_cache),
        )
    except Exception as exc:
        logger.warning("Could not load built-in RADIUS attributes: %s", exc)
        _builtin_attr_cache = []

    return _builtin_attr_cache


def _reload_radius() -> None:
    """Restart the radius-server container so it re-reads custom dictionaries.

    FreeRADIUS only loads dictionaries at startup.  After uploading,
    editing or deleting a dictionary file the container must be restarted
    for the changes to take effect.
    """
    try:
        client = docker_sdk.from_env()
        container = client.containers.get("radius-server")
        container.restart(timeout=5)
        logger.info("radius-server restarted to reload custom dictionaries")
    except Exception as exc:
        logger.warning("Could not restart radius-server: %s", exc)


# ---------- Schemas ----------


class AttributeValue(BaseModel):
    name: str
    value: str | int


class AttributeInfo(BaseModel):
    name: str
    code: str | int
    type: str
    vendor: Optional[str] = None
    dictionary: Optional[str] = "Unknown"


class ContentBody(BaseModel):
    content: str


# ---------- File CRUD ----------


@router.get("/files", response_model=List[str])
@limiter.limit("60/minute")
async def list_dictionary_files(
    request: Request,
    current_user: AdminUser = Depends(get_current_active_user),
):
    """List loaded dictionary files."""
    return dictionary_service.list_files()


@router.post("/upload")
@limiter.limit("10/minute")
async def upload_dictionary(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    """Upload and validate a new dictionary file (auto-converts v4 types)."""
    content = await file.read()
    if len(content) > 1_048_576:  # 1MB
        raise HTTPException(
            status_code=413, detail="File too large. Maximum size is 1MB."
        )
    try:
        result = dictionary_service.validate_and_save(
            file.filename or "unknown",
            content,
        )
        msg = f"Dictionary {file.filename} uploaded successfully."
        if result["conversions"] > 0:
            msg += (
                f" {result['conversions']} FreeRADIUS 4.x type(s) were "
                "auto-converted to 3.x equivalents."
            )
        if result.get("renames"):
            msg += (
                f" {len(result['renames'])} vendor attribute(s) were "
                f"auto-renamed to avoid collisions: "
                f"{', '.join(result['renames'])}."
            )
        await log_audit(
            db,
            current_user.username,
            "UPLOAD",
            "dictionary",
            file.filename,
        )
        _reload_radius()
        return {"message": msg}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rename")
@limiter.limit("10/minute")
async def rename_dictionary(
    request: Request,
    old_name: str,
    new_name: str,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    """Rename a dictionary file."""
    try:
        dictionary_service.rename_file(old_name, new_name)
        await log_audit(
            db,
            current_user.username,
            "RENAME",
            "dictionary",
            old_name,
            new_value={"new_name": new_name},
        )
        _reload_radius()
        return {"message": f"File {old_name} renamed to {new_name}"}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except FileExistsError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{filename}")
@limiter.limit("10/minute")
async def delete_dictionary(
    request: Request,
    filename: str,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    """Delete a dictionary file."""
    try:
        dictionary_service.delete_file(filename)
        await log_audit(
            db,
            current_user.username,
            "DELETE",
            "dictionary",
            filename,
        )
        _reload_radius()
        return {"message": f"Dictionary {filename} deleted."}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- Content (read / edit) ----------


@router.get("/content/{filename}")
@limiter.limit("60/minute")
async def get_dictionary_content(
    request: Request,
    filename: str,
    current_user: AdminUser = Depends(get_current_active_user),
):
    """Return the raw text content of a dictionary file."""
    try:
        content = dictionary_service.read_content(filename)
        return {"filename": filename, "content": content}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/content/{filename}")
@limiter.limit("10/minute")
async def update_dictionary_content(
    request: Request,
    filename: str,
    body: ContentBody,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    """Overwrite a dictionary file with new content (auto-converts v4 types)."""
    try:
        result = dictionary_service.write_content(filename, body.content)
        msg = f"Dictionary {filename} updated successfully."
        if result["conversions"] > 0:
            msg += (
                f" {result['conversions']} FreeRADIUS 4.x type(s) were "
                "auto-converted to 3.x equivalents."
            )
        if result.get("renames"):
            msg += (
                f" {len(result['renames'])} vendor attribute(s) were "
                f"auto-renamed to avoid collisions: "
                f"{', '.join(result['renames'])}."
            )
        await log_audit(
            db,
            current_user.username,
            "UPDATE",
            "dictionary",
            filename,
        )
        _reload_radius()
        return {"message": msg}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- Built-in dictionaries (read-only view) ----------


def _exec_in_radius(cmd: list) -> str:
    """Run a command inside the radius-server container and return stdout.

    Uses the Docker SDK that is already a project dependency and already
    used by _reload_radius().  Raises RuntimeError if the container is
    unavailable or the command fails.
    """
    client = docker_sdk.from_env()
    container = client.containers.get("radius-server")
    exit_code, output = container.exec_run(cmd)
    if exit_code != 0:
        raise RuntimeError(f"Command {cmd} exited with code {exit_code}")
    return output.decode("utf-8", errors="replace")


class BuiltinDictInfo(BaseModel):
    filename: str
    vendor: str


@router.get("/builtin", response_model=List[BuiltinDictInfo])
@limiter.limit("60/minute")
async def list_builtin_dictionaries(
    request: Request,
    current_user: AdminUser = Depends(get_current_active_user),
):
    """List built-in FreeRADIUS vendor dictionaries from the radius-server container.

    Reads /usr/share/freeradius/ inside the container and returns every
    'dictionary.<vendor>' file (skipping the top-level 'dictionary' index file
    which just $INCLUDEs the others — it is too large and not useful to display).
    """
    try:
        raw = _exec_in_radius(["ls", "/usr/share/freeradius/"])
        results = []
        for name in sorted(raw.splitlines()):
            name = name.strip()
            # Only vendor-specific dictionary files
            if not name.startswith("dictionary."):
                continue
            vendor = name[len("dictionary.") :]  # e.g. "cisco", "cisco.asa"
            results.append(BuiltinDictInfo(filename=name, vendor=vendor))
        return results
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not read built-in dictionaries from radius-server: {exc}",
        )


@router.get("/builtin/{filename}")
@limiter.limit("60/minute")
async def get_builtin_dictionary_content(
    request: Request,
    filename: str,
    current_user: AdminUser = Depends(get_current_active_user),
):
    """Return the raw content of a built-in FreeRADIUS dictionary file.

    Validates that the requested filename follows the expected pattern to
    prevent path traversal attacks before exec-ing into the container.
    """
    import re as _re

    if not _re.fullmatch(r"dictionary\.[a-zA-Z0-9._-]+", filename):
        raise HTTPException(
            status_code=400, detail="Invalid built-in dictionary filename."
        )
    try:
        content = _exec_in_radius(["cat", f"/usr/share/freeradius/{filename}"])
        return {"filename": filename, "content": content, "builtin": True}
    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Could not read {filename} from radius-server: {exc}",
        )


# ---------- Attribute queries ----------


@router.get("/attributes", response_model=List[AttributeInfo])
@limiter.limit("60/minute")
async def get_attributes(
    request: Request,
    current_user: AdminUser = Depends(get_current_active_user),
):
    """Get all available RADIUS attributes from custom and built-in dictionaries.

    Merges attributes from:
    1. Custom dictionaries uploaded by the user (``backend/dictionaries/``)
    2. FreeRADIUS built-in vendor dictionaries (``/usr/share/freeradius/``)

    Custom attributes always take precedence over built-ins with the same name.
    Built-in attributes are tagged with a ``[Sistema] dictionary.*`` prefix in
    the ``dictionary`` field so the UI can group them separately.
    """
    custom_attrs = dictionary_service.get_attributes()
    builtin_attrs = _get_builtin_attributes_cached()

    # Custom attrs win on name collision — avoids duplicates in the selector
    custom_names = {a["name"] for a in custom_attrs}
    merged = custom_attrs + [a for a in builtin_attrs if a["name"] not in custom_names]
    return sorted(merged, key=lambda x: x["name"])


@router.get("/values/{attribute_name}", response_model=List[AttributeValue])
@limiter.limit("60/minute")
async def get_attribute_values(
    request: Request,
    attribute_name: str,
    current_user: AdminUser = Depends(get_current_active_user),
):
    """Get predefined values (enums) for a specific attribute."""
    return dictionary_service.get_values(attribute_name)


# ---------- FreeRADIUS logs ----------


@router.get("/radius-logs")
@limiter.limit("30/minute")
async def get_radius_logs(
    request: Request,
    lines: int = 80,
    current_user: AdminUser = require_roles(Role.ADMIN, Role.SUPERADMIN),
):
    """Return recent FreeRADIUS container logs for dictionary diagnostics.

    Filters the output to show only dictionary-related lines (includes,
    errors, warnings) plus the last startup status.
    """
    try:
        client = docker_sdk.from_env()
        container = client.containers.get("radius-server")
        raw_logs = container.logs(tail=lines, timestamps=False).decode(
            "utf-8", errors="replace"
        )

        all_lines = raw_logs.splitlines()

        # Filter for dictionary/startup relevant lines
        keywords = [
            "dictionary",
            "dict_init",
            "dict_add",
            "Duplicate attribute",
            "Error",
            "error",
            "Warning",
            "warning",
            "Including custom",
            "Skipping duplicate",
            "Starting -",
            "Ready to process",
            "Listening on",
            "Exiting",
            "removed v4 keyword",
        ]
        filtered = [
            ln for ln in all_lines if any(kw.lower() in ln.lower() for kw in keywords)
        ]

        # Determine overall status
        status = "unknown"
        for ln in reversed(all_lines):
            if "Ready to process requests" in ln:
                status = "running"
                break
            if "Exiting normally" in ln or "Error" in ln.lower():
                status = "error"
                break

        return {
            "status": status,
            "total_lines": len(all_lines),
            "filtered_lines": len(filtered),
            "logs": filtered[-50:],  # last 50 relevant lines
        }
    except Exception as exc:
        return {
            "status": "unavailable",
            "total_lines": 0,
            "filtered_lines": 0,
            "logs": [f"Could not fetch logs: {exc}"],
        }
