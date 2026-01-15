"""Content Service - Business logic for content management."""

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from src.modules.content.interface import (
    Content,
    IContentService,
    ProcessedContent,
    RawContent,
    SourceAdapter,
)
from src.modules.content.adapters.arxiv import ArxivAdapter, get_arxiv_adapter
from src.modules.content.adapters.rss import RSSAdapter, get_rss_adapter
from src.modules.content.adapters.youtube import YouTubeAdapter, get_youtube_adapter
from src.modules.content.adapters.github import GitHubAdapter, get_github_adapter
from src.modules.content.adapters.reddit import RedditAdapter, get_reddit_adapter
from src.modules.content.adapters.twitter import TwitterAdapter, get_twitter_adapter
from src.modules.llm.service import LLMService, get_llm_service
from src.shared.models import SourceType


@dataclass
class StoredContent:
    """Content stored in the system."""

    id: UUID
    raw: RawContent
    processed: ProcessedContent | None = None
    seen_by: set[UUID] = field(default_factory=set)
    feedback: list[dict] = field(default_factory=list)


@dataclass
class UserContentProfile:
    """User's content interaction profile."""

    user_id: UUID
    topics_of_interest: list[UUID] = field(default_factory=list)
    difficulty_preference: int = 3  # 1-5
    seen_content: set[UUID] = field(default_factory=set)
    feedback_history: list[dict] = field(default_factory=list)


