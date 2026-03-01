"""SQLite async engine and session factory.

Uses SQLAlchemy 2.0 async API with aiosqlite driver.
WAL mode is enabled at connection time for better read concurrency.
"""

from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sidecar.config import get_settings

_engine = None
_async_session_factory = None


def get_engine():
    """Return (creating if needed) the shared async engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=False,
            connect_args={"check_same_thread": False},
        )

        # Enable WAL mode for better read concurrency on SQLite
        @event.listens_for(_engine.sync_engine, "connect")
        def set_wal_mode(dbapi_conn, _connection_record):
            dbapi_conn.execute("PRAGMA journal_mode=WAL")
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return (creating if needed) the shared async session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _async_session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session per request."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_all_tables() -> None:
    """Create all tables defined in sidecar.db. Called at app startup."""
    import sidecar.db  # noqa: F401 — triggers db/__init__.py which imports all table modules
    from sidecar.db.base import Base  # noqa: F401

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
