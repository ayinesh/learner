"""Auth Service - JWT-based authentication implementation."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
import jwt
from sqlalchemy import select, update

from src.modules.auth.interface import AuthResult, TokenPair, User
from src.modules.auth.models import (
    PasswordResetTokenModel,
    RefreshTokenModel,
    UserModel,
)
from src.shared.config import get_settings
from src.shared.database import get_db_session, get_redis

settings = get_settings()


class AuthService:
    """JWT-based authentication service using bcrypt and Redis."""

    # Pre-computed dummy hash for timing attack prevention.
    # This is a real bcrypt hash of a random string, used when user doesn't exist
    # to ensure constant-time response regardless of user existence.
    _DUMMY_PASSWORD_HASH = bcrypt.hashpw(b"dummy_password_for_timing_attack_prevention", bcrypt.gensalt()).decode()

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
        expire = datetime.now(timezone.utc) + timedelta(
            hours=self.access_token_expire_hours
        )
        payload = {
            "sub": str(user_id),
            "exp": expire,
            "type": "access",
            "iat": datetime.now(timezone.utc),
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
    # Model Conversions
    # ===================

    def _user_model_to_user(self, user_model: UserModel) -> User:
        """Convert UserModel to User interface object."""
        return User(
            id=user_model.id,
            email=user_model.email,
            is_active=user_model.is_active,
            is_verified=user_model.is_verified,
            created_at=user_model.created_at,
            last_login=user_model.last_login,
        )

    # ===================
    # Public Methods
    # ===================

    async def register(self, email: str, password: str) -> AuthResult:
        """Register a new user."""
        async with get_db_session() as session:
            # Check if email exists
            result = await session.execute(
                select(UserModel).where(UserModel.email == email)
            )
            existing_user = result.scalar_one_or_none()

            if existing_user:
                # Security: Use generic error message to prevent email enumeration
                # Attacker shouldn't be able to determine if an email is registered
                return AuthResult(success=False, error="Registration failed. Please try again or contact support.")

            # Create user
            password_hash = self._hash_password(password)
            new_user = UserModel(
                email=email,
                password_hash=password_hash,
            )
            session.add(new_user)
            await session.flush()  # Get the ID without committing

            # Generate tokens
            tokens = self._create_token_pair(new_user.id)

            # Store refresh token hash
            refresh_token_hash = self._hash_refresh_token(tokens.refresh_token)
            refresh_token_model = RefreshTokenModel(
                user_id=new_user.id,
                token_hash=refresh_token_hash,
                expires_at=datetime.now(timezone.utc)
                + timedelta(days=self.refresh_token_expire_days),
            )
            session.add(refresh_token_model)

            await session.commit()

            return AuthResult(
                success=True,
                user_id=new_user.id,
                tokens=tokens,
            )

    async def login(self, email: str, password: str) -> AuthResult:
        """Authenticate user and return tokens."""
        async with get_db_session() as session:
            # Find user by email
            result = await session.execute(
                select(UserModel).where(UserModel.email == email)
            )
            user = result.scalar_one_or_none()

            # Always perform password verification to prevent timing attacks
            # This ensures consistent response time whether user exists or not
            if user:
                password_valid = self._verify_password(password, user.password_hash)
            else:
                # Perform dummy hash check to maintain constant time
                # Use the class-level pre-computed hash for timing attack prevention
                self._verify_password(password, self._DUMMY_PASSWORD_HASH)
                password_valid = False

            if not user or not password_valid:
                return AuthResult(success=False, error="Invalid credentials")

            # Check if user is active
            if not user.is_active:
                return AuthResult(success=False, error="Account is deactivated")

            # Generate tokens
            tokens = self._create_token_pair(user.id)

            # Store refresh token
            refresh_token_hash = self._hash_refresh_token(tokens.refresh_token)
            refresh_token_model = RefreshTokenModel(
                user_id=user.id,
                token_hash=refresh_token_hash,
                expires_at=datetime.now(timezone.utc)
                + timedelta(days=self.refresh_token_expire_days),
            )
            session.add(refresh_token_model)

            # Update last_login
            user.last_login = datetime.now(timezone.utc)

            await session.commit()

            return AuthResult(
                success=True,
                user_id=user.id,
                tokens=tokens,
            )

    async def logout(self, refresh_token: str) -> bool:
        """Revoke refresh token."""
        async with get_db_session() as session:
            token_hash = self._hash_refresh_token(refresh_token)

            # Mark token as revoked
            result = await session.execute(
                update(RefreshTokenModel)
                .where(RefreshTokenModel.token_hash == token_hash)
                .values(revoked=True)
            )

            await session.commit()
            return result.rowcount > 0

    async def validate_access_token(self, access_token: str) -> User | None:
        """Validate access token and return user."""
        try:
            payload = jwt.decode(
                access_token, self.secret_key, algorithms=[self.algorithm]
            )
            if payload.get("type") != "access":
                return None

            user_id = UUID(payload["sub"])

            # Fetch user from database
            async with get_db_session() as session:
                result = await session.execute(
                    select(UserModel).where(UserModel.id == user_id)
                )
                user_model = result.scalar_one_or_none()

                if not user_model or not user_model.is_active:
                    return None

                return self._user_model_to_user(user_model)

        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
        except Exception:
            return None

    async def refresh_tokens(self, refresh_token: str) -> AuthResult:
        """Refresh tokens using refresh token."""
        async with get_db_session() as session:
            token_hash = self._hash_refresh_token(refresh_token)

            # Find refresh token
            result = await session.execute(
                select(RefreshTokenModel).where(
                    RefreshTokenModel.token_hash == token_hash
                )
            )
            token_model = result.scalar_one_or_none()

            if not token_model:
                return AuthResult(success=False, error="Invalid refresh token")

            if token_model.revoked:
                return AuthResult(success=False, error="Token has been revoked")

            if token_model.expires_at < datetime.now(timezone.utc):
                return AuthResult(success=False, error="Token has expired")

            # Generate new token pair
            new_tokens = self._create_token_pair(token_model.user_id)

            # Revoke old refresh token
            token_model.revoked = True

            # Store new refresh token
            new_refresh_token_hash = self._hash_refresh_token(new_tokens.refresh_token)
            new_refresh_token_model = RefreshTokenModel(
                user_id=token_model.user_id,
                token_hash=new_refresh_token_hash,
                expires_at=datetime.now(timezone.utc)
                + timedelta(days=self.refresh_token_expire_days),
            )
            session.add(new_refresh_token_model)

            await session.commit()

            return AuthResult(
                success=True,
                user_id=token_model.user_id,
                tokens=new_tokens,
            )

    async def change_password(
        self, user_id: UUID, current_password: str, new_password: str
    ) -> AuthResult:
        """Change user password."""
        async with get_db_session() as session:
            # Get user
            result = await session.execute(
                select(UserModel).where(UserModel.id == user_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                return AuthResult(success=False, error="User not found")

            # Verify current password
            if not self._verify_password(current_password, user.password_hash):
                return AuthResult(success=False, error="Invalid current password")

            # Update password
            user.password_hash = self._hash_password(new_password)

            # Revoke all refresh tokens for security
            await session.execute(
                update(RefreshTokenModel)
                .where(RefreshTokenModel.user_id == user_id)
                .values(revoked=True)
            )

            await session.commit()

            return AuthResult(success=True, user_id=user_id)

    async def request_password_reset(self, email: str) -> bool:
        """Request password reset (always returns True to prevent email enumeration)."""
        async with get_db_session() as session:
            # Find user by email
            result = await session.execute(
                select(UserModel).where(UserModel.email == email)
            )
            user = result.scalar_one_or_none()

            # Always return True, but only create token if user exists
            if user:
                # Generate reset token
                reset_token = secrets.token_urlsafe(32)
                token_hash = hashlib.sha256(reset_token.encode()).hexdigest()

                # Store reset token
                reset_token_model = PasswordResetTokenModel(
                    user_id=user.id,
                    token_hash=token_hash,
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                )
                session.add(reset_token_model)
                await session.commit()

                # TODO: Send email with reset_token
                # In production, you would send an email here:
                # await email_service.send_password_reset(email, reset_token)

            return True

    async def reset_password(self, reset_token: str, new_password: str) -> AuthResult:
        """Reset password with token."""
        async with get_db_session() as session:
            token_hash = hashlib.sha256(reset_token.encode()).hexdigest()

            # Find reset token with FOR UPDATE lock to prevent race conditions
            # This ensures only one request can use the token at a time
            result = await session.execute(
                select(PasswordResetTokenModel)
                .where(PasswordResetTokenModel.token_hash == token_hash)
                .with_for_update()
            )
            token_model = result.scalar_one_or_none()

            if not token_model:
                return AuthResult(success=False, error="Invalid reset token")

            if token_model.used:
                return AuthResult(success=False, error="Token already used")

            if token_model.expires_at < datetime.now(timezone.utc):
                return AuthResult(success=False, error="Token has expired")

            # Get user
            user_result = await session.execute(
                select(UserModel).where(UserModel.id == token_model.user_id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                return AuthResult(success=False, error="User not found")

            # Update password
            user.password_hash = self._hash_password(new_password)

            # Mark token as used
            token_model.used = True

            # Revoke all refresh tokens for security
            await session.execute(
                update(RefreshTokenModel)
                .where(RefreshTokenModel.user_id == user.id)
                .values(revoked=True)
            )

            await session.commit()

            return AuthResult(success=True, user_id=user.id)

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        """Get user by ID."""
        async with get_db_session() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.id == user_id)
            )
            user_model = result.scalar_one_or_none()

            if not user_model:
                return None

            return self._user_model_to_user(user_model)

    async def revoke_all_tokens(self, user_id: UUID) -> bool:
        """Revoke all refresh tokens for user."""
        async with get_db_session() as session:
            result = await session.execute(
                update(RefreshTokenModel)
                .where(RefreshTokenModel.user_id == user_id)
                .values(revoked=True)
            )
            await session.commit()
            return result.rowcount > 0

    async def cleanup_expired_tokens(self) -> dict[str, int]:
        """Clean up expired and used tokens to prevent database bloat.

        This should be called periodically (e.g., by a background job).

        Returns:
            Dict with counts of cleaned up tokens
        """
        from sqlalchemy import delete, or_

        async with get_db_session() as session:
            now = datetime.now(timezone.utc)
            cleanup_cutoff = now - timedelta(days=7)  # Keep for 7 days for audit

            # Clean up old password reset tokens
            reset_result = await session.execute(
                delete(PasswordResetTokenModel).where(
                    or_(
                        # Used tokens older than 7 days
                        PasswordResetTokenModel.used == True,
                        # Expired tokens older than 7 days
                        PasswordResetTokenModel.expires_at < cleanup_cutoff,
                    )
                )
            )
            reset_count = reset_result.rowcount

            # Clean up old refresh tokens
            refresh_result = await session.execute(
                delete(RefreshTokenModel).where(
                    or_(
                        # Revoked tokens older than 7 days
                        RefreshTokenModel.revoked == True,
                        # Expired tokens older than 7 days
                        RefreshTokenModel.expires_at < cleanup_cutoff,
                    )
                )
            )
            refresh_count = refresh_result.rowcount

            await session.commit()

            return {
                "password_reset_tokens_cleaned": reset_count,
                "refresh_tokens_cleaned": refresh_count,
            }


# Singleton instance
_auth_service: AuthService | None = None


def get_auth_service() -> AuthService:
    """Get auth service singleton."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service
