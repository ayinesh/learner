"""Vector search service using pgvector for semantic similarity search.

This module provides vector similarity search operations using PostgreSQL's
pgvector extension. It supports efficient approximate nearest neighbor (ANN)
search using cosine similarity.

Usage:
    from src.modules.content.vector_search import get_vector_search_service

    service = get_vector_search_service()
    results = await service.similarity_search(
        query_embedding=embedding,
        limit=10,
        user_id=user_id
    )
"""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.content.models import ContentModel
from src.shared.database import get_db_session
from src.shared.models import SourceType

logger = logging.getLogger(__name__)


class VectorSearchService:
    """Service for performing vector similarity search on content.

    Uses pgvector's cosine distance operator (<->) for efficient
    nearest neighbor search. Supports filtering by user, source types,
    and difficulty levels.
    """

    def __init__(self):
        """Initialize vector search service."""
        logger.info("VectorSearchService initialized")

    async def similarity_search(
        self,
        query_embedding: list[float],
        limit: int = 10,
        user_id: UUID | None = None,
        source_types: list[SourceType] | None = None,
        min_difficulty: int | None = None,
        max_difficulty: int | None = None,
        min_similarity: float = 0.0,
    ) -> list[tuple[UUID, float]]:
        """Search for similar content using vector similarity.

        Uses pgvector's <=> operator for cosine distance. The distance is
        converted to similarity score (1 - distance) where:
        - 1.0 = identical vectors
        - 0.0 = orthogonal vectors
        - -1.0 = opposite vectors (rare in practice)

        Args:
            query_embedding: Query vector to search for (must be 1536 dims)
            limit: Maximum number of results to return
            user_id: Optional user ID for personalized filtering
            source_types: Optional list of source types to filter by
            min_difficulty: Minimum difficulty level (1-5)
            max_difficulty: Maximum difficulty level (1-5)
            min_similarity: Minimum similarity threshold (0-1)

        Returns:
            List of (content_id, similarity_score) tuples sorted by similarity

        Raises:
            ValueError: If query_embedding dimension is incorrect
        """
        if len(query_embedding) != 1536:
            raise ValueError(
                f"Query embedding must be 1536 dimensions, got {len(query_embedding)}"
            )

        async with get_db_session() as session:
            # Build query with filters
            query = select(
                ContentModel.id,
                # Convert cosine distance to similarity (1 - distance)
                (1 - ContentModel.embedding.cosine_distance(query_embedding)).label("similarity")
            ).where(
                ContentModel.embedding.isnot(None),
                ContentModel.processed_at.isnot(None)
            )

            # Apply source type filter
            if source_types:
                source_values = [s.value for s in source_types]
                query = query.where(ContentModel.source_type.in_(source_values))

            # Apply difficulty filters
            if min_difficulty is not None:
                query = query.where(ContentModel.difficulty_level >= min_difficulty)
            if max_difficulty is not None:
                query = query.where(ContentModel.difficulty_level <= max_difficulty)

            # Order by similarity (using cosine distance for index optimization)
            query = query.order_by(
                ContentModel.embedding.cosine_distance(query_embedding)
            ).limit(limit)

            result = await session.execute(query)
            rows = result.all()

            # Filter by minimum similarity and return
            results = [
                (row.id, row.similarity)
                for row in rows
                if row.similarity >= min_similarity
            ]

            logger.info(
                f"Vector search found {len(results)} results "
                f"(limit={limit}, min_similarity={min_similarity})"
            )

            return results

    async def similarity_search_with_content(
        self,
        query_embedding: list[float],
        limit: int = 10,
        source_types: list[SourceType] | None = None,
        min_similarity: float = 0.0,
    ) -> list[tuple[ContentModel, float]]:
        """Search for similar content and return full content objects.

        This is a convenience method that returns the full ContentModel
        objects instead of just IDs.

        Args:
            query_embedding: Query vector to search for
            limit: Maximum number of results
            source_types: Optional source type filter
            min_similarity: Minimum similarity threshold

        Returns:
            List of (ContentModel, similarity_score) tuples
        """
        if len(query_embedding) != 1536:
            raise ValueError(
                f"Query embedding must be 1536 dimensions, got {len(query_embedding)}"
            )

        async with get_db_session() as session:
            # Build query
            query = select(
                ContentModel,
                (1 - ContentModel.embedding.cosine_distance(query_embedding)).label("similarity")
            ).where(
                ContentModel.embedding.isnot(None),
                ContentModel.processed_at.isnot(None)
            )

            if source_types:
                source_values = [s.value for s in source_types]
                query = query.where(ContentModel.source_type.in_(source_values))

            query = query.order_by(
                ContentModel.embedding.cosine_distance(query_embedding)
            ).limit(limit)

            result = await session.execute(query)
            rows = result.all()

            # Filter by similarity and return
            results = [
                (row.ContentModel, row.similarity)
                for row in rows
                if row.similarity >= min_similarity
            ]

            return results

    async def find_similar_to_content(
        self,
        content_id: UUID,
        limit: int = 10,
        exclude_self: bool = True,
        min_similarity: float = 0.5,
    ) -> list[tuple[UUID, float]]:
        """Find content similar to a given content item.

        Useful for "related content" recommendations.

        Args:
            content_id: ID of the content to find similar items for
            limit: Maximum number of results
            exclude_self: Whether to exclude the source content from results
            min_similarity: Minimum similarity threshold

        Returns:
            List of (content_id, similarity_score) tuples

        Raises:
            ValueError: If content not found or has no embedding
        """
        async with get_db_session() as session:
            # Get the source content's embedding
            result = await session.execute(
                select(ContentModel.embedding).where(ContentModel.id == content_id)
            )
            row = result.first()

            if row is None:
                raise ValueError(f"Content not found: {content_id}")

            embedding = row[0]
            if embedding is None:
                raise ValueError(f"Content has no embedding: {content_id}")

            # Convert embedding to list if needed
            if not isinstance(embedding, list):
                embedding = list(embedding)

            # Search for similar content
            results = await self.similarity_search(
                query_embedding=embedding,
                limit=limit + 1 if exclude_self else limit,
                min_similarity=min_similarity,
            )

            # Filter out the source content if requested
            if exclude_self:
                results = [
                    (cid, score)
                    for cid, score in results
                    if cid != content_id
                ][:limit]

            return results

    async def hybrid_search(
        self,
        query_text: str,
        query_embedding: list[float],
        limit: int = 10,
        vector_weight: float = 0.6,
        keyword_weight: float = 0.4,
        source_types: list[SourceType] | None = None,
    ) -> list[tuple[UUID, float]]:
        """Perform hybrid search combining vector similarity and keyword matching.

        This combines semantic search (via embeddings) with keyword search
        for better results on specific queries.

        Args:
            query_text: Text query for keyword matching
            query_embedding: Vector embedding for semantic search
            limit: Maximum number of results
            vector_weight: Weight for vector similarity (0-1)
            keyword_weight: Weight for keyword matching (0-1)
            source_types: Optional source type filter

        Returns:
            List of (content_id, combined_score) tuples

        Note:
            Weights should sum to 1.0 for normalized scoring
        """
        if abs(vector_weight + keyword_weight - 1.0) > 0.01:
            logger.warning(
                f"Hybrid search weights don't sum to 1.0: "
                f"vector={vector_weight}, keyword={keyword_weight}"
            )

        # Perform vector search
        vector_results = await self.similarity_search(
            query_embedding=query_embedding,
            limit=limit * 2,  # Get more for merging
            source_types=source_types,
        )

        # Convert to dict for easy lookup
        vector_scores = {cid: score for cid, score in vector_results}

        # Perform keyword search
        keywords = query_text.lower().split()

        async with get_db_session() as session:
            # Build keyword search query
            query = select(ContentModel.id, ContentModel.title, ContentModel.summary).where(
                ContentModel.processed_at.isnot(None)
            )

            if source_types:
                source_values = [s.value for s in source_types]
                query = query.where(ContentModel.source_type.in_(source_values))

            result = await session.execute(query)
            rows = result.all()

            # Score by keyword matching
            keyword_scores = {}
            for row in rows:
                text = f"{row.title} {row.summary or ''}".lower()
                keyword_hits = sum(1 for kw in keywords if kw in text)
                if keyword_hits > 0:
                    score = min(keyword_hits / max(len(keywords), 1), 1.0)
                    keyword_scores[row.id] = score

        # Combine scores
        all_content_ids = set(vector_scores.keys()) | set(keyword_scores.keys())
        combined_results = []

        for content_id in all_content_ids:
            vector_score = vector_scores.get(content_id, 0.0)
            keyword_score = keyword_scores.get(content_id, 0.0)
            combined_score = (vector_score * vector_weight) + (keyword_score * keyword_weight)
            combined_results.append((content_id, combined_score))

        # Sort by combined score and limit
        combined_results.sort(key=lambda x: x[1], reverse=True)

        return combined_results[:limit]

    async def get_index_stats(self) -> dict:
        """Get statistics about the vector index.

        Returns information about:
        - Total number of indexed content items
        - Average embedding norm
        - Index size

        Returns:
            Dictionary with index statistics
        """
        async with get_db_session() as session:
            # Count indexed content
            count_result = await session.execute(
                select(text("COUNT(*)")).select_from(ContentModel).where(
                    ContentModel.embedding.isnot(None)
                )
            )
            total_indexed = count_result.scalar()

            # Get processed content count
            processed_result = await session.execute(
                select(text("COUNT(*)")).select_from(ContentModel).where(
                    ContentModel.processed_at.isnot(None)
                )
            )
            total_processed = processed_result.scalar()

            stats = {
                "total_indexed": total_indexed,
                "total_processed": total_processed,
                "index_coverage": (
                    total_indexed / total_processed if total_processed > 0 else 0.0
                ),
            }

            logger.info(f"Vector index stats: {stats}")
            return stats


# Factory function

_vector_search_service: VectorSearchService | None = None


def get_vector_search_service() -> VectorSearchService:
    """Get the singleton vector search service instance.

    Returns:
        VectorSearchService instance
    """
    global _vector_search_service
    if _vector_search_service is None:
        _vector_search_service = VectorSearchService()
    return _vector_search_service


def clear_vector_search_cache() -> None:
    """Clear the cached vector search service.

    Useful for testing.
    """
    global _vector_search_service
    _vector_search_service = None
    logger.info("Vector search service cache cleared")
