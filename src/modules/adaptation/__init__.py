"""Adaptation Module - Learning pattern analysis and system adjustments.

Usage:
    # Recommended: Use service registry (respects feature flags)
    from src.modules.adaptation import get_adaptation_service
    service = get_adaptation_service()

    # Direct access (bypasses feature flags)
    from src.modules.adaptation import get_inmemory_adaptation_service
    from src.modules.adaptation import get_db_adaptation_service
"""

from src.modules.adaptation.interface import (
    AdaptationEvent,
    AdaptationResult,
    AdaptationTrigger,
    IAdaptationService,
    PaceRecommendation,
    RecoveryPlan,
)
from src.modules.adaptation.service import AdaptationService
from src.modules.adaptation.service import get_adaptation_service as get_inmemory_adaptation_service
from src.modules.adaptation.db_service import DatabaseAdaptationService, get_db_adaptation_service
from src.modules.adaptation.models import AdaptationEventModel

# Registry-based service getter (recommended)
from src.shared.service_registry import get_adaptation_service

__all__ = [
    # Interface types
    "AdaptationEvent",
    "AdaptationResult",
    "AdaptationTrigger",
    "IAdaptationService",
    "PaceRecommendation",
    "RecoveryPlan",
    # Implementations
    "AdaptationService",
    "DatabaseAdaptationService",
    # Models
    "AdaptationEventModel",
    # Factory functions (recommended: get_adaptation_service from registry)
    "get_adaptation_service",  # Registry-based (respects feature flags)
    "get_inmemory_adaptation_service",  # Direct in-memory access
    "get_db_adaptation_service",  # Direct database access
]
