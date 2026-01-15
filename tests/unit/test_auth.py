"""Unit tests for auth module."""

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import text

from src.modules.auth import get_auth_service
from src.modules.auth.models import UserModel, RefreshTokenModel, PasswordResetTokenModel
from src.shared.database import get_db_session


@pytest.fixture
async def auth_service():
    """Get auth service instance."""
    return get_auth_service()


@pytest.fixture
async def clean_db():
    """Clean database before each test."""
    async with get_db_session() as session:
        # Clean up test data
        await session.execute(text("DELETE FROM password_reset_tokens"))
        await session.execute(text("DELETE FROM refresh_tokens"))
        await session.execute(text("DELETE FROM users WHERE email LIKE 'test%@example.com'"))
        await session.commit()
    yield
    # Cleanup after test
    async with get_db_session() as session:
        await session.execute(text("DELETE FROM password_reset_tokens"))
        await session.execute(text("DELETE FROM refresh_tokens"))
        await session.execute(text("DELETE FROM users WHERE email LIKE 'test%@example.com'"))
        await session.commit()


class TestRegistration:
    """Test user registration."""

    @pytest.mark.asyncio
    async def test_register_success(self, auth_service, clean_db):
        """Test successful user registration."""
        result = await auth_service.register(
            email="test1@example.com",
            password="SecurePass123"
        )

        assert result.success is True
        assert result.user_id is not None
        assert result.tokens is not None
        assert result.tokens.access_token
        assert result.tokens.refresh_token
        assert result.error is None

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, auth_service, clean_db):
        """Test registration with duplicate email."""
        # First registration
        await auth_service.register("test2@example.com", "Pass123")

        # Second registration with same email
        result = await auth_service.register("test2@example.com", "Pass456")

        assert result.success is False
        assert result.error == "Email already registered"
        assert result.tokens is None


class TestLogin:
    """Test user login."""

    @pytest.mark.asyncio
    async def test_login_success(self, auth_service, clean_db):
        """Test successful login."""
        # Register user
        await auth_service.register("test3@example.com", "SecurePass123")

        # Login
        result = await auth_service.login("test3@example.com", "SecurePass123")

        assert result.success is True
        assert result.user_id is not None
        assert result.tokens is not None

    @pytest.mark.asyncio
    async def test_login_invalid_email(self, auth_service, clean_db):
        """Test login with non-existent email."""
        result = await auth_service.login("nonexistent@example.com", "Password123")

        assert result.success is False
        assert result.error == "Invalid credentials"

    @pytest.mark.asyncio
    async def test_login_invalid_password(self, auth_service, clean_db):
        """Test login with wrong password."""
        # Register user
        await auth_service.register("test4@example.com", "SecurePass123")

        # Login with wrong password
        result = await auth_service.login("test4@example.com", "WrongPassword")

        assert result.success is False
        assert result.error == "Invalid credentials"


class TestTokenValidation:
    """Test token validation."""

    @pytest.mark.asyncio
    async def test_validate_access_token_success(self, auth_service, clean_db):
        """Test validating a valid access token."""
        # Register and get tokens
        result = await auth_service.register("test5@example.com", "SecurePass123")
        access_token = result.tokens.access_token

        # Validate token
        user = await auth_service.validate_access_token(access_token)

        assert user is not None
        assert user.email == "test5@example.com"
        assert user.is_active is True

    @pytest.mark.asyncio
    async def test_validate_invalid_token(self, auth_service, clean_db):
        """Test validating an invalid token."""
        user = await auth_service.validate_access_token("invalid.token.here")

        assert user is None


class TestTokenRefresh:
    """Test token refresh."""

    @pytest.mark.asyncio
    async def test_refresh_tokens_success(self, auth_service, clean_db):
        """Test refreshing tokens with valid refresh token."""
        import asyncio

        # Register and get tokens
        result = await auth_service.register("test6@example.com", "SecurePass123")
        refresh_token = result.tokens.refresh_token

        # Wait 1 second to ensure different timestamps
        await asyncio.sleep(1)

        # Refresh tokens
        refresh_result = await auth_service.refresh_tokens(refresh_token)

        assert refresh_result.success is True
        assert refresh_result.tokens is not None
        assert refresh_result.tokens.access_token != result.tokens.access_token
        assert refresh_result.tokens.refresh_token != refresh_token

    @pytest.mark.asyncio
    async def test_refresh_with_invalid_token(self, auth_service, clean_db):
        """Test refresh with invalid token."""
        result = await auth_service.refresh_tokens("invalid_token")

        assert result.success is False
        assert result.error == "Invalid refresh token"

    @pytest.mark.asyncio
    async def test_refresh_with_revoked_token(self, auth_service, clean_db):
        """Test refresh with revoked token."""
        # Register and get tokens
        result = await auth_service.register("test7@example.com", "SecurePass123")
        refresh_token = result.tokens.refresh_token

        # Logout (revokes token)
        await auth_service.logout(refresh_token)

        # Try to refresh with revoked token
        refresh_result = await auth_service.refresh_tokens(refresh_token)

        assert refresh_result.success is False
        assert refresh_result.error == "Token has been revoked"


