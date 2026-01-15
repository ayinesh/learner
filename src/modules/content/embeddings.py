"""Embedding service for generating vector embeddings from text.

This module provides an abstraction layer for embedding generation with
support for multiple providers (OpenAI) and a placeholder fallback for
development and testing.

Usage:
    from src.modules.content.embeddings import get_embedding_service

    service = get_embedding_service()
    embedding = await service.generate("Some text to embed")
"""

import hashlib
import logging
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Protocol

from src.shared.config import get_settings
from src.shared.feature_flags import FeatureFlags, get_feature_flags

logger = logging.getLogger(__name__)

# Standard embedding dimension for text-embedding-3-small
EMBEDDING_DIMENSION = 1536


class EmbeddingService(ABC):
    """Abstract base class for embedding services.

    All embedding services must implement the generate method to convert
    text into a fixed-size vector representation.
    """

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding dimension size."""
        ...

    @abstractmethod
    async def generate(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector
        """
        ...

    async def batch_generate(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Default implementation generates embeddings sequentially.
        Subclasses can override for batch optimization.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors, one per input text
        """
        embeddings = []
        for text in texts:
            embedding = await self.generate(text)
            embeddings.append(embedding)
        return embeddings


class OpenAIEmbedding(EmbeddingService):
    """OpenAI embedding service using text-embedding-3-small model.

    This service uses OpenAI's embedding API to generate high-quality
    semantic embeddings. It requires an OpenAI API key to be configured.

    Features:
    - 1536-dimensional embeddings
    - Automatic text truncation to avoid token limits
    - Batch support for efficient API usage
    - Error handling with informative logging
    """

    def __init__(self, api_key: str | None = None):
        """Initialize OpenAI embedding service.

        Args:
            api_key: OpenAI API key. If not provided, reads from settings.
        """
        self._api_key = api_key
        self._client = None
        logger.info("OpenAIEmbedding service initialized")

    @property
    def dimension(self) -> int:
        """Return embedding dimension (1536 for text-embedding-3-small)."""
        return EMBEDDING_DIMENSION

    async def _get_client(self):
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            try:
                import openai

                settings = get_settings()
                api_key = self._api_key or settings.openai_api_key

                if not api_key:
                    raise ValueError("OpenAI API key not configured")

                self._client = openai.AsyncOpenAI(api_key=api_key)
                logger.info("OpenAI client initialized")
            except ImportError:
                raise ImportError(
                    "openai package not installed. Install with: pip install openai"
                )
        return self._client

    async def generate(self, text: str) -> list[float]:
        """Generate embedding for text using OpenAI API.

        Args:
            text: Text to embed (will be truncated to 8000 chars)

        Returns:
            1536-dimensional embedding vector

        Raises:
            ValueError: If API key not configured
            ImportError: If openai package not installed
        """
        if not text or not text.strip():
            logger.warning("Empty text provided to embedding service")
            return [0.0] * self.dimension

        try:
            client = await self._get_client()

            # Truncate text to avoid token limits (8000 chars ~= 2000 tokens)
            truncated_text = text[:8000]

            # Generate embedding
            response = await client.embeddings.create(
                model="text-embedding-3-small",
                input=truncated_text,
                encoding_format="float"
            )

            embedding = response.data[0].embedding

            # Validate dimension
            if len(embedding) != self.dimension:
                logger.error(
                    f"Unexpected embedding dimension: {len(embedding)}, "
                    f"expected {self.dimension}"
                )
                # Pad or truncate to correct dimension
                if len(embedding) < self.dimension:
                    embedding.extend([0.0] * (self.dimension - len(embedding)))
                else:
                    embedding = embedding[:self.dimension]

            return embedding

        except Exception as e:
            logger.error(f"Error generating OpenAI embedding: {e}")
            raise

    async def batch_generate(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts using batch API.

        More efficient than calling generate() multiple times.

        Args:
            texts: List of texts to embed (each truncated to 8000 chars)

        Returns:
            List of 1536-dimensional embedding vectors
        """
        if not texts:
            return []

        try:
            client = await self._get_client()

            # Truncate all texts
            truncated_texts = [text[:8000] for text in texts]

            # Remove empty texts but track their indices
            text_map = {}
            valid_texts = []
            for idx, text in enumerate(truncated_texts):
                if text and text.strip():
                    text_map[len(valid_texts)] = idx
                    valid_texts.append(text)

            if not valid_texts:
                return [[0.0] * self.dimension] * len(texts)

            # Generate embeddings in batch
            response = await client.embeddings.create(
                model="text-embedding-3-small",
                input=valid_texts,
                encoding_format="float"
            )

            # Build result list with embeddings in correct positions
            embeddings = [[0.0] * self.dimension] * len(texts)
            for i, data in enumerate(response.data):
                original_idx = text_map[i]
                embeddings[original_idx] = data.embedding

            return embeddings

        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            # Fall back to sequential generation
            logger.info("Falling back to sequential embedding generation")
            return await super().batch_generate(texts)


class PlaceholderEmbedding(EmbeddingService):
    """Placeholder embedding service for development and testing.

    This service generates deterministic embeddings using MD5 hashing.
    It does not require any API keys and is useful for:
    - Development without API costs
    - Testing with reproducible embeddings
    - CI/CD pipelines

    Note: These embeddings do not capture semantic meaning and should
    only be used for development/testing purposes.
    """

    @property
    def dimension(self) -> int:
        """Return embedding dimension (1536 to match OpenAI)."""
        return EMBEDDING_DIMENSION

    async def generate(self, text: str) -> list[float]:
        """Generate deterministic placeholder embedding using MD5 hash.

        The embedding is generated by:
        1. Computing MD5 hash of the text (32 hex chars)
        2. Converting hex pairs to floats in [0, 1] range
        3. Padding with zeros to reach 1536 dimensions

        Args:
            text: Text to embed

        Returns:
            1536-dimensional embedding vector
        """
        if not text:
            return [0.0] * self.dimension

        # Generate MD5 hash
        hash_val = hashlib.md5(text.encode()).hexdigest()

        # Convert hex pairs to floats (32 chars = 16 float values)
        embedding = []
        for i in range(0, 32, 2):
            # Convert hex pair to int (0-255), then normalize to [0, 1]
            value = int(hash_val[i:i+2], 16) / 255.0
            embedding.append(value)

        # Pad with zeros to reach target dimension
        embedding.extend([0.0] * (self.dimension - len(embedding)))

        return embedding[:self.dimension]

    async def batch_generate(self, texts: list[str]) -> list[list[float]]:
        """Generate placeholder embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of 1536-dimensional embedding vectors
        """
        return [await self.generate(text) for text in texts]


# Factory and singleton management

_embedding_service: EmbeddingService | None = None


def get_embedding_service(force_reload: bool = False) -> EmbeddingService:
    """Get the appropriate embedding service based on configuration.

    Selection logic:
    1. If FF_ENABLE_REAL_EMBEDDINGS flag is enabled and OpenAI API key is set:
       -> Use OpenAIEmbedding
    2. Otherwise:
       -> Use PlaceholderEmbedding

    Args:
        force_reload: If True, recreate the service instance

    Returns:
        Configured embedding service instance
    """
    global _embedding_service

    if _embedding_service is not None and not force_reload:
        return _embedding_service

    settings = get_settings()
    flags = get_feature_flags()

    # Check if real embeddings should be used
    use_real_embeddings = (
        flags.is_enabled(FeatureFlags.ENABLE_REAL_EMBEDDINGS) and
        settings.openai_api_key is not None
    )

    if use_real_embeddings:
        logger.info("Using OpenAI embeddings")
        _embedding_service = OpenAIEmbedding()
    else:
        if not settings.openai_api_key:
            logger.info("OpenAI API key not configured, using placeholder embeddings")
        else:
            logger.info(
                "Real embeddings feature flag disabled, using placeholder embeddings"
            )
        _embedding_service = PlaceholderEmbedding()

    return _embedding_service


def clear_embedding_service_cache() -> None:
    """Clear the cached embedding service instance.

    Useful for testing or when configuration changes.
    """
    global _embedding_service
    _embedding_service = None
    logger.info("Embedding service cache cleared")
