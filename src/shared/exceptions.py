"""Shared exceptions for the learning system.

This module defines a consistent exception hierarchy used across all modules
to standardize error handling and provide clear error semantics.
"""

from typing import Any
from uuid import UUID


class LearnerException(Exception):
    """Base exception for all application errors.

    All domain-specific exceptions should inherit from this class
    to enable consistent error handling at the API layer.
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


# ===================
# Authentication Errors
# ===================

class AuthenticationError(LearnerException):
    """Base class for authentication-related errors."""
    pass


class InvalidCredentialsError(AuthenticationError):
    """Raised when login credentials are invalid."""

    def __init__(self) -> None:
        super().__init__("Invalid email or password")


class TokenExpiredError(AuthenticationError):
    """Raised when an authentication token has expired."""

    def __init__(self) -> None:
        super().__init__("Token has expired")


class InvalidTokenError(AuthenticationError):
    """Raised when an authentication token is invalid."""

    def __init__(self) -> None:
        super().__init__("Invalid token")


class UserAlreadyExistsError(AuthenticationError):
    """Raised when attempting to register a user that already exists."""

    def __init__(self, email: str) -> None:
        super().__init__(
            f"User with email '{email}' already exists",
            {"email": email}
        )


# ===================
# Resource Errors
# ===================

class ResourceNotFoundError(LearnerException):
    """Raised when a requested resource is not found."""

    def __init__(
        self,
        resource_type: str,
        resource_id: UUID | str,
    ) -> None:
        super().__init__(
            f"{resource_type} not found: {resource_id}",
            {"resource_type": resource_type, "resource_id": str(resource_id)}
        )


class SessionNotFoundError(ResourceNotFoundError):
    """Raised when a session is not found."""

    def __init__(self, session_id: UUID) -> None:
        super().__init__("Session", session_id)


class ContentNotFoundError(ResourceNotFoundError):
    """Raised when content is not found."""

    def __init__(self, content_id: UUID) -> None:
        super().__init__("Content", content_id)


class TopicNotFoundError(ResourceNotFoundError):
    """Raised when a topic is not found."""

    def __init__(self, topic_id: UUID) -> None:
        super().__init__("Topic", topic_id)


class QuizNotFoundError(ResourceNotFoundError):
    """Raised when a quiz is not found."""

    def __init__(self, quiz_id: UUID) -> None:
        super().__init__("Quiz", quiz_id)


class FeynmanSessionNotFoundError(ResourceNotFoundError):
    """Raised when a Feynman session is not found."""

    def __init__(self, session_id: UUID) -> None:
        super().__init__("FeynmanSession", session_id)


class UserNotFoundError(ResourceNotFoundError):
    """Raised when a user is not found."""

    def __init__(self, user_id: UUID) -> None:
        super().__init__("User", user_id)


# ===================
# State Errors
# ===================

class InvalidStateError(LearnerException):
    """Raised when an operation is invalid for the current state."""
    pass


class SessionAlreadyActiveError(InvalidStateError):
    """Raised when user tries to start a session but already has one active."""

    def __init__(self, user_id: UUID) -> None:
        super().__init__(
            "User already has an active session",
            {"user_id": str(user_id)}
        )


class SessionNotActiveError(InvalidStateError):
    """Raised when an operation requires an active session."""

    def __init__(self, session_id: UUID, current_status: str) -> None:
        super().__init__(
            f"Session is not active (current status: {current_status})",
            {"session_id": str(session_id), "status": current_status}
        )


class ActivityNotFoundError(ResourceNotFoundError):
    """Raised when an activity is not found."""

    def __init__(self, activity_id: UUID) -> None:
        super().__init__("Activity", activity_id)


# ===================
# Validation Errors
# ===================

class ValidationError(LearnerException):
    """Raised when input validation fails."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(
            f"Validation error for '{field}': {message}",
            {"field": field}
        )


