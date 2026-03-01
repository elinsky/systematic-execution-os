"""Alembic environment configuration for async SQLAlchemy + aiosqlite."""

import asyncio
import os
from logging.config import fileConfig

from dotenv import dotenv_values
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Import all table modules so Base.metadata is fully populated
import sidecar.db  # noqa: F401
from sidecar.db.base import Base

# Alembic Config object — provides access to values in alembic.ini
config = context.config

# Resolve the database URL.  Priority:
#   1. DATABASE_URL env var (if set explicitly)
#   2. Value from .env file
#   3. Default from alembic.ini
_DEFAULT_DB_URL = "sqlite+aiosqlite:///./bam_execution.db"
_dotenv = dotenv_values(".env")
_db_url = os.environ.get(
    "DATABASE_URL",
    _dotenv.get("DATABASE_URL", _DEFAULT_DB_URL),
)
config.set_main_option("sqlalchemy.url", _db_url)

# Set up Python logging from the ini file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# MetaData object for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Configures the context with just a URL (no Engine needed), so a DBAPI
    driver does not need to be available. Calls to context.execute() emit
    the given SQL string to the script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # Required for SQLite ALTER TABLE support
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Shared helper — configure context and run migrations on a connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # Required for SQLite ALTER TABLE support
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations in 'online' mode."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online (connected) migrations — delegates to async."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
