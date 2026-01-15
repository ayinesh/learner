"""Unit tests for vector search service."""

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from src.modules.content.models import ContentModel, TopicModel
from src.modules.content.vector_search import (
    VectorSearchService,
    clear_vector_search_cache,
    get_vector_search_service,
)
from src.shared.database import get_db_session
from src.shared.models import SourceType


@pytest.fixture
async def sample_embeddings():
    """Create sample embeddings for testing."""
    # Create diverse embeddings with known similarities
    base_embedding = [0.1] * 1536
    similar_embedding = [0.11] * 1536  # Very similar
    different_embedding = [0.9] * 1536  # Very different

    return {
        "base": base_embedding,
        "similar": similar_embedding,
        "different": different_embedding,
    }


@pytest.fixture
async def sample_content(sample_embeddings):
    """Create sample content with embeddings in the database."""
    async with get_db_session() as session:
        # Create topics
        topic1 = TopicModel(id=uuid4(), name="machine learning")
        topic2 = TopicModel(id=uuid4(), name="deep learning")
        session.add(topic1)
        session.add(topic2)
        await session.flush()

        # Create content items
        content1 = ContentModel(
            id=uuid4(),
            source_type=SourceType.ARXIV.value,
            source_url="https://arxiv.org/abs/1",
            title="Machine Learning Basics",
            summary="Introduction to ML",
            embedding=sample_embeddings["base"],
            topics=[topic1.id],
            difficulty_level=2,
            importance_score=0.8,
            created_at=datetime.utcnow(),
            processed_at=datetime.utcnow(),
        )

        content2 = ContentModel(
            id=uuid4(),
            source_type=SourceType.ARXIV.value,
            source_url="https://arxiv.org/abs/2",
            title="Advanced ML Techniques",
            summary="Advanced techniques in ML",
            embedding=sample_embeddings["similar"],
            topics=[topic1.id, topic2.id],
            difficulty_level=4,
            importance_score=0.9,
            created_at=datetime.utcnow(),
            processed_at=datetime.utcnow(),
        )

        content3 = ContentModel(
            id=uuid4(),
            source_type=SourceType.BLOG.value,
            source_url="https://blog.example.com/3",
            title="Completely Different Topic",
            summary="Something unrelated",
            embedding=sample_embeddings["different"],
            topics=[],
            difficulty_level=1,
            importance_score=0.5,
            created_at=datetime.utcnow(),
            processed_at=datetime.utcnow(),
        )

        # Content without embedding
        content4 = ContentModel(
            id=uuid4(),
            source_type=SourceType.YOUTUBE.value,
            source_url="https://youtube.com/4",
            title="No Embedding",
            summary="This has no embedding",
            embedding=None,
            topics=[],
            difficulty_level=3,
            created_at=datetime.utcnow(),
            processed_at=datetime.utcnow(),
        )

        session.add_all([content1, content2, content3, content4])
        await session.commit()

        return {
            "content1": content1.id,
            "content2": content2.id,
            "content3": content3.id,
            "content4": content4.id,
            "topic1": topic1.id,
            "topic2": topic2.id,
        }


