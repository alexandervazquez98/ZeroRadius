from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import users, nas, auth, groups, audit, dictionary, admin_users
from app.routers import system, privilege_map, sessions, iam_nac, nas_categories
from app.db.session import engine, Base
from app.core.limiter import limiter
from app.middleware.force_password_change import ForcePasswordChangeMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
import asyncio
import logging
import os

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
    version="1.1.1",
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


# Startup event to create tables if they don't exist (useful for dev)
@app.on_event("startup")
async def startup():
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
app.include_router(privilege_map.router)
app.include_router(sessions.router)
app.include_router(iam_nac.router)
app.include_router(nas_categories.router)


# ---------------------------------------------------------------------------
# T33 — Background integrity hash job
# Runs every 60 seconds, backfilling integrity_hash for new radpostauth rows.
# ---------------------------------------------------------------------------

_integrity_task: asyncio.Task | None = None


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


@app.on_event("startup")
async def start_background_jobs() -> None:
    """Start the integrity hash background loop on application startup."""
    global _integrity_task
    _integrity_task = asyncio.create_task(_integrity_hash_loop())
    logger.info("Background integrity hash job started.")


@app.on_event("shutdown")
async def stop_background_jobs() -> None:
    """Cancel background tasks gracefully on shutdown."""
    global _integrity_task
    if _integrity_task and not _integrity_task.done():
        _integrity_task.cancel()
        try:
            await _integrity_task
        except asyncio.CancelledError:
            pass
    logger.info("Background integrity hash job stopped.")


@app.get("/")
def read_root():
    return {"message": "Welcome to FreeRADIUS Manager API"}
