from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import (
    users,
    nas,
    auth,
    groups,
    audit,
    dictionary,
    admin_users,
    access_policies,
)
from app.routers import (
    system,
    sessions,
    nas_categories,
    syslog,
    network_segments,
    device_registry,
    circuits,
)
from app.db.session import engine, Base
from app.core.limiter import limiter
from app.middleware.force_password_change import ForcePasswordChangeMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
import asyncio
import json
import logging
import os


class _JSONFormatter(logging.Formatter):
    @staticmethod
    def _to_jsonable(value, _depth: int = 0):
        if value is None or isinstance(value, (str, int, float, bool)):
            return value

        if _depth >= 4:
            try:
                return repr(value)
            except Exception:
                return "<unrepr-able>"

        if isinstance(value, (list, tuple)):
            return [_JSONFormatter._to_jsonable(v, _depth + 1) for v in value]
        if isinstance(value, (set, frozenset)):
            return [_JSONFormatter._to_jsonable(v, _depth + 1) for v in value]
        if isinstance(value, dict):
            out = {}
            for k, v in value.items():
                try:
                    key = k if isinstance(k, str) else str(k)
                except Exception:
                    key = "<unstringable-key>"
                out[key] = _JSONFormatter._to_jsonable(v, _depth + 1)
            return out

        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")

        if isinstance(value, BaseException):
            return {
                "type": type(value).__name__,
                "message": str(value),
            }

        iso = getattr(value, "isoformat", None)
        if callable(iso):
            try:
                return iso()
            except Exception:
                pass

        try:
            return repr(value)
        except Exception:
            return "<unrepr-able>"

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        extra_skip = logging.LogRecord.__dict__.keys() | {
            "message",
            "asctime",
            "args",
            "exc_text",
            "stack_info",
            "exc_info",
        }
        for key, value in record.__dict__.items():
            if key not in extra_skip:
                payload[key] = self._to_jsonable(value)
        try:
            return json.dumps(payload)
        except Exception as exc:  # pragma: no cover
            fallback = {
                "timestamp": payload.get("timestamp"),
                "level": record.levelname,
                "logger": record.name,
                "message": payload.get("message"),
                "json_error": str(exc),
            }
            if record.exc_info:
                fallback["exc_info"] = payload.get("exc_info")
            return json.dumps(fallback)