class TestVectorSearchService:
    """Test vector search service."""

    @pytest.fixture
    def service(self):
        """Create vector search service."""
        return VectorSearchService()

    @pytest.mark.asyncio
    async def test_similarity_search_basic(self, service, sample_content, sample_embeddings):
        """Test basic similarity search."""
        results = await service.similarity_search(
            query_embedding=sample_embeddings["base"],
            limit=10,
        )

        assert len(results) > 0
        # Results should be list of (content_id, similarity_score) tuples
        assert all(isinstance(r, tuple) and len(r) == 2 for r in results)

        # First result should be most similar (content1)
        assert results[0][0] == sample_content["content1"]
        assert results[0][1] > 0.9  # Very high similarity to itself

        # Second should be similar (content2)
        assert results[1][0] == sample_content["content2"]
        assert results[1][1] > 0.8

    @pytest.mark.asyncio
    async def test_similarity_search_limit(self, service, sample_content, sample_embeddings):
        """Test limit parameter."""
        results = await service.similarity_search(
            query_embedding=sample_embeddings["base"],
            limit=2,
        )

        assert len(results) <= 2

    @pytest.mark.asyncio
    async def test_similarity_search_min_similarity(self, service, sample_content, sample_embeddings):
        """Test minimum similarity threshold."""
        results = await service.similarity_search(
            query_embedding=sample_embeddings["base"],
            limit=10,
            min_similarity=0.95,
        )

        # Only very similar items should be returned
        assert all(score >= 0.95 for _, score in results)

    @pytest.mark.asyncio
    async def test_similarity_search_source_type_filter(
        self, service, sample_content, sample_embeddings
    ):
        """Test filtering by source types."""
        results = await service.similarity_search(
            query_embedding=sample_embeddings["base"],
            limit=10,
            source_types=[SourceType.ARXIV],
        )

        # Should only return ARXIV content
        async with get_db_session() as session:
            for content_id, _ in results:
                result = await session.execute(
                    select(ContentModel.source_type).where(ContentModel.id == content_id)
                )
                source_type = result.scalar_one()
                assert source_type == SourceType.ARXIV.value

    @pytest.mark.asyncio
    async def test_similarity_search_difficulty_filter(
        self, service, sample_content, sample_embeddings
    ):
        """Test filtering by difficulty level."""
        results = await service.similarity_search(
            query_embedding=sample_embeddings["base"],
            limit=10,
            min_difficulty=3,
            max_difficulty=5,
        )

        # Check difficulty levels
        async with get_db_session() as session:
            for content_id, _ in results:
                result = await session.execute(
                    select(ContentModel.difficulty_level).where(ContentModel.id == content_id)
                )
                difficulty = result.scalar_one()
                assert 3 <= difficulty <= 5

    @pytest.mark.asyncio
    async def test_similarity_search_excludes_no_embedding(
        self, service, sample_content, sample_embeddings
    ):
        """Test that content without embeddings is excluded."""
        results = await service.similarity_search(
            query_embedding=sample_embeddings["base"],
            limit=10,
        )

        # content4 has no embedding, should not be in results
        content_ids = [cid for cid, _ in results]
        assert sample_content["content4"] not in content_ids

    @pytest.mark.asyncio
    async def test_similarity_search_sorted_by_similarity(
        self, service, sample_content, sample_embeddings
    ):
        """Test results are sorted by similarity (highest first)."""
        results = await service.similarity_search(
            query_embedding=sample_embeddings["base"],
            limit=10,
        )

        # Verify descending order
        similarities = [score for _, score in results]
        assert similarities == sorted(similarities, reverse=True)

    @pytest.mark.asyncio
    async def test_similarity_search_with_content(
        self, service, sample_content, sample_embeddings
    ):
        """Test similarity search returning full content objects."""
        results = await service.similarity_search_with_content(
            query_embedding=sample_embeddings["base"],
            limit=10,
        )

        assert len(results) > 0
        # Results should be (ContentModel, similarity_score) tuples
        for content, similarity in results:
            assert isinstance(content, ContentModel)
            assert isinstance(similarity, float)
            assert 0.0 <= similarity <= 1.0

    @pytest.mark.asyncio
    async def test_find_similar_to_content(self, service, sample_content):
        """Test finding content similar to a specific content item."""
        results = await service.find_similar_to_content(
            content_id=sample_content["content1"],
            limit=5,
            exclude_self=True,
        )

        # Should return similar items
        assert len(results) > 0

        # Should not include the source content itself
        content_ids = [cid for cid, _ in results]
        assert sample_content["content1"] not in content_ids

        # Most similar should be content2
        assert results[0][0] == sample_content["content2"]

    @pytest.mark.asyncio
    async def test_find_similar_include_self(self, service, sample_content):
        """Test finding similar content including source."""
        results = await service.find_similar_to_content(
            content_id=sample_content["content1"],
            limit=5,
            exclude_self=False,
        )

        # Source content should be included and be first (100% similar to itself)
        content_ids = [cid for cid, _ in results]
        assert sample_content["content1"] in content_ids
        assert results[0][0] == sample_content["content1"]
        assert results[0][1] > 0.99  # Nearly 1.0

    @pytest.mark.asyncio
    async def test_find_similar_nonexistent_content(self, service):
        """Test finding similar to nonexistent content."""
        with pytest.raises(ValueError, match="Content not found"):
            await service.find_similar_to_content(
                content_id=uuid4(),  # Random UUID
                limit=5,
            )

    @pytest.mark.asyncio
    async def test_find_similar_no_embedding(self, service, sample_content):
        """Test finding similar to content without embedding."""
        with pytest.raises(ValueError, match="has no embedding"):
            await service.find_similar_to_content(
                content_id=sample_content["content4"],  # Has no embedding
                limit=5,
            )

    @pytest.mark.asyncio
    async def test_hybrid_search(self, service, sample_content, sample_embeddings):
        """Test hybrid search combining vector and keyword."""
        results = await service.hybrid_search(
            query_text="machine learning",
            query_embedding=sample_embeddings["base"],
            limit=5,
            vector_weight=0.6,
            keyword_weight=0.4,
        )

        assert len(results) > 0

        # Results should be (content_id, combined_score) tuples
        for content_id, score in results:
            assert isinstance(content_id, UUID)
            assert isinstance(score, float)

        # Items matching both vector and keyword should rank higher
        # content1 and content2 both match "machine learning"
        top_ids = [cid for cid, _ in results[:2]]
        assert sample_content["content1"] in top_ids or sample_content["content2"] in top_ids

    @pytest.mark.asyncio
    async def test_hybrid_search_weight_validation(
        self, service, sample_content, sample_embeddings
    ):
        """Test hybrid search with non-normalized weights."""
        # Weights don't sum to 1.0 - should still work with warning
        results = await service.hybrid_search(
            query_text="machine learning",
            query_embedding=sample_embeddings["base"],
            limit=5,
            vector_weight=0.8,
            keyword_weight=0.5,  # Sum = 1.3
        )

        # Should still return results despite warning
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_hybrid_search_pure_vector(
        self, service, sample_content, sample_embeddings
    ):
        """Test hybrid search with vector-only weighting."""
        results = await service.hybrid_search(
            query_text="machine learning",
            query_embedding=sample_embeddings["base"],
            limit=5,
            vector_weight=1.0,
            keyword_weight=0.0,
        )

        # Should work like pure vector search
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_hybrid_search_pure_keyword(
        self, service, sample_content, sample_embeddings
    ):
        """Test hybrid search with keyword-only weighting."""
        results = await service.hybrid_search(
            query_text="machine learning",
            query_embedding=sample_embeddings["base"],
            limit=5,
            vector_weight=0.0,
            keyword_weight=1.0,
        )

        # Should work like pure keyword search
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_invalid_embedding_dimension(self, service):
        """Test error with wrong embedding dimension."""
        wrong_embedding = [0.1] * 100  # Wrong size

        with pytest.raises(ValueError, match="must be 1536 dimensions"):
            await service.similarity_search(
                query_embedding=wrong_embedding,
                limit=10,
            )

    @pytest.mark.asyncio
    async def test_get_index_stats(self, service, sample_content):
        """Test retrieving index statistics."""
        stats = await service.get_index_stats()

        assert "total_indexed" in stats
        assert "total_processed" in stats
        assert "index_coverage" in stats

        # Should have at least 3 indexed items (content1, content2, content3)
        assert stats["total_indexed"] >= 3

        # Coverage should be reasonable
        assert 0.0 <= stats["index_coverage"] <= 1.0


