"""Async SQLAlchemy 2.0 engine, session factory, and Base declarative class.

Usage in routers / services:
    from app.database import async_session, Base

    async with async_session() as session:
        ...
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all ORM models."""
    pass


async def init_db() -> None:
    """Create all tables (for development only; use Alembic in production)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Dispose the engine connection pool."""
    await engine.dispose()
