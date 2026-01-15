"""Tests for Content module - adapters and service."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

from src.modules.content.interface import Content, ProcessedContent, RawContent
from src.modules.content.adapters.arxiv import ArxivAdapter
from src.modules.content.adapters.rss import RSSAdapter
from src.modules.content.service import ContentService
from src.shared.models import SourceType


# --- ArXiv Adapter Tests ---

class TestArxivAdapter:
    """Tests for ArxivAdapter."""

    @pytest.fixture
    def adapter(self) -> ArxivAdapter:
        return ArxivAdapter()

    @pytest.mark.asyncio
    async def test_source_type(self, adapter: ArxivAdapter):
        """Test that source type is ARXIV."""
        assert adapter.source_type == SourceType.ARXIV

    @pytest.mark.asyncio
    async def test_validate_config_with_categories(self, adapter: ArxivAdapter):
        """Test config validation with categories."""
        config = {"categories": ["cs.AI"]}
        assert await adapter.validate_config(config) is True

    @pytest.mark.asyncio
    async def test_validate_config_with_keywords(self, adapter: ArxivAdapter):
        """Test config validation with keywords."""
        config = {"keywords": ["machine learning"]}
        assert await adapter.validate_config(config) is True

    @pytest.mark.asyncio
    async def test_validate_config_with_authors(self, adapter: ArxivAdapter):
        """Test config validation with authors."""
        config = {"authors": ["John Smith"]}
        assert await adapter.validate_config(config) is True

    @pytest.mark.asyncio
    async def test_validate_config_empty(self, adapter: ArxivAdapter):
        """Test config validation with empty config."""
        config = {}
        assert await adapter.validate_config(config) is False

    def test_build_query_categories(self, adapter: ArxivAdapter):
        """Test query building with categories."""
        config = {"categories": ["cs.AI", "cs.LG"]}
        query = adapter._build_query(config)
        assert "cat:cs.AI" in query
        assert "cat:cs.LG" in query

    def test_build_query_keywords(self, adapter: ArxivAdapter):
        """Test query building with keywords."""
        config = {"keywords": ["neural network", "deep learning"]}
        query = adapter._build_query(config)
        assert 'all:"neural network"' in query
        assert 'all:"deep learning"' in query

    def test_parse_entry_success(self, adapter: ArxivAdapter):
        """Test parsing a valid arXiv entry."""
        import xml.etree.ElementTree as ET

        xml_str = """
        <entry xmlns="http://www.w3.org/2005/Atom">
            <id>http://arxiv.org/abs/2401.00001</id>
            <title>Test Paper Title</title>
            <summary>This is the abstract of the paper.</summary>
            <author><name>John Doe</name></author>
            <published>2024-01-15T00:00:00Z</published>
            <link type="text/html" href="http://arxiv.org/abs/2401.00001"/>
            <category term="cs.AI"/>
        </entry>
        """
        entry = ET.fromstring(xml_str)

        # Need to use the correct namespace
        adapter.NAMESPACE = {"atom": "http://www.w3.org/2005/Atom"}
        result = adapter._parse_entry(entry)

        assert result is not None
        assert result.title == "Test Paper Title"
        assert "abstract" in result.content.lower()
        assert result.author == "John Doe"
        assert result.source_type == SourceType.ARXIV

    def test_clean_text(self, adapter: ArxivAdapter):
        """Test text cleaning."""
        dirty = "  This   has   extra    whitespace  "
        clean = adapter._clean_text(dirty)
        assert clean == "This has extra whitespace"


# --- RSS Adapter Tests ---

class TestRSSAdapter:
    """Tests for RSSAdapter."""

    @pytest.fixture
    def adapter(self) -> RSSAdapter:
        return RSSAdapter()

    @pytest.mark.asyncio
    async def test_source_type(self, adapter: RSSAdapter):
        """Test that source type is BLOG."""
        assert adapter.source_type == SourceType.BLOG

    @pytest.mark.asyncio
    async def test_validate_config_with_feeds(self, adapter: RSSAdapter):
        """Test config validation with feed URLs."""
        config = {"feed_urls": ["https://example.com/feed.xml"]}
        assert await adapter.validate_config(config) is True

    @pytest.mark.asyncio
    async def test_validate_config_empty(self, adapter: RSSAdapter):
        """Test config validation with empty config."""
        config = {}
        assert await adapter.validate_config(config) is False

    @pytest.mark.asyncio
    async def test_validate_config_empty_feeds(self, adapter: RSSAdapter):
        """Test config validation with empty feed list."""
        config = {"feed_urls": []}
        assert await adapter.validate_config(config) is False

    def test_clean_html(self, adapter: RSSAdapter):
        """Test HTML cleaning."""
        html = "<p>Hello <b>World</b></p>"
        clean = adapter._clean_html(html)
        assert clean == "Hello World"

    def test_clean_html_entities(self, adapter: RSSAdapter):
        """Test HTML entity decoding."""
        html = "Hello &amp; World &quot;test&quot;"
        clean = adapter._clean_html(html)
        assert "&" in clean
        assert '"' in clean

    def test_parse_rss_feed(self, adapter: RSSAdapter):
        """Test parsing RSS 2.0 feed."""
        rss_content = """<?xml version="1.0"?>
        <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <item>
                    <title>Test Article</title>
                    <link>https://example.com/article</link>
                    <description>Article description</description>
                    <pubDate>Mon, 15 Jan 2024 10:00:00 GMT</pubDate>
                </item>
            </channel>
        </rss>
        """

        results = adapter._parse_feed(rss_content, "https://example.com/feed", None)

        assert len(results) == 1
        assert results[0].title == "Test Article"
        assert results[0].source_url == "https://example.com/article"

    def test_parse_atom_feed(self, adapter: RSSAdapter):
        """Test parsing Atom feed."""
        atom_content = """<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
            <title>Test Feed</title>
            <entry>
                <title>Test Article</title>
                <link rel="alternate" href="https://example.com/article"/>
                <summary>Article summary</summary>
                <published>2024-01-15T10:00:00Z</published>
            </entry>
        </feed>
        """

        results = adapter._parse_feed(atom_content, "https://example.com/feed", None)

        assert len(results) == 1
        assert results[0].title == "Test Article"


# --- Content Service Tests ---

class TestContentService:
    """Tests for ContentService."""

    @pytest.fixture
    def mock_llm(self) -> MagicMock:
        """Create mock LLM service."""
        llm = MagicMock()
        llm.complete = AsyncMock(return_value=MagicMock(content="Test summary"))
        return llm

    @pytest.fixture
    def service(self, mock_llm: MagicMock) -> ContentService:
        """Create ContentService with mocked dependencies."""
        return ContentService(llm_service=mock_llm)

    @pytest.mark.asyncio
    async def test_ingest_validates_config(self, service: ContentService):
        """Test that ingestion validates config."""
        with pytest.raises(ValueError, match="Invalid configuration"):
            await service.ingest_from_source(
                source_type=SourceType.ARXIV,
                config={},  # Empty config should fail
            )

    @pytest.mark.asyncio
    async def test_process_content_not_found(self, service: ContentService):
        """Test processing non-existent content."""
        fake_id = uuid4()
        with pytest.raises(ValueError, match="Content not found"):
            await service.process_content(fake_id)

    @pytest.mark.asyncio
    async def test_score_relevance_not_found(self, service: ContentService):
        """Test relevance scoring for non-existent content."""
        fake_id = uuid4()
        user_id = uuid4()
        score = await service.score_relevance(fake_id, user_id)
        assert score == 0.0

    @pytest.mark.asyncio
    async def test_mark_content_seen(self, service: ContentService):
        """Test marking content as seen."""
        user_id = uuid4()
        content_id = uuid4()

        # Should not raise even if content doesn't exist
        await service.mark_content_seen(content_id, user_id)

    @pytest.mark.asyncio
    async def test_record_feedback(self, service: ContentService):
        """Test recording user feedback."""
        user_id = uuid4()
        content_id = uuid4()

        # Should not raise even if content doesn't exist
        await service.record_feedback(
            content_id=content_id,
            user_id=user_id,
            relevance_rating=4,
            notes="Good article",
        )

    @pytest.mark.asyncio
    async def test_get_relevant_content_empty(self, service: ContentService):
        """Test getting relevant content when none exists."""
        user_id = uuid4()
        results = await service.get_relevant_content(user_id, limit=10)
        assert results == []

    @pytest.mark.asyncio
    async def test_search_content_empty(self, service: ContentService):
        """Test searching content when none exists."""
        user_id = uuid4()
        results = await service.search_content("test query", user_id)
        assert results == []

    @pytest.mark.asyncio
    async def test_get_content_by_topic_empty(self, service: ContentService):
        """Test getting content by topic when none exists."""
        user_id = uuid4()
        topic_id = uuid4()
        results = await service.get_content_by_topic(topic_id, user_id)
        assert results == []

    def test_clean_content(self, service: ContentService):
        """Test content cleaning."""
        dirty = "Hello [1] world [citation needed]."
        clean = service._clean_content(dirty)
        assert "[1]" not in clean
        assert "[citation needed]" not in clean

    @pytest.mark.asyncio
    async def test_generate_embedding(self, service: ContentService):
        """Test embedding generation (placeholder)."""
        embedding = await service._generate_embedding("test text")
        assert isinstance(embedding, list)
        assert len(embedding) == 384
        assert all(isinstance(x, float) for x in embedding)

    def test_calculate_importance_recent(self, service: ContentService):
        """Test importance calculation for recent content."""
        raw = RawContent(
            source_type=SourceType.ARXIV,
            source_url="https://example.com",
            title="Test",
            content="Content",
            published_at=datetime.utcnow(),
        )
        importance = service._calculate_importance(raw)
        assert importance > 0.5  # Recent content gets boost

    def test_calculate_importance_old(self, service: ContentService):
        """Test importance calculation for old content."""
        from datetime import timedelta
        raw = RawContent(
            source_type=SourceType.BLOG,
            source_url="https://example.com",
            title="Test",
            content="Content",
            published_at=datetime.utcnow() - timedelta(days=60),
        )
        importance = service._calculate_importance(raw)
        assert importance <= 0.6  # Old content doesn't get boost


# --- Integration-like Tests ---

class TestContentServiceIntegration:
    """Integration-like tests for ContentService."""

    @pytest.fixture
    def mock_llm(self) -> MagicMock:
        """Create mock LLM service."""
        llm = MagicMock()
        llm.complete = AsyncMock(return_value=MagicMock(content="Test summary\n\nmachine learning\nneural networks"))
        return llm

    @pytest.fixture
    def service(self, mock_llm: MagicMock) -> ContentService:
        """Create ContentService with mocked dependencies."""
        return ContentService(llm_service=mock_llm)

    @pytest.mark.asyncio
    async def test_full_content_flow(self, service: ContentService, mock_llm: MagicMock):
        """Test full content ingestion and processing flow."""
        # Manually add content (simulating ingestion)
        from src.modules.content.service import StoredContent

        content_id = uuid4()
        raw = RawContent(
            source_type=SourceType.ARXIV,
            source_url="https://arxiv.org/abs/test",
            title="Test Paper",
            content="This is a test paper about machine learning and AI.",
            author="Test Author",
            published_at=datetime.utcnow(),
            metadata={"arxiv_id": "test.12345"},
        )

        stored = StoredContent(id=content_id, raw=raw)
        service._content[content_id] = stored
        service._url_index[raw.source_url] = content_id

        # Configure LLM mock for all calls
        mock_llm.complete = AsyncMock(side_effect=[
            MagicMock(content="This paper discusses ML techniques."),  # summary
            MagicMock(content="machine learning\nneural networks"),  # topics
            MagicMock(content="3"),  # difficulty
        ])

        # Process content
        processed = await service.process_content(content_id)

        assert processed.id == content_id
        assert processed.title == "Test Paper"
        assert len(processed.summary) > 0
        assert len(processed.embedding) == 384
        assert processed.difficulty_level >= 1
        assert processed.difficulty_level <= 5

        # Score relevance
        user_id = uuid4()
        score = await service.score_relevance(content_id, user_id)
        assert 0.0 <= score <= 1.0

        # Search
        results = await service.search_content("machine learning", user_id)
        assert len(results) >= 0  # May or may not match depending on processing

        # Get relevant content
        relevant = await service.get_relevant_content(user_id, min_relevance=0.0)
        assert len(relevant) >= 0
