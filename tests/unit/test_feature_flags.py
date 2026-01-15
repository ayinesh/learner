"""Unit tests for feature flag management."""

import os
from unittest.mock import patch

import pytest

from src.shared.feature_flags import (
    FeatureFlagManager,
    FeatureFlags,
    get_feature_flags,
    is_database_persistence_enabled,
    is_nlp_commands_enabled,
    is_real_embeddings_enabled,
    is_background_jobs_enabled,
)


class TestFeatureFlags:
    """Tests for FeatureFlags enum."""

    def test_env_key_format(self):
        """Test that env_key returns correct format."""
        assert FeatureFlags.USE_DATABASE_PERSISTENCE.env_key == "FF_USE_DATABASE_PERSISTENCE"
        assert FeatureFlags.ENABLE_NLP_COMMANDS.env_key == "FF_ENABLE_NLP_COMMANDS"
        assert FeatureFlags.ENABLE_REAL_EMBEDDINGS.env_key == "FF_ENABLE_REAL_EMBEDDINGS"
        assert FeatureFlags.ENABLE_BACKGROUND_JOBS.env_key == "FF_ENABLE_BACKGROUND_JOBS"

    def test_all_flags_have_unique_values(self):
        """Test that all flags have unique values."""
        values = [f.value for f in FeatureFlags]
        assert len(values) == len(set(values))


class TestFeatureFlagManager:
    """Tests for FeatureFlagManager."""

    @pytest.fixture
    def manager(self):
        """Create a fresh manager for each test."""
        # Clear the singleton
        FeatureFlagManager._instance = None
        manager = FeatureFlagManager()
        manager.clear_all_overrides()
        return manager

    def test_default_is_disabled(self, manager):
        """Test that flags are disabled by default."""
        with patch.dict(os.environ, {}, clear=True):
            assert manager.is_enabled(FeatureFlags.USE_DATABASE_PERSISTENCE) is False
            assert manager.is_enabled(FeatureFlags.ENABLE_NLP_COMMANDS) is False

    def test_enable_via_env_true(self, manager):
        """Test enabling via environment variable with 'true'."""
        with patch.dict(os.environ, {"FF_USE_DATABASE_PERSISTENCE": "true"}):
            assert manager.is_enabled(FeatureFlags.USE_DATABASE_PERSISTENCE) is True

    def test_enable_via_env_variations(self, manager):
        """Test various truthy env values."""
        truthy_values = ["true", "True", "TRUE", "1", "yes", "YES", "on", "ON"]
        for value in truthy_values:
            with patch.dict(os.environ, {"FF_USE_DATABASE_PERSISTENCE": value}):
                assert manager.is_enabled(FeatureFlags.USE_DATABASE_PERSISTENCE) is True, f"Failed for {value}"

    def test_disable_via_env_variations(self, manager):
        """Test various falsy env values."""
        falsy_values = ["false", "False", "FALSE", "0", "no", "NO", "off", "OFF", "random"]
        for value in falsy_values:
            with patch.dict(os.environ, {"FF_USE_DATABASE_PERSISTENCE": value}):
                assert manager.is_enabled(FeatureFlags.USE_DATABASE_PERSISTENCE) is False, f"Failed for {value}"

    def test_runtime_enable(self, manager):
        """Test runtime enable override."""
        with patch.dict(os.environ, {"FF_USE_DATABASE_PERSISTENCE": "false"}):
            assert manager.is_enabled(FeatureFlags.USE_DATABASE_PERSISTENCE) is False
            manager.enable(FeatureFlags.USE_DATABASE_PERSISTENCE)
            assert manager.is_enabled(FeatureFlags.USE_DATABASE_PERSISTENCE) is True

    def test_runtime_disable(self, manager):
        """Test runtime disable override."""
        with patch.dict(os.environ, {"FF_USE_DATABASE_PERSISTENCE": "true"}):
            assert manager.is_enabled(FeatureFlags.USE_DATABASE_PERSISTENCE) is True
            manager.disable(FeatureFlags.USE_DATABASE_PERSISTENCE)
            assert manager.is_enabled(FeatureFlags.USE_DATABASE_PERSISTENCE) is False

    def test_clear_override(self, manager):
        """Test clearing a runtime override."""
        with patch.dict(os.environ, {"FF_USE_DATABASE_PERSISTENCE": "true"}):
            manager.disable(FeatureFlags.USE_DATABASE_PERSISTENCE)
            assert manager.is_enabled(FeatureFlags.USE_DATABASE_PERSISTENCE) is False
            manager.clear_override(FeatureFlags.USE_DATABASE_PERSISTENCE)
            assert manager.is_enabled(FeatureFlags.USE_DATABASE_PERSISTENCE) is True

    def test_clear_all_overrides(self, manager):
        """Test clearing all runtime overrides."""
        with patch.dict(os.environ, {
            "FF_USE_DATABASE_PERSISTENCE": "true",
            "FF_ENABLE_NLP_COMMANDS": "true",
        }):
            manager.disable(FeatureFlags.USE_DATABASE_PERSISTENCE)
            manager.disable(FeatureFlags.ENABLE_NLP_COMMANDS)
            manager.clear_all_overrides()
            assert manager.is_enabled(FeatureFlags.USE_DATABASE_PERSISTENCE) is True
            assert manager.is_enabled(FeatureFlags.ENABLE_NLP_COMMANDS) is True

    def test_get_all_states(self, manager):
        """Test getting all flag states."""
        with patch.dict(os.environ, {"FF_USE_DATABASE_PERSISTENCE": "true"}):
            states = manager.get_all_states()
            assert isinstance(states, dict)
            assert len(states) == len(FeatureFlags)
            assert states["use_database_persistence"] is True
            assert states["enable_nlp_commands"] is False


