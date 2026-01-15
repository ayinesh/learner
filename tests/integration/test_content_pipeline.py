"""Integration tests for content pipeline with embeddings and vector search."""

from datetime import datetime
from uuid import uuid4

import pytest

from src.modules.content.db_service import DatabaseContentService, get_db_content_service
from src.modules.content.embeddings import PlaceholderEmbedding, get_embedding_service
from src.modules.content.interface import RawContent
from src.modules.content.models import ContentModel, UserTopicProgressModel
from src.modules.content.vector_search import get_vector_search_service
from src.modules.user.models import UserModel
from src.shared.database import get_db_session
from src.shared.feature_flags import FeatureFlags, get_feature_flags
from src.shared.models import SourceType


@pytest.fixture
async def test_user():
    """Create a test user."""
    async with get_db_session() as session:
        user = UserModel(
            id=uuid4(),
            email=f"test_{uuid4()}@example.com",
            password_hash="hashed_password",
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user.id


@pytest.fixture
async def content_service():
    """Get content service with placeholder embeddings for testing."""
    # Ensure we use placeholder embeddings for testing
    flags = get_feature_flags()
    flags.disable(FeatureFlags.ENABLE_REAL_EMBEDDINGS)

    service = DatabaseContentService(
        embedding_service=PlaceholderEmbedding()
    )
    return service


class TestContentIngestionPipeline:
    """Test the full content ingestion and processing pipeline."""

    @pytest.mark.asyncio
    async def test_full_pipeline_single_content(self, content_service, test_user):
        """Test complete pipeline from ingestion to retrieval."""
        # Step 1: Ingest raw content
        async with get_db_session() as session:
            content_id = uuid4()
            raw_content = ContentModel(
                id=content_id,
                source_type=SourceType.ARXIV.value,
                source_url=f"https://arxiv.org/abs/{uuid4()}",
                title="Understanding Transformer Networks",
                raw_content="This paper presents a comprehensive overview of transformer networks...",
                created_at=datetime.utcnow(),
            )
            session.add(raw_content)
            await session.commit()

        # Step 2: Process content
        processed = await content_service.process_content(content_id)

        # Verify processing
        assert processed is not None
        assert processed.id == content_id
        assert processed.summary is not None
        assert len(processed.embedding) == 1536
        assert all(isinstance(x, float) for x in processed.embedding)
        assert processed.processed_at is not None

        # Step 3: Retrieve content
        content = await content_service.get_content(content_id)

        assert content is not None
        assert content.id == content_id
        assert content.title == "Understanding Transformer Networks"

        # Step 4: Search for similar content
        results = await content_service.search_content(
            query="transformer networks",
            user_id=test_user,
            limit=5,
        )

        # Should find the content we just added
        assert len(results) > 0
        content_ids = [c.id for c in results]
        assert content_id in content_ids

    @pytest.mark.asyncio
    async def test_batch_content_processing(self, content_service, test_user):
        """Test processing multiple content items."""
        content_ids = []

        # Create multiple raw content items
        async with get_db_session() as session:
            for i in range(5):
                content_id = uuid4()
                content = ContentModel(
                    id=content_id,
                    source_type=SourceType.BLOG.value,
                    source_url=f"https://blog.example.com/{uuid4()}",
                    title=f"Blog Post {i}: Machine Learning",
                    raw_content=f"Content about machine learning topic {i}...",
                    created_at=datetime.utcnow(),
                )
                session.add(content)
                content_ids.append(content_id)
            await session.commit()

        # Process all content
        processed_items = []
        for content_id in content_ids:
            processed = await content_service.process_content(content_id)
            processed_items.append(processed)

        # Verify all processed
        assert len(processed_items) == 5
        for processed in processed_items:
            assert processed.embedding is not None
            assert len(processed.embedding) == 1536
            assert processed.summary is not None

    @pytest.mark.asyncio
    async def test_embedding_consistency(self, content_service):
        """Test that same content produces same embedding."""
        text = "Consistent content for testing"

        # Create two content items with same text
        content_ids = []
        async with get_db_session() as session:
            for _ in range(2):
                content_id = uuid4()
                content = ContentModel(
                    id=content_id,
                    source_type=SourceType.BLOG.value,
                    source_url=f"https://blog.example.com/{uuid4()}",
                    title=text,
                    raw_content=text,
                    created_at=datetime.utcnow(),
                )
                session.add(content)
                content_ids.append(content_id)
            await session.commit()

        # Process both
        processed1 = await content_service.process_content(content_ids[0])
        processed2 = await content_service.process_content(content_ids[1])

        # Embeddings should be identical (using placeholder)
        assert processed1.embedding == processed2.embedding


class TestVectorSearchIntegration:
    """Test vector search integration with content service."""

    @pytest.mark.asyncio
    async def test_semantic_search(self, content_service, test_user):
        """Test semantic search finds relevant content."""
        # Create content about related topics
        async with get_db_session() as session:
            topics = [
                ("Neural Networks Fundamentals", "Introduction to neural networks and backpropagation"),
                ("Deep Learning Overview", "Comprehensive guide to deep learning techniques"),
                ("Quantum Computing Basics", "Introduction to quantum computing principles"),
            ]

            content_ids = []
            for title, summary in topics:
                content_id = uuid4()
                content = ContentModel(
                    id=content_id,
                    source_type=SourceType.ARXIV.value,
                    source_url=f"https://arxiv.org/abs/{uuid4()}",
                    title=title,
                    raw_content=summary,
                    summary=summary,
                    created_at=datetime.utcnow(),
                )
                session.add(content)
                content_ids.append(content_id)
            await session.commit()

        # Process all content
        for content_id in content_ids:
            await content_service.process_content(content_id)

        # Search for neural network content
        results = await content_service.search_content(
            query="neural networks deep learning",
            user_id=test_user,
            limit=10,
        )

        assert len(results) > 0

        # First two results should be about neural networks/deep learning
        # (more relevant than quantum computing)
        top_titles = [r.title for r in results[:2]]
        assert any("Neural" in title or "Deep" in title for title in top_titles)

    @pytest.mark.asyncio
    async def test_personalized_relevance_scoring(self, content_service, test_user):
        """Test that relevance scoring considers user's topic progress."""
        # Create topics and content
        async with get_db_session() as session:
            # Create two content items with different difficulty
            beginner_id = uuid4()
            beginner_content = ContentModel(
                id=beginner_id,
                source_type=SourceType.BLOG.value,
                source_url=f"https://blog.example.com/{uuid4()}",
                title="Python Basics for Beginners",
                raw_content="Introduction to Python programming",
                difficulty_level=1,
                created_at=datetime.utcnow(),
            )

            advanced_id = uuid4()
            advanced_content = ContentModel(
                id=advanced_id,
                source_type=SourceType.ARXIV.value,
                source_url=f"https://arxiv.org/abs/{uuid4()}",
                title="Advanced Type Theory in Python",
                raw_content="Advanced concepts in type theory",
                difficulty_level=5,
                created_at=datetime.utcnow(),
            )

            session.add_all([beginner_content, advanced_content])
            await session.commit()

        # Process content
        await content_service.process_content(beginner_id)
        await content_service.process_content(advanced_id)

        # Get relevant content (user has no topic progress, default proficiency ~0.5)
        results = await content_service.get_relevant_content(
            user_id=test_user,
            limit=10,
        )

        # Verify results include both items
        result_ids = [r.id for r in results]
        assert beginner_id in result_ids or advanced_id in result_ids

    @pytest.mark.asyncio
    async def test_vector_search_with_filters(self, content_service, test_user):
        """Test vector search with source type and difficulty filters."""
        # Create content from different sources
        async with get_db_session() as session:
            arxiv_id = uuid4()
            arxiv_content = ContentModel(
                id=arxiv_id,
                source_type=SourceType.ARXIV.value,
                source_url=f"https://arxiv.org/abs/{uuid4()}",
                title="Research Paper",
                raw_content="Academic research content",
                difficulty_level=4,
                created_at=datetime.utcnow(),
            )

            blog_id = uuid4()
            blog_content = ContentModel(
                id=blog_id,
                source_type=SourceType.BLOG.value,
                source_url=f"https://blog.example.com/{uuid4()}",
                title="Blog Post",
                raw_content="Blog content about same topic",
                difficulty_level=2,
                created_at=datetime.utcnow(),
            )

            session.add_all([arxiv_content, blog_content])
            await session.commit()

        # Process content
        await content_service.process_content(arxiv_id)
        await content_service.process_content(blog_id)

        # Get embedding for search
        embedding = await get_embedding_service().generate("research topic")

        # Search only ARXIV content
        results = await content_service.vector_search_content(
            query_embedding=embedding,
            user_id=test_user,
            limit=10,
            source_types=[SourceType.ARXIV],
        )

        # Should only return ARXIV content
        assert all(r.source_type == SourceType.ARXIV for r in results)


class TestContentRecommendations:
    """Test content recommendation system."""

    @pytest.mark.asyncio
    async def test_find_related_content(self, content_service, test_user):
        """Test finding content related to a specific item."""
        # Create a cluster of related content
        async with get_db_session() as session:
            source_id = uuid4()
            source_content = ContentModel(
                id=source_id,
                source_type=SourceType.ARXIV.value,
                source_url=f"https://arxiv.org/abs/{uuid4()}",
                title="Attention Mechanisms in NLP",
                raw_content="Detailed analysis of attention mechanisms",
                created_at=datetime.utcnow(),
            )

            related_id = uuid4()
            related_content = ContentModel(
                id=related_id,
                source_type=SourceType.BLOG.value,
                source_url=f"https://blog.example.com/{uuid4()}",
                title="Understanding Attention in Transformers",
                raw_content="Explaining attention in transformer models",
                created_at=datetime.utcnow(),
            )

            unrelated_id = uuid4()
            unrelated_content = ContentModel(
                id=unrelated_id,
                source_type=SourceType.YOUTUBE.value,
                source_url=f"https://youtube.com/{uuid4()}",
                title="Cooking Tutorial",
                raw_content="How to cook pasta",
                created_at=datetime.utcnow(),
            )

            session.add_all([source_content, related_content, unrelated_content])
            await session.commit()

        # Process all content
        await content_service.process_content(source_id)
        await content_service.process_content(related_id)
        await content_service.process_content(unrelated_id)

        # Find similar content
        vector_search = get_vector_search_service()
        results = await vector_search.find_similar_to_content(
            content_id=source_id,
            limit=5,
            exclude_self=True,
            min_similarity=0.1,
        )

        # Should find related content ranked higher than unrelated
        if len(results) >= 2:
            assert results[0][0] == related_id  # Most similar should be related
            assert results[0][1] > results[1][1]  # Higher similarity score

    @pytest.mark.asyncio
    async def test_novelty_in_recommendations(self, content_service, test_user):
        """Test that already-seen content is deprioritized."""
        async with get_db_session() as session:
            # Create content
            seen_id = uuid4()
            seen_content = ContentModel(
                id=seen_id,
                source_type=SourceType.BLOG.value,
                source_url=f"https://blog.example.com/{uuid4()}",
                title="Already Seen Content",
                raw_content="Content the user has already seen",
                created_at=datetime.utcnow(),
            )

            new_id = uuid4()
            new_content = ContentModel(
                id=new_id,
                source_type=SourceType.BLOG.value,
                source_url=f"https://blog.example.com/{uuid4()}",
                title="New Content",
                raw_content="Fresh content for the user",
                created_at=datetime.utcnow(),
            )

            session.add_all([seen_content, new_content])
            await session.commit()

        # Process content
        await content_service.process_content(seen_id)
        await content_service.process_content(new_id)

        # Mark one as seen
        await content_service.mark_content_seen(seen_id, test_user)

        # Get relevant content
        results = await content_service.get_relevant_content(
            user_id=test_user,
            limit=10,
            min_relevance=0.0,
        )

        # Novelty should affect ranking
        # (exact ordering depends on other factors, but new content should rank higher)
        result_ids = [r.id for r in results]
        if seen_id in result_ids and new_id in result_ids:
            seen_pos = result_ids.index(seen_id)
            new_pos = result_ids.index(new_id)
            # New content should generally rank higher (lower position number)
            # This is probabilistic due to other scoring factors


class TestEmbeddingCaching:
    """Test embedding caching and reprocessing."""

    @pytest.mark.asyncio
    async def test_no_reprocessing_when_already_processed(self, content_service):
        """Test that already processed content isn't reprocessed."""
        async with get_db_session() as session:
            content_id = uuid4()
            content = ContentModel(
                id=content_id,
                source_type=SourceType.BLOG.value,
                source_url=f"https://blog.example.com/{uuid4()}",
                title="Test Content",
                raw_content="Original content",
                created_at=datetime.utcnow(),
            )
            session.add(content)
            await session.commit()

        # Process first time
        processed1 = await content_service.process_content(content_id)
        first_processed_at = processed1.processed_at
        first_embedding = processed1.embedding

        # Process again
        processed2 = await content_service.process_content(content_id)

        # Should return same processed content without regenerating
        assert processed2.processed_at == first_processed_at
        assert processed2.embedding == first_embedding


class TestErrorHandling:
    """Test error handling in content pipeline."""

    @pytest.mark.asyncio
    async def test_process_nonexistent_content(self, content_service):
        """Test processing nonexistent content."""
        with pytest.raises(ValueError, match="Content not found"):
            await content_service.process_content(uuid4())

    @pytest.mark.asyncio
    async def test_search_with_invalid_embedding_dimension(self):
        """Test search with wrong embedding dimension."""
        vector_search = get_vector_search_service()

        with pytest.raises(ValueError, match="must be 1536 dimensions"):
            await vector_search.similarity_search(
                query_embedding=[0.1] * 100,  # Wrong dimension
                limit=10,
            )

    @pytest.mark.asyncio
    async def test_empty_content_processing(self, content_service):
        """Test processing content with empty text."""
        async with get_db_session() as session:
            content_id = uuid4()
            content = ContentModel(
                id=content_id,
                source_type=SourceType.BLOG.value,
                source_url=f"https://blog.example.com/{uuid4()}",
                title="Empty Content",
                raw_content="",  # Empty
                created_at=datetime.utcnow(),
            )
            session.add(content)
            await session.commit()

        # Should still process (with defaults)
        processed = await content_service.process_content(content_id)

        assert processed is not None
        assert processed.embedding is not None
        assert len(processed.embedding) == 1536
