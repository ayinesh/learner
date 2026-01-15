"""Content Service - Database-backed implementation."""

import hashlib
import json
import logging
import re
from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import and_, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.content.interface import (
    Content,
    IContentService,
    ProcessedContent,
    RawContent,
    SourceAdapter,
)
from src.modules.content.models import (
    ContentModel,
    TopicModel,
    UserContentInteractionModel,
    UserTopicProgressModel,
)
from src.modules.content.adapters.arxiv import ArxivAdapter, get_arxiv_adapter
from src.modules.content.adapters.rss import RSSAdapter, get_rss_adapter
from src.modules.content.adapters.youtube import YouTubeAdapter, get_youtube_adapter
from src.modules.content.adapters.github import GitHubAdapter, get_github_adapter
from src.modules.content.adapters.reddit import RedditAdapter, get_reddit_adapter
from src.modules.content.adapters.twitter import TwitterAdapter, get_twitter_adapter
from src.modules.content.embeddings import EmbeddingService, get_embedding_service
from src.modules.content.vector_search import VectorSearchService, get_vector_search_service
from src.modules.llm.service import LLMService, get_llm_service
from src.shared.config import get_settings
from src.shared.database import get_db_session
from src.shared.models import SourceType

logger = logging.getLogger(__name__)


class DatabaseContentService(IContentService):
    """Database-backed content service.

    Handles the full content lifecycle:
    1. Ingestion from various sources (arXiv, RSS, etc.)
    2. Processing (summarization, embedding, topic tagging)
    3. Relevance scoring for personalization
    4. Retrieval and search
    """

    def __init__(
        self,
        llm_service: LLMService | None = None,
        embedding_service: EmbeddingService | None = None,
        vector_search_service: VectorSearchService | None = None,
        arxiv_adapter: ArxivAdapter | None = None,
        rss_adapter: RSSAdapter | None = None,
        youtube_adapter: YouTubeAdapter | None = None,
        github_adapter: GitHubAdapter | None = None,
        reddit_adapter: RedditAdapter | None = None,
        twitter_adapter: TwitterAdapter | None = None,
    ) -> None:
        self._llm = llm_service or get_llm_service()
        self._embedding_service = embedding_service or get_embedding_service()
        self._vector_search = vector_search_service or get_vector_search_service()
        self._adapters: dict[SourceType, SourceAdapter] = {}

        # Register all adapters
        self._adapters[SourceType.ARXIV] = arxiv_adapter or get_arxiv_adapter()

        rss = rss_adapter or get_rss_adapter()
        self._adapters[SourceType.BLOG] = rss
        self._adapters[SourceType.NEWSLETTER] = rss

        self._adapters[SourceType.YOUTUBE] = youtube_adapter or get_youtube_adapter()
        self._adapters[SourceType.GITHUB] = github_adapter or get_github_adapter()
        self._adapters[SourceType.REDDIT] = reddit_adapter or get_reddit_adapter()
        self._adapters[SourceType.TWITTER] = twitter_adapter or get_twitter_adapter()

        logger.info(f"DatabaseContentService initialized with {len(self._adapters)} adapters")

    async def ingest_from_source(
        self,
        source_type: SourceType,
        config: dict,
        user_id: UUID | None = None,
    ) -> list[UUID]:
        """Ingest content from a source."""
        adapter = self._adapters.get(source_type)
        if adapter is None:
            raise ValueError(f"No adapter registered for source type: {source_type}")

        # Validate config
        if not await adapter.validate_config(config):
            raise ValueError(f"Invalid configuration for {source_type}")

        # Fetch new content
        raw_items = await adapter.fetch_new(config, since=None)

        ingested_ids: list[UUID] = []

        async with get_db_session() as session:
            for raw in raw_items:
                # Check for duplicates by URL
                existing = await session.execute(
                    select(ContentModel.id).where(
                        ContentModel.source_url == raw.source_url
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                # Create content record
                content_id = uuid4()
                content = ContentModel(
                    id=content_id,
                    source_type=raw.source_type.value,
                    source_url=raw.source_url,
                    title=raw.title,
                    raw_content=raw.content,
                    author=raw.author,
                    published_at=raw.published_at,
                    created_at=datetime.utcnow(),
                )
                session.add(content)
                ingested_ids.append(content_id)

        return ingested_ids

    async def process_content(self, content_id: UUID) -> ProcessedContent:
        """Process raw content through the pipeline."""
        async with get_db_session() as session:
            result = await session.execute(
                select(ContentModel).where(ContentModel.id == content_id)
            )
            content = result.scalar_one_or_none()

            if content is None:
                raise ValueError(f"Content not found: {content_id}")

            # Already processed?
            if content.processed_at is not None:
                return self._model_to_processed(content)

            raw_content = content.raw_content or ""

            # Clean and normalize content
            cleaned_content = self._clean_content(raw_content)

            # Generate summary using LLM
            summary = await self._generate_summary(content.title, cleaned_content)

            # Generate embedding
            embedding = await self._generate_embedding(f"{content.title} {summary}")

            # Extract topics using LLM
            topic_ids = await self._extract_topics(
                session, content.title, summary, cleaned_content
            )

            # Assess difficulty
            difficulty = await self._assess_difficulty(content.title, cleaned_content)

            # Calculate importance score
            importance = self._calculate_importance(
                SourceType(content.source_type),
                content.published_at,
            )

            # Update content record
            content.processed_content = cleaned_content
            content.summary = summary
            content.embedding = embedding
            content.topics = topic_ids
            content.difficulty_level = difficulty
            content.importance_score = importance
            content.processed_at = datetime.utcnow()

            await session.commit()
            await session.refresh(content)

            return self._model_to_processed(content)

    async def score_relevance(self, content_id: UUID, user_id: UUID) -> float:
        """Score content relevance for a specific user."""
        async with get_db_session() as session:
            # Get content
            result = await session.execute(
                select(ContentModel).where(ContentModel.id == content_id)
            )
            content = result.scalar_one_or_none()

            if content is None or content.processed_at is None:
                return 0.0

            # Get user interaction
            interaction_result = await session.execute(
                select(UserContentInteractionModel).where(
                    and_(
                        UserContentInteractionModel.user_id == user_id,
                        UserContentInteractionModel.content_id == content_id,
                    )
                )
            )
            interaction = interaction_result.scalar_one_or_none()

            # Get user's topic progress
            user_topic_result = await session.execute(
                select(UserTopicProgressModel).where(
                    UserTopicProgressModel.user_id == user_id
                )
            )
            user_topics = {
                row.topic_id: row.proficiency_level
                for row in user_topic_result.scalars().all()
            }

            # Calculate component scores
            scores: list[float] = []

            # Topic alignment (0-1)
            content_topics = content.topics or []
            if user_topics and content_topics:
                matching = sum(
                    1 for t in content_topics if t in user_topics
                )
                topic_score = min(matching / max(len(content_topics), 1), 1.0)
            else:
                topic_score = 0.5
            scores.append(topic_score * 0.35)

            # Difficulty match (0-1) - use average proficiency
            avg_proficiency = (
                sum(user_topics.values()) / len(user_topics)
                if user_topics
                else 0.5
            )
            # Map proficiency to preferred difficulty (0->1, 1->5)
            preferred_difficulty = 1 + (avg_proficiency * 4)
            diff_delta = abs(content.difficulty_level - preferred_difficulty)
            difficulty_score = 1.0 - (diff_delta / 4.0)
            scores.append(max(difficulty_score, 0.0) * 0.15)

            # Novelty - penalize already seen content
            novelty_score = 0.0 if (interaction and interaction.completed) else 1.0
            scores.append(novelty_score * 0.20)

            # Recency (0-1) - decay over 30 days
            if content.created_at:
                age_days = (datetime.utcnow() - content.created_at).days
                recency_score = max(1.0 - (age_days / 30.0), 0.0)
            else:
                recency_score = 0.5
            scores.append(recency_score * 0.15)

            # Importance score directly
            scores.append(content.importance_score * 0.15)

            return sum(scores)

    def _score_content_batch(
        self,
        content: ContentModel,
        user_topics: dict[UUID, float],
        user_interactions: dict[UUID, bool],
    ) -> float:
        """Score content relevance using pre-loaded user data.

        This is an optimized version that doesn't make database calls.

        Args:
            content: The content model to score
            user_topics: Dict mapping topic_id to proficiency_level
            user_interactions: Dict mapping content_id to completed status

        Returns:
            Relevance score between 0.0 and 1.0
        """
        if content.processed_at is None:
            return 0.0

        scores: list[float] = []

        # Topic alignment (0-1)
        content_topics = content.topics or []
        if user_topics and content_topics:
            matching = sum(1 for t in content_topics if t in user_topics)
            topic_score = min(matching / max(len(content_topics), 1), 1.0)
        else:
            topic_score = 0.5
        scores.append(topic_score * 0.35)

        # Difficulty match (0-1)
        avg_proficiency = (
            sum(user_topics.values()) / len(user_topics)
            if user_topics
            else 0.5
        )
        preferred_difficulty = 1 + (avg_proficiency * 4)
        diff_delta = abs(content.difficulty_level - preferred_difficulty)
        difficulty_score = 1.0 - (diff_delta / 4.0)
        scores.append(max(difficulty_score, 0.0) * 0.15)

        # Novelty - penalize already seen content
        is_completed = user_interactions.get(content.id, False)
        novelty_score = 0.0 if is_completed else 1.0
        scores.append(novelty_score * 0.20)

        # Recency (0-1) - decay over 30 days
        if content.created_at:
            age_days = (datetime.utcnow() - content.created_at).days
            recency_score = max(1.0 - (age_days / 30.0), 0.0)
        else:
            recency_score = 0.5
        scores.append(recency_score * 0.15)

        # Importance score directly
        scores.append(content.importance_score * 0.15)

        return sum(scores)

    async def get_relevant_content(
        self,
        user_id: UUID,
        limit: int = 10,
        min_relevance: float = 0.5,
        source_types: Optional[list[SourceType]] = None,
    ) -> list[Content]:
        """Get most relevant content for a user.

        Optimized to batch-load user data to avoid N+1 queries.
        """
        async with get_db_session() as session:
            # Build query for processed content
            query = select(ContentModel).where(
                ContentModel.processed_at.isnot(None)
            )

            if source_types:
                query = query.where(
                    ContentModel.source_type.in_([s.value for s in source_types])
                )

            # Order by importance and recency
            query = query.order_by(
                desc(ContentModel.importance_score),
                desc(ContentModel.created_at),
            ).limit(limit * 3)  # Get more for scoring

            result = await session.execute(query)
            contents = result.scalars().all()

            if not contents:
                return []

            # Batch load user's topic progress (single query instead of N queries)
            user_topic_result = await session.execute(
                select(UserTopicProgressModel).where(
                    UserTopicProgressModel.user_id == user_id
                )
            )
            user_topics = {
                row.topic_id: row.proficiency_level
                for row in user_topic_result.scalars().all()
            }

            # Batch load user's content interactions (single query instead of N queries)
            content_ids = [c.id for c in contents]
            interaction_result = await session.execute(
                select(UserContentInteractionModel).where(
                    and_(
                        UserContentInteractionModel.user_id == user_id,
                        UserContentInteractionModel.content_id.in_(content_ids),
                    )
                )
            )
            user_interactions = {
                row.content_id: row.completed
                for row in interaction_result.scalars().all()
            }

            # Score using batch-loaded data (no additional DB calls)
            scored: list[tuple[float, ContentModel]] = []
            for content in contents:
                score = self._score_content_batch(content, user_topics, user_interactions)
                if score >= min_relevance:
                    scored.append((score, content))

            # Sort by score
            scored.sort(key=lambda x: x[0], reverse=True)

            # Convert to Content objects
            return [
                self._model_to_content(c, score)
                for score, c in scored[:limit]
            ]

    async def search_content(
        self,
        query: str,
        user_id: UUID,
        limit: int = 10,
    ) -> list[Content]:
        """Search content semantically using vector similarity and keywords.

        This method uses hybrid search combining:
        - Vector similarity (semantic search via embeddings)
        - Keyword matching (traditional text search)

        Args:
            query: Search query text
            user_id: User ID for personalized scoring
            limit: Maximum number of results

        Returns:
            List of relevant content items sorted by combined score
        """
        # Generate embedding for the query
        query_embedding = await self._generate_embedding(query)

        # Use vector search service for hybrid search
        search_results = await self._vector_search.hybrid_search(
            query_text=query,
            query_embedding=query_embedding,
            limit=limit * 2,  # Get more for personalized re-ranking
            vector_weight=0.6,
            keyword_weight=0.4,
        )

        if not search_results:
            return []

        # Load content models and apply personalized scoring
        async with get_db_session() as session:
            content_ids = [cid for cid, _ in search_results]
            result = await session.execute(
                select(ContentModel).where(ContentModel.id.in_(content_ids))
            )
            content_map = {c.id: c for c in result.scalars().all()}

            # Batch load user data for efficient scoring
            user_topic_result = await session.execute(
                select(UserTopicProgressModel).where(
                    UserTopicProgressModel.user_id == user_id
                )
            )
            user_topics = {
                row.topic_id: row.proficiency_level
                for row in user_topic_result.scalars().all()
            }

            interaction_result = await session.execute(
                select(UserContentInteractionModel).where(
                    and_(
                        UserContentInteractionModel.user_id == user_id,
                        UserContentInteractionModel.content_id.in_(content_ids),
                    )
                )
            )
            user_interactions = {
                row.content_id: row.completed
                for row in interaction_result.scalars().all()
            }

            # Re-rank with personalized relevance
            scored: list[tuple[float, ContentModel]] = []
            for content_id, search_score in search_results:
                content = content_map.get(content_id)
                if not content:
                    continue

                # Calculate personalized relevance
                relevance = self._score_content_batch(
                    content, user_topics, user_interactions
                )

                # Combine search score with personalized relevance
                combined_score = (search_score * 0.5) + (relevance * 0.5)
                scored.append((combined_score, content))

            # Sort by combined score
            scored.sort(key=lambda x: x[0], reverse=True)

            return [
                self._model_to_content(c, score)
                for score, c in scored[:limit]
            ]

    async def vector_search_content(
        self,
        query_embedding: list[float],
        user_id: UUID,
        limit: int = 10,
        source_types: list[SourceType] | None = None,
        min_similarity: float = 0.5,
    ) -> list[Content]:
        """Search content using pure vector similarity.

        This method performs semantic search using only embedding similarity,
        without keyword matching. Useful for exploratory search or
        when you have a pre-computed embedding.

        Args:
            query_embedding: Pre-computed query embedding vector
            user_id: User ID for context
            limit: Maximum number of results
            source_types: Optional filter by source types
            min_similarity: Minimum cosine similarity threshold

        Returns:
            List of semantically similar content items
        """
        # Use vector search service
        results = await self._vector_search.similarity_search_with_content(
            query_embedding=query_embedding,
            limit=limit,
            source_types=source_types,
            min_similarity=min_similarity,
        )

        # Convert to Content objects
        return [
            self._model_to_content(content, similarity)
            for content, similarity in results
        ]

    async def get_content_by_topic(
        self,
        topic_id: UUID,
        user_id: UUID,
        limit: int = 10,
    ) -> list[Content]:
        """Get content for a specific topic."""
        async with get_db_session() as session:
            # Use array contains for topics
            query = (
                select(ContentModel)
                .where(ContentModel.processed_at.isnot(None))
                .where(ContentModel.topics.contains([topic_id]))
                .limit(limit * 2)
            )

            result = await session.execute(query)
            contents = result.scalars().all()

            # Score and sort
            scored: list[tuple[float, ContentModel]] = []
            for content in contents:
                score = await self.score_relevance(content.id, user_id)
                scored.append((score, content))

            scored.sort(key=lambda x: x[0], reverse=True)

            return [
                self._model_to_content(c, score)
                for score, c in scored[:limit]
            ]

    async def get_content(self, content_id: UUID) -> Optional[Content]:
        """Get a single content item by ID."""
        async with get_db_session() as session:
            result = await session.execute(
                select(ContentModel).where(ContentModel.id == content_id)
            )
            content = result.scalar_one_or_none()

            if content is None:
                return None

            return self._model_to_content(content, content.importance_score)

    async def mark_content_seen(self, content_id: UUID, user_id: UUID) -> None:
        """Mark content as seen by user."""
        async with get_db_session() as session:
            # Check if interaction exists
            result = await session.execute(
                select(UserContentInteractionModel).where(
                    and_(
                        UserContentInteractionModel.user_id == user_id,
                        UserContentInteractionModel.content_id == content_id,
                    )
                )
            )
            interaction = result.scalar_one_or_none()

            if interaction is None:
                interaction = UserContentInteractionModel(
                    user_id=user_id,
                    content_id=content_id,
                    presented_at=datetime.utcnow(),
                )
                session.add(interaction)
            else:
                interaction.completed = True

    async def record_feedback(
        self,
        content_id: UUID,
        user_id: UUID,
        relevance_rating: int,
        notes: str | None = None,
    ) -> None:
        """Record user feedback on content."""
        async with get_db_session() as session:
            # Get or create interaction
            result = await session.execute(
                select(UserContentInteractionModel).where(
                    and_(
                        UserContentInteractionModel.user_id == user_id,
                        UserContentInteractionModel.content_id == content_id,
                    )
                )
            )
            interaction = result.scalar_one_or_none()

            if interaction is None:
                interaction = UserContentInteractionModel(
                    user_id=user_id,
                    content_id=content_id,
                    presented_at=datetime.utcnow(),
                    relevance_feedback=relevance_rating,
                    notes=notes,
                )
                session.add(interaction)
            else:
                interaction.relevance_feedback = relevance_rating
                if notes:
                    interaction.notes = notes

    async def get_user_topics(self, user_id: UUID) -> list[dict]:
        """Get topics for a user based on their content interactions."""
        async with get_db_session() as session:
            # Get content the user has interacted with
            interactions = await session.execute(
                select(UserContentInteractionModel.content_id).where(
                    UserContentInteractionModel.user_id == user_id
                )
            )
            content_ids = [row for row in interactions.scalars().all()]

            if not content_ids:
                return []

            # Get topics from those content items
            result = await session.execute(
                select(ContentModel.topics).where(
                    ContentModel.id.in_(content_ids)
                )
            )

            # Count topic occurrences
            topic_counts: dict[UUID, int] = {}
            for row in result.scalars().all():
                for topic_id in (row or []):
                    topic_counts[topic_id] = topic_counts.get(topic_id, 0) + 1

            # Get topic names
            topics: list[dict] = []
            for topic_id, count in sorted(
                topic_counts.items(), key=lambda x: x[1], reverse=True
            ):
                topic_result = await session.execute(
                    select(TopicModel).where(TopicModel.id == topic_id)
                )
                topic = topic_result.scalar_one_or_none()
                if topic:
                    topics.append({
                        "id": topic_id,
                        "name": topic.name,
                        "content_count": count,
                    })
                else:
                    topics.append({
                        "id": topic_id,
                        "name": str(topic_id)[:8],
                        "content_count": count,
                    })

            return topics

    # --- Private methods ---

    def _clean_content(self, content: str) -> str:
        """Clean and normalize content text."""
        cleaned = " ".join(content.split())
        cleaned = re.sub(r"\[.*?\]", "", cleaned)
        return cleaned.strip()

    async def _generate_summary(self, title: str, content: str) -> str:
        """Generate a concise summary using LLM."""
        if len(content) < 100:
            return content

        prompt = f"""Summarize this content in 2-3 sentences, focusing on the key insights:

Title: {title}

Content:
{content[:3000]}

Provide a concise summary:"""

        try:
            response = await self._llm.complete(
                prompt=prompt,
                system_prompt="You are a content summarizer. Provide concise, informative summaries.",
                temperature=0.3,
                max_tokens=200,
            )
            return response.content.strip()
        except Exception:
            return content[:200] + "..."

    async def _generate_embedding(self, text: str) -> list[float]:
        """Generate embedding vector for text using configured embedding service.

        Uses the embedding service which automatically selects between:
        - OpenAI embeddings (if FF_ENABLE_REAL_EMBEDDINGS is true and API key is set)
        - Placeholder embeddings (for development/testing)

        Args:
            text: Text to generate embedding for

        Returns:
            1536-dimensional embedding vector
        """
        return await self._embedding_service.generate(text)

    async def _extract_topics(
        self,
        session: AsyncSession,
        title: str,
        summary: str,
        content: str,
    ) -> list[UUID]:
        """Extract topic IDs from content using LLM."""
        prompt = f"""Identify the main topics (3-5) covered in this content:

Title: {title}
Summary: {summary}

List the main topics as keywords, one per line:"""

        try:
            response = await self._llm.complete(
                prompt=prompt,
                system_prompt="You extract topic keywords from content. List one topic per line.",
                temperature=0.2,
                max_tokens=100,
            )

            topic_ids: list[UUID] = []
            for line in response.content.strip().split("\n"):
                topic_name = line.strip().lower()
                if not topic_name:
                    continue

                # Look up or create topic
                result = await session.execute(
                    select(TopicModel).where(
                        func.lower(TopicModel.name) == topic_name
                    )
                )
                topic = result.scalar_one_or_none()

                if topic is None:
                    topic = TopicModel(
                        id=uuid4(),
                        name=topic_name,
                    )
                    session.add(topic)
                    await session.flush()

                topic_ids.append(topic.id)

            return topic_ids[:5]
        except Exception:
            return []

    async def _assess_difficulty(self, title: str, content: str) -> int:
        """Assess content difficulty level (1-5) using LLM."""
        prompt = f"""Rate the difficulty level of this content from 1-5:
1 = Beginner, no prior knowledge needed
2 = Basic, some familiarity helpful
3 = Intermediate, requires foundational knowledge
4 = Advanced, requires significant background
5 = Expert, requires deep domain expertise

Title: {title}
Content preview: {content[:1000]}

Respond with just the number (1-5):"""

        try:
            response = await self._llm.complete(
                prompt=prompt,
                system_prompt="You assess content difficulty. Respond with a single number 1-5.",
                temperature=0.1,
                max_tokens=5,
            )

            difficulty = int(response.content.strip()[0])
            return max(1, min(5, difficulty))
        except Exception:
            return 3

    def _calculate_importance(
        self,
        source_type: SourceType,
        published_at: Optional[datetime],
    ) -> float:
        """Calculate initial importance score based on metadata."""
        score = 0.5

        if published_at:
            age_days = (datetime.utcnow() - published_at).days
            if age_days < 7:
                score += 0.2
            elif age_days < 30:
                score += 0.1

        if source_type == SourceType.ARXIV:
            score += 0.1

        return min(score, 1.0)

    def _model_to_processed(self, content: ContentModel) -> ProcessedContent:
        """Convert ContentModel to ProcessedContent."""
        return ProcessedContent(
            id=content.id,
            source_type=SourceType(content.source_type),
            source_url=content.source_url,
            title=content.title,
            raw_content=content.raw_content or "",
            processed_content=content.processed_content or "",
            summary=content.summary or "",
            embedding=list(content.embedding) if content.embedding else [],
            topics=content.topics or [],
            difficulty_level=content.difficulty_level,
            importance_score=content.importance_score,
            created_at=content.created_at,
        )

    def _model_to_content(
        self,
        content: ContentModel,
        relevance_score: float,
    ) -> Content:
        """Convert ContentModel to Content."""
        # Convert topic UUIDs to names (simplified)
        topic_names = [str(t)[:8] for t in (content.topics or [])]

        return Content(
            id=content.id,
            title=content.title,
            summary=content.summary or "",
            content=content.processed_content or "",
            source_type=SourceType(content.source_type),
            source_url=content.source_url,
            topics=topic_names,
            difficulty_level=content.difficulty_level,
            relevance_score=relevance_score,
            created_at=content.created_at,
        )


# Factory function
_db_content_service: DatabaseContentService | None = None


def get_db_content_service() -> DatabaseContentService:
    """Get database content service singleton."""
    global _db_content_service
    if _db_content_service is None:
        _db_content_service = DatabaseContentService()
    return _db_content_service
