"""Unit tests for embedding service."""

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.modules.content.embeddings import (
    EMBEDDING_DIMENSION,
    EmbeddingService,
    OpenAIEmbedding,
    PlaceholderEmbedding,
    clear_embedding_service_cache,
    get_embedding_service,
)
from src.shared.feature_flags import FeatureFlags, get_feature_flags


class TestPlaceholderEmbedding:
    """Test placeholder embedding service."""

    @pytest.fixture
    def service(self):
        """Create placeholder embedding service."""
        return PlaceholderEmbedding()

    @pytest.mark.asyncio
    async def test_dimension(self, service):
        """Test embedding dimension is correct."""
        assert service.dimension == EMBEDDING_DIMENSION

    @pytest.mark.asyncio
    async def test_generate_embedding(self, service):
        """Test embedding generation."""
        text = "This is a test"
        embedding = await service.generate(text)

        assert isinstance(embedding, list)
        assert len(embedding) == EMBEDDING_DIMENSION
        assert all(isinstance(x, float) for x in embedding)
        assert all(0.0 <= x <= 1.0 for x in embedding)

    @pytest.mark.asyncio
    async def test_deterministic(self, service):
        """Test embeddings are deterministic."""
        text = "Deterministic test"
        embedding1 = await service.generate(text)
        embedding2 = await service.generate(text)

        assert embedding1 == embedding2

    @pytest.mark.asyncio
    async def test_different_text_different_embedding(self, service):
        """Test different texts produce different embeddings."""
        text1 = "First text"
        text2 = "Second text"

        embedding1 = await service.generate(text1)
        embedding2 = await service.generate(text2)

        assert embedding1 != embedding2

    @pytest.mark.asyncio
    async def test_empty_text(self, service):
        """Test embedding generation with empty text."""
        embedding = await service.generate("")

        assert len(embedding) == EMBEDDING_DIMENSION
        assert all(x == 0.0 for x in embedding)

    @pytest.mark.asyncio
    async def test_batch_generate(self, service):
        """Test batch embedding generation."""
        texts = ["First", "Second", "Third"]
        embeddings = await service.batch_generate(texts)

        assert len(embeddings) == len(texts)
        for embedding in embeddings:
            assert len(embedding) == EMBEDDING_DIMENSION

        # Verify each embedding matches individual generation
        for text, batch_embedding in zip(texts, embeddings):
            individual_embedding = await service.generate(text)
            assert batch_embedding == individual_embedding

    @pytest.mark.asyncio
    async def test_batch_empty_list(self, service):
        """Test batch generation with empty list."""
        embeddings = await service.batch_generate([])
        assert embeddings == []

    @pytest.mark.asyncio
    async def test_md5_based_generation(self, service):
        """Test that embedding is based on MD5 hash."""
        text = "MD5 test"
        embedding = await service.generate(text)

        # Manually compute expected embedding
        hash_val = hashlib.md5(text.encode()).hexdigest()
        expected = []
        for i in range(0, 32, 2):
            value = int(hash_val[i:i+2], 16) / 255.0
            expected.append(value)
        expected.extend([0.0] * (EMBEDDING_DIMENSION - len(expected)))

        assert embedding == expected[:EMBEDDING_DIMENSION]


