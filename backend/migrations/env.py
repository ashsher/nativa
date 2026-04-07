"""
migrations/env.py — Alembic async migration environment.

Configures Alembic to use the same async SQLAlchemy engine as the application
so that migrations run against the correct database and can detect schema
changes from all ORM models automatically.

Supports both:
  - Online mode: run migrations directly against a live database.
  - Offline mode: generate SQL scripts without a live DB connection.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

# ---------------------------------------------------------------------------
# Import application config and all ORM models.
# ---------------------------------------------------------------------------
# Importing app.config makes settings available (reads .env if present).
from app.config import settings

# Import the shared declarative Base so Alembic can inspect metadata.
from app.database import Base

# Import all models to register them with Base.metadata.
# Without these imports, autogenerate would produce empty migrations.
import app.models  # noqa: F401

# ---------------------------------------------------------------------------
# Alembic Config object — provides access to values in alembic.ini.
# ---------------------------------------------------------------------------
config = context.config

# Set up Python logging from the alembic.ini [loggers] section if present.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Point Alembic at the application's full metadata so autogenerate works.
target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Offline mode: generate SQL without a DB connection.
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    In offline mode Alembic renders SQL statements to stdout (or a file)
    without connecting to the database.  Useful for generating migration
    scripts to review before applying.
    """
    # Use the DATABASE_URL from application settings.
    url = settings.DATABASE_URL

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        # Use 'compare_type=True' so column type changes are detected.
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online mode: run migrations against a live async database connection.
# ---------------------------------------------------------------------------
def do_run_migrations(connection: Connection) -> None:
    """Run the actual migration commands inside a synchronous connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Create an async engine and run migrations within it.

    We use NullPool to avoid pooling issues during migration runs
    (migrations are short-lived, not long-running web requests).
    """
    connectable = create_async_engine(
        settings.DATABASE_URL,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        # Alembic's run_sync bridges the async/sync gap.
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migration mode."""
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Choose mode based on Alembic context.
# ---------------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
