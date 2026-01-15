"""Content Adapter Registry.

This module provides a registry pattern for content source adapters,
allowing new adapters to be registered and retrieved dynamically.
"""

from typing import Callable, Type

from src.modules.content.interface import SourceAdapter
from src.shared.exceptions import AdapterNotFoundError
from src.shared.models import SourceType


class AdapterRegistry:
    """Registry for content source adapters.

    Provides a centralized way to register and retrieve adapters
    for different content source types. This enables:
    - Dynamic adapter registration at startup
    - Easy addition of new adapters without modifying core code
    - Lazy instantiation of adapters

    Usage:
        # Register adapters (typically at application startup)
        registry = AdapterRegistry()
        registry.register(SourceType.ARXIV, ArxivAdapter)
        registry.register(SourceType.RSS, RSSAdapter)

        # Get adapter instance
        adapter = registry.get(SourceType.ARXIV)
        content = await adapter.fetch_new(config)
    """

    def __init__(self) -> None:
        """Initialize empty registry."""
        self._adapters: dict[SourceType, Type[SourceAdapter]] = {}
        self._instances: dict[SourceType, SourceAdapter] = {}

    def register(
        self,
        source_type: SourceType,
        adapter_class: Type[SourceAdapter],
    ) -> None:
        """Register an adapter class for a source type.

        Args:
            source_type: The source type this adapter handles
            adapter_class: The adapter class to register
        """
        self._adapters[source_type] = adapter_class

    def unregister(self, source_type: SourceType) -> None:
        """Unregister an adapter.

        Args:
            source_type: The source type to unregister
        """
        self._adapters.pop(source_type, None)
        self._instances.pop(source_type, None)

    def get(self, source_type: SourceType) -> SourceAdapter:
        """Get adapter instance for a source type.

        Adapters are lazily instantiated and cached.

        Args:
            source_type: The source type to get adapter for

        Returns:
            SourceAdapter instance

        Raises:
            AdapterNotFoundError: If no adapter is registered for the source type
        """
        if source_type not in self._adapters:
            raise AdapterNotFoundError(source_type.value)

        if source_type not in self._instances:
            adapter_class = self._adapters[source_type]
            self._instances[source_type] = adapter_class()

        return self._instances[source_type]

    def has_adapter(self, source_type: SourceType) -> bool:
        """Check if an adapter is registered for a source type.

        Args:
            source_type: The source type to check

        Returns:
            True if adapter is registered
        """
        return source_type in self._adapters

    def get_registered_types(self) -> list[SourceType]:
        """Get list of registered source types.

        Returns:
            List of registered SourceType values
        """
        return list(self._adapters.keys())

    def clear_instances(self) -> None:
        """Clear all cached adapter instances.

        Useful for testing or when adapters need to be re-instantiated.
        """
        self._instances.clear()


# Global registry instance
_global_registry: AdapterRegistry | None = None


def get_adapter_registry() -> AdapterRegistry:
    """Get the global adapter registry.

    Returns:
        The global AdapterRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = AdapterRegistry()
    return _global_registry


def register_default_adapters(registry: AdapterRegistry) -> None:
    """Register all default content adapters.

    This function registers all built-in adapters with the registry.
    It should be called during application startup.

    Args:
        registry: The registry to register adapters with
    """
    from src.modules.content.adapters.arxiv import ArxivAdapter
    from src.modules.content.adapters.rss import RSSAdapter
    from src.modules.content.adapters.youtube import YouTubeAdapter
    from src.modules.content.adapters.github import GitHubAdapter
    from src.modules.content.adapters.reddit import RedditAdapter
    from src.modules.content.adapters.twitter import TwitterAdapter

    registry.register(SourceType.ARXIV, ArxivAdapter)
    registry.register(SourceType.BLOG, RSSAdapter)
    registry.register(SourceType.YOUTUBE, YouTubeAdapter)
    registry.register(SourceType.GITHUB, GitHubAdapter)
    registry.register(SourceType.REDDIT, RedditAdapter)
    registry.register(SourceType.TWITTER, TwitterAdapter)


def initialize_adapters() -> AdapterRegistry:
    """Initialize the global adapter registry with default adapters.

    Returns:
        The initialized AdapterRegistry
    """
    registry = get_adapter_registry()
    register_default_adapters(registry)
    return registry
