"""Request body size limiting middleware.

Prevents denial-of-service attacks via large request bodies.
"""

import logging
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_413_REQUEST_ENTITY_TOO_LARGE

logger = logging.getLogger(__name__)

# Default maximum request body size (1 MB)
DEFAULT_MAX_BODY_SIZE = 1_000_000

# Larger limit for content ingestion endpoints (10 MB)
LARGE_BODY_ENDPOINTS = {
    "/content/ingest": 10_000_000,
}


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to limit request body size.

    Prevents DoS attacks via large request bodies by checking
    Content-Length header and rejecting requests that exceed limits.

    Attributes:
        max_body_size: Default maximum request body size in bytes
        endpoint_limits: Custom limits for specific endpoints
    """

    def __init__(
        self,
        app,
        max_body_size: int = DEFAULT_MAX_BODY_SIZE,
        endpoint_limits: dict[str, int] | None = None,
    ):
        """Initialize request size limit middleware.

        Args:
            app: ASGI application
            max_body_size: Default maximum body size in bytes
            endpoint_limits: Custom limits for specific endpoints
        """
        super().__init__(app)
        self.max_body_size = max_body_size
        self.endpoint_limits = {**LARGE_BODY_ENDPOINTS}
        if endpoint_limits:
            self.endpoint_limits.update(endpoint_limits)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with size limiting.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/endpoint

        Returns:
            HTTP response (possibly 413 if too large)
        """
        # Skip size check for GET, HEAD, OPTIONS requests
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)

        # Get Content-Length header
        content_length = request.headers.get("content-length")

        if content_length:
            try:
                body_size = int(content_length)
            except ValueError:
                # Invalid Content-Length header
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "Invalid Content-Length header",
                        "message": "Content-Length must be a valid integer",
                    },
                )

            # Determine limit for this endpoint
            path = request.url.path
            limit = self._get_limit_for_path(path)

            if body_size > limit:
                logger.warning(
                    f"Request body too large: {body_size} bytes "
                    f"(limit: {limit} bytes) for {request.method} {path}"
                )
                return JSONResponse(
                    status_code=HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={
                        "error": "Request too large",
                        "message": f"Request body exceeds maximum size of {limit} bytes",
                        "max_size": limit,
                        "received_size": body_size,
                    },
                )

        return await call_next(request)

    def _get_limit_for_path(self, path: str) -> int:
        """Get size limit for a specific path.

        Args:
            path: Request path

        Returns:
            Size limit in bytes
        """
        # Check for exact match
        if path in self.endpoint_limits:
            return self.endpoint_limits[path]

        # Check for prefix match
        for endpoint, limit in self.endpoint_limits.items():
            if path.startswith(endpoint):
                return limit

        return self.max_body_size
