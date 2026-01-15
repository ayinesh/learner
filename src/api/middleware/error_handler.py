"""Global exception handlers for the API."""

import logging
import traceback
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from src.shared.config import get_settings
from src.shared.exceptions import (
    LearnerException,
    AuthenticationError,
    ResourceNotFoundError,
    InvalidStateError,
    ValidationError as DomainValidationError,
    ExternalServiceError,
    ConfigurationError,
    FeatureDisabledError,
)

settings = get_settings()
logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base API exception with structured error response."""

    def __init__(
        self,
        message: str,
        error_code: str = "API_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(APIError):
    """Resource not found error."""

    def __init__(self, resource: str, identifier: str | None = None):
        message = f"{resource} not found"
        if identifier:
            message = f"{resource} with id '{identifier}' not found"
        super().__init__(
            message=message,
            error_code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"resource": resource, "identifier": identifier},
        )


class ConflictError(APIError):
    """Resource conflict error."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            error_code="CONFLICT",
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class UnauthorizedError(APIError):
    """Authentication required error."""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            message=message,
            error_code="UNAUTHORIZED",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ForbiddenError(APIError):
    """Access forbidden error."""

    def __init__(self, message: str = "Access denied"):
        super().__init__(
            message=message,
            error_code="FORBIDDEN",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class BadRequestError(APIError):
    """Bad request error."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            error_code="BAD_REQUEST",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class RateLimitError(APIError):
    """Rate limit exceeded error."""

    def __init__(self, retry_after: int = 60):
        super().__init__(
            message="Rate limit exceeded",
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details={"retry_after": retry_after},
        )


def create_error_response(
    request_id: str,
    error_code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create standardized error response.

    Args:
        request_id: Unique request identifier
        error_code: Error code string
        message: Human-readable error message
        details: Optional additional details

    Returns:
        Structured error response dict
    """
    return {
        "success": False,
        "error": {
            "code": error_code,
            "message": message,
            "details": details or {},
        },
        "request_id": request_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def setup_exception_handlers(app: FastAPI) -> None:
    """Setup global exception handlers for the application.

    Args:
        app: FastAPI application instance
    """

    @app.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
        """Handle custom API errors."""
        request_id = getattr(request.state, "request_id", str(uuid4()))

        logger.warning(
            f"API Error: {exc.error_code} - {exc.message}",
            extra={
                "request_id": request_id,
                "error_code": exc.error_code,
                "status_code": exc.status_code,
                "path": request.url.path,
            },
        )

        return JSONResponse(
            status_code=exc.status_code,
            content=create_error_response(
                request_id=request_id,
                error_code=exc.error_code,
                message=exc.message,
                details=exc.details,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Handle request validation errors."""
        request_id = getattr(request.state, "request_id", str(uuid4()))

        # Format validation errors
        errors = []
        for error in exc.errors():
            loc = " -> ".join(str(x) for x in error["loc"])
            errors.append({
                "field": loc,
                "message": error["msg"],
                "type": error["type"],
            })

        logger.warning(
            f"Validation Error: {len(errors)} errors",
            extra={
                "request_id": request_id,
                "path": request.url.path,
                "errors": errors,
            },
        )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=create_error_response(
                request_id=request_id,
                error_code="VALIDATION_ERROR",
                message="Request validation failed",
                details={"errors": errors},
            ),
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        """Handle ValueError as bad request."""
        request_id = getattr(request.state, "request_id", str(uuid4()))

        logger.warning(
            f"ValueError: {str(exc)}",
            extra={
                "request_id": request_id,
                "path": request.url.path,
            },
        )

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=create_error_response(
                request_id=request_id,
                error_code="BAD_REQUEST",
                message=str(exc),
            ),
        )

    @app.exception_handler(LearnerException)
    async def learner_exception_handler(
        request: Request, exc: LearnerException
    ) -> JSONResponse:
        """Handle domain exceptions with proper HTTP status mapping.

        Maps LearnerException subclasses to appropriate HTTP status codes:
        - AuthenticationError -> 401 Unauthorized
        - ResourceNotFoundError -> 404 Not Found
        - InvalidStateError -> 409 Conflict
        - ValidationError -> 400 Bad Request
        - ExternalServiceError -> 503 Service Unavailable
        - ConfigurationError -> 500 Internal Server Error
        - FeatureDisabledError -> 403 Forbidden
        """
        request_id = getattr(request.state, "request_id", str(uuid4()))

        # Map exception types to HTTP status codes
        if isinstance(exc, AuthenticationError):
            status_code = status.HTTP_401_UNAUTHORIZED
            error_code = "AUTHENTICATION_ERROR"
        elif isinstance(exc, ResourceNotFoundError):
            status_code = status.HTTP_404_NOT_FOUND
            error_code = "NOT_FOUND"
        elif isinstance(exc, InvalidStateError):
            status_code = status.HTTP_409_CONFLICT
            error_code = "CONFLICT"
        elif isinstance(exc, DomainValidationError):
            status_code = status.HTTP_400_BAD_REQUEST
            error_code = "VALIDATION_ERROR"
        elif isinstance(exc, FeatureDisabledError):
            status_code = status.HTTP_403_FORBIDDEN
            error_code = "FEATURE_DISABLED"
        elif isinstance(exc, ExternalServiceError):
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            error_code = "SERVICE_UNAVAILABLE"
        elif isinstance(exc, ConfigurationError):
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            error_code = "CONFIGURATION_ERROR"
        else:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            error_code = "DOMAIN_ERROR"

        logger.warning(
            f"Domain Exception: {exc.__class__.__name__} - {exc.message}",
            extra={
                "request_id": request_id,
                "error_type": exc.__class__.__name__,
                "status_code": status_code,
                "path": request.url.path,
            },
        )

        return JSONResponse(
            status_code=status_code,
            content=create_error_response(
                request_id=request_id,
                error_code=error_code,
                message=exc.message,
                details=exc.details,
            ),
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle unexpected errors."""
        request_id = getattr(request.state, "request_id", str(uuid4()))

        # Log full traceback in development
        if settings.is_development:
            logger.error(
                f"Unhandled Exception: {type(exc).__name__}: {str(exc)}",
                extra={
                    "request_id": request_id,
                    "path": request.url.path,
                    "traceback": traceback.format_exc(),
                },
            )
        else:
            logger.error(
                f"Unhandled Exception: {type(exc).__name__}",
                extra={
                    "request_id": request_id,
                    "path": request.url.path,
                },
            )

        # Don't expose internal errors in production
        message = str(exc) if settings.is_development else "Internal server error"

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=create_error_response(
                request_id=request_id,
                error_code="INTERNAL_ERROR",
                message=message,
            ),
        )
