from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import users, nas, auth, groups, audit, dictionary, admin_users
from app.routers import system, privilege_map, sessions, iam_nac, nas_categories
from app.db.session import engine, Base
import asyncio
import logging
import os

logger = logging.getLogger(__name__)

app = FastAPI(title="FreeRADIUS Manager", version="1.1.1", redirect_slashes=False)

# CORS
origins = os.getenv(
    "ALLOWED_ORIGINS",
    "*",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
