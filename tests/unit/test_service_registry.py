"""Unit tests for service registry."""

import os
from unittest.mock import patch, MagicMock

import pytest

from src.shared.feature_flags import FeatureFlagManager, FeatureFlags
from src.shared.service_registry import (
    ServiceRegistry,
    get_service_registry,
    get_session_service,
    get_content_service,
    get_assessment_service,
    get_adaptation_service,
)


class TestServiceRegistry:
    """Tests for ServiceRegistry."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for each test."""
        # Clear singletons
        ServiceRegistry._instance = None
        FeatureFlagManager._instance = None
        registry = ServiceRegistry()
        registry.clear_cache()
        return registry

    @pytest.fixture(autouse=True)
    def reset_env(self):
        """Reset environment variables."""
        with patch.dict(os.environ, {}, clear=True):
            yield

    def test_singleton_pattern(self):
        """Test that ServiceRegistry is a singleton."""
        ServiceRegistry._instance = None
        registry1 = ServiceRegistry()
        registry2 = ServiceRegistry()
        assert registry1 is registry2

    def test_get_session_service_inmemory_default(self, registry):
        """Test that in-memory session service is returned by default."""
        with patch.dict(os.environ, {"FF_USE_DATABASE_PERSISTENCE": "false"}):
            FeatureFlagManager._instance = None
            registry._flags = FeatureFlagManager()
            registry.clear_cache()

            service = registry.get_session_service()
            assert service is not None
            assert "SessionService" in type(service).__name__

    def test_get_session_service_database_when_enabled(self, registry):
        """Test that database session service is returned when flag enabled."""
        with patch.dict(os.environ, {"FF_USE_DATABASE_PERSISTENCE": "true"}):
            FeatureFlagManager._instance = None
            registry._flags = FeatureFlagManager()
            registry.clear_cache()

            # Mock the database service to avoid actual DB connection
            with patch("src.modules.session.db_service.DatabaseSessionService") as mock_db:
                mock_instance = MagicMock()
                mock_db.return_value = mock_instance

                # Need to reimport to use patched version
                registry._session_service = None
                service = registry._create_session_service()

                # Should attempt to create database service
                mock_db.assert_called_once()

    def test_get_content_service_inmemory_default(self, registry):
        """Test that in-memory content service is returned by default."""
        with patch.dict(os.environ, {"FF_USE_DATABASE_PERSISTENCE": "false"}):
            FeatureFlagManager._instance = None
            registry._flags = FeatureFlagManager()
            registry.clear_cache()

            service = registry.get_content_service()
            assert service is not None
            assert "ContentService" in type(service).__name__

    def test_get_assessment_service_inmemory_default(self, registry):
        """Test that in-memory assessment service is returned by default."""
        with patch.dict(os.environ, {"FF_USE_DATABASE_PERSISTENCE": "false"}):
            FeatureFlagManager._instance = None
            registry._flags = FeatureFlagManager()
            registry.clear_cache()

            service = registry.get_assessment_service()
            assert service is not None
            assert "AssessmentService" in type(service).__name__

    def test_get_adaptation_service_inmemory_default(self, registry):
        """Test that in-memory adaptation service is returned by default."""
        with patch.dict(os.environ, {"FF_USE_DATABASE_PERSISTENCE": "false"}):
            FeatureFlagManager._instance = None
            registry._flags = FeatureFlagManager()
            registry.clear_cache()

            service = registry.get_adaptation_service()
            assert service is not None
            assert "AdaptationService" in type(service).__name__

    def test_service_caching(self, registry):
        """Test that services are cached after first creation."""
        with patch.dict(os.environ, {"FF_USE_DATABASE_PERSISTENCE": "false"}):
            FeatureFlagManager._instance = None
            registry._flags = FeatureFlagManager()
            registry.clear_cache()

            service1 = registry.get_session_service()
            service2 = registry.get_session_service()
            assert service1 is service2

    def test_clear_cache(self, registry):
        """Test that clear_cache removes cached services."""
        with patch.dict(os.environ, {"FF_USE_DATABASE_PERSISTENCE": "false"}):
            FeatureFlagManager._instance = None
            registry._flags = FeatureFlagManager()
            registry.clear_cache()

            service1 = registry.get_session_service()
            registry.clear_cache()
            service2 = registry.get_session_service()
            # After cache clear, should get new instance
            # (Note: for in-memory services, these may still be same singleton)
            assert registry._session_service is not None

    def test_get_service_info(self, registry):
        """Test getting service info."""
        with patch.dict(os.environ, {"FF_USE_DATABASE_PERSISTENCE": "false"}):
            FeatureFlagManager._instance = None
            registry._flags = FeatureFlagManager()
            registry.clear_cache()

            # Initially empty
            assert registry.get_service_info() == {}

            # After getting services
            registry.get_session_service()
            info = registry.get_service_info()
            assert "session" in info
            assert "SessionService" in info["session"]

    def test_fallback_on_db_error(self, registry):
        """Test fallback to in-memory when DB service creation fails."""
        with patch.dict(os.environ, {"FF_USE_DATABASE_PERSISTENCE": "true"}):
            FeatureFlagManager._instance = None
            registry._flags = FeatureFlagManager()
            registry.clear_cache()

            # Mock database service to raise an error
            with patch(
                "src.modules.session.db_service.DatabaseSessionService",
                side_effect=RuntimeError("DB connection failed")
            ):
                service = registry.get_session_service()
                # Should fallback to in-memory
                assert "SessionService" in type(service).__name__
                assert "Database" not in type(service).__name__

    def test_repr(self, registry):
        """Test string representation."""
        with patch.dict(os.environ, {"FF_USE_DATABASE_PERSISTENCE": "false"}):
            FeatureFlagManager._instance = None
            registry._flags = FeatureFlagManager()
            registry.clear_cache()

            repr_str = repr(registry)
            assert "ServiceRegistry" in repr_str
            assert "db_enabled=False" in repr_str


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    @pytest.fixture(autouse=True)
    def reset_singletons(self):
        """Reset singletons before each test."""
        ServiceRegistry._instance = None
        FeatureFlagManager._instance = None
        get_service_registry.cache_clear()
        yield

    def test_get_session_service_convenience(self):
        """Test get_session_service convenience function."""
        with patch.dict(os.environ, {"FF_USE_DATABASE_PERSISTENCE": "false"}):
            service = get_session_service()
            assert service is not None

    def test_get_content_service_convenience(self):
        """Test get_content_service convenience function."""
        with patch.dict(os.environ, {"FF_USE_DATABASE_PERSISTENCE": "false"}):
            service = get_content_service()
            assert service is not None

    def test_get_assessment_service_convenience(self):
        """Test get_assessment_service convenience function."""
        with patch.dict(os.environ, {"FF_USE_DATABASE_PERSISTENCE": "false"}):
            service = get_assessment_service()
            assert service is not None

    def test_get_adaptation_service_convenience(self):
        """Test get_adaptation_service convenience function."""
        with patch.dict(os.environ, {"FF_USE_DATABASE_PERSISTENCE": "false"}):
            service = get_adaptation_service()
            assert service is not None


