"""Base models and common types used across modules."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class TimestampMixin(BaseModel):
    """Mixin for created/updated timestamps."""

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UUIDMixin(BaseModel):
    """Mixin for UUID primary key."""

    id: UUID = Field(default_factory=uuid4)


# Common response types


class SuccessResponse(BaseSchema):
    """Generic success response."""

    success: bool = True
    message: str = "Operation completed successfully"


class ErrorResponse(BaseSchema):
    """Generic error response."""

    success: bool = False
    error: str
    details: dict[str, Any] | None = None


class PaginatedResponse(BaseSchema):
    """Paginated list response."""

    items: list[Any]
    total: int
    page: int
    page_size: int
    has_more: bool


# Common enums and types

from enum import Enum


class SourceType(str, Enum):
    """Content source types."""

    ARXIV = "arxiv"
    TWITTER = "twitter"
    YOUTUBE = "youtube"
    NEWSLETTER = "newsletter"
    BLOG = "blog"
    GITHUB = "github"
    REDDIT = "reddit"
    DISCORD = "discord"


class SessionStatus(str, Enum):
    """Learning session status."""

    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class SessionType(str, Enum):
    """Type of learning session."""

    REGULAR = "regular"
    CATCHUP = "catchup"
    DRILL = "drill"


class ActivityType(str, Enum):
    """Types of activities within a session."""

    CONTENT_READ = "content_read"
    QUIZ = "quiz"
    FEYNMAN_DIALOGUE = "feynman_dialogue"
    DRILL = "drill"
    REFLECTION = "reflection"


class AdaptationType(str, Enum):
    """Types of system adaptations."""

    PACE_ADJUSTMENT = "pace_adjustment"
    CURRICULUM_CHANGE = "curriculum_change"
    DIFFICULTY_CHANGE = "difficulty_change"
    RECOVERY_PLAN = "recovery_plan"
