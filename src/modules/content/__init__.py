"""Content Module - Ingestion, processing, and retrieval.

Usage:
    # Recommended: Use service registry (respects feature flags)
    from src.modules.content import get_content_service
    service = get_content_service()

    # Direct access (bypasses feature flags)
    from src.modules.content import get_inmemory_content_service
    from src.modules.content import get_db_content_service
"""

from src.modules.content.interface import (
    Content,
    IContentService,
    ProcessedContent,
    RawContent,
    SourceAdapter,
)
from src.modules.content.service import ContentService
from src.modules.content.service import get_content_service as get_inmemory_content_service
from src.modules.content.db_service import DatabaseContentService, get_db_content_service
from src.modules.content.adapters import ArxivAdapter, RSSAdapter
from src.modules.content.models import (
    ContentModel,
    TopicModel,
    UserContentInteractionModel,
    UserTopicProgressModel,
)

# Registry-based service getter (recommended)
from src.shared.service_registry import get_content_service

__all__ = [
    # Interface types
    "Content",
    "IContentService",
    "ProcessedContent",
    "RawContent",
    "SourceAdapter",
    # Implementations
    "ContentService",
    "DatabaseContentService",
    "ArxivAdapter",
    "RSSAdapter",
    # Models
    "ContentModel",
    "TopicModel",
    "UserContentInteractionModel",
    "UserTopicProgressModel",
    # Factory functions (recommended: get_content_service from registry)
    "get_content_service",  # Registry-based (respects feature flags)
    "get_inmemory_content_service",  # Direct in-memory access
    "get_db_content_service",  # Direct database access
]
