"""Feature flag management for safe feature rollout.

This module provides a centralized system for toggling features on/off
without code changes, enabling gradual rollout and quick rollback.

Usage:
    from src.shared.feature_flags import get_feature_flags, FeatureFlags

    flags = get_feature_flags()
    if flags.is_enabled(FeatureFlags.USE_DATABASE_PERSISTENCE):
        # Use database-backed service
    else:
        # Use in-memory service

Environment Variables:
    FF_USE_DATABASE_PERSISTENCE: Enable database persistence (default: false)
    FF_ENABLE_NLP_COMMANDS: Enable NLP chat commands (default: false)
    FF_ENABLE_REAL_EMBEDDINGS: Use OpenAI embeddings (default: false)
    FF_ENABLE_BACKGROUND_JOBS: Enable background job scheduler (default: false)
    FF_ENABLE_ENHANCED_QUESTIONS: Enable enhanced question types (default: false)
"""

from enum import Enum
from functools import lru_cache
from typing import Any, Callable, TypeVar
import logging
import os

logger = logging.getLogger(__name__)

T = TypeVar("T")


class FeatureFlags(str, Enum):
    """Available feature flags.

    Each flag corresponds to an environment variable with FF_ prefix.
    """

    USE_DATABASE_PERSISTENCE = "use_database_persistence"
    ENABLE_NLP_COMMANDS = "enable_nlp_commands"
    ENABLE_REAL_EMBEDDINGS = "enable_real_embeddings"
    ENABLE_BACKGROUND_JOBS = "enable_background_jobs"
    ENABLE_ENHANCED_QUESTIONS = "enable_enhanced_questions"

    @property
    def env_key(self) -> str:
        """Get the environment variable name for this flag."""
        return f"FF_{self.value.upper()}"


class FeatureFlagManager:
    """Manages feature flags with environment variable and runtime overrides.

    Thread-safe singleton that supports:
    - Environment variable configuration
    - Runtime overrides for testing
    - Graceful fallback execution
    - Logging of flag state changes
    """

    _instance: "FeatureFlagManager | None" = None
    _lock_initialized: bool = False

    def __new__(cls) -> "FeatureFlagManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._overrides: dict[str, bool] = {}
        self._initialized = True
        logger.info("FeatureFlagManager initialized")

    def is_enabled(self, flag: FeatureFlags) -> bool:
        """Check if a feature flag is enabled.

        Priority:
        1. Runtime overrides (set via enable/disable methods)
        2. Environment variables (FF_<FLAG_NAME>=true/false)
        3. Default (false)

        Args:
            flag: The feature flag to check

        Returns:
            True if the flag is enabled, False otherwise
        """
        # Check runtime overrides first
        if flag.value in self._overrides:
            return self._overrides[flag.value]

        # Check environment variable
        env_value = os.getenv(flag.env_key, "false").lower()
        return env_value in ("true", "1", "yes", "on")

    def enable(self, flag: FeatureFlags) -> None:
        """Enable a feature flag at runtime.

        This override persists until disable() is called or the process restarts.

        Args:
            flag: The feature flag to enable
        """
        self._overrides[flag.value] = True
        logger.info(f"Feature flag enabled: {flag.value}")

    def disable(self, flag: FeatureFlags) -> None:
        """Disable a feature flag at runtime.

        This override persists until enable() is called or the process restarts.

        Args:
            flag: The feature flag to disable
        """
        self._overrides[flag.value] = False
        logger.info(f"Feature flag disabled: {flag.value}")

    def clear_override(self, flag: FeatureFlags) -> None:
        """Clear runtime override for a flag, reverting to environment variable.

        Args:
            flag: The feature flag to clear override for
        """
        if flag.value in self._overrides:
            del self._overrides[flag.value]
            logger.info(f"Feature flag override cleared: {flag.value}")

    def clear_all_overrides(self) -> None:
        """Clear all runtime overrides, reverting to environment variables."""
        self._overrides.clear()
        logger.info("All feature flag overrides cleared")

    def with_fallback(
        self,
        flag: FeatureFlags,
        primary: Callable[[], T],
        fallback: Callable[[], T],
        log_fallback: bool = True,
    ) -> T:
        """Execute primary function if flag enabled, fallback otherwise.

        If primary raises an exception when flag is enabled, automatically
        falls back to the fallback function for resilience.

        Args:
            flag: The feature flag to check
            primary: Function to call when flag is enabled
            fallback: Function to call when flag is disabled or primary fails
            log_fallback: Whether to log when falling back due to error

        Returns:
            Result from primary or fallback function
        """
        if self.is_enabled(flag):
            try:
                return primary()
            except Exception as e:
                if log_fallback:
                    logger.warning(
                        f"Feature {flag.value} primary failed, using fallback: {e}"
                    )
                return fallback()
        return fallback()

    async def with_fallback_async(
        self,
        flag: FeatureFlags,
        primary: Callable[[], Any],
        fallback: Callable[[], Any],
        log_fallback: bool = True,
    ) -> Any:
        """Async version of with_fallback.

        Args:
            flag: The feature flag to check
            primary: Async function to call when flag is enabled
            fallback: Async function to call when flag is disabled or primary fails
            log_fallback: Whether to log when falling back due to error

        Returns:
            Result from primary or fallback function
        """
        if self.is_enabled(flag):
            try:
                return await primary()
            except Exception as e:
                if log_fallback:
                    logger.warning(
                        f"Feature {flag.value} primary failed, using fallback: {e}"
                    )
                return await fallback()
        return await fallback()

    def get_all_states(self) -> dict[str, bool]:
        """Get the current state of all feature flags.

        Useful for debugging and health endpoints.

        Returns:
            Dictionary of flag names to their enabled states
        """
        return {flag.value: self.is_enabled(flag) for flag in FeatureFlags}

    def __repr__(self) -> str:
        states = self.get_all_states()
        enabled = [k for k, v in states.items() if v]
        return f"FeatureFlagManager(enabled={enabled})"


@lru_cache
def get_feature_flags() -> FeatureFlagManager:
    """Get the singleton FeatureFlagManager instance.

    Returns:
        The shared FeatureFlagManager instance
    """
    return FeatureFlagManager()


# Convenience functions for common checks
def is_database_persistence_enabled() -> bool:
    """Check if database persistence is enabled."""
    return get_feature_flags().is_enabled(FeatureFlags.USE_DATABASE_PERSISTENCE)


def is_nlp_commands_enabled() -> bool:
    """Check if NLP commands are enabled."""
    return get_feature_flags().is_enabled(FeatureFlags.ENABLE_NLP_COMMANDS)


def is_real_embeddings_enabled() -> bool:
    """Check if real embeddings are enabled."""
    return get_feature_flags().is_enabled(FeatureFlags.ENABLE_REAL_EMBEDDINGS)


def is_background_jobs_enabled() -> bool:
    """Check if background jobs are enabled."""
    return get_feature_flags().is_enabled(FeatureFlags.ENABLE_BACKGROUND_JOBS)


def is_enhanced_questions_enabled() -> bool:
    """Check if enhanced question types are enabled."""
    return get_feature_flags().is_enabled(FeatureFlags.ENABLE_ENHANCED_QUESTIONS)
