"""Database connection and session management for Railway PostgreSQL + Redis."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from src.shared.config import get_settings

settings = get_settings()


# ===================
# SQLAlchemy Base
# ===================


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


# ===================
# PostgreSQL (Railway)
# ===================

_engine = None
_session_factory = None


def get_engine():
    """Get SQLAlchemy async engine."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.is_development,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
    return _engine


def get_session_factory():
    """Get SQLAlchemy session factory."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session context manager.

    Usage:
        async with get_db_session() as session:
            result = await session.execute(query)
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables.

    Call this on application startup to create all tables.
    In production, use Alembic migrations instead.
    """
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections.

    Call this on application shutdown.
    """
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


# ===================
# Redis (Railway)
# ===================

_redis_pool = None


async def get_redis() -> redis.Redis:
    """Get Redis connection from pool.

    Usage:
        redis_client = await get_redis()
        await redis_client.set("key", "value")
        value = await redis_client.get("key")
    """
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,
        )
    return redis.Redis(connection_pool=_redis_pool)


async def close_redis() -> None:
    """Close Redis connection pool.

    Call this on application shutdown.
    """
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.disconnect()
        _redis_pool = None


# ===================
# Lifecycle Helpers
# ===================


async def startup() -> None:
    """Initialize all connections on application startup."""
    # Verify database connection
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute("SELECT 1")

    # Verify Redis connection
    redis_client = await get_redis()
    await redis_client.ping()


async def shutdown() -> None:
    """Close all connections on application shutdown."""
    await close_db()
    await close_redis()
