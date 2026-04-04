from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from typing import TYPE_CHECKING

# ---------------------------------------------------------------------------
# Base is always available — it does NOT depend on DATABASE_URL.
# This allows importing Base for model definitions and test collection
# without requiring a database connection.
# ---------------------------------------------------------------------------
Base = declarative_base()

# ---------------------------------------------------------------------------
# engine and SessionLocal are created lazily on first access.
# This prevents module-level RuntimeError during test collection when
# DATABASE_URL is not set (tests use their own in-memory SQLite engine).
# ---------------------------------------------------------------------------

_engine = None
_SessionLocal = None


def _require_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL environment variable is required. "
            "Set it to a valid SQLAlchemy async connection string, e.g.: "
            "mysql+aiomysql://user:password@host/database"
        )
    return url


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            _require_database_url(),
            echo=os.getenv("SQL_ECHO", "false").lower() == "true",
        )
    return _engine


def _get_session_local():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=_get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _SessionLocal


# Lazy module attributes — triggered on `from app.db.session import engine`
def __getattr__(name: str):
    if name == "engine":
        return _get_engine()
    if name == "SessionLocal":
        return _get_session_local()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# For type checkers
if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine
    from sqlalchemy.orm import sessionmaker as _sessionmaker_cls

    engine: AsyncEngine
    SessionLocal: _sessionmaker_cls[AsyncSession]  # type: ignore[type-arg]


async def get_db():
    async with _get_session_local()() as session:
        yield session
