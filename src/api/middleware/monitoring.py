"""Request monitoring and health check middleware.

This module provides:
- Request metrics collection (latency, status codes, throughput)
- Health check endpoints for load balancers and orchestrators
- Readiness and liveness probes
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Callable, Optional

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from src.shared.config import get_settings
from src.shared.database import get_db_session, check_db_health

logger = logging.getLogger(__name__)


@dataclass
class RequestMetrics:
    """Container for request metrics."""

    # Request counts by status code
    status_counts: dict[int, int] = field(default_factory=lambda: defaultdict(int))

    # Request counts by endpoint
    endpoint_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    # Latency tracking (in milliseconds)
    latencies: list[float] = field(default_factory=list)
    max_latency_samples: int = 1000

    # Error tracking
    error_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    # Timing
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_request_time: Optional[datetime] = None

    def record_request(
        self,
        status_code: int,
        endpoint: str,
        latency_ms: float,
        error: Optional[str] = None,
    ) -> None:
        """Record metrics for a completed request."""
        self.status_counts[status_code] += 1
        self.endpoint_counts[endpoint] += 1
        self.last_request_time = datetime.now(timezone.utc)

        # Maintain a rolling window of latencies
        if len(self.latencies) >= self.max_latency_samples:
            self.latencies.pop(0)
        self.latencies.append(latency_ms)

        if error:
            self.error_counts[error] += 1

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of collected metrics."""
        total_requests = sum(self.status_counts.values())
        success_requests = sum(
            count for code, count in self.status_counts.items()
            if 200 <= code < 300
        )
        error_requests = sum(
            count for code, count in self.status_counts.items()
            if code >= 400
        )

        # Calculate latency percentiles
        latencies = sorted(self.latencies) if self.latencies else [0]
        p50_idx = int(len(latencies) * 0.5)
        p95_idx = int(len(latencies) * 0.95)
        p99_idx = int(len(latencies) * 0.99)

        uptime = (datetime.now(timezone.utc) - self.start_time).total_seconds()

        return {
            'total_requests': total_requests,
            'success_requests': success_requests,
            'error_requests': error_requests,
            'success_rate': success_requests / total_requests if total_requests > 0 else 1.0,
            'requests_per_minute': total_requests / (uptime / 60) if uptime > 0 else 0,
            'latency': {
                'p50_ms': latencies[p50_idx] if latencies else 0,
                'p95_ms': latencies[p95_idx] if latencies else 0,
                'p99_ms': latencies[p99_idx] if latencies else 0,
                'avg_ms': sum(latencies) / len(latencies) if latencies else 0,
            },
            'status_codes': dict(self.status_counts),
            'top_endpoints': dict(
                sorted(self.endpoint_counts.items(), key=lambda x: -x[1])[:10]
            ),
            'top_errors': dict(
                sorted(self.error_counts.items(), key=lambda x: -x[1])[:5]
            ),
            'uptime_seconds': uptime,
            'started_at': self.start_time.isoformat(),
            'last_request_at': self.last_request_time.isoformat() if self.last_request_time else None,
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self.status_counts.clear()
        self.endpoint_counts.clear()
        self.latencies.clear()
        self.error_counts.clear()
        self.start_time = datetime.now(timezone.utc)
        self.last_request_time = None


# Singleton metrics instance
_metrics_instance: Optional[RequestMetrics] = None


@lru_cache(maxsize=1)
def get_metrics() -> RequestMetrics:
    """Get the singleton metrics instance."""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = RequestMetrics()
    return _metrics_instance


def reset_metrics() -> None:
    """Reset the metrics instance (for testing)."""
    global _metrics_instance
    _metrics_instance = None
    get_metrics.cache_clear()


class MonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware for collecting request metrics.

    Records timing, status codes, and errors for all requests.
    Metrics are available via the /metrics endpoint.
    """

    def __init__(
        self,
        app,
        exclude_paths: Optional[list[str]] = None,
    ):
        """Initialize the middleware.

        Args:
            app: The FastAPI application.
            exclude_paths: Paths to exclude from metrics (e.g., /health).
        """
        super().__init__(app)
        self.exclude_paths = set(exclude_paths or ['/health', '/ready', '/live'])
        self.metrics = get_metrics()

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Process request and record metrics."""
        path = request.url.path

        # Skip excluded paths
        if path in self.exclude_paths:
            return await call_next(request)

        start_time = time.perf_counter()
        error_type = None

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            error_type = type(e).__name__
            status_code = 500
            logger.exception(f"Request failed: {e}")
            response = JSONResponse(
                status_code=500,
                content={'detail': 'Internal server error'},
            )

        # Calculate latency
        latency_ms = (time.perf_counter() - start_time) * 1000

        # Record metrics
        endpoint = f"{request.method} {path}"
        self.metrics.record_request(
            status_code=status_code,
            endpoint=endpoint,
            latency_ms=latency_ms,
            error=error_type,
        )

        # Add timing header
        response.headers['X-Response-Time'] = f"{latency_ms:.2f}ms"

        return response


class HealthCheckRouter:
    """Router providing health check endpoints.

    Provides three types of health checks:
    - /health: Full system health with dependency checks
    - /ready: Readiness probe (is the app ready to serve traffic?)
    - /live: Liveness probe (is the app process alive?)
    """

    def __init__(self):
        """Initialize the health check router."""
        self.router = APIRouter(tags=["Health"])
        self._setup_routes()
        self._health_checks: dict[str, Callable] = {}

    def _setup_routes(self):
        """Set up health check routes."""

        @self.router.get("/health")
        async def health_check() -> dict[str, Any]:
            """Full system health check.

            Checks all registered dependencies and returns detailed status.
            """
            checks = {}
            overall_healthy = True

            # Run registered health checks
            for name, check_func in self._health_checks.items():
                try:
                    result = await check_func()
                    checks[name] = {
                        'healthy': result.get('healthy', True),
                        'latency_ms': result.get('latency_ms'),
                        'details': result.get('details'),
                    }
                    if not result.get('healthy', True):
                        overall_healthy = False
                except Exception as e:
                    checks[name] = {
                        'healthy': False,
                        'error': str(e),
                    }
                    overall_healthy = False

            # Always check database
            db_check = await self._check_database()
            checks['database'] = db_check
            if not db_check.get('healthy', False):
                overall_healthy = False

            return {
                'status': 'healthy' if overall_healthy else 'unhealthy',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'checks': checks,
            }

        @self.router.get("/ready")
        async def readiness_check() -> dict[str, Any]:
            """Readiness probe for Kubernetes/load balancers.

            Returns 200 if the application is ready to serve traffic.
            """
            # Check critical dependencies
            db_healthy = (await self._check_database()).get('healthy', False)

            if db_healthy:
                return {
                    'status': 'ready',
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                }
            else:
                return JSONResponse(
                    status_code=503,
                    content={
                        'status': 'not_ready',
                        'reason': 'Database unavailable',
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                    },
                )

        @self.router.get("/live")
        async def liveness_check() -> dict[str, Any]:
            """Liveness probe for Kubernetes/orchestrators.

            Returns 200 if the application process is alive.
            This should be a lightweight check that doesn't depend
            on external services.
            """
            return {
                'status': 'alive',
                'timestamp': datetime.now(timezone.utc).isoformat(),
            }

        @self.router.get("/metrics")
        async def get_request_metrics() -> dict[str, Any]:
            """Get request metrics summary."""
            metrics = get_metrics()
            return metrics.get_summary()

        @self.router.post("/metrics/reset")
        async def reset_request_metrics() -> dict[str, str]:
            """Reset request metrics (admin operation)."""
            metrics = get_metrics()
            metrics.reset()
            return {'status': 'metrics reset'}

    async def _check_database(self) -> dict[str, Any]:
        """Check database connectivity."""
        start_time = time.perf_counter()

        try:
            healthy = await check_db_health(max_retries=1, retry_delay=0)
            latency_ms = (time.perf_counter() - start_time) * 1000

            return {
                'healthy': healthy,
                'latency_ms': round(latency_ms, 2),
            }
        except Exception as e:
            return {
                'healthy': False,
                'error': str(e),
            }

    def register_check(
        self,
        name: str,
        check_func: Callable,
    ) -> None:
        """Register a custom health check.

        Args:
            name: Name for the health check.
            check_func: Async function that returns a dict with 'healthy' key.
        """
        self._health_checks[name] = check_func

    def get_router(self) -> APIRouter:
        """Get the FastAPI router with health endpoints."""
        return self.router


# Factory function for easy integration
def create_health_router() -> APIRouter:
    """Create and return a health check router."""
    health_router = HealthCheckRouter()
    return health_router.get_router()


async def check_redis_health() -> dict[str, Any]:
    """Example health check for Redis (if used).

    This can be registered as a custom health check:
        health_router.register_check('redis', check_redis_health)
    """
    # Placeholder - implement based on actual Redis client
    return {
        'healthy': True,
        'details': 'Redis check not implemented',
    }


async def check_llm_health() -> dict[str, Any]:
    """Health check for LLM service availability."""
    from src.shared.feature_flags import FeatureFlags, get_feature_flags

    flags = get_feature_flags()

    # If LLM features aren't enabled, consider it healthy (not needed)
    if not flags.is_enabled(FeatureFlags.ENABLE_NLP_COMMANDS):
        return {
            'healthy': True,
            'details': 'LLM features disabled',
        }

    try:
        from src.modules.llm import get_llm_service

        llm = get_llm_service()
        # Simple availability check
        is_available = await llm.is_available()

        return {
            'healthy': is_available,
            'details': 'LLM service operational' if is_available else 'LLM unavailable',
        }
    except Exception as e:
        return {
            'healthy': False,
            'error': str(e),
        }
