"""
T35 — pytest conftest.py for RADIUS-gestor backend tests.

Provides:
- test_db: in-memory SQLite AsyncSession with all tables created
- async_client: httpx.AsyncClient wired to FastAPI app + test DB
- Token fixtures: superadmin_token, admin_token, helpdesk_token, auditor_token, readonly_token
- test_group_id: creates a test radius group and returns its id
"""

import pytest
import pytest_asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

# Use SQLite in-memory for tests (aiosqlite driver)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    from app.db.session import Base
    import app.models.models  # noqa: F401 — register all ORM models with Base.metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_db(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean AsyncSession for each test, with automatic rollback."""
    TestSessionLocal = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="session")
async def seed_test_users(test_engine):
    """Seed all 5 role-based test users into the test DB (session-scoped, runs once)."""
    from app.models.models import AdminUser

    TestSessionLocal = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )

    test_users = [
        {"username": "test_superadmin", "role": "superadmin"},
        {"username": "test_admin", "role": "admin"},
        {"username": "test_helpdesk", "role": "helpdesk"},
        {"username": "test_auditor", "role": "auditor"},
        {"username": "test_readonly", "role": "readonly"},
    ]

    # Pre-computed bcrypt hash for "TestPassword1!" — avoids passlib/bcrypt
    # incompatibility on Python 3.14 where passlib's wrap-bug detection fails.
    hashed_pw = "$2b$12$o1OT5/N.USFa0TLuT482HOhFm1UtQ/BQhnZ.si36AZgZbFp0Sjzgu"

    async with TestSessionLocal() as session:
        for u in test_users:
            user = AdminUser(
                username=u["username"],
                hashed_password=hashed_pw,
                is_active=1,
                force_password_change=0,
                role=u["role"],
            )
            session.add(user)
        await session.commit()

    yield  # users remain in DB for the entire test session


@pytest_asyncio.fixture(scope="session")
async def async_client(
    test_engine, seed_test_users
) -> AsyncGenerator[AsyncClient, None]:
    """httpx.AsyncClient targeting the FastAPI app with the test DB session injected."""
    from app.main import app
    from app.db.session import get_db

    TestSessionLocal = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers to create test users and generate tokens
# ---------------------------------------------------------------------------


def _make_token(username: str, role: str) -> str:
    """Generate a real (signed) JWT for testing using the app's security module."""
    from app.core.security import create_access_token

    return create_access_token(data={"sub": username, "role": role})


@pytest.fixture(scope="session")
def superadmin_token() -> str:
    return _make_token("test_superadmin", "superadmin")


@pytest.fixture(scope="session")
def admin_token() -> str:
    return _make_token("test_admin", "admin")


@pytest.fixture(scope="session")
def helpdesk_token() -> str:
    return _make_token("test_helpdesk", "helpdesk")


@pytest.fixture(scope="session")
def auditor_token() -> str:
    return _make_token("test_auditor", "auditor")


@pytest.fixture(scope="session")
def readonly_token() -> str:
    return _make_token("test_readonly", "readonly")


# ---------------------------------------------------------------------------
# DB object fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def test_group_id(test_db: AsyncSession) -> int:
    """Insert a test radius group and return its id."""
    from app.models.models import RadiusGroup

    group = RadiusGroup(
        groupname="test_group_t40",
        description="Test group for RBAC tests",
    )
    test_db.add(group)
    await test_db.commit()
    await test_db.refresh(group)
    return group.id
