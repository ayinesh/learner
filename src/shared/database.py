"""Database connection and session management for Railway PostgreSQL + Redis."""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from src.shared.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


# ===================
# SQLAlchemy Base
# ===================


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


# ===================
# PostgreSQL (Railway)
# ===================

# Store engine per event loop ID to avoid cross-loop connection issues
_engines: dict[int, object] = {}
_session_factories: dict[int, object] = {}


def _get_loop_id() -> int:
    """Get current event loop ID for tracking connections."""
    try:
        loop = asyncio.get_running_loop()
        return id(loop)
    except RuntimeError:
        # No running loop - use 0 as fallback
        return 0


def get_engine():
    """Get SQLAlchemy async engine for current event loop."""
    global _engines
    loop_id = _get_loop_id()

    if loop_id not in _engines or _engines[loop_id] is None:
        _engines[loop_id] = create_async_engine(
            settings.database_url,
            echo=False,  # Disable SQL logging (was too verbose for CLI)
            pool_pre_ping=True,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_recycle=settings.db_pool_recycle,
        )
    return _engines[loop_id]


def get_session_factory():
    """Get SQLAlchemy session factory for current event loop."""
    global _session_factories
    loop_id = _get_loop_id()

    if loop_id not in _session_factories or _session_factories[loop_id] is None:
        engine = get_engine()
        _session_factories[loop_id] = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factories[loop_id]


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
            try:
                await session.commit()
            except Exception:
                # Rollback if commit itself fails to prevent connection leak
                await session.rollback()
                raise
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
    global _engines, _session_factories
    for loop_id, engine in list(_engines.items()):
        if engine is not None:
            try:
                await engine.dispose()
            except Exception:
                pass  # Ignore errors during cleanup
    _engines.clear()
    _session_factories.clear()


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
        try:
            # Properly close all connections in the pool
            await _redis_pool.aclose()
        except AttributeError:
            # Fallback for older redis versions without aclose()
            try:
                await _redis_pool.disconnect()
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"Error closing Redis pool: {e}")
        finally:
            _redis_pool = None


# ===================
# Lifecycle Helpers
# ===================


async def check_db_health(max_retries: int = 3, retry_delay: float = 1.0) -> bool:
    """Check database health with retries.

    Args:
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds

    Returns:
        True if database is healthy, False otherwise
    """
    for attempt in range(max_retries):
        try:
            engine = get_engine()
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            logger.debug("Database health check passed")
            return True
        except Exception as e:
            logger.warning(f"Database health check failed (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
    return False


async def check_redis_health(max_retries: int = 3, retry_delay: float = 1.0) -> bool:
    """Check Redis health with retries.

    Args:
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds

    Returns:
        True if Redis is healthy, False otherwise
    """
    for attempt in range(max_retries):
        try:
            redis_client = await get_redis()
            await redis_client.ping()
            logger.debug("Redis health check passed")
            return True
        except Exception as e:
            logger.warning(f"Redis health check failed (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
    return False


async def get_health_status() -> dict:
    """Get health status of all database connections.

    Returns:
        Dictionary with health status for each connection
    """
    db_healthy = await check_db_health(max_retries=1, retry_delay=0)
    redis_healthy = await check_redis_health(max_retries=1, retry_delay=0)

    return {
        "database": {
            "healthy": db_healthy,
            "type": "postgresql",
        },
        "redis": {
            "healthy": redis_healthy,
            "type": "redis",
        },
        "overall": db_healthy and redis_healthy,
    }


async def startup() -> None:
    """Initialize all connections on application startup."""
    # Verify database connection with retries
    if not await check_db_health(max_retries=5, retry_delay=2.0):
        raise RuntimeError("Failed to connect to database after retries")

    # Verify Redis connection with retries
    if not await check_redis_health(max_retries=5, retry_delay=2.0):
        raise RuntimeError("Failed to connect to Redis after retries")

    logger.info("All database connections initialized successfully")


async def shutdown() -> None:
    """Close all connections on application shutdown."""
    await close_db()
    await close_redis()
    logger.info("All database connections closed")