class TestVectorSearchFactory:
    """Test vector search service factory."""

    def teardown_method(self):
        """Clear cache after each test."""
        clear_vector_search_cache()

    def test_singleton(self):
        """Test that factory returns singleton."""
        service1 = get_vector_search_service()
        service2 = get_vector_search_service()

        assert service1 is service2

    def test_clear_cache(self):
        """Test cache clearing."""
        service1 = get_vector_search_service()
        clear_vector_search_cache()
        service2 = get_vector_search_service()

        assert service1 is not service2

    def test_service_type(self):
        """Test correct service type is returned."""
        service = get_vector_search_service()
        assert isinstance(service, VectorSearchService)


class TestVectorSearchEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def service(self):
        """Create vector search service."""
        return VectorSearchService()

    @pytest.mark.asyncio
    async def test_empty_database(self, service):
        """Test search with empty database."""
        # Clear all content first
        async with get_db_session() as session:
            await session.execute("DELETE FROM content")
            await session.commit()

        embedding = [0.1] * 1536
        results = await service.similarity_search(
            query_embedding=embedding,
            limit=10,
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_zero_vector_query(self, service, sample_content):
        """Test search with zero vector."""
        zero_embedding = [0.0] * 1536

        results = await service.similarity_search(
            query_embedding=zero_embedding,
            limit=10,
        )

        # Should still return results, though similarities may be unusual
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_normalized_vs_unnormalized(self, service, sample_content):
        """Test that cosine similarity works with unnormalized vectors."""
        # Cosine similarity is scale-invariant
        embedding1 = [0.1] * 1536
        embedding2 = [1.0] * 1536  # 10x larger but same direction

        results1 = await service.similarity_search(
            query_embedding=embedding1,
            limit=5,
        )

        results2 = await service.similarity_search(
            query_embedding=embedding2,
            limit=5,
        )

        # Results should be similar (same order)
        ids1 = [cid for cid, _ in results1]
        ids2 = [cid for cid, _ in results2]

        # At least top result should match
        assert ids1[0] == ids2[0]
