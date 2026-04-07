"""
app/database.py — async SQLAlchemy engine and session factory.

Import `get_db` as a FastAPI dependency to obtain a per-request async session.
Import `Base` in all ORM models so they share the same metadata registry.
"""

from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from app.config import settings

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
# create_async_engine uses asyncpg under the hood (postgresql+asyncpg://...).
# pool_pre_ping=True checks connections before use to handle stale sockets.
# echo=False keeps SQL statements out of production logs (flip for debugging).
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=False,
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------
# expire_on_commit=False prevents lazy-load errors after a commit when the
# session is still alive but the transaction has ended.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------
# All ORM models inherit from this Base so SQLAlchemy can discover them for
# migrations and schema creation.
Base = declarative_base()


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an async database session.

    Usage:
        @router.get("/")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            # Commit any pending changes when the request completes normally.
            await session.commit()
        except Exception:
            # Roll back the transaction on any unhandled exception so the DB
            # stays in a consistent state.
            await session.rollback()
            raise
