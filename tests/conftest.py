"""Shared pytest fixtures for all tests."""

import httpx
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sidecar.db.base import Base
from sidecar.main import create_app


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session():
    """In-memory SQLite session for unit/integration tests."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # Import all ORM models to ensure tables are registered
    import sidecar.db  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def test_client(db_session: AsyncSession):
    """AsyncClient with in-memory DB injected via FastAPI dependency override."""
    from sidecar.database import get_db_session

    async def override_db_session():
        yield db_session

    app = create_app()
    app.dependency_overrides[get_db_session] = override_db_session

    transport = httpx.ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
