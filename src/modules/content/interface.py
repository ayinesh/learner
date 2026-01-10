"""Content Module - Ingestion, processing, and retrieval."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from uuid import UUID

from src.shared.models import SourceType


@dataclass
class RawContent:
    """Raw content from a source before processing."""

    source_type: SourceType
    source_url: str
    title: str
    content: str
    author: str | None = None
    published_at: datetime | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class ProcessedContent:
    """Content after processing pipeline."""

    id: UUID
    source_type: SourceType
    source_url: str
    title: str
    raw_content: str
    processed_content: str  # Cleaned and chunked
    summary: str
    embedding: list[float]  # Vector embedding
    topics: list[UUID]  # Related topic IDs
    difficulty_level: int  # 1-5
    importance_score: float  # 0-1
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Content:
    """Content ready for delivery to user."""

    id: UUID
    title: str
    summary: str
    content: str
    source_type: SourceType
    source_url: str
    topics: list[str]  # Topic names
    difficulty_level: int
    relevance_score: float  # Personalized score for this user
    created_at: datetime


class SourceAdapter(ABC):
    """Abstract base class for content source adapters.

    Each content source (arXiv, Twitter, etc.) implements this interface.
    """

    @property
    @abstractmethod
    def source_type(self) -> SourceType:
        """Return the source type this adapter handles."""
        ...

    @abstractmethod
    async def fetch_new(self, config: dict, since: datetime | None = None) -> list[RawContent]:
        """Fetch new content from the source.

        Args:
            config: Source-specific configuration
            since: Only fetch content newer than this timestamp

        Returns:
            List of raw content items
        """
        ...

    @abstractmethod
    async def validate_config(self, config: dict) -> bool:
        """Validate source configuration.

        Args:
            config: Configuration to validate

        Returns:
            True if configuration is valid
        """
        ...


class IContentService(Protocol):
    """Interface for content service.

    Handles content ingestion, processing, and retrieval.
    """

    async def ingest_from_source(
        self,
        source_type: SourceType,
        config: dict,
        user_id: UUID | None = None,
    ) -> list[UUID]:
        """Ingest content from a source.

        Args:
            source_type: Type of source
            config: Source configuration
            user_id: Optional user to associate content with

        Returns:
            List of content IDs that were ingested
        """
        ...

    async def process_content(self, content_id: UUID) -> ProcessedContent:
        """Process raw content through the pipeline.

        Pipeline: clean -> chunk -> summarize -> embed -> tag topics -> assess difficulty

        Args:
            content_id: ID of content to process

        Returns:
            Processed content
        """
        ...

    async def score_relevance(self, content_id: UUID, user_id: UUID) -> float:
        """Score content relevance for a specific user.

        Factors: goal alignment, prerequisite readiness, recency, novelty

        Args:
            content_id: Content to score
            user_id: User to score for

        Returns:
            Relevance score 0-1
        """
        ...

    async def get_relevant_content(
        self,
        user_id: UUID,
        limit: int = 10,
        min_relevance: float = 0.5,
    ) -> list[Content]:
        """Get most relevant content for a user.

        Args:
            user_id: User to get content for
            limit: Maximum number of items
            min_relevance: Minimum relevance score threshold

        Returns:
            List of content sorted by relevance
        """
        ...

    async def search_content(
        self,
        query: str,
        user_id: UUID,
        limit: int = 10,
    ) -> list[Content]:
        """Search content semantically.

        Args:
            query: Search query
            user_id: User context for personalization
            limit: Maximum results

        Returns:
            List of matching content
        """
        ...

    async def get_content_by_topic(
        self,
        topic_id: UUID,
        user_id: UUID,
        limit: int = 10,
    ) -> list[Content]:
        """Get content for a specific topic.

        Args:
            topic_id: Topic to get content for
            user_id: User context
            limit: Maximum results

        Returns:
            List of content for the topic
        """
        ...

    async def mark_content_seen(self, content_id: UUID, user_id: UUID) -> None:
        """Mark content as seen by user.

        Args:
            content_id: Content that was seen
            user_id: User who saw it
        """
        ...

    async def record_feedback(
        self,
        content_id: UUID,
        user_id: UUID,
        relevance_rating: int,
        notes: str | None = None,
    ) -> None:
        """Record user feedback on content.

        Args:
            content_id: Content being rated
            user_id: User providing feedback
            relevance_rating: 1-5 rating
            notes: Optional notes
        """
        ...
