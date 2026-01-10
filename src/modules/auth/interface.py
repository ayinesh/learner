"""Auth Module - JWT-based authentication."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass
class TokenPair:
    """Access and refresh token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 86400  # seconds


@dataclass
class AuthResult:
    """Result of authentication operation."""

    success: bool
    user_id: UUID | None = None
    tokens: TokenPair | None = None
    error: str | None = None


@dataclass
class User:
    """Authenticated user."""

    id: UUID
    email: str
    is_active: bool = True
    is_verified: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_login: datetime | None = None


class IAuthService(Protocol):
    """Interface for JWT-based authentication service.

    This interface defines the contract that the auth module must implement.
    Uses bcrypt for password hashing and JWT for token-based auth.
    """

    async def register(self, email: str, password: str) -> AuthResult:
        """Register a new user.

        Args:
            email: User's email address
            password: User's password (will be hashed with bcrypt)

        Returns:
            AuthResult with user_id and tokens on success, error on failure
        """
        ...

    async def login(self, email: str, password: str) -> AuthResult:
        """Authenticate a user with email and password.

        Args:
            email: User's email address
            password: User's password

        Returns:
            AuthResult with tokens on success, error on failure
        """
        ...

    async def logout(self, refresh_token: str) -> bool:
        """Log out a user by revoking their refresh token.

        Args:
            refresh_token: The user's refresh token to revoke

        Returns:
            True if logout successful
        """
        ...

    async def validate_access_token(self, access_token: str) -> User | None:
        """Validate an access token and return the user.

        Args:
            access_token: The JWT access token to validate

        Returns:
            User if token is valid and not expired, None otherwise
        """
        ...

    async def refresh_tokens(self, refresh_token: str) -> AuthResult:
        """Refresh access and refresh tokens.

        Args:
            refresh_token: The refresh token

        Returns:
            AuthResult with new token pair on success, error on failure
        """
        ...

    async def change_password(
        self, user_id: UUID, current_password: str, new_password: str
    ) -> AuthResult:
        """Change user's password.

        Args:
            user_id: User's UUID
            current_password: Current password for verification
            new_password: New password

        Returns:
            AuthResult indicating success or failure
        """
        ...

    async def request_password_reset(self, email: str) -> bool:
        """Request a password reset email.

        Args:
            email: User's email address

        Returns:
            True always (to prevent email enumeration)
        """
        ...

    async def reset_password(self, reset_token: str, new_password: str) -> AuthResult:
        """Reset password using reset token.

        Args:
            reset_token: Password reset token from email
            new_password: New password

        Returns:
            AuthResult indicating success or failure
        """
        ...

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        """Get user by ID.

        Args:
            user_id: User's UUID

        Returns:
            User if found, None otherwise
        """
        ...

    async def revoke_all_tokens(self, user_id: UUID) -> bool:
        """Revoke all refresh tokens for a user.

        Useful for security events (password change, suspicious activity).

        Args:
            user_id: User's UUID

        Returns:
            True if successful
        """
        ...