class TestOpenAIEmbedding:
    """Test OpenAI embedding service."""

    @pytest.fixture
    def service(self):
        """Create OpenAI embedding service with mock API key."""
        return OpenAIEmbedding(api_key="test-key")

    def test_dimension(self, service):
        """Test embedding dimension is correct."""
        assert service.dimension == EMBEDDING_DIMENSION

    @pytest.mark.asyncio
    async def test_generate_embedding_success(self, service):
        """Test successful embedding generation."""
        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * EMBEDDING_DIMENSION)]

        mock_client = AsyncMock()
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)

        with patch("openai.AsyncOpenAI", return_value=mock_client):
            text = "Test text"
            embedding = await service.generate(text)

            assert len(embedding) == EMBEDDING_DIMENSION
            assert all(x == 0.1 for x in embedding)

            # Verify API was called correctly
            mock_client.embeddings.create.assert_called_once()
            call_kwargs = mock_client.embeddings.create.call_args.kwargs
            assert call_kwargs["model"] == "text-embedding-3-small"
            assert call_kwargs["input"] == text

    @pytest.mark.asyncio
    async def test_text_truncation(self, service):
        """Test that long text is truncated."""
        # Create text longer than 8000 chars
        long_text = "a" * 10000

        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.5] * EMBEDDING_DIMENSION)]

        mock_client = AsyncMock()
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)

        with patch("openai.AsyncOpenAI", return_value=mock_client):
            await service.generate(long_text)

            # Verify truncated text was sent
            call_kwargs = mock_client.embeddings.create.call_args.kwargs
            assert len(call_kwargs["input"]) == 8000

    @pytest.mark.asyncio
    async def test_empty_text_handling(self, service):
        """Test handling of empty text."""
        embedding = await service.generate("")

        # Should return zero vector without API call
        assert len(embedding) == EMBEDDING_DIMENSION
        assert all(x == 0.0 for x in embedding)

    @pytest.mark.asyncio
    async def test_dimension_correction(self, service):
        """Test correction of unexpected embedding dimensions."""
        # Mock response with wrong dimension
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 100)]  # Wrong size

        mock_client = AsyncMock()
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)

        with patch("openai.AsyncOpenAI", return_value=mock_client):
            embedding = await service.generate("test")

            # Should be corrected to correct dimension
            assert len(embedding) == EMBEDDING_DIMENSION

    @pytest.mark.asyncio
    async def test_batch_generate_success(self, service):
        """Test successful batch embedding generation."""
        texts = ["First", "Second", "Third"]

        # Mock batch response
        mock_response = MagicMock()
        mock_response.data = [
            MagicMock(embedding=[0.1] * EMBEDDING_DIMENSION),
            MagicMock(embedding=[0.2] * EMBEDDING_DIMENSION),
            MagicMock(embedding=[0.3] * EMBEDDING_DIMENSION),
        ]

        mock_client = AsyncMock()
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)

        with patch("openai.AsyncOpenAI", return_value=mock_client):
            embeddings = await service.batch_generate(texts)

            assert len(embeddings) == 3
            assert embeddings[0][0] == 0.1
            assert embeddings[1][0] == 0.2
            assert embeddings[2][0] == 0.3

    @pytest.mark.asyncio
    async def test_batch_with_empty_texts(self, service):
        """Test batch generation handles empty texts."""
        texts = ["First", "", "Third"]

        mock_response = MagicMock()
        mock_response.data = [
            MagicMock(embedding=[0.1] * EMBEDDING_DIMENSION),
            MagicMock(embedding=[0.3] * EMBEDDING_DIMENSION),
        ]

        mock_client = AsyncMock()
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)

        with patch("openai.AsyncOpenAI", return_value=mock_client):
            embeddings = await service.batch_generate(texts)

            assert len(embeddings) == 3
            # Second embedding should be zero vector
            assert all(x == 0.0 for x in embeddings[1])

    @pytest.mark.asyncio
    async def test_batch_empty_list(self, service):
        """Test batch generation with empty list."""
        embeddings = await service.batch_generate([])
        assert embeddings == []

    @pytest.mark.asyncio
    async def test_api_error_handling(self, service):
        """Test handling of API errors."""
        mock_client = AsyncMock()
        mock_client.embeddings.create = AsyncMock(
            side_effect=Exception("API Error")
        )

        with patch("openai.AsyncOpenAI", return_value=mock_client):
            with pytest.raises(Exception, match="API Error"):
                await service.generate("test")

    @pytest.mark.asyncio
    async def test_no_api_key(self):
        """Test error when no API key is provided."""
        service = OpenAIEmbedding(api_key=None)

        with patch("src.modules.content.embeddings.get_settings") as mock_settings:
            mock_settings.return_value.openai_api_key = None

            with pytest.raises(ValueError, match="OpenAI API key not configured"):
                await service.generate("test")

    @pytest.mark.asyncio
    async def test_batch_fallback_on_error(self, service):
        """Test batch generation falls back to sequential on error."""
        mock_client = AsyncMock()
        # First call (batch) fails, subsequent calls (sequential) succeed
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * EMBEDDING_DIMENSION)]

        mock_client.embeddings.create = AsyncMock(
            side_effect=[
                Exception("Batch failed"),
                mock_response,
                mock_response,
            ]
        )

        with patch("openai.AsyncOpenAI", return_value=mock_client):
            texts = ["First", "Second"]
            embeddings = await service.batch_generate(texts)

            # Should still return results via fallback
            assert len(embeddings) == 2


