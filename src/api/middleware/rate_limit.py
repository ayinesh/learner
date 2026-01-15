"""Rate limiting middleware for API endpoints."""

import logging
import random
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Dict

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

from src.shared.constants import (
    RATE_LIMIT_CLEANUP_PROBABILITY,
    RATE_LIMIT_CLEANUP_MAX_AGE_SECONDS,
)

logger = logging.getLogger(__name__)

# Memory cleanup settings from constants
CLEANUP_PROBABILITY = RATE_LIMIT_CLEANUP_PROBABILITY
CLEANUP_MAX_AGE_SECONDS = RATE_LIMIT_CLEANUP_MAX_AGE_SECONDS


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    requests: int  # Number of requests allowed
    window_seconds: int  # Time window in seconds
    scope: str = "global"  # Scope: global, per_ip, per_user


@dataclass
class RequestRecord:
    """Record of requests for rate limiting."""

    timestamps: list[float]
    blocked_until: float = 0.0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting API requests.

    Implements token bucket algorithm with configurable limits per endpoint.

    Features:
    - Per-IP rate limiting
    - Per-endpoint configuration
    - Configurable rate limits and time windows
    - Proper 429 responses with Retry-After header
    """

    # Default rate limits by endpoint pattern
    # Security: Tighter limits on sensitive authentication endpoints
    DEFAULT_LIMITS: Dict[str, RateLimitConfig] = {
        # Auth endpoints - SECURITY CRITICAL: Very restrictive to prevent brute force
        "/auth/register": RateLimitConfig(requests=3, window_seconds=3600),  # 3 per hour
        "/auth/login": RateLimitConfig(requests=5, window_seconds=300),  # 5 per 5 min (brute force protection)
        "/auth/refresh": RateLimitConfig(requests=10, window_seconds=3600),  # 10 per hour
        "/auth/request-reset": RateLimitConfig(requests=2, window_seconds=3600),  # 2 per hour (prevent enumeration)
        "/auth/reset-password": RateLimitConfig(requests=3, window_seconds=3600),  # 3 per hour
        "/auth/change-password": RateLimitConfig(requests=5, window_seconds=3600),  # 5 per hour
        "/auth/logout": RateLimitConfig(requests=10, window_seconds=300),  # 10 per 5 min
        # Content endpoints - moderate
        "/content": RateLimitConfig(requests=100, window_seconds=60),  # 100 per minute
        "/content/search": RateLimitConfig(requests=30, window_seconds=60),  # 30 per minute
        # Assessment endpoints - moderate
        "/assessments/quiz": RateLimitConfig(requests=20, window_seconds=300),  # 20 per 5 min
        "/assessments/submit": RateLimitConfig(requests=30, window_seconds=300),  # 30 per 5 min
        # Session endpoints - lenient
        "/sessions": RateLimitConfig(requests=50, window_seconds=60),  # 50 per minute
        # User endpoints - moderate
        "/users": RateLimitConfig(requests=30, window_seconds=60),  # 30 per minute
        # Health check - no limit
        "/health": RateLimitConfig(requests=1000, window_seconds=60),  # 1000 per minute
    }

    def __init__(self, app, custom_limits: Dict[str, RateLimitConfig] | None = None):
        """Initialize rate limiting middleware.

        Args:
            app: ASGI application
            custom_limits: Custom rate limit configurations to override defaults
        """
        super().__init__(app)
        self.limits = {**self.DEFAULT_LIMITS}
        if custom_limits:
            self.limits.update(custom_limits)

        # Store request records per IP
        self._ip_records: Dict[str, Dict[str, RequestRecord]] = defaultdict(
            lambda: defaultdict(lambda: RequestRecord(timestamps=[]))
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/endpoint

        Returns:
            HTTP response (possibly 429 if rate limited)
        """
        # Get client IP
        client_ip = self._get_client_ip(request)

        # Get endpoint path
        path = request.url.path

        # Find matching rate limit config
        limit_config = self._get_limit_config(path)

        if limit_config:
            # Check rate limit
            allowed, retry_after = self._check_rate_limit(
                client_ip, path, limit_config
            )

            if not allowed:
                logger.warning(
                    f"Rate limit exceeded for IP {client_ip} on endpoint {path}. "
                    f"Retry after {retry_after} seconds"
                )
                return JSONResponse(
                    status_code=HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "Too many requests",
                        "message": f"Rate limit exceeded. Please try again in {retry_after} seconds.",
                        "retry_after": retry_after,
                    },
                    headers={"Retry-After": str(int(retry_after))},
                )

        # Process request
        response = await call_next(request)
        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request.

        Handles proxy headers (X-Forwarded-For, X-Real-IP).

        Args:
            request: HTTP request

        Returns:
            Client IP address
        """
        # Check proxy headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For can contain multiple IPs, use the first one
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        # Fall back to direct client
        if request.client:
            return request.client.host

        return "unknown"

    def _get_limit_config(self, path: str) -> RateLimitConfig | None:
        """Get rate limit configuration for endpoint.

        Args:
            path: Request path

        Returns:
            Rate limit config or None if no limit
        """
        # Exact match
        if path in self.limits:
            return self.limits[path]

        # Prefix match (e.g., /content/123 matches /content)
        for endpoint_pattern, config in self.limits.items():
            if path.startswith(endpoint_pattern):
                return config

        return None

    def _check_rate_limit(
        self, client_ip: str, endpoint: str, config: RateLimitConfig
    ) -> tuple[bool, float]:
        """Check if request is within rate limit.

        Uses token bucket algorithm.

        Args:
            client_ip: Client IP address
            endpoint: Endpoint path
            config: Rate limit configuration

        Returns:
            Tuple of (allowed, retry_after_seconds)
        """
        current_time = time.time()
        record = self._ip_records[client_ip][endpoint]

        # Probabilistic cleanup to prevent unbounded memory growth
        if random.random() < CLEANUP_PROBABILITY:
            self._cleanup_old_records(current_time)

        # Check if currently blocked
        if record.blocked_until > current_time:
            retry_after = record.blocked_until - current_time
            return False, retry_after

        # Clean up old timestamps outside the window
        window_start = current_time - config.window_seconds
        record.timestamps = [ts for ts in record.timestamps if ts > window_start]

        # Check if limit exceeded
        if len(record.timestamps) >= config.requests:
            # Calculate when the oldest request will expire
            oldest_timestamp = min(record.timestamps)
            retry_after = (oldest_timestamp + config.window_seconds) - current_time

            # Set blocked until
            record.blocked_until = current_time + retry_after

            return False, max(1.0, retry_after)  # At least 1 second

        # Add current request
        record.timestamps.append(current_time)

        return True, 0.0

    def _cleanup_old_records(self, current_time: float) -> None:
        """Remove stale IP records to prevent unbounded memory growth.

        Removes IP records that haven't been accessed in CLEANUP_MAX_AGE_SECONDS.

        Args:
            current_time: Current timestamp
        """
        cutoff = current_time - CLEANUP_MAX_AGE_SECONDS
        ips_to_remove = []
        endpoints_removed = 0

        for ip in list(self._ip_records.keys()):
            endpoints_to_remove = []

            for endpoint in list(self._ip_records[ip].keys()):
                record = self._ip_records[ip][endpoint]
                # Check if all timestamps are old
                if not record.timestamps or max(record.timestamps) < cutoff:
                    endpoints_to_remove.append(endpoint)

            # Remove stale endpoints
            for endpoint in endpoints_to_remove:
                del self._ip_records[ip][endpoint]
                endpoints_removed += 1

            # If no endpoints left, mark IP for removal
            if not self._ip_records[ip]:
                ips_to_remove.append(ip)

        # Remove empty IPs
        for ip in ips_to_remove:
            del self._ip_records[ip]

        if ips_to_remove or endpoints_removed:
            logger.debug(
                f"Rate limiter cleanup: removed {len(ips_to_remove)} IPs, "
                f"{endpoints_removed} endpoint records"
            )

    def clear_records(self, client_ip: str | None = None):
        """Clear rate limit records.

        Args:
            client_ip: IP to clear, or None to clear all
        """
        if client_ip:
            if client_ip in self._ip_records:
                del self._ip_records[client_ip]
                logger.info(f"Cleared rate limit records for IP {client_ip}")
        else:
            self._ip_records.clear()
            logger.info("Cleared all rate limit records")

    def get_stats(self, client_ip: str) -> Dict[str, Dict[str, int]]:
        """Get rate limit statistics for an IP.

        Args:
            client_ip: Client IP address

        Returns:
            Dictionary of endpoint -> stats
        """
        if client_ip not in self._ip_records:
            return {}

        current_time = time.time()
        stats = {}

        for endpoint, record in self._ip_records[client_ip].items():
            config = self._get_limit_config(endpoint)
            if not config:
                continue

            # Clean up old timestamps
            window_start = current_time - config.window_seconds
            active_requests = [ts for ts in record.timestamps if ts > window_start]

            stats[endpoint] = {
                "requests_made": len(active_requests),
                "requests_allowed": config.requests,
                "window_seconds": config.window_seconds,
                "requests_remaining": max(0, config.requests - len(active_requests)),
                "reset_at": int(
                    min(active_requests) + config.window_seconds
                    if active_requests
                    else current_time
                ),
            }

        return stats
