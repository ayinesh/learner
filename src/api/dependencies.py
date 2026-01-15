"""FastAPI dependency injection for services and authentication.

This module implements proper dependency injection for all services,
replacing the global singleton pattern with FastAPI's Depends() system.
"""

from typing import Annotated, AsyncGenerator
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.auth.interface import User
from src.shared.database import get_db_session as get_db_context


# Security scheme
security = HTTPBearer()


# ===================
# Database Session
# ===================

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for dependency injection.

    This properly manages the session lifecycle within a request.
    """
    async with get_db_context() as session:
        yield session


# Type alias for database session dependency
DbSession = Annotated[AsyncSession, Depends(get_db)]


# ===================
# Service Dependencies
# ===================

async def get_auth_service():
    """Get auth service instance."""
    from src.modules.auth.service import AuthService
    return AuthService()


async def get_user_service():
    """Get user service instance."""
    from src.modules.user.service import UserService
    return UserService()


async def get_session_service(db: DbSession):
    """Get session service instance with injected database session."""
    from src.modules.session.service import SessionService
    return SessionService(db)


async def get_content_service(db: DbSession):
    """Get content service instance with injected database session."""
    from src.modules.content.service import ContentService
    return ContentService(db)


async def get_assessment_service(db: DbSession):
    """Get assessment service instance with injected database session."""
    from src.modules.assessment.service import AssessmentService
    return AssessmentService(db)


async def get_adaptation_service(db: DbSession):
    """Get adaptation service instance with injected database session."""
    from src.modules.adaptation.service import AdaptationService
    return AdaptationService(db)


async def get_agent_orchestrator():
    """Get agent orchestrator instance."""
    from src.modules.agents.orchestrator import AgentOrchestrator
    return AgentOrchestrator()


# ===================
# Authentication Dependencies
# ===================

async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> User:
    """Validate JWT token and return current user.

    Args:
        credentials: HTTP Bearer credentials

    Returns:
        Authenticated User object

    Raises:
        HTTPException: If token is invalid or expired
    """
    from src.modules.auth.service import AuthService

    auth_service = AuthService()
    token = credentials.credentials
    user = await auth_service.validate_access_token(token)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_user_id(
    user: Annotated[User, Depends(get_current_user)],
) -> UUID:
    """Get current user's ID.

    Args:
        user: Current authenticated user

    Returns:
        User's UUID
    """
    return user.id


# ===================
# Type Aliases for Dependencies
# ===================

CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentUserId = Annotated[UUID, Depends(get_current_user_id)]

# Service type aliases with proper dependency injection
from src.modules.auth.service import AuthService
from src.modules.user.service import UserService

AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]

# Dynamic service types - these use the db session
SessionServiceDep = Annotated["SessionService", Depends(get_session_service)]
ContentServiceDep = Annotated["ContentService", Depends(get_content_service)]
AssessmentServiceDep = Annotated["AssessmentService", Depends(get_assessment_service)]
AdaptationServiceDep = Annotated["AdaptationService", Depends(get_adaptation_service)]
AgentOrchestratorDep = Annotated["AgentOrchestrator", Depends(get_agent_orchestrator)]