class InvalidTimeBudgetError(ValidationError):
    """Raised when time budget is out of valid range."""

    def __init__(self, minutes: int) -> None:
        super().__init__(
            "time_budget_minutes",
            f"Time budget must be between 5 and 480 minutes, got {minutes}"
        )


class InvalidDifficultyLevelError(ValidationError):
    """Raised when difficulty level is out of valid range."""

    def __init__(self, level: int) -> None:
        super().__init__(
            "difficulty_level",
            f"Difficulty level must be between 1 and 5, got {level}"
        )


class InvalidScoreError(ValidationError):
    """Raised when a score is out of valid range."""

    def __init__(self, score: float) -> None:
        super().__init__(
            "score",
            f"Score must be between 0.0 and 1.0, got {score}"
        )


# ===================
# Integration Errors
# ===================

class ExternalServiceError(LearnerException):
    """Raised when an external service call fails."""

    def __init__(self, service: str, message: str) -> None:
        super().__init__(
            f"External service error ({service}): {message}",
            {"service": service}
        )


class LLMServiceError(ExternalServiceError):
    """Raised when LLM service fails."""

    def __init__(self, message: str) -> None:
        super().__init__("LLM", message)


class ContentSourceError(ExternalServiceError):
    """Raised when content source fails."""

    def __init__(self, source_type: str, message: str) -> None:
        super().__init__(f"ContentSource:{source_type}", message)


# ===================
# Configuration Errors
# ===================

class ConfigurationError(LearnerException):
    """Raised when there's a configuration problem."""
    pass


class AdapterNotFoundError(ConfigurationError):
    """Raised when a content adapter is not registered."""

    def __init__(self, source_type: str) -> None:
        super().__init__(
            f"No adapter registered for source type: {source_type}",
            {"source_type": source_type}
        )


class InvalidConfigurationError(ConfigurationError):
    """Raised when configuration is invalid."""

    def __init__(self, source_type: str) -> None:
        super().__init__(
            f"Invalid configuration for source type: {source_type}",
            {"source_type": source_type}
        )


# ===================
# Feature Flag Errors
# ===================

class FeatureFlagError(LearnerException):
    """Raised when a feature flag operation fails."""

    def __init__(self, flag: str, message: str) -> None:
        super().__init__(
            f"Feature flag error ({flag}): {message}",
            {"flag": flag}
        )


class FeatureDisabledError(FeatureFlagError):
    """Raised when attempting to use a disabled feature."""

    def __init__(self, feature: str) -> None:
        super().__init__(
            feature,
            f"Feature '{feature}' is not enabled. Set FF_{feature.upper()}=true to enable."
        )


class ServiceNotAvailableError(LearnerException):
    """Raised when a service is not available."""

    def __init__(self, service: str, reason: str | None = None) -> None:
        message = f"Service '{service}' is not available"
        if reason:
            message += f": {reason}"
        super().__init__(message, {"service": service, "reason": reason})


# ===================
# NLP Parsing Errors
# ===================

class NLPParseError(ValidationError):
    """Raised when natural language parsing fails."""

    def __init__(self, user_input: str, reason: str) -> None:
        super().__init__(
            "nlp_input",
            f"Could not parse command: {reason}"
        )
        # Truncate user input for safety (avoid log injection)
        self.details["user_input"] = user_input[:100] if len(user_input) > 100 else user_input


class AmbiguousCommandError(NLPParseError):
    """Raised when command intent is ambiguous."""

    def __init__(self, user_input: str, possibilities: list[str]) -> None:
        super().__init__(
            user_input,
            f"Ambiguous command. Did you mean: {', '.join(possibilities)}?"
        )
        self.details["possibilities"] = possibilities


class CommandNotFoundError(NLPParseError):
    """Raised when no matching command is found."""

    def __init__(self, user_input: str, suggestion: str | None = None) -> None:
        reason = "No matching command found"
        if suggestion:
            reason += f". Try: {suggestion}"
        super().__init__(user_input, reason)
        if suggestion:
            self.details["suggestion"] = suggestion
