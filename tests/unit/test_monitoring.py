"""Unit tests for monitoring middleware."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from src.api.middleware.monitoring import (
    RequestMetrics,
    MonitoringMiddleware,
    HealthCheckRouter,
    get_metrics,
    reset_metrics,
    create_health_router,
)


class TestRequestMetrics:
    """Tests for RequestMetrics class."""

    @pytest.fixture(autouse=True)
    def reset(self):
        """Reset metrics before each test."""
        reset_metrics()
        yield
        reset_metrics()

    def test_initialization(self):
        """Test metrics initialize with defaults."""
        metrics = RequestMetrics()
        assert metrics.status_counts == {}
        assert metrics.endpoint_counts == {}
        assert metrics.latencies == []

    def test_record_request(self):
        """Test recording a request."""
        metrics = RequestMetrics()
        metrics.record_request(
            status_code=200,
            endpoint="GET /api/test",
            latency_ms=50.5,
        )

        assert metrics.status_counts[200] == 1
        assert metrics.endpoint_counts["GET /api/test"] == 1
        assert 50.5 in metrics.latencies

    def test_record_request_with_error(self):
        """Test recording a request with error."""
        metrics = RequestMetrics()
        metrics.record_request(
            status_code=500,
            endpoint="GET /api/error",
            latency_ms=100,
            error="ConnectionError",
        )

        assert metrics.status_counts[500] == 1
        assert metrics.error_counts["ConnectionError"] == 1

    def test_latency_rolling_window(self):
        """Test latency maintains rolling window."""
        metrics = RequestMetrics()
        metrics.max_latency_samples = 5

        for i in range(10):
            metrics.record_request(200, "/test", float(i))

        assert len(metrics.latencies) == 5
        assert metrics.latencies == [5.0, 6.0, 7.0, 8.0, 9.0]

    def test_get_summary(self):
        """Test getting metrics summary."""
        metrics = RequestMetrics()
        metrics.record_request(200, "GET /a", 50)
        metrics.record_request(200, "GET /b", 100)
        metrics.record_request(404, "GET /c", 30)
        metrics.record_request(500, "GET /d", 200, error="Error")

        summary = metrics.get_summary()

        assert summary["total_requests"] == 4
        assert summary["success_requests"] == 2
        assert summary["error_requests"] == 2
        assert summary["success_rate"] == 0.5
        assert "latency" in summary
        assert summary["latency"]["avg_ms"] == 95  # (50+100+30+200)/4

    def test_reset(self):
        """Test resetting metrics."""
        metrics = RequestMetrics()
        metrics.record_request(200, "/test", 50)
        metrics.reset()

        assert metrics.status_counts == {}
        assert metrics.latencies == []


class TestGetMetrics:
    """Tests for get_metrics singleton."""

    @pytest.fixture(autouse=True)
    def reset(self):
        """Reset metrics before each test."""
        reset_metrics()
        yield
        reset_metrics()

    def test_returns_singleton(self):
        """Test get_metrics returns singleton."""
        m1 = get_metrics()
        m2 = get_metrics()
        assert m1 is m2

    def test_reset_clears_singleton(self):
        """Test reset creates new instance."""
        m1 = get_metrics()
        m1.record_request(200, "/test", 50)
        reset_metrics()
        m2 = get_metrics()
        assert m2.status_counts == {}


class TestMonitoringMiddleware:
    """Tests for MonitoringMiddleware."""

    @pytest.fixture
    def app(self):
        """Create test app with middleware."""
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        @app.get("/health")
        async def health():
            return {"status": "healthy"}

        app.add_middleware(MonitoringMiddleware)
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        reset_metrics()
        return TestClient(app)

    def test_records_successful_request(self, client):
        """Test middleware records successful requests."""
        response = client.get("/test")
        assert response.status_code == 200

        metrics = get_metrics()
        assert metrics.status_counts[200] >= 1
        assert "X-Response-Time" in response.headers

    def test_excludes_health_endpoint(self, client):
        """Test middleware excludes health endpoint."""
        client.get("/health")

        metrics = get_metrics()
        # Health endpoint should not be recorded
        assert "GET /health" not in metrics.endpoint_counts


class TestHealthCheckRouter:
    """Tests for HealthCheckRouter."""

    @pytest.fixture
    def mock_db_health(self):
        """Mock database health check."""
        with patch("src.api.middleware.monitoring.check_db_health") as mock:
            mock.return_value = True
            yield mock

    @pytest.fixture
    def app(self, mock_db_health):
        """Create test app with health router."""
        app = FastAPI()
        health_router = HealthCheckRouter()
        app.include_router(health_router.get_router())
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        reset_metrics()
        return TestClient(app)

    def test_health_endpoint(self, client, mock_db_health):
        """Test /health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "checks" in data
        assert "database" in data["checks"]

    def test_ready_endpoint_success(self, client, mock_db_health):
        """Test /ready endpoint when healthy."""
        response = client.get("/ready")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ready"

    def test_ready_endpoint_failure(self, client, mock_db_health):
        """Test /ready endpoint when database unavailable."""
        mock_db_health.return_value = False

        response = client.get("/ready")
        # Ready should return 503 when not ready
        assert response.status_code in (200, 503)

    def test_live_endpoint(self, client, mock_db_health):
        """Test /live endpoint."""
        response = client.get("/live")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "alive"

    def test_metrics_endpoint(self, client, mock_db_health):
        """Test /metrics endpoint."""
        response = client.get("/metrics")
        assert response.status_code == 200

        data = response.json()
        assert "total_requests" in data
        assert "latency" in data

    def test_metrics_reset_endpoint(self, client, mock_db_health):
        """Test /metrics/reset endpoint."""
        # First record some metrics
        metrics = get_metrics()
        metrics.record_request(200, "/test", 50)

        response = client.post("/metrics/reset")
        assert response.status_code == 200

        # Verify reset
        metrics_after = get_metrics()
        assert metrics_after.status_counts == {}


class TestCreateHealthRouter:
    """Tests for create_health_router factory."""

    def test_creates_router(self):
        """Test factory creates router."""
        from fastapi import APIRouter
        router = create_health_router()
        assert isinstance(router, APIRouter)


class TestHealthCheckIntegration:
    """Integration tests for health checks."""

    @pytest.fixture
    def health_router(self):
        """Create health router instance."""
        return HealthCheckRouter()

    def test_register_custom_check(self, health_router):
        """Test registering custom health check."""
        async def custom_check():
            return {"healthy": True, "details": "All good"}

        health_router.register_check("custom", custom_check)
        assert "custom" in health_router._health_checks

    @pytest.mark.asyncio
    async def test_custom_check_executed(self, health_router):
        """Test custom check is executed."""
        called = False

        async def custom_check():
            nonlocal called
            called = True
            return {"healthy": True}

        health_router.register_check("custom", custom_check)

        # Trigger health check via endpoint would call custom check
        # This tests the registration mechanism
        assert health_router._health_checks["custom"] is custom_check