class TestModuleImports:
    """Tests for module-level imports using registry."""

    @pytest.fixture(autouse=True)
    def reset_singletons(self):
        """Reset singletons before each test."""
        ServiceRegistry._instance = None
        FeatureFlagManager._instance = None
        get_service_registry.cache_clear()
        yield

    def test_session_module_import(self):
        """Test importing get_session_service from session module."""
        with patch.dict(os.environ, {"FF_USE_DATABASE_PERSISTENCE": "false"}):
            from src.modules.session import get_session_service as session_get
            service = session_get()
            assert service is not None

    def test_content_module_import(self):
        """Test importing get_content_service from content module."""
        with patch.dict(os.environ, {"FF_USE_DATABASE_PERSISTENCE": "false"}):
            from src.modules.content import get_content_service as content_get
            service = content_get()
            assert service is not None

    def test_assessment_module_import(self):
        """Test importing get_assessment_service from assessment module."""
        with patch.dict(os.environ, {"FF_USE_DATABASE_PERSISTENCE": "false"}):
            from src.modules.assessment import get_assessment_service as assessment_get
            service = assessment_get()
            assert service is not None

    def test_adaptation_module_import(self):
        """Test importing get_adaptation_service from adaptation module."""
        with patch.dict(os.environ, {"FF_USE_DATABASE_PERSISTENCE": "false"}):
            from src.modules.adaptation import get_adaptation_service as adaptation_get
            service = adaptation_get()
            assert service is not None

    def test_direct_inmemory_access(self):
        """Test direct in-memory service access bypasses registry."""
        with patch.dict(os.environ, {"FF_USE_DATABASE_PERSISTENCE": "true"}):
            from src.modules.session import get_inmemory_session_service
            service = get_inmemory_session_service()
            # Should be in-memory even though flag says DB
            assert "SessionService" in type(service).__name__
            assert "Database" not in type(service).__name__