def _configure_logging() -> None:
    raw_log_level = os.getenv("LOG_LEVEL", "INFO").strip()
    if raw_log_level.isdigit():
        log_level = int(raw_log_level)
        invalid_log_level = None
    else:
        level = logging.getLevelName(raw_log_level.upper())
        if isinstance(level, int):
            log_level = level
            invalid_log_level = None
        else:
            log_level = logging.INFO
            invalid_log_level = raw_log_level
    handler = logging.StreamHandler()
    handler.setFormatter(_JSONFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = [handler]

    if invalid_log_level is not None:
        logging.getLogger(__name__).warning(
            "Invalid LOG_LEVEL=%r; falling back to INFO.",
            invalid_log_level,
        )

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers = [handler]
        uv_logger.propagate = False


_configure_logging()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CORS — Restricted whitelist (Task 3.1 / 3.2 / 3.3 / 3.4)
# ---------------------------------------------------------------------------
_DEFAULT_DEV_ORIGINS = [
    "http://localhost:3009",
    "http://localhost:5173",
]


def _parse_allowed_origins() -> list[str]:
    """Parse ALLOWED_ORIGINS env var into a validated list of origins.

    - Reads comma-separated URLs from the ``ALLOWED_ORIGINS`` environment variable.
    - Falls back to dev-only localhost origins when the variable is not set.
    - Invalid entries (not starting with http:// or https://) are skipped with
      a warning instead of crashing the application.
    """
    raw = os.getenv("ALLOWED_ORIGINS", "").strip()
    if not raw:
        logger.warning(
            "ALLOWED_ORIGINS is not set — falling back to default development origins: %s",
            _DEFAULT_DEV_ORIGINS,
        )
        return list(_DEFAULT_DEV_ORIGINS)

    validated: list[str] = []
    for entry in raw.split(","):
        origin = entry.strip()
        if not origin:
            continue
        if not (origin.startswith("http://") or origin.startswith("https://")):
            logger.warning(
                "ALLOWED_ORIGINS: '%s' is not a valid URL (must start with http:// or https://) — skipping.",
                origin,
            )
            continue
        validated.append(origin)

    if not validated:
        logger.warning(
            "ALLOWED_ORIGINS contained no valid URLs — falling back to default development origins: %s",
            _DEFAULT_DEV_ORIGINS,
        )
        return list(_DEFAULT_DEV_ORIGINS)

    return validated


_disable_docs = os.getenv("DISABLE_DOCS", "false").lower() == "true"

# ---------------------------------------------------------------------------
# Startup validations — fail fast on dangerous configuration
# ---------------------------------------------------------------------------
_token_expire = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
if _token_expire > 1440:
    raise RuntimeError(
        f"ACCESS_TOKEN_EXPIRE_MINUTES={_token_expire} exceeds maximum allowed value of 1440 (24 hours). "
        "Reduce the token lifetime to improve security."
    )

app = FastAPI(
    title="FreeRADIUS Manager",
    version="1.3.0",
    redirect_slashes=False,
    docs_url=None if _disable_docs else "/docs",
    redoc_url=None if _disable_docs else "/redoc",
    openapi_url=None if _disable_docs else "/openapi.json",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_allowed_origins = _parse_allowed_origins()
logger.info(
    "CORS whitelist configured with %d origin(s): %s",
    len(_allowed_origins),
    _allowed_origins,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

app.add_middleware(ForcePasswordChangeMiddleware)


# ---------------------------------------------------------------------------
# Security Headers Middleware
# ---------------------------------------------------------------------------
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        return response


app.add_middleware(SecurityHeadersMiddleware)


# ---------------------------------------------------------------------------
# Schema Validation and Auto-Migration (Task: db-schema-validation)
# ---------------------------------------------------------------------------


async def run_pending_migrations() -> None:
    """Run alembic.command.upgrade('head'), respecting DISABLE_AUTO_MIGRATE.

    Skips migration if DISABLE_AUTO_MIGRATE=true but still runs validation.
    """
    if os.getenv("DISABLE_AUTO_MIGRATE", "").lower() == "true":
        logger.info("Auto-migration disabled via DISABLE_AUTO_MIGRATE=true — skipping alembic upgrade")
        return

    import alembic.config
    import alembic.command

    cfg = alembic.config.Config("alembic.ini")
    try:
        alembic.command.upgrade(cfg, "head")
        logger.info("Alembic migrations applied successfully")
    except Exception as exc:
        logger.error("Alembic migration failed: %s", exc)
        raise


async def validate_and_migrate() -> None:
    """Run schema validation and auto-migration on startup.

    This function is called during FastAPI startup to ensure the database
    schema matches the SQLAlchemy models before accepting traffic.

    Fail-fast behavior:
    - If DISABLE_AUTO_MIGRATE=true: skip migration but still validate (fail on drift)
    - If auto-migration fails: exit with error
    - If schema drift detected after migration: exit with error
    """
    from app.db.schema_validator import validate_schema_drift
    from app.db.exceptions import KNOWN_EXCEPTIONS

    # Run pending migrations first (if not disabled)
    await run_pending_migrations()

    # Validate schema drift (always, even if migrations were skipped)
    try:
        drift_errors = await validate_schema_drift(engine, KNOWN_EXCEPTIONS)
        if drift_errors:
            error_msg = (
                "Schema drift detected — database schema does not match SQLAlchemy models:\n"
                + "\n".join(f"  - {err}" for err in drift_errors)
                + "\n\nPlease run Alembic migrations or update the database schema."
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        logger.info("Schema validation passed — no drift detected")
    except RuntimeError:
        # Re-raise RuntimeError for fail-fast behavior
        raise
    except Exception as exc:
        logger.error("Schema validation failed: %s", exc)
        raise RuntimeError(f"Schema validation failed: {exc}") from exc


# Startup event to create tables if they don't exist (useful for dev)
@app.on_event("startup")
async def startup():
    # Run schema validation and auto-migration (fail-fast on drift)
    # This runs BEFORE create_all to ensure schema is up-to-date
    try:
        await validate_and_migrate()
    except RuntimeError as exc:
        logger.error("Startup failed: %s", exc)
        import sys
        sys.exit(1)

    async with engine.begin() as conn:
        # In production, use Alembic for migrations
        await conn.run_sync(Base.metadata.create_all)

    # Initialize DB with default admin if not exists
    from app.db.session import SessionLocal
    from app.models.models import AdminUser
    from app.core.security import get_password_hash
    from sqlalchemy import select

    async with SessionLocal() as db:  # type: ignore[attr-defined]
        result = await db.execute(
            select(AdminUser).where(AdminUser.username == "admin")
        )
        user = result.scalars().first()
        if not user:
            # Create default admin user
            hashed_pw = get_password_hash("admin")
            new_admin = AdminUser(
                username="admin",
                hashed_password=hashed_pw,
                role="superadmin",
                force_password_change=1,  # Force change immediately
            )
            db.add(new_admin)
            await db.commit()
            print("Default admin user created.")


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(nas.router)
app.include_router(groups.router)
app.include_router(audit.router)
app.include_router(dictionary.router)
app.include_router(admin_users.router)
app.include_router(system.router)
app.include_router(sessions.router)
app.include_router(nas_categories.router)
app.include_router(network_segments.router)
app.include_router(access_policies.router)
app.include_router(device_registry.router)
app.include_router(circuits.router)


# ---------------------------------------------------------------------------
# Syslog Compliance API
# ---------------------------------------------------------------------------
app.include_router(syslog.router)


# ---------------------------------------------------------------------------
# T33 — Background integrity hash job
# Runs every 60 seconds, backfilling integrity_hash for new radpostauth rows.
# ---------------------------------------------------------------------------

_integrity_task: asyncio.Task | None = None
_syslog_integrity_task: asyncio.Task | None = None


async def _integrity_hash_loop() -> None:
    """Periodic background task: backfill missing integrity hashes every 60 seconds."""
    from app.db.session import SessionLocal  # type: ignore[attr-defined]
    from app.services.integrity import backfill_hashes

    while True:
        try:
            async with SessionLocal() as db:  # type: ignore[attr-defined]
                count = await backfill_hashes(db, batch_size=500)
            if count > 0:
                logger.info(
                    "Background integrity job: hashed %d new radpostauth records.",
                    count,
                )
        except Exception as exc:  # pragma: no cover
            logger.error("Background integrity job error: %s", exc)

        await asyncio.sleep(60)


async def _syslog_integrity_loop() -> None:
    """Periodic background task: backfill missing syslog hashes every 60 seconds."""
    from app.db.session import SessionLocal  # type: ignore[attr-defined]
    from app.services.syslog_integrity import backfill_syslog_hashes

    while True:
        try:
            async with SessionLocal() as db:  # type: ignore[attr-defined]
                count = await backfill_syslog_hashes(db, batch_size=500)
            if count > 0:
                logger.info(
                    "Background syslog integrity job: hashed %d new syslog records.",
                    count,
                )
        except Exception as exc:  # pragma: no cover
            logger.error("Background syslog integrity job error: %s", exc)

        await asyncio.sleep(60)


@app.on_event("startup")
async def start_background_jobs() -> None:
    """Start the integrity hash background loop on application startup."""
    global _integrity_task, _syslog_integrity_task
    _integrity_task = asyncio.create_task(_integrity_hash_loop())
    _syslog_integrity_task = asyncio.create_task(_syslog_integrity_loop())
    logger.info("Background integrity hash job started.")
    logger.info("Background syslog integrity hash job started.")


@app.on_event("shutdown")
async def stop_background_jobs() -> None:
    """Cancel background tasks gracefully on shutdown."""
    global _integrity_task, _syslog_integrity_task
    if _integrity_task and not _integrity_task.done():
        _integrity_task.cancel()
        try:
            await _integrity_task
        except asyncio.CancelledError:
            pass
    logger.info("Background integrity hash job stopped.")

    if _syslog_integrity_task and not _syslog_integrity_task.done():
        _syslog_integrity_task.cancel()
        try:
            await _syslog_integrity_task
        except asyncio.CancelledError:
            pass
    logger.info("Background syslog integrity hash job stopped.")


@app.get("/")
def read_root():
    return {"message": "Welcome to FreeRADIUS Manager API"}


@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration.

    Returns service status for all critical dependencies.
    """
    status = {"status": "ok", "services": {}}

    # Check database connectivity
    try:
        from app.db.session import SessionLocal  # type: ignore[attr-defined]

        async with SessionLocal() as db:  # type: ignore[attr-defined]
            from sqlalchemy import text

            await db.execute(text("SELECT 1"))
        status["services"]["database"] = "ok"
    except Exception:
        status["services"]["database"] = "error"
        status["status"] = "degraded"

    return status
