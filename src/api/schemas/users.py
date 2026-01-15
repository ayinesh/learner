"""User profile API schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from src.shared.models import SourceType


class UserProfileResponse(BaseModel):
    """User profile response."""

    user_id: UUID = Field(
        ...,
        description="User's unique identifier",
    )
    background: str = Field(
        default="",
        description="User's professional background",
    )
    goals: list[str] = Field(
        default_factory=list,
        description="Learning goals",
    )
    time_budget_minutes: int = Field(
        default=30,
        description="Daily time budget in minutes",
    )
    preferred_sources: list[SourceType] = Field(
        default_factory=list,
        description="Preferred content sources",
    )
    timezone: str = Field(
        default="UTC",
        description="User's timezone",
    )
    onboarding_completed: bool = Field(
        default=False,
        description="Whether onboarding is complete",
    )
    created_at: datetime = Field(
        ...,
        description="Profile creation timestamp",
    )
    updated_at: datetime = Field(
        ...,
        description="Last update timestamp",
    )

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    """Profile update request."""

    background: str | None = Field(
        default=None,
        description="Professional background",
    )
    goals: list[str] | None = Field(
        default=None,
        description="Learning goals",
    )
    timezone: str | None = Field(
        default=None,
        description="User's timezone",
    )


class OnboardingRequest(BaseModel):
    """Onboarding completion request."""

    background: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description="Professional background description",
    )
    goals: list[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Learning goals (1-10 items)",
    )
    time_budget_minutes: int = Field(
        ...,
        ge=10,
        le=180,
        description="Daily time budget (10-180 minutes)",
    )
    timezone: str = Field(
        default="UTC",
        description="User's timezone",
    )
    preferred_sources: list[SourceType] = Field(
        ...,
        min_length=1,
        description="Preferred content sources",
    )
    initial_topics: list[str] | None = Field(
        default=None,
        description="Initial topics of interest",
    )

    @field_validator("goals")
    @classmethod
    def validate_goals(cls, v: list[str]) -> list[str]:
        """Validate goals are not empty strings."""
        if any(not goal.strip() for goal in v):
            raise ValueError("Goals cannot be empty strings")
        return [goal.strip() for goal in v]


class LearningPatternResponse(BaseModel):
    """User learning pattern response."""

    user_id: UUID = Field(
        ...,
        description="User's unique identifier",
    )
    avg_session_duration: float = Field(
        default=0.0,
        description="Average session duration in minutes",
    )
    preferred_time_of_day: str | None = Field(
        default=None,
        description="Preferred learning time (morning/afternoon/evening)",
    )
    completion_rate: float = Field(
        default=0.0,
        description="Session completion rate (0-1)",
    )
    quiz_accuracy_trend: float = Field(
        default=0.0,
        description="Quiz accuracy trend (-1 to 1)",
    )
    feynman_score_trend: float = Field(
        default=0.0,
        description="Feynman score trend (-1 to 1)",
    )
    days_since_last_session: int = Field(
        default=0,
        description="Days since last learning session",
    )
    total_sessions: int = Field(
        default=0,
        description="Total completed sessions",
    )
    current_streak: int = Field(
        default=0,
        description="Current learning streak in days",
    )
    longest_streak: int = Field(
        default=0,
        description="Longest learning streak in days",
    )
    updated_at: datetime = Field(
        ...,
        description="Last update timestamp",
    )

    model_config = {"from_attributes": True}


class UpdateTimeBudgetRequest(BaseModel):
    """Time budget update request."""

    minutes: int = Field(
        ...,
        ge=10,
        le=180,
        description="New time budget in minutes",
    )


class SourceConfigRequest(BaseModel):
    """Source configuration request."""

    source_type: SourceType = Field(
        ...,
        description="Content source type",
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Source-specific configuration",
    )
    enabled: bool = Field(
        default=True,
        description="Whether the source is enabled",
    )


class SourceConfigResponse(BaseModel):
    """Source configuration response."""

    source_type: SourceType = Field(
        ...,
        description="Content source type",
    )
    config: dict[str, Any] = Field(
        ...,
        description="Source configuration",
    )
    enabled: bool = Field(
        ...,
        description="Whether the source is enabled",
    )


class SourcesListResponse(BaseModel):
    """List of configured sources."""

    sources: list[SourceConfigResponse] = Field(
        ...,
        description="List of configured sources",
    )
