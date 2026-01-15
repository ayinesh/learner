"""Session Module - Learning session lifecycle management.

Usage:
    # Recommended: Use service registry (respects feature flags)
    from src.modules.session import get_session_service
    service = get_session_service()

    # Direct access (bypasses feature flags)
    from src.modules.session import get_inmemory_session_service
    from src.modules.session import get_db_session_service
"""

from src.modules.session.interface import (
    ISessionService,
    Session,
    SessionActivity,
    SessionPlan,
    SessionPlanItem,
    SessionSummary,
)
from src.modules.session.service import SessionService
from src.modules.session.service import get_session_service as get_inmemory_session_service
from src.modules.session.db_service import DatabaseSessionService, get_db_session_service
from src.modules.session.models import (
    SessionModel,
    SessionActivityModel,
    UserLearningPatternModel,
)
from src.shared.models import SessionType, SessionStatus, ActivityType

# Registry-based service getter (recommended)
from src.shared.service_registry import get_session_service

__all__ = [
    # Interface types
    "ISessionService",
    "Session",
    "SessionActivity",
    "SessionPlan",
    "SessionPlanItem",
    "SessionSummary",
    # Enums (re-exported for convenience)
    "SessionType",
    "SessionStatus",
    "ActivityType",
    # Implementations
    "SessionService",
    "DatabaseSessionService",
    # Models
    "SessionModel",
    "SessionActivityModel",
    "UserLearningPatternModel",
    # Factory functions (recommended: get_session_service from registry)
    "get_session_service",  # Registry-based (respects feature flags)
    "get_inmemory_session_service",  # Direct in-memory access
    "get_db_session_service",  # Direct database access
]
