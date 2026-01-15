"""Validation script for Phase 4: Content Pipeline Completion.

This script validates that all Phase 4 components are working correctly:
- Embedding service (placeholder and OpenAI)
- Vector search service
- Content service integration
- Feature flag integration

Run: python validate_phase4.py
"""

import asyncio
import sys
from uuid import uuid4

from src.modules.content.embeddings import (
    PlaceholderEmbedding,
    OpenAIEmbedding,
    get_embedding_service,
    EMBEDDING_DIMENSION,
)
from src.modules.content.vector_search import get_vector_search_service
from src.modules.content.db_service import DatabaseContentService
from src.shared.feature_flags import FeatureFlags, get_feature_flags
from src.shared.config import get_settings


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def print_success(message: str):
    """Print a success message."""
    print(f"[OK] {message}")


def print_error(message: str):
    """Print an error message."""
    print(f"[ERROR] {message}")


def print_warning(message: str):
    """Print a warning message."""
    print(f"[WARN] {message}")


async def validate_placeholder_embedding():
    """Validate placeholder embedding service."""
    print_section("Placeholder Embedding Service")

    try:
        service = PlaceholderEmbedding()

        # Test dimension
        assert service.dimension == EMBEDDING_DIMENSION
        print_success(f"Dimension correct: {service.dimension}")

        # Test single embedding
        text = "Test embedding generation"
        embedding = await service.generate(text)
        assert len(embedding) == EMBEDDING_DIMENSION
        assert all(isinstance(x, float) for x in embedding)
        print_success(f"Single embedding generated: {len(embedding)} dimensions")

        # Test deterministic
        embedding2 = await service.generate(text)
        assert embedding == embedding2
        print_success("Embeddings are deterministic")

        # Test batch
        texts = ["First", "Second", "Third"]
        embeddings = await service.batch_generate(texts)
        assert len(embeddings) == len(texts)
        print_success(f"Batch embeddings generated: {len(embeddings)} items")

        return True
    except Exception as e:
        print_error(f"Placeholder embedding validation failed: {e}")
        return False


async def validate_openai_embedding():
    """Validate OpenAI embedding service (mock mode)."""
    print_section("OpenAI Embedding Service")

    try:
        settings = get_settings()

        if not settings.openai_api_key:
            print_warning("OpenAI API key not configured (this is OK for testing)")
            print_warning("Set OPENAI_API_KEY to test real embeddings")
            return True

        # Don't actually call API in validation
        service = OpenAIEmbedding(api_key=settings.openai_api_key)
        assert service.dimension == EMBEDDING_DIMENSION
        print_success(f"OpenAI service initialized with dimension: {service.dimension}")

        print_warning("Skipping real API calls in validation (to avoid costs)")
        print_warning("Run integration tests to validate API calls")

        return True
    except Exception as e:
        print_error(f"OpenAI embedding validation failed: {e}")
        return False


async def validate_embedding_factory():
    """Validate embedding service factory."""
    print_section("Embedding Service Factory")

    try:
        flags = get_feature_flags()
        settings = get_settings()

        # Test with flag disabled
        flags.disable(FeatureFlags.ENABLE_REAL_EMBEDDINGS)
        service = get_embedding_service(force_reload=True)
        assert isinstance(service, PlaceholderEmbedding)
        print_success("Factory returns PlaceholderEmbedding when flag disabled")

        # Test with flag enabled but no API key
        flags.enable(FeatureFlags.ENABLE_REAL_EMBEDDINGS)
        if not settings.openai_api_key:
            service = get_embedding_service(force_reload=True)
            assert isinstance(service, PlaceholderEmbedding)
            print_success("Factory returns PlaceholderEmbedding when API key missing")
        else:
            service = get_embedding_service(force_reload=True)
            assert isinstance(service, OpenAIEmbedding)
            print_success("Factory returns OpenAIEmbedding when enabled and key present")

        # Reset flag
        flags.clear_all_overrides()

        return True
    except Exception as e:
        print_error(f"Embedding factory validation failed: {e}")
        return False


