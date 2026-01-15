"""FastAPI application setup and configuration."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.shared.config import get_settings
from src.shared.database import startup, shutdown
from src.api.middleware.error_handler import setup_exception_handlers
from src.api.middleware.logging import RequestLoggingMiddleware
from src.api.middleware.rate_limit import RateLimitMiddleware
from src.api.middleware.request_size import RequestSizeLimitMiddleware
from src.api.middleware.security_headers import SecurityHeadersMiddleware

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Handles startup and shutdown events for database connections
    and other resources.
    """
    # Startup
    await startup()
    yield
    # Shutdown
    await shutdown()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    application = FastAPI(
        title="AI Learning System API",
        description="""
        Personalized AI Learning System API for managing:
        - User authentication and profiles
        - Learning sessions with adaptive planning
        - Content ingestion and personalized recommendations
        - Assessments (quizzes and Feynman dialogues)
        - Spaced repetition and gap identification
        """,
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Configure CORS with restrictive settings
    # In production, set CORS_ORIGINS env variable with actual frontend domains
    cors_origins = settings.cors_origins_list

    # Security: Warn if no CORS origins configured in production
    if settings.is_production and not cors_origins:
        import logging
        logging.getLogger(__name__).warning(
            "No CORS_ORIGINS configured in production. "
            "API will not be accessible from browsers. "
            "Set CORS_ORIGINS env variable to allow frontend access."
        )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        # Security: Only allow specific HTTP methods
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        # Security: Only allow necessary headers
        allow_headers=[
            "Content-Type",
            "Authorization",
            "Accept",
            "Origin",
            "X-Requested-With",
            "X-Request-ID",
        ],
        # Security: Limit preflight cache
        max_age=600,  # 10 minutes
    )

    # Setup exception handlers
    setup_exception_handlers(application)

    # Add security headers middleware (outermost - runs last on response)
    # Disable HSTS in development mode
    is_development = settings.is_development
    application.add_middleware(
        SecurityHeadersMiddleware,
        enable_hsts=not is_development,
    )

    # Add request size limiting middleware (prevents DoS via large payloads)
    application.add_middleware(RequestSizeLimitMiddleware)

    # Add rate limiting middleware (before logging to avoid logging rate limited requests)
    application.add_middleware(RateLimitMiddleware)

    # Add request logging middleware
    application.add_middleware(RequestLoggingMiddleware)

    # Include routers
    from src.api.routers import (
        auth_router,
        users_router,
        sessions_router,
        content_router,
        assessments_router,
        health_router,
    )

    application.include_router(
        health_router,
        prefix="/health",
        tags=["Health"],
    )
    application.include_router(
        auth_router,
        prefix="/auth",
        tags=["Authentication"],
    )
    application.include_router(
        users_router,
        prefix="/users",
        tags=["Users"],
    )
    application.include_router(
        sessions_router,
        prefix="/sessions",
        tags=["Sessions"],
    )
    application.include_router(
        content_router,
        prefix="/content",
        tags=["Content"],
    )
    application.include_router(
        assessments_router,
        prefix="/assessments",
        tags=["Assessments"],
    )

    return application


# Create app instance
app = create_app()