class TestWithFallback:
    """Tests for with_fallback functionality."""

    @pytest.fixture
    def manager(self):
        """Create a fresh manager for each test."""
        FeatureFlagManager._instance = None
        manager = FeatureFlagManager()
        manager.clear_all_overrides()
        return manager

    def test_with_fallback_primary_when_enabled(self, manager):
        """Test that primary is called when flag is enabled."""
        manager.enable(FeatureFlags.USE_DATABASE_PERSISTENCE)
        result = manager.with_fallback(
            FeatureFlags.USE_DATABASE_PERSISTENCE,
            primary=lambda: "primary",
            fallback=lambda: "fallback",
        )
        assert result == "primary"

    def test_with_fallback_fallback_when_disabled(self, manager):
        """Test that fallback is called when flag is disabled."""
        manager.disable(FeatureFlags.USE_DATABASE_PERSISTENCE)
        result = manager.with_fallback(
            FeatureFlags.USE_DATABASE_PERSISTENCE,
            primary=lambda: "primary",
            fallback=lambda: "fallback",
        )
        assert result == "fallback"

    def test_with_fallback_fallback_on_error(self, manager):
        """Test that fallback is called when primary raises an error."""
        manager.enable(FeatureFlags.USE_DATABASE_PERSISTENCE)

        def failing_primary():
            raise RuntimeError("Primary failed")

        result = manager.with_fallback(
            FeatureFlags.USE_DATABASE_PERSISTENCE,
            primary=failing_primary,
            fallback=lambda: "fallback",
        )
        assert result == "fallback"


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton before each test."""
        FeatureFlagManager._instance = None
        yield

    def test_is_database_persistence_enabled(self):
        """Test convenience function for database persistence."""
        with patch.dict(os.environ, {"FF_USE_DATABASE_PERSISTENCE": "true"}):
            # Clear cached instance
            get_feature_flags.cache_clear()
            assert is_database_persistence_enabled() is True

    def test_is_nlp_commands_enabled(self):
        """Test convenience function for NLP commands."""
        with patch.dict(os.environ, {"FF_ENABLE_NLP_COMMANDS": "true"}):
            get_feature_flags.cache_clear()
            assert is_nlp_commands_enabled() is True

    def test_is_real_embeddings_enabled(self):
        """Test convenience function for real embeddings."""
        with patch.dict(os.environ, {"FF_ENABLE_REAL_EMBEDDINGS": "true"}):
            get_feature_flags.cache_clear()
            assert is_real_embeddings_enabled() is True

    def test_is_background_jobs_enabled(self):
        """Test convenience function for background jobs."""
        with patch.dict(os.environ, {"FF_ENABLE_BACKGROUND_JOBS": "true"}):
            get_feature_flags.cache_clear()
            assert is_background_jobs_enabled() is True


class TestSingleton:
    """Tests for singleton behavior."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton before each test."""
        FeatureFlagManager._instance = None
        yield

    def test_singleton_returns_same_instance(self):
        """Test that singleton returns the same instance."""
        manager1 = FeatureFlagManager()
        manager2 = FeatureFlagManager()
        assert manager1 is manager2

    def test_get_feature_flags_returns_same_instance(self):
        """Test that get_feature_flags returns the same instance."""
        get_feature_flags.cache_clear()
        manager1 = get_feature_flags()
        manager2 = get_feature_flags()
        assert manager1 is manager2

    def test_overrides_persist_across_calls(self):
        """Test that overrides persist across function calls."""
        get_feature_flags.cache_clear()
        manager = get_feature_flags()
        manager.enable(FeatureFlags.USE_DATABASE_PERSISTENCE)

        # Get again and check
        manager2 = get_feature_flags()
        assert manager2.is_enabled(FeatureFlags.USE_DATABASE_PERSISTENCE) is True