class TestLogout:
    """Test logout."""

    @pytest.mark.asyncio
    async def test_logout_success(self, auth_service, clean_db):
        """Test successful logout."""
        # Register and get tokens
        result = await auth_service.register("test8@example.com", "SecurePass123")
        refresh_token = result.tokens.refresh_token

        # Logout
        success = await auth_service.logout(refresh_token)

        assert success is True

        # Try to use the revoked token
        refresh_result = await auth_service.refresh_tokens(refresh_token)
        assert refresh_result.success is False


class TestPasswordChange:
    """Test password change."""

    @pytest.mark.asyncio
    async def test_change_password_success(self, auth_service, clean_db):
        """Test successful password change."""
        # Register user
        result = await auth_service.register("test9@example.com", "OldPass123")
        user_id = result.user_id

        # Change password
        change_result = await auth_service.change_password(
            user_id=user_id,
            current_password="OldPass123",
            new_password="NewPass456"
        )

        assert change_result.success is True

        # Verify can login with new password
        login_result = await auth_service.login("test9@example.com", "NewPass456")
        assert login_result.success is True

        # Verify cannot login with old password
        old_login = await auth_service.login("test9@example.com", "OldPass123")
        assert old_login.success is False

    @pytest.mark.asyncio
    async def test_change_password_wrong_current(self, auth_service, clean_db):
        """Test password change with wrong current password."""
        # Register user
        result = await auth_service.register("test10@example.com", "OldPass123")
        user_id = result.user_id

        # Try to change with wrong current password
        change_result = await auth_service.change_password(
            user_id=user_id,
            current_password="WrongPass",
            new_password="NewPass456"
        )

        assert change_result.success is False
        assert change_result.error == "Invalid current password"


class TestPasswordReset:
    """Test password reset."""

    @pytest.mark.asyncio
    async def test_request_password_reset(self, auth_service, clean_db):
        """Test requesting password reset."""
        # Register user
        await auth_service.register("test11@example.com", "OldPass123")

        # Request reset
        result = await auth_service.request_password_reset("test11@example.com")

        assert result is True

    @pytest.mark.asyncio
    async def test_request_reset_nonexistent_email(self, auth_service, clean_db):
        """Test reset request with non-existent email (should still return True)."""
        result = await auth_service.request_password_reset("nonexistent@example.com")

        # Always returns True to prevent email enumeration
        assert result is True


class TestGetUser:
    """Test getting user by ID."""

    @pytest.mark.asyncio
    async def test_get_user_by_id_success(self, auth_service, clean_db):
        """Test getting user by valid ID."""
        # Register user
        result = await auth_service.register("test12@example.com", "Pass123")
        user_id = result.user_id

        # Get user
        user = await auth_service.get_user_by_id(user_id)

        assert user is not None
        assert user.email == "test12@example.com"
        assert user.id == user_id

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, auth_service, clean_db):
        """Test getting user with non-existent ID."""
        user = await auth_service.get_user_by_id(uuid4())

        assert user is None


class TestRevokeAllTokens:
    """Test revoking all user tokens."""

    @pytest.mark.asyncio
    async def test_revoke_all_tokens(self, auth_service, clean_db):
        """Test revoking all tokens for a user."""
        # Register and login multiple times to create multiple tokens
        result = await auth_service.register("test13@example.com", "Pass123")
        user_id = result.user_id
        token1 = result.tokens.refresh_token

        result2 = await auth_service.login("test13@example.com", "Pass123")
        token2 = result2.tokens.refresh_token

        # Revoke all tokens
        success = await auth_service.revoke_all_tokens(user_id)
        assert success is True

        # Verify both tokens are revoked
        refresh1 = await auth_service.refresh_tokens(token1)
        refresh2 = await auth_service.refresh_tokens(token2)

        assert refresh1.success is False
        assert refresh2.success is False
