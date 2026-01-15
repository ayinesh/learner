"""Domain Data Transfer Objects (DTOs).

This module defines data transfer objects used to pass data between
layers of the application, decoupling the API layer from the domain layer.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from src.shared.models import SessionType, SessionStatus, ActivityType, SourceType


# ===================
# Session DTOs
# ===================

@dataclass(frozen=True)
class StartSessionCommand:
    """Command to start a new learning session."""
    user_id: UUID
    available_minutes: int | None = None
    session_type: SessionType = SessionType.REGULAR
    focus_topics: list[UUID] = field(default_factory=list)


@dataclass(frozen=True)
class EndSessionCommand:
    """Command to end a learning session."""
    session_id: UUID
    user_id: UUID


@dataclass(frozen=True)
class RecordActivityCommand:
    """Command to record a session activity."""
    session_id: UUID
    activity_type: ActivityType
    topic_id: UUID | None = None
    content_id: UUID | None = None
    performance_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionInfo:
    """Session information for display/API responses."""
    id: UUID
    user_id: UUID
    session_type: SessionType
    status: SessionStatus
    planned_duration_minutes: int
    actual_duration_minutes: int | None
    started_at: datetime
    ended_at: datetime | None
    activity_count: int = 0


# ===================
# Content DTOs
# ===================

@dataclass(frozen=True)
class IngestContentCommand:
    """Command to ingest new content."""
    user_id: UUID
    source_type: SourceType
    url: str | None = None
    raw_content: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProcessContentCommand:
    """Command to process ingested content."""
    content_id: UUID
    force_reprocess: bool = False


@dataclass(frozen=True)
class ContentSearchQuery:
    """Query parameters for content search."""
    user_id: UUID
    keywords: list[str] = field(default_factory=list)
    topic_ids: list[UUID] = field(default_factory=list)
    source_types: list[SourceType] = field(default_factory=list)
    limit: int = 20


@dataclass
class ContentInfo:
    """Content information for display/API responses."""
    id: UUID
    title: str
    summary: str | None
    source_type: SourceType
    source_url: str | None
    importance_score: float
    created_at: datetime
    processed: bool
    topics: list[str] = field(default_factory=list)


# ===================
# Assessment DTOs
# ===================

@dataclass(frozen=True)
class GenerateQuizCommand:
    """Command to generate a quiz."""
    user_id: UUID
    topic_ids: list[UUID] = field(default_factory=list)
    question_count: int = 5
    include_review: bool = True


@dataclass(frozen=True)
class EvaluateQuizCommand:
    """Command to evaluate quiz answers."""
    quiz_id: UUID
    user_id: UUID
    answers: list[dict[str, Any]]
    time_taken_seconds: int


@dataclass(frozen=True)
class StartFeynmanCommand:
    """Command to start a Feynman dialogue."""
    user_id: UUID
    topic_id: UUID


@dataclass(frozen=True)
class ContinueFeynmanCommand:
    """Command to continue a Feynman dialogue."""
    session_id: UUID
    user_id: UUID
    response: str


@dataclass
class QuizInfo:
    """Quiz information for display/API responses."""
    id: UUID
    topic_count: int
    question_count: int
    is_spaced_repetition: bool
    created_at: datetime


@dataclass
class QuizResultInfo:
    """Quiz result information for display/API responses."""
    quiz_id: UUID
    score: float
    correct_count: int
    total_count: int
    time_taken_seconds: int
    gaps_count: int


# ===================
# Adaptation DTOs
# ===================

@dataclass(frozen=True)
class AnalyzePatternsCommand:
    """Command to analyze learning patterns."""
    user_id: UUID


@dataclass(frozen=True)
class ApplyAdaptationCommand:
    """Command to apply an adaptation."""
    user_id: UUID
    adaptation_type: str
    trigger_reason: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GenerateRecoveryCommand:
    """Command to generate a recovery plan."""
    user_id: UUID
    days_missed: int


@dataclass
class PaceInfo:
    """Pace recommendation information."""
    current_pace: str
    recommended_pace: str
    reason: str
    confidence: float


@dataclass
class RecoveryInfo:
    """Recovery plan information."""
    days_missed: int
    review_topic_count: int
    reduced_new_content: bool
    suggested_sessions: int
    message: str


# ===================
# User DTOs
# ===================

@dataclass(frozen=True)
class UpdateProfileCommand:
    """Command to update user profile."""
    user_id: UUID
    background: str | None = None
    goals: list[str] | None = None
    time_budget_minutes: int | None = None
    preferred_sources: list[SourceType] | None = None
    timezone: str | None = None


@dataclass
class UserProfileInfo:
    """User profile information for display/API responses."""
    user_id: UUID
    background: str | None
    goals: list[str]
    time_budget_minutes: int
    preferred_sources: list[SourceType]
    timezone: str
    onboarding_completed: bool


# ===================
# Value Objects
# ===================

@dataclass(frozen=True)
class TimeBudget:
    """Value object for validated time budget.

    Enforces business rule: time budget must be 5-480 minutes.
    """
    minutes: int

    def __post_init__(self) -> None:
        if not 5 <= self.minutes <= 480:
            raise ValueError("Time budget must be between 5 and 480 minutes")

    @classmethod
    def from_minutes(cls, minutes: int) -> "TimeBudget":
        """Create TimeBudget from minutes."""
        return cls(minutes=minutes)


@dataclass(frozen=True)
class DifficultyLevel:
    """Value object for validated difficulty level.

    Enforces business rule: difficulty must be 1-5.
    """
    level: int

    def __post_init__(self) -> None:
        if not 1 <= self.level <= 5:
            raise ValueError("Difficulty level must be between 1 and 5")

    @classmethod
    def from_int(cls, level: int) -> "DifficultyLevel":
        """Create DifficultyLevel from integer."""
        return cls(level=level)


@dataclass(frozen=True)
class ProficiencyScore:
    """Value object for validated proficiency score.

    Enforces business rule: score must be 0.0-1.0.
    """
    score: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("Proficiency score must be between 0.0 and 1.0")

    @classmethod
    def from_float(cls, score: float) -> "ProficiencyScore":
        """Create ProficiencyScore from float."""
        return cls(score=score)
