"""Unified service registry for dependency injection.

This module provides a centralized service factory that switches between
in-memory and database-backed implementations based on feature flags.

Usage:
    from src.shared.service_registry import get_service_registry

    registry = get_service_registry()
    session_service = registry.get_session_service()
    content_service = registry.get_content_service()

The registry automatically:
- Returns DB services when FF_USE_DATABASE_PERSISTENCE=true
- Falls back to in-memory services when DB is unavailable
- Caches service instances for consistent singleton behavior
- Logs service creation for debugging
"""

from functools import lru_cache
from typing import TYPE_CHECKING, Protocol, TypeVar
import logging

from src.shared.feature_flags import (
    FeatureFlags,
    get_feature_flags,
    is_database_persistence_enabled,
)

if TYPE_CHECKING:
    from src.modules.session.interface import ISessionService
    from src.modules.content.interface import IContentService
    from src.modules.assessment.interface import IAssessmentService
    from src.modules.adaptation.interface import IAdaptationService

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ServiceRegistry:
    """Unified service factory with feature flag support.

    This registry manages service instantiation across the application,
    providing a single point of control for switching between implementations.

    Features:
    - Lazy service instantiation
    - Feature flag-based implementation selection
    - Automatic fallback on connection errors
    - Service instance caching
    """

    _instance: "ServiceRegistry | None" = None

    def __new__(cls) -> "ServiceRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._flags = get_feature_flags()
        self._session_service: "ISessionService | None" = None
        self._content_service: "IContentService | None" = None
        self._assessment_service: "IAssessmentService | None" = None
        self._adaptation_service: "IAdaptationService | None" = None
        self._initialized = True
        logger.info("ServiceRegistry initialized")

    def get_session_service(self) -> "ISessionService":
        """Get the session service instance.

        Returns database-backed service if FF_USE_DATABASE_PERSISTENCE is enabled,
        otherwise returns in-memory service.

        Returns:
            ISessionService implementation
        """
        if self._session_service is None:
            self._session_service = self._create_session_service()
        return self._session_service

    def get_content_service(self) -> "IContentService":
        """Get the content service instance.

        Returns database-backed service if FF_USE_DATABASE_PERSISTENCE is enabled,
        otherwise returns in-memory service.

        Returns:
            IContentService implementation
        """
        if self._content_service is None:
            self._content_service = self._create_content_service()
        return self._content_service

    def get_assessment_service(self) -> "IAssessmentService":
        """Get the assessment service instance.

        Returns database-backed service if FF_USE_DATABASE_PERSISTENCE is enabled,
        otherwise returns in-memory service.

        Returns:
            IAssessmentService implementation
        """
        if self._assessment_service is None:
            self._assessment_service = self._create_assessment_service()
        return self._assessment_service

    def get_adaptation_service(self) -> "IAdaptationService":
        """Get the adaptation service instance.

        Returns database-backed service if FF_USE_DATABASE_PERSISTENCE is enabled,
        otherwise returns in-memory service.

        Returns:
            IAdaptationService implementation
        """
        if self._adaptation_service is None:
            self._adaptation_service = self._create_adaptation_service()
        return self._adaptation_service

    def _create_session_service(self) -> "ISessionService":
        """Create session service based on feature flags."""
        if self._flags.is_enabled(FeatureFlags.USE_DATABASE_PERSISTENCE):
            try:
                from src.modules.session.db_service import DatabaseSessionService

                logger.info("Creating DatabaseSessionService")
                return DatabaseSessionService()
            except Exception as e:
                logger.warning(
                    f"Failed to create DatabaseSessionService, falling back: {e}"
                )

        from src.modules.session.service import SessionService

        logger.info("Creating in-memory SessionService")
        return SessionService()

    def _create_content_service(self) -> "IContentService":
        """Create content service based on feature flags."""
        if self._flags.is_enabled(FeatureFlags.USE_DATABASE_PERSISTENCE):
            try:
                from src.modules.content.db_service import DatabaseContentService

                logger.info("Creating DatabaseContentService")
                return DatabaseContentService()
            except Exception as e:
                logger.warning(
                    f"Failed to create DatabaseContentService, falling back: {e}"
                )

        from src.modules.content.service import ContentService

        logger.info("Creating in-memory ContentService")
        return ContentService()

    def _create_assessment_service(self) -> "IAssessmentService":
        """Create assessment service based on feature flags."""
        if self._flags.is_enabled(FeatureFlags.USE_DATABASE_PERSISTENCE):
            try:
                from src.modules.assessment.db_service import DatabaseAssessmentService

                logger.info("Creating DatabaseAssessmentService")
                return DatabaseAssessmentService()
            except Exception as e:
                logger.warning(
                    f"Failed to create DatabaseAssessmentService, falling back: {e}"
                )

        from src.modules.assessment.service import AssessmentService

        logger.info("Creating in-memory AssessmentService")
        return AssessmentService()

    def _create_adaptation_service(self) -> "IAdaptationService":
        """Create adaptation service based on feature flags."""
        if self._flags.is_enabled(FeatureFlags.USE_DATABASE_PERSISTENCE):
            try:
                from src.modules.adaptation.db_service import DatabaseAdaptationService

                logger.info("Creating DatabaseAdaptationService")
                return DatabaseAdaptationService()
            except Exception as e:
                logger.warning(
                    f"Failed to create DatabaseAdaptationService, falling back: {e}"
                )

        from src.modules.adaptation.service import AdaptationService

        logger.info("Creating in-memory AdaptationService")
        return AdaptationService()

    def clear_cache(self) -> None:
        """Clear all cached service instances.

        Use this when feature flags change at runtime to force
        recreation of services with new settings.
        """
        self._session_service = None
        self._content_service = None
        self._assessment_service = None
        self._adaptation_service = None
        logger.info("ServiceRegistry cache cleared")

    def get_service_info(self) -> dict[str, str]:
        """Get information about currently instantiated services.

        Returns:
            Dictionary of service names to their implementation types
        """
        info = {}
        if self._session_service:
            info["session"] = type(self._session_service).__name__
        if self._content_service:
            info["content"] = type(self._content_service).__name__
        if self._assessment_service:
            info["assessment"] = type(self._assessment_service).__name__
        if self._adaptation_service:
            info["adaptation"] = type(self._adaptation_service).__name__
        return info

    def __repr__(self) -> str:
        db_enabled = self._flags.is_enabled(FeatureFlags.USE_DATABASE_PERSISTENCE)
        return f"ServiceRegistry(db_enabled={db_enabled}, services={self.get_service_info()})"


@lru_cache
def get_service_registry() -> ServiceRegistry:
    """Get the singleton ServiceRegistry instance.

    Returns:
        The shared ServiceRegistry instance
    """
    return ServiceRegistry()


# Convenience functions for common service access
def get_session_service() -> "ISessionService":
    """Get session service from the registry.

    This is the recommended way to get a session service instance,
    as it respects feature flags and provides fallback behavior.
    """
    return get_service_registry().get_session_service()


def get_content_service() -> "IContentService":
    """Get content service from the registry.

    This is the recommended way to get a content service instance,
    as it respects feature flags and provides fallback behavior.
    """
    return get_service_registry().get_content_service()


def get_assessment_service() -> "IAssessmentService":
    """Get assessment service from the registry.

    This is the recommended way to get an assessment service instance,
    as it respects feature flags and provides fallback behavior.
    """
    return get_service_registry().get_assessment_service()


def get_adaptation_service() -> "IAdaptationService":
    """Get adaptation service from the registry.

    This is the recommended way to get an adaptation service instance,
    as it respects feature flags and provides fallback behavior.
    """
    return get_service_registry().get_adaptation_service()
