"""API routers package."""

from src.api.routers.auth import router as auth_router
from src.api.routers.users import router as users_router
from src.api.routers.sessions import router as sessions_router
from src.api.routers.content import router as content_router
from src.api.routers.assessments import router as assessments_router
from src.api.routers.health import router as health_router

__all__ = [
    "auth_router",
    "users_router",
    "sessions_router",
    "content_router",
    "assessments_router",
    "health_router",
]
