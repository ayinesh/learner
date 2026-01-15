"""Pydantic schemas for Session module."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.shared.models import ActivityType, SessionStatus, SessionType


class SessionSchema(BaseModel):
    """Session schema for API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    session_type: SessionType
    status: SessionStatus
    planned_duration_minutes: int
    actual_duration_minutes: Optional[int] = None
    started_at: datetime
    ended_at: Optional[datetime] = None


class SessionActivitySchema(BaseModel):
    """Session activity schema for API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    activity_type: ActivityType
    topic_id: Optional[UUID] = None
    content_id: Optional[UUID] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    performance_data: dict[str, Any] = Field(default_factory=dict)


class SessionPlanItemSchema(BaseModel):
    """Session plan item schema."""

    order: int
    activity_type: ActivityType
    duration_minutes: int
    topic_id: Optional[UUID] = None
    topic_name: Optional[str] = None
    content_id: Optional[UUID] = None
    description: str = ""


class SessionPlanSchema(BaseModel):
    """Session plan schema."""

    session_id: UUID
    total_duration_minutes: int
    consumption_minutes: int
    production_minutes: int
    items: list[SessionPlanItemSchema]
    topics_covered: list[str]
    includes_review: bool


class SessionSummarySchema(BaseModel):
    """Session summary schema."""

    session_id: UUID
    duration_minutes: int
    activities_completed: int
    topics_covered: list[str]
    content_consumed: int
    new_gaps_identified: list[str]
    quiz_score: Optional[float] = None
    feynman_score: Optional[float] = None
    streak_updated: bool = False
    next_session_preview: Optional[str] = None


class CreateSessionRequest(BaseModel):
    """Request schema for creating a session."""

    available_minutes: Optional[int] = None
    session_type: SessionType = SessionType.REGULAR


class RecordActivityRequest(BaseModel):
    """Request schema for recording an activity."""

    activity_type: ActivityType
    topic_id: Optional[UUID] = None
    content_id: Optional[UUID] = None
    performance_data: Optional[dict[str, Any]] = None


class CompleteActivityRequest(BaseModel):
    """Request schema for completing an activity."""

    performance_data: Optional[dict[str, Any]] = None


class AbandonSessionRequest(BaseModel):
    """Request schema for abandoning a session."""

    reason: Optional[str] = None


class StreakInfoSchema(BaseModel):
    """Streak information schema."""

    current_streak: int
    longest_streak: int
    last_session_date: Optional[datetime] = None
    streak_at_risk: bool = False
