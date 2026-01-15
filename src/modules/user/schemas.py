"""Pydantic schemas for user profile requests and responses."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from src.shared.models import SourceType


# ==================
# Request Schemas
# ==================


class CreateProfileRequest(BaseModel):
    """Request schema for creating initial user profile."""

    user_id: UUID = Field(
        ...,
        description="User's UUID",
    )


class UpdateProfileRequest(BaseModel):
    """Request schema for updating user profile."""

    background: str | None = Field(
        default=None,
        description="Professional or educational background",
        max_length=5000,
    )

    goals: list[str] | None = Field(
        default=None,
        description="Learning objectives",
        max_length=20,
    )

    time_budget_minutes: int | None = Field(
        default=None,
        ge=5,
        le=480,
        description="Daily time budget in minutes (5-480)",
    )

    preferred_sources: list[SourceType] | None = Field(
        default=None,
        description="Preferred content sources",
        max_length=10,
    )

    timezone: str | None = Field(
        default=None,
        description="User's timezone (e.g., 'America/New_York')",
    )


class CompleteOnboardingRequest(BaseModel):
    """Request schema for completing onboarding."""

    background: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="Professional or educational background",
    )

    goals: list[str] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Learning objectives",
    )

    time_budget_minutes: int = Field(
        ...,
        ge=5,
        le=480,
        description="Daily time budget in minutes (5-480)",
    )

    preferred_sources: list[SourceType] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Preferred content sources",
    )

    timezone: str = Field(
        default="UTC",
        description="User's timezone",
    )

    initial_topics: list[str] | None = Field(
        default=None,
        max_length=10,
        description="Initial topics user wants to learn",
    )

    @field_validator("goals")
    @classmethod
    def validate_goals(cls, v: list[str]) -> list[str]:
        """Validate goals are non-empty strings."""
        if not v:
            raise ValueError("At least one goal is required")
        for goal in v:
            if not goal.strip():
                raise ValueError("Goals cannot be empty strings")
        return [g.strip() for g in v]

    @field_validator("initial_topics")
    @classmethod
    def validate_topics(cls, v: list[str] | None) -> list[str] | None:
        """Validate topics are non-empty strings."""
        if v is None:
            return None
        return [t.strip() for t in v if t.strip()]


class UpdateTimeBudgetRequest(BaseModel):
    """Request schema for updating time budget."""

    minutes: int = Field(
        ...,
        ge=5,
        le=480,
        description="Time budget in minutes (5-480)",
    )


class AddSourceRequest(BaseModel):
    """Request schema for adding a content source."""

    source: SourceType = Field(
        ...,
        description="Source type to add",
    )

    config: dict = Field(
        ...,
        description="Source-specific configuration",
    )

    @field_validator("config")
    @classmethod
    def validate_config(cls, v: dict) -> dict:
        """Validate config is not empty."""
        if not v:
            raise ValueError("Config cannot be empty")
        return v


class RemoveSourceRequest(BaseModel):
    """Request schema for removing a content source."""

    source: SourceType = Field(
        ...,
        description="Source type to remove",
    )


# ==================
# Response Schemas
# ==================


class UserProfileSchema(BaseModel):
    """Schema for user profile information."""

    user_id: UUID = Field(
        ...,
        description="User's unique identifier",
    )

    background: str | None = Field(
        default=None,
        description="Professional/educational background",
    )

    goals: list[str] = Field(
        default_factory=list,
        description="Learning objectives",
    )

    time_budget_minutes: int = Field(
        default=30,
        description="Daily time budget in minutes",
    )

    preferred_sources: list[str] = Field(
        default_factory=list,
        description="Preferred content sources",
    )

    timezone: str = Field(
        default="UTC",
        description="User's timezone",
    )

    onboarding_completed: bool = Field(
        default=False,
        description="Whether onboarding is completed",
    )

    created_at: datetime = Field(
        ...,
        description="Profile creation timestamp",
    )

    updated_at: datetime = Field(
        ...,
        description="Profile last update timestamp",
    )

    model_config = {
        "from_attributes": True,
    }


class UserLearningPatternSchema(BaseModel):
    """Schema for user learning pattern information."""

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
        description="Preferred time of day for learning",
    )

    completion_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Session completion rate (0-1)",
    )

    quiz_accuracy_trend: float = Field(
        default=0.0,
        description="Quiz accuracy trend (positive = improving)",
    )

    feynman_score_trend: float = Field(
        default=0.0,
        description="Feynman technique score trend (positive = improving)",
    )

    days_since_last_session: int = Field(
        default=0,
        ge=0,
        description="Days since last learning session",
    )

    total_sessions: int = Field(
        default=0,
        ge=0,
        description="Total number of sessions completed",
    )

    current_streak: int = Field(
        default=0,
        ge=0,
        description="Current learning streak in days",
    )

    longest_streak: int = Field(
        default=0,
        ge=0,
        description="Longest learning streak in days",
    )

    updated_at: datetime = Field(
        ...,
        description="Pattern last update timestamp",
    )

    model_config = {
        "from_attributes": True,
    }


class SourceConfigSchema(BaseModel):
    """Schema for source configuration."""

    source_type: SourceType = Field(
        ...,
        description="Source type",
    )

    config: dict = Field(
        ...,
        description="Source-specific configuration",
    )

    enabled: bool = Field(
        default=True,
        description="Whether source is enabled",
    )


class ProfileSuccessResponse(BaseModel):
    """Schema for successful profile operation response."""

    success: Literal[True] = True
    profile: UserProfileSchema = Field(
        ...,
        description="User profile information",
    )


class PatternSuccessResponse(BaseModel):
    """Schema for successful learning pattern response."""

    success: Literal[True] = True
    pattern: UserLearningPatternSchema = Field(
        ...,
        description="User learning pattern information",
    )


class SourceSuccessResponse(BaseModel):
    """Schema for successful source operation response."""

    success: Literal[True] = True
    message: str = Field(
        default="Source operation completed successfully",
        description="Success message",
    )


class SourceConfigResponse(BaseModel):
    """Schema for source configuration response."""

    success: Literal[True] = True
    config: dict = Field(
        ...,
        description="Source configuration",
    )


class UserErrorResponse(BaseModel):
    """Schema for user operation error response."""

    success: Literal[False] = False
    error: str = Field(
        ...,
        description="Error message",
        examples=["User profile not found", "Invalid configuration"],
    )