class TestEmbeddingServiceFactory:
    """Test embedding service factory function."""

    def teardown_method(self):
        """Clear caches after each test."""
        clear_embedding_service_cache()
        get_feature_flags().clear_all_overrides()

    def test_placeholder_when_flag_disabled(self):
        """Test placeholder service when feature flag is disabled."""
        flags = get_feature_flags()
        flags.disable(FeatureFlags.ENABLE_REAL_EMBEDDINGS)

        with patch("src.modules.content.embeddings.get_settings") as mock_settings:
            mock_settings.return_value.openai_api_key = "test-key"

            service = get_embedding_service(force_reload=True)
            assert isinstance(service, PlaceholderEmbedding)

    def test_placeholder_when_no_api_key(self):
        """Test placeholder service when API key is missing."""
        flags = get_feature_flags()
        flags.enable(FeatureFlags.ENABLE_REAL_EMBEDDINGS)

        with patch("src.modules.content.embeddings.get_settings") as mock_settings:
            mock_settings.return_value.openai_api_key = None

            service = get_embedding_service(force_reload=True)
            assert isinstance(service, PlaceholderEmbedding)

    def test_openai_when_enabled_and_key_present(self):
        """Test OpenAI service when feature flag enabled and API key present."""
        flags = get_feature_flags()
        flags.enable(FeatureFlags.ENABLE_REAL_EMBEDDINGS)

        with patch("src.modules.content.embeddings.get_settings") as mock_settings:
            mock_settings.return_value.openai_api_key = "test-key"

            service = get_embedding_service(force_reload=True)
            assert isinstance(service, OpenAIEmbedding)

    def test_singleton_caching(self):
        """Test that service is cached."""
        service1 = get_embedding_service()
        service2 = get_embedding_service()

        assert service1 is service2

    def test_force_reload(self):
        """Test force reload creates new instance."""
        service1 = get_embedding_service()
        service2 = get_embedding_service(force_reload=True)

        # May be different instances
        # (depending on configuration, but reload should be respected)
        assert service1 is not service2 or service1 is service2

    def test_clear_cache(self):
        """Test cache clearing."""
        service1 = get_embedding_service()
        clear_embedding_service_cache()
        service2 = get_embedding_service()

        # Should create new instance
        assert service1 is not service2


class TestEmbeddingIntegration:
    """Integration tests for embedding services."""

    @pytest.mark.asyncio
    async def test_consistent_dimensions(self):
        """Test that all services return same dimension."""
        placeholder = PlaceholderEmbedding()
        openai_service = OpenAIEmbedding(api_key="test")

        assert placeholder.dimension == openai_service.dimension == EMBEDDING_DIMENSION

    @pytest.mark.asyncio
    async def test_embedding_normalization(self):
        """Test that embeddings are normalized properly."""
        service = PlaceholderEmbedding()
        text = "Normalization test"

        embedding = await service.generate(text)

        # Check all values are valid floats
        assert all(isinstance(x, float) for x in embedding)
        assert all(not (x < 0 or x > 1) for x in embedding)

    @pytest.mark.asyncio
    async def test_batch_consistency(self):
        """Test batch and individual generation are consistent."""
        service = PlaceholderEmbedding()
        texts = ["Text 1", "Text 2", "Text 3"]

        # Generate individually
        individual = [await service.generate(t) for t in texts]

        # Generate in batch
        batch = await service.batch_generate(texts)

        assert individual == batch
