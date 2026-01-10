"""Shared utilities and common code."""

from src.shared.config import Settings, get_settings
from src.shared.database import (
    Base,
    close_db,
    close_redis,
    get_db_session,
    get_redis,
    init_db,
    shutdown,
    startup,
)
from src.shared.models import (
    ActivityType,
    AdaptationType,
    BaseSchema,
    ErrorResponse,
    PaginatedResponse,
    SessionStatus,
    SessionType,
    SourceType,
    SuccessResponse,
    TimestampMixin,
    UUIDMixin,
)

__all__ = [
    # Config
    "Settings",
    "get_settings",
    # Database
    "Base",
    "get_db_session",
    "get_redis",
    "init_db",
    "close_db",
    "close_redis",
    "startup",
    "shutdown",
    # Models
    "BaseSchema",
    "TimestampMixin",
    "UUIDMixin",
    "SuccessResponse",
    "ErrorResponse",
    "PaginatedResponse",
    # Enums
    "SourceType",
    "SessionStatus",
    "SessionType",
    "ActivityType",
    "AdaptationType",
]