class ContentService(IContentService):
    """Service for content ingestion, processing, and retrieval.

    Handles the full content lifecycle:
    1. Ingestion from various sources (arXiv, RSS, etc.)
    2. Processing (summarization, embedding, topic tagging)
    3. Relevance scoring for personalization
    4. Retrieval and search
    """

    def __init__(
        self,
        llm_service: LLMService | None = None,
        arxiv_adapter: ArxivAdapter | None = None,
        rss_adapter: RSSAdapter | None = None,
        youtube_adapter: YouTubeAdapter | None = None,
        github_adapter: GitHubAdapter | None = None,
        reddit_adapter: RedditAdapter | None = None,
        twitter_adapter: TwitterAdapter | None = None,
    ) -> None:
        self._llm = llm_service or get_llm_service()
        self._adapters: dict[SourceType, SourceAdapter] = {}

        # Register adapters
        self._adapters[SourceType.ARXIV] = arxiv_adapter or get_arxiv_adapter()
        rss = rss_adapter or get_rss_adapter()
        self._adapters[SourceType.BLOG] = rss
        self._adapters[SourceType.NEWSLETTER] = rss
        self._adapters[SourceType.YOUTUBE] = youtube_adapter or get_youtube_adapter()
        self._adapters[SourceType.GITHUB] = github_adapter or get_github_adapter()
        self._adapters[SourceType.REDDIT] = reddit_adapter or get_reddit_adapter()
        self._adapters[SourceType.TWITTER] = twitter_adapter or get_twitter_adapter()

        # In-memory storage (use DB in production)
        self._content: dict[UUID, StoredContent] = {}
        self._url_index: dict[str, UUID] = {}  # URL -> content ID
        self._topic_index: dict[UUID, set[UUID]] = {}  # topic ID -> content IDs
        self._user_profiles: dict[UUID, UserContentProfile] = {}

        # Track ingestion timestamps per source
        self._last_ingested: dict[str, datetime] = {}

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
        adapter = self._adapters.get(source_type)
        if adapter is None:
            raise ValueError(f"No adapter registered for source type: {source_type}")

        # Validate config
        if not await adapter.validate_config(config):
            raise ValueError(f"Invalid configuration for {source_type}")

        # Get last ingestion time for incremental fetching
        source_key = f"{source_type.value}:{hashlib.md5(json.dumps(config, sort_keys=True).encode()).hexdigest()}"
        since = self._last_ingested.get(source_key)

        # Fetch new content
        raw_items = await adapter.fetch_new(config, since)

        # Store and deduplicate
        ingested_ids: list[UUID] = []
        for raw in raw_items:
            # Check for duplicates by URL
            existing_id = self._url_index.get(raw.source_url)
            if existing_id:
                continue

            # Create stored content
            content_id = uuid4()
            stored = StoredContent(id=content_id, raw=raw)
            self._content[content_id] = stored
            self._url_index[raw.source_url] = content_id
            ingested_ids.append(content_id)

        # Update last ingestion time
        self._last_ingested[source_key] = datetime.utcnow()

        return ingested_ids

    async def process_content(self, content_id: UUID) -> ProcessedContent:
        """Process raw content through the pipeline.

        Pipeline: clean -> summarize -> embed -> tag topics -> assess difficulty

        Args:
            content_id: ID of content to process

        Returns:
            Processed content
        """
        stored = self._content.get(content_id)
        if stored is None:
            raise ValueError(f"Content not found: {content_id}")

        # Already processed?
        if stored.processed is not None:
            return stored.processed

        raw = stored.raw

        # Clean and normalize content
        cleaned_content = self._clean_content(raw.content)

        # Generate summary using LLM
        summary = await self._generate_summary(raw.title, cleaned_content)

        # Generate embedding (placeholder - would use actual embedding model)
        embedding = await self._generate_embedding(f"{raw.title} {summary}")

        # Extract topics using LLM
        topics = await self._extract_topics(raw.title, summary, cleaned_content)

        # Assess difficulty
        difficulty = await self._assess_difficulty(raw.title, cleaned_content)

        # Calculate initial importance score
        importance = self._calculate_importance(raw)

        processed = ProcessedContent(
            id=content_id,
            source_type=raw.source_type,
            source_url=raw.source_url,
            title=raw.title,
            raw_content=raw.content,
            processed_content=cleaned_content,
            summary=summary,
            embedding=embedding,
            topics=topics,
            difficulty_level=difficulty,
            importance_score=importance,
            created_at=datetime.utcnow(),
        )

        stored.processed = processed

        # Update topic index
        for topic_id in topics:
            if topic_id not in self._topic_index:
                self._topic_index[topic_id] = set()
            self._topic_index[topic_id].add(content_id)

        return processed

    async def score_relevance(self, content_id: UUID, user_id: UUID) -> float:
        """Score content relevance for a specific user.

        Factors:
        - Topic alignment with user interests
        - Difficulty match
        - Novelty (not seen before)
        - Recency
        - Importance

        Args:
            content_id: Content to score
            user_id: User to score for

        Returns:
            Relevance score 0-1
        """
        stored = self._content.get(content_id)
        if stored is None:
            return 0.0

        # Ensure content is processed
        if stored.processed is None:
            await self.process_content(content_id)

        processed = stored.processed
        if processed is None:
            return 0.0

        # Get or create user profile
        profile = await self._get_or_create_profile(user_id)

        # Calculate component scores
        scores: list[float] = []

        # Topic alignment (0-1)
        if profile.topics_of_interest and processed.topics:
            matching = len(set(processed.topics) & set(profile.topics_of_interest))
            topic_score = min(matching / max(len(processed.topics), 1), 1.0)
        else:
            topic_score = 0.5  # Neutral if no preferences
        scores.append(topic_score * 0.35)

        # Difficulty match (0-1)
        diff_delta = abs(processed.difficulty_level - profile.difficulty_preference)
        difficulty_score = 1.0 - (diff_delta / 4.0)  # Max diff is 4 (1 vs 5)
        scores.append(max(difficulty_score, 0.0) * 0.15)

        # Novelty - penalize already seen content
        novelty_score = 0.0 if content_id in profile.seen_content else 1.0
        scores.append(novelty_score * 0.20)

        # Recency (0-1) - decay over 30 days
        if processed.created_at:
            age_days = (datetime.utcnow() - processed.created_at).days
            recency_score = max(1.0 - (age_days / 30.0), 0.0)
        else:
            recency_score = 0.5
        scores.append(recency_score * 0.15)

        # Importance score directly
        scores.append(processed.importance_score * 0.15)

        return sum(scores)

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
        # Score all content
        scored: list[tuple[float, UUID]] = []
        for content_id, stored in self._content.items():
            score = await self.score_relevance(content_id, user_id)
            if score >= min_relevance:
                scored.append((score, content_id))

        # Sort by score descending
        scored.sort(reverse=True)

        # Convert to Content objects
        results: list[Content] = []
        for score, content_id in scored[:limit]:
            stored = self._content.get(content_id)
            if stored and stored.processed:
                content = self._to_content(stored, score)
                results.append(content)

        return results

    async def search_content(
        self,
        query: str,
        user_id: UUID,
        limit: int = 10,
    ) -> list[Content]:
        """Search content semantically.

        Uses keyword matching and LLM for semantic understanding.

        Args:
            query: Search query
            user_id: User context for personalization
            limit: Maximum results

        Returns:
            List of matching content
        """
        query_lower = query.lower()
        keywords = set(query_lower.split())

        # Score based on keyword matches and relevance
        scored: list[tuple[float, UUID]] = []
        for content_id, stored in self._content.items():
            if stored.processed is None:
                continue

            processed = stored.processed

            # Keyword matching in title and summary
            text = f"{processed.title} {processed.summary}".lower()
            keyword_hits = sum(1 for kw in keywords if kw in text)
            keyword_score = min(keyword_hits / max(len(keywords), 1), 1.0)

            # Combine with relevance score
            relevance = await self.score_relevance(content_id, user_id)
            combined_score = (keyword_score * 0.6) + (relevance * 0.4)

            if combined_score > 0.1:
                scored.append((combined_score, content_id))

        # Sort and return
        scored.sort(reverse=True)
        results: list[Content] = []
        for score, content_id in scored[:limit]:
            stored = self._content.get(content_id)
            if stored and stored.processed:
                content = self._to_content(stored, score)
                results.append(content)

        return results

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
        content_ids = self._topic_index.get(topic_id, set())

        # Score and sort
        scored: list[tuple[float, UUID]] = []
        for content_id in content_ids:
            score = await self.score_relevance(content_id, user_id)
            scored.append((score, content_id))

        scored.sort(reverse=True)

        results: list[Content] = []
        for score, content_id in scored[:limit]:
            stored = self._content.get(content_id)
            if stored and stored.processed:
                content = self._to_content(stored, score)
                results.append(content)

        return results

    async def mark_content_seen(self, content_id: UUID, user_id: UUID) -> None:
        """Mark content as seen by user."""
        stored = self._content.get(content_id)
        if stored:
            stored.seen_by.add(user_id)

        profile = await self._get_or_create_profile(user_id)
        profile.seen_content.add(content_id)

    async def record_feedback(
        self,
        content_id: UUID,
        user_id: UUID,
        relevance_rating: int,
        notes: str | None = None,
    ) -> None:
        """Record user feedback on content."""
        feedback = {
            "user_id": str(user_id),
            "content_id": str(content_id),
            "rating": relevance_rating,
            "notes": notes,
            "timestamp": datetime.utcnow().isoformat(),
        }

        stored = self._content.get(content_id)
        if stored:
            stored.feedback.append(feedback)

        profile = await self._get_or_create_profile(user_id)
        profile.feedback_history.append(feedback)

    # --- Private methods ---

    def _clean_content(self, content: str) -> str:
        """Clean and normalize content text."""
        # Remove excessive whitespace
        cleaned = " ".join(content.split())
        # Remove common artifacts
        cleaned = re.sub(r"\[.*?\]", "", cleaned)  # Remove [citations]
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
            # Fallback: first 200 chars
            return content[:200] + "..."

    async def _generate_embedding(self, text: str) -> list[float]:
        """Generate embedding vector for text.

        Note: In production, use an actual embedding model like OpenAI's
        text-embedding-3-small or a local model.
        """
        # Placeholder - returns a simple hash-based vector
        # In production: use embedding API
        hash_val = hashlib.md5(text.encode()).hexdigest()
        # Convert hex to floats (mock embedding)
        embedding = [int(hash_val[i:i+2], 16) / 255.0 for i in range(0, 32, 2)]
        # Pad to common embedding size
        embedding.extend([0.0] * (384 - len(embedding)))
        return embedding[:384]

    async def _extract_topics(
        self,
        title: str,
        summary: str,
        content: str,
    ) -> list[UUID]:
        """Extract topic IDs from content using LLM.

        Note: In production, this would map to actual topic IDs from the DB.
        """
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

            # Parse topics and convert to mock UUIDs
            # In production: look up actual topic IDs from DB
            topics: list[UUID] = []
            for line in response.content.strip().split("\n"):
                topic = line.strip().lower()
                if topic:
                    # Create deterministic UUID from topic name
                    topic_uuid = UUID(hashlib.md5(topic.encode()).hexdigest())
                    topics.append(topic_uuid)

            return topics[:5]
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
            return 3  # Default to intermediate

    def _calculate_importance(self, raw: RawContent) -> float:
        """Calculate initial importance score based on metadata."""
        score = 0.5  # Base score

        # Boost for recent content
        if raw.published_at:
            age_days = (datetime.utcnow() - raw.published_at).days
            if age_days < 7:
                score += 0.2
            elif age_days < 30:
                score += 0.1

        # Source-specific boosts
        if raw.source_type == SourceType.ARXIV:
            score += 0.1  # Academic sources get slight boost

        # Metadata boosts (e.g., citation count, engagement metrics)
        citations = raw.metadata.get("citations", 0)
        if citations > 100:
            score += 0.15
        elif citations > 10:
            score += 0.1

        return min(score, 1.0)

    async def _get_or_create_profile(self, user_id: UUID) -> UserContentProfile:
        """Get or create user content profile."""
        if user_id not in self._user_profiles:
            self._user_profiles[user_id] = UserContentProfile(user_id=user_id)
        return self._user_profiles[user_id]

    def _to_content(self, stored: StoredContent, relevance_score: float) -> Content:
        """Convert stored content to Content response."""
        processed = stored.processed
        if processed is None:
            raise ValueError("Content must be processed first")

        # Convert topic UUIDs to names (in production: lookup from DB)
        topic_names = [str(t)[:8] for t in processed.topics]

        return Content(
            id=stored.id,
            title=processed.title,
            summary=processed.summary,
            content=processed.processed_content,
            source_type=processed.source_type,
            source_url=processed.source_url,
            topics=topic_names,
            difficulty_level=processed.difficulty_level,
            relevance_score=relevance_score,
            created_at=processed.created_at,
        )


# Factory function
_content_service: ContentService | None = None


def get_content_service() -> ContentService:
    """Get content service singleton."""
    global _content_service
    if _content_service is None:
        _content_service = ContentService()
    return _content_service
