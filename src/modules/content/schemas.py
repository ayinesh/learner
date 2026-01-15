"""Pydantic schemas for Content module."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from src.shared.models import SourceType


class ContentSchema(BaseModel):
    """Content schema for API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_type: SourceType
    source_url: str
    title: str
    raw_content: Optional[str] = None
    processed_content: Optional[str] = None
    summary: Optional[str] = None
    topics: list[UUID] = Field(default_factory=list)
    difficulty_level: int = 3
    importance_score: float = 0.5
    relevance_score: float = 0.5  # For user-specific relevance
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    created_at: datetime
    processed_at: Optional[datetime] = None


class ContentCreateRequest(BaseModel):
    """Request schema for creating content."""

    source_type: SourceType
    source_url: str
    title: str
    raw_content: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[datetime] = None


class ContentProcessRequest(BaseModel):
    """Request schema for processing content."""

    content_id: UUID


class ContentSearchRequest(BaseModel):
    """Request schema for searching content."""

    query: str
    limit: int = 10
    source_types: Optional[list[SourceType]] = None


class ContentFeedbackRequest(BaseModel):
    """Request schema for content feedback."""

    content_id: UUID
    relevance_rating: int = Field(..., ge=1, le=5)
    notes: Optional[str] = None


class UserContentInteractionSchema(BaseModel):
    """User content interaction schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    content_id: UUID
    presented_at: datetime
    completed: bool = False
    time_spent_seconds: int = 0
    relevance_feedback: Optional[int] = None
    notes: Optional[str] = None


class TopicSchema(BaseModel):
    """Topic schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: Optional[str] = None
    prerequisites: list[UUID] = Field(default_factory=list)
    difficulty_level: int = 3
    created_at: datetime


class UserTopicProgressSchema(BaseModel):
    """User topic progress schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    topic_id: UUID
    proficiency_level: float = 0.0
    last_practiced: Optional[datetime] = None
    next_review: Optional[datetime] = None
    practice_count: int = 0
    interleaving_eligible: bool = False
    ease_factor: float = 2.5
    interval_days: int = 1


class SourceConfigSchema(BaseModel):
    """Source configuration schema."""

    source_type: SourceType
    config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class IngestFromSourceRequest(BaseModel):
    """Request schema for ingesting from a source."""

    source_type: SourceType
    config: dict[str, Any] = Field(default_factory=dict)


class ProcessedContentSchema(BaseModel):
    """Processed content schema with additional user-specific data."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_type: SourceType
    source_url: str
    title: str
    summary: Optional[str] = None
    topics: list[str] = Field(default_factory=list)  # Topic names
    difficulty_level: int = 3
    relevance_score: float = 0.5
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    created_at: datetime
