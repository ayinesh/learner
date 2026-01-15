"""Security headers middleware for API responses.

Adds standard security headers to protect against common web vulnerabilities.
"""

from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.shared.constants import HSTS_MAX_AGE_SECONDS


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware that adds security headers to all responses.

    Headers added:
    - X-Content-Type-Options: Prevents MIME-type sniffing
    - X-Frame-Options: Prevents clickjacking attacks
    - X-XSS-Protection: Enables XSS filter in older browsers
    - Strict-Transport-Security: Enforces HTTPS (only in production)
    - Content-Security-Policy: Restricts resource loading
    - Referrer-Policy: Controls referrer information
    - Permissions-Policy: Restricts browser features
    - Cache-Control: Prevents caching of sensitive responses
    """

    def __init__(
        self,
        app,
        enable_hsts: bool = True,
        hsts_max_age: int = HSTS_MAX_AGE_SECONDS,
    ):
        """Initialize security headers middleware.

        Args:
            app: ASGI application
            enable_hsts: Whether to add HSTS header (disable for development)
            hsts_max_age: Max age for HSTS in seconds
        """
        super().__init__(app)
        self.enable_hsts = enable_hsts
        self.hsts_max_age = hsts_max_age

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/endpoint

        Returns:
            Response with security headers
        """
        response = await call_next(request)

        # Prevent MIME-type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking - deny framing from any origin
        response.headers["X-Frame-Options"] = "DENY"

        # Enable XSS filter in older browsers
        # Note: Deprecated in modern browsers but still useful for legacy support
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Strict Transport Security - enforce HTTPS
        if self.enable_hsts:
            response.headers["Strict-Transport-Security"] = (
                f"max-age={self.hsts_max_age}; includeSubDomains"
            )

        # Content Security Policy - restrict resource loading
        # This is a restrictive policy suitable for an API
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; "
            "frame-ancestors 'none'; "
            "form-action 'none'"
        )

        # Control referrer information sent with requests
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Restrict browser feature access
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), "
            "camera=(), "
            "geolocation=(), "
            "gyroscope=(), "
            "magnetometer=(), "
            "microphone=(), "
            "payment=(), "
            "usb=()"
        )

        # Prevent caching of API responses by default
        # Individual endpoints can override if needed
        if "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"

        return response
