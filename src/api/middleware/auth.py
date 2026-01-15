"""JWT authentication middleware for FastAPI."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.modules.auth.interface import User
from src.modules.auth.service import get_auth_service


class JWTBearer(HTTPBearer):
    """Custom JWT Bearer authentication.

    Extends HTTPBearer to provide JWT-specific validation
    and better error messages.
    """

    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)

    async def __call__(self, request: Request) -> HTTPAuthorizationCredentials | None:
        """Validate the Bearer token.

        Args:
            request: FastAPI request

        Returns:
            HTTPAuthorizationCredentials if valid

        Raises:
            HTTPException: If token is missing or invalid
        """
        credentials = await super().__call__(request)

        if credentials is None:
            if self.auto_error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return None

        if credentials.scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication scheme",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return credentials


# Dependency instances
jwt_bearer = JWTBearer()
jwt_bearer_optional = JWTBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(jwt_bearer)],
) -> User:
    """Validate JWT token and return current user.

    Args:
        credentials: HTTP Bearer credentials

    Returns:
        Authenticated User object

    Raises:
        HTTPException: If token is invalid or expired
    """
    auth_service = get_auth_service()
    token = credentials.credentials
    user = await auth_service.validate_access_token(token)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_user_optional(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(jwt_bearer_optional),
    ],
) -> User | None:
    """Optionally validate JWT token.

    Returns user if valid token provided, None otherwise.

    Args:
        credentials: Optional HTTP Bearer credentials

    Returns:
        User if authenticated, None otherwise
    """
    if credentials is None:
        return None

    auth_service = get_auth_service()
    token = credentials.credentials
    return await auth_service.validate_access_token(token)


# Type aliases
CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_current_user_optional)]