async def validate_vector_search():
    """Validate vector search service."""
    print_section("Vector Search Service")

    try:
        service = get_vector_search_service()
        print_success("Vector search service initialized")

        # Test that methods exist
        assert hasattr(service, 'similarity_search')
        assert hasattr(service, 'similarity_search_with_content')
        assert hasattr(service, 'find_similar_to_content')
        assert hasattr(service, 'hybrid_search')
        assert hasattr(service, 'get_index_stats')
        print_success("All vector search methods available")

        # Test dimension validation
        try:
            await service.similarity_search(
                query_embedding=[0.1] * 100,  # Wrong dimension
                limit=10
            )
            print_error("Should have raised dimension error")
            return False
        except ValueError as e:
            if "1536 dimensions" in str(e):
                print_success("Dimension validation working correctly")
            else:
                raise

        return True
    except Exception as e:
        print_error(f"Vector search validation failed: {e}")
        return False


async def validate_content_service_integration():
    """Validate content service integration."""
    print_section("Content Service Integration")

    try:
        service = DatabaseContentService(
            embedding_service=PlaceholderEmbedding()
        )
        print_success("DatabaseContentService initialized with embedding service")

        # Check methods exist
        assert hasattr(service, 'search_content')
        assert hasattr(service, 'vector_search_content')
        assert hasattr(service, 'process_content')
        print_success("All required methods available")

        # Test embedding generation (without DB)
        test_embedding = await service._generate_embedding("Test text")
        assert len(test_embedding) == EMBEDDING_DIMENSION
        print_success(f"Embedding generation working: {len(test_embedding)} dimensions")

        return True
    except Exception as e:
        print_error(f"Content service integration validation failed: {e}")
        return False


async def validate_feature_flags():
    """Validate feature flag integration."""
    print_section("Feature Flag Integration")

    try:
        flags = get_feature_flags()

        # Test flag exists
        assert hasattr(FeatureFlags, 'ENABLE_REAL_EMBEDDINGS')
        print_success("ENABLE_REAL_EMBEDDINGS flag exists")

        # Test flag operations
        flags.enable(FeatureFlags.ENABLE_REAL_EMBEDDINGS)
        assert flags.is_enabled(FeatureFlags.ENABLE_REAL_EMBEDDINGS)
        print_success("Flag enable/check working")

        flags.disable(FeatureFlags.ENABLE_REAL_EMBEDDINGS)
        assert not flags.is_enabled(FeatureFlags.ENABLE_REAL_EMBEDDINGS)
        print_success("Flag disable working")

        # Reset
        flags.clear_all_overrides()

        return True
    except Exception as e:
        print_error(f"Feature flag validation failed: {e}")
        return False


async def main():
    """Run all validation checks."""
    print("=" * 60)
    print("  Phase 4: Content Pipeline Completion - Validation")
    print("=" * 60)
    print("\nValidating implementation components...\n")

    results = []

    # Run all validations
    results.append(("Placeholder Embedding", await validate_placeholder_embedding()))
    results.append(("OpenAI Embedding", await validate_openai_embedding()))
    results.append(("Embedding Factory", await validate_embedding_factory()))
    results.append(("Vector Search", await validate_vector_search()))
    results.append(("Content Service", await validate_content_service_integration()))
    results.append(("Feature Flags", await validate_feature_flags()))

    # Summary
    print_section("Validation Summary")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "PASS" if result else "FAIL"
        symbol = "[OK]" if result else "[X]"
        print(f"{symbol} {name}: {status}")

    print(f"\nTotal: {passed}/{total} checks passed")

    if passed == total:
        print("\n[SUCCESS] All Phase 4 components validated successfully!")
        print("\nNext steps:")
        print("  1. Apply database migration: python migrate.py")
        print("  2. Run tests: pytest tests/unit/test_embeddings.py -v")
        print("  3. Run integration tests: pytest tests/integration/test_content_pipeline.py -v")
        print("  4. Set OPENAI_API_KEY to enable real embeddings (optional)")
        return 0
    else:
        print("\n[FAILURE] Some validations failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
