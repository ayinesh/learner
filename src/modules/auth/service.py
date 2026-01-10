"""Auth Service - JWT-based authentication implementation."""

import hashlib
import secrets
from datetime import datetime, timedelta
from uuid import UUID

import bcrypt
import jwt
from sqlalchemy import select, update

from src.modules.auth.interface import AuthResult, TokenPair, User
from src.shared.config import get_settings
from src.shared.database import get_db_session, get_redis

settings = get_settings()


class AuthService:
    """JWT-based authentication service using bcrypt and Redis."""

    def __init__(self) -> None:
        self.secret_key = settings.jwt_secret_key
        self.algorithm = settings.jwt_algorithm
        self.access_token_expire_hours = settings.jwt_expiration_hours
        self.refresh_token_expire_days = settings.jwt_refresh_expiration_days

    # ===================
    # Password Hashing
    # ===================

    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt."""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode(), salt).decode()

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash."""
        return bcrypt.checkpw(password.encode(), password_hash.encode())

    # ===================
    # Token Generation
    # ===================

    def _create_access_token(self, user_id: UUID) -> str:
        """Create JWT access token."""
        expire = datetime.utcnow() + timedelta(hours=self.access_token_expire_hours)
        payload = {
            "sub": str(user_id),
            "exp": expire,
            "type": "access",
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def _create_refresh_token(self) -> str:
        """Create random refresh token."""
        return secrets.token_urlsafe(32)

    def _hash_refresh_token(self, token: str) -> str:
        """Hash refresh token for storage."""
        return hashlib.sha256(token.encode()).hexdigest()

    def _create_token_pair(self, user_id: UUID) -> TokenPair:
        """Create access and refresh token pair."""
        return TokenPair(
            access_token=self._create_access_token(user_id),
            refresh_token=self._create_refresh_token(),
            expires_in=self.access_token_expire_hours * 3600,
        )

    # ===================
    # Public Methods
    # ===================

    async def register(self, email: str, password: str) -> AuthResult:
        """Register a new user."""
        async with get_db_session() as session:
            # Check if email exists
            result = await session.execute(
                select("*").where("email = :email"),  # TODO: Use proper model
                {"email": email},
            )
            if result.first():
                return AuthResult(success=False, error="Email already registered")

            # Create user
            password_hash = self._hash_password(password)
            # TODO: Insert user and get user_id

            # Generate tokens
            # tokens = self._create_token_pair(user_id)

            # TODO: Store refresh token hash

            return AuthResult(
                success=False,
                error="Not implemented - complete this in auth/service.py",
            )

    async def login(self, email: str, password: str) -> AuthResult:
        """Authenticate user and return tokens."""
        # TODO: Implement login logic
        # 1. Find user by email
        # 2. Verify password
        # 3. Generate tokens
        # 4. Store refresh token
        # 5. Update last_login
        return AuthResult(
            success=False,
            error="Not implemented - complete this in auth/service.py",
        )

    async def logout(self, refresh_token: str) -> bool:
        """Revoke refresh token."""
        # TODO: Mark refresh token as revoked
        return False

    async def validate_access_token(self, access_token: str) -> User | None:
        """Validate access token and return user."""
        try:
            payload = jwt.decode(
                access_token, self.secret_key, algorithms=[self.algorithm]
            )
            if payload.get("type") != "access":
                return None

            user_id = UUID(payload["sub"])
            # TODO: Fetch user from database
            return None

        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    async def refresh_tokens(self, refresh_token: str) -> AuthResult:
        """Refresh tokens using refresh token."""
        # TODO: Implement token refresh
        # 1. Validate refresh token exists and not revoked
        # 2. Generate new token pair
        # 3. Revoke old refresh token
        # 4. Store new refresh token
        return AuthResult(
            success=False,
            error="Not implemented - complete this in auth/service.py",
        )

    async def change_password(
        self, user_id: UUID, current_password: str, new_password: str
    ) -> AuthResult:
        """Change user password."""
        # TODO: Implement password change
        return AuthResult(success=False, error="Not implemented")

    async def request_password_reset(self, email: str) -> bool:
        """Request password reset (always returns True)."""
        # TODO: Generate reset token and send email
        return True

    async def reset_password(self, reset_token: str, new_password: str) -> AuthResult:
        """Reset password with token."""
        # TODO: Implement password reset
        return AuthResult(success=False, error="Not implemented")

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        """Get user by ID."""
        # TODO: Fetch from database
        return None

    async def revoke_all_tokens(self, user_id: UUID) -> bool:
        """Revoke all refresh tokens for user."""
        # TODO: Mark all user's refresh tokens as revoked
        return False


# Singleton instance
_auth_service: AuthService | None = None


def get_auth_service() -> AuthService:
    """Get auth service singleton."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service
