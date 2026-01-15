"""Health check API routes."""

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from src.shared.database import get_db_session, get_redis

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(
        ...,
        description="Overall health status",
    )
    version: str = Field(
        default="1.0.0",
        description="API version",
    )


class ReadinessResponse(BaseModel):
    """Readiness check response."""

    status: str = Field(
        ...,
        description="Overall readiness status",
    )
    database: str = Field(
        ...,
        description="Database connection status",
    )
    redis: str = Field(
        ...,
        description="Redis connection status",
    )


class LivenessResponse(BaseModel):
    """Liveness check response."""

    status: str = Field(
        default="alive",
        description="Liveness status",
    )


@router.get(
    "",
    response_model=HealthResponse,
    summary="Basic health check",
    description="Simple health check endpoint.",
)
async def health_check() -> HealthResponse:
    """Basic health check.

    Returns:
        Health status
    """
    return HealthResponse(
        status="healthy",
        version="1.0.0",
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness check",
    description="Check if the service is ready to accept traffic.",
)
async def readiness_check() -> ReadinessResponse:
    """Readiness check with dependency verification.

    Checks database and Redis connections.

    Returns:
        Readiness status with component details
    """
    db_status = "healthy"
    redis_status = "healthy"

    # Check database
    try:
        async with get_db_session() as session:
            await session.execute("SELECT 1")
    except Exception:
        db_status = "unhealthy"

    # Check Redis
    try:
        redis_client = await get_redis()
        await redis_client.ping()
    except Exception:
        redis_status = "unhealthy"

    overall_status = "ready" if db_status == "healthy" and redis_status == "healthy" else "not_ready"

    return ReadinessResponse(
        status=overall_status,
        database=db_status,
        redis=redis_status,
    )


@router.get(
    "/live",
    response_model=LivenessResponse,
    summary="Liveness check",
    description="Check if the service is alive.",
)
async def liveness_check() -> LivenessResponse:
    """Liveness check.

    Always returns alive if the endpoint is reachable.

    Returns:
        Liveness status
    """
    return LivenessResponse(status="alive")
