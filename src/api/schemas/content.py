"""Content API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from src.shared.models import SourceType


class ContentResponse(BaseModel):
    """Content item response."""

    id: UUID = Field(
        ...,
        description="Content unique identifier",
    )
    title: str = Field(
        ...,
        description="Content title",
    )
    summary: str = Field(
        ...,
        description="Content summary",
    )
    source_type: SourceType = Field(
        ...,
        description="Source type (arxiv, youtube, etc.)",
    )
    source_url: str = Field(
        ...,
        description="Original source URL",
    )
    topics: list[str] = Field(
        default_factory=list,
        description="Associated topics",
    )
    difficulty_level: int = Field(
        ...,
        ge=1,
        le=5,
        description="Difficulty level (1-5)",
    )
    relevance_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Relevance score for user (0-1)",
    )
    importance_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Content importance score (0-1)",
    )
    created_at: datetime = Field(
        ...,
        description="Content creation timestamp",
    )

    model_config = {"from_attributes": True}


class ContentDetailResponse(ContentResponse):
    """Detailed content response with full text."""

    raw_content: str = Field(
        ...,
        description="Original raw content",
    )
    processed_content: str = Field(
        ...,
        description="Processed/cleaned content",
    )
    authors: list[str] | None = Field(
        default=None,
        description="Content authors",
    )
    published_at: datetime | None = Field(
        default=None,
        description="Original publication date",
    )


class ContentFeedRequest(BaseModel):
    """Content feed request parameters."""

    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum items to return",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Offset for pagination",
    )
    source_types: list[SourceType] | None = Field(
        default=None,
        description="Filter by source types",
    )
    topic_ids: list[UUID] | None = Field(
        default=None,
        description="Filter by topic IDs",
    )
    min_relevance: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum relevance score",
    )


class ContentFeedResponse(BaseModel):
    """Content feed response."""

    items: list[ContentResponse] = Field(
        ...,
        description="Content items",
    )
    total: int = Field(
        ...,
        description="Total available items",
    )
    has_more: bool = Field(
        ...,
        description="Whether more items exist",
    )


class ContentFeedbackRequest(BaseModel):
    """Content feedback request."""

    relevance_rating: int = Field(
        ...,
        ge=1,
        le=5,
        description="Relevance rating (1-5)",
    )
    notes: str | None = Field(
        default=None,
        max_length=500,
        description="Optional feedback notes",
    )


class ContentSearchRequest(BaseModel):
    """Content search request."""

    query: str = Field(
        ...,
        min_length=2,
        max_length=200,
        description="Search query",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum results",
    )
    source_types: list[SourceType] | None = Field(
        default=None,
        description="Filter by source types",
    )


class ContentSearchResponse(BaseModel):
    """Content search response."""

    items: list[ContentResponse] = Field(
        ...,
        description="Matching content items",
    )
    total: int = Field(
        ...,
        description="Total matches",
    )
    query: str = Field(
        ...,
        description="Original query",
    )


class IngestContentRequest(BaseModel):
    """Content ingestion request (admin)."""

    source_type: SourceType = Field(
        ...,
        description="Source type to ingest from",
    )
    config: dict = Field(
        default_factory=dict,
        description="Source-specific configuration",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum items to ingest",
    )


class IngestContentResponse(BaseModel):
    """Content ingestion response."""

    success: bool = Field(
        ...,
        description="Whether ingestion succeeded",
    )
    items_ingested: int = Field(
        ...,
        description="Number of items ingested",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Any errors encountered",
    )
