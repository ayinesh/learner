"""Session API schemas."""

from datetime import datetime, date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from src.shared.models import ActivityType, SessionStatus, SessionType


class StartSessionRequest(BaseModel):
    """Start session request."""

    available_minutes: int = Field(
        default=30,
        ge=10,
        le=180,
        description="Available time for the session (10-180 minutes)",
    )
    session_type: SessionType = Field(
        default=SessionType.REGULAR,
        description="Type of learning session",
    )


class SessionResponse(BaseModel):
    """Session information response."""

    id: UUID = Field(
        ...,
        description="Session unique identifier",
    )
    user_id: UUID = Field(
        ...,
        description="User who owns the session",
    )
    session_type: SessionType = Field(
        ...,
        description="Type of session",
    )
    status: SessionStatus = Field(
        ...,
        description="Current session status",
    )
    planned_duration_minutes: int = Field(
        ...,
        description="Planned duration in minutes",
    )
    actual_duration_minutes: int | None = Field(
        default=None,
        description="Actual duration (after completion)",
    )
    started_at: datetime = Field(
        ...,
        description="Session start time",
    )
    ended_at: datetime | None = Field(
        default=None,
        description="Session end time",
    )

    model_config = {"from_attributes": True}


class SessionPlanItemResponse(BaseModel):
    """Session plan item response."""

    order: int = Field(
        ...,
        description="Activity order in the plan",
    )
    activity_type: ActivityType = Field(
        ...,
        description="Type of activity",
    )
    duration_minutes: int = Field(
        ...,
        description="Planned duration in minutes",
    )
    description: str = Field(
        ...,
        description="Activity description",
    )
    topic_name: str | None = Field(
        default=None,
        description="Related topic name",
    )
    topic_id: UUID | None = Field(
        default=None,
        description="Related topic ID",
    )
    content_id: UUID | None = Field(
        default=None,
        description="Related content ID",
    )


class SessionPlanResponse(BaseModel):
    """Session plan response."""

    session_id: UUID = Field(
        ...,
        description="Session this plan belongs to",
    )
    total_duration_minutes: int = Field(
        ...,
        description="Total planned duration",
    )
    consumption_minutes: int = Field(
        ...,
        description="Time allocated for content consumption",
    )
    production_minutes: int = Field(
        ...,
        description="Time allocated for production activities",
    )
    items: list[SessionPlanItemResponse] = Field(
        ...,
        description="Ordered list of planned activities",
    )
    topics_covered: list[str] = Field(
        ...,
        description="Topics to be covered",
    )
    includes_review: bool = Field(
        ...,
        description="Whether plan includes spaced repetition review",
    )


class RecordActivityRequest(BaseModel):
    """Record activity request."""

    activity_type: ActivityType = Field(
        ...,
        description="Type of activity",
    )
    topic_id: UUID | None = Field(
        default=None,
        description="Related topic ID",
    )
    content_id: UUID | None = Field(
        default=None,
        description="Related content ID",
    )
    performance_data: dict[str, Any] | None = Field(
        default=None,
        description="Activity performance metrics",
    )


class ActivityResponse(BaseModel):
    """Activity response."""

    id: UUID = Field(
        ...,
        description="Activity unique identifier",
    )
    session_id: UUID = Field(
        ...,
        description="Session this activity belongs to",
    )
    activity_type: ActivityType = Field(
        ...,
        description="Type of activity",
    )
    topic_id: UUID | None = Field(
        default=None,
        description="Related topic ID",
    )
    content_id: UUID | None = Field(
        default=None,
        description="Related content ID",
    )
    started_at: datetime = Field(
        ...,
        description="Activity start time",
    )
    ended_at: datetime | None = Field(
        default=None,
        description="Activity end time",
    )
    performance_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Performance metrics",
    )

    model_config = {"from_attributes": True}


class CompleteActivityRequest(BaseModel):
    """Complete activity request."""

    performance_data: dict[str, Any] | None = Field(
        default=None,
        description="Final performance metrics",
    )


class SessionSummaryResponse(BaseModel):
    """Session summary response."""

    session_id: UUID = Field(
        ...,
        description="Session identifier",
    )
    duration_minutes: int = Field(
        ...,
        description="Actual session duration",
    )
    activities_completed: int = Field(
        ...,
        description="Number of completed activities",
    )
    topics_covered: list[str] = Field(
        ...,
        description="Topics covered in session",
    )
    quiz_score: float | None = Field(
        default=None,
        description="Quiz score if quiz was taken",
    )
    feynman_score: float | None = Field(
        default=None,
        description="Feynman exercise score if completed",
    )
    content_consumed: int = Field(
        ...,
        description="Number of content pieces consumed",
    )
    new_gaps_identified: list[str] = Field(
        ...,
        description="Newly identified knowledge gaps",
    )
    streak_updated: bool = Field(
        ...,
        description="Whether streak was incremented",
    )
    next_session_preview: str = Field(
        ...,
        description="Preview of next session focus",
    )


class SessionHistoryResponse(BaseModel):
    """Session history response."""

    sessions: list[SessionResponse] = Field(
        ...,
        description="List of past sessions",
    )
    total: int = Field(
        ...,
        description="Total number of sessions",
    )


class StreakInfoResponse(BaseModel):
    """Streak information response."""

    current_streak: int = Field(
        ...,
        description="Current streak in days",
    )
    longest_streak: int = Field(
        ...,
        description="Longest streak in days",
    )
    last_session_date: date | None = Field(
        default=None,
        description="Date of last session",
    )
    streak_at_risk: bool = Field(
        ...,
        description="Whether streak is at risk of breaking",
    )
