"""Integration tests for authentication flow."""

import pytest
from sqlalchemy import text

from src.modules.auth import get_auth_service
from src.shared.database import get_db_session


@pytest.fixture
async def clean_test_users():
    """Clean up test users before and after tests."""
    async with get_db_session() as session:
        await session.execute(text("DELETE FROM password_reset_tokens"))
        await session.execute(text("DELETE FROM refresh_tokens"))
        await session.execute(text("DELETE FROM users WHERE email LIKE 'integration_test%@example.com'"))
        await session.commit()
    yield
    async with get_db_session() as session:
        await session.execute(text("DELETE FROM password_reset_tokens"))
        await session.execute(text("DELETE FROM refresh_tokens"))
        await session.execute(text("DELETE FROM users WHERE email LIKE 'integration_test%@example.com'"))
        await session.commit()


class TestAuthenticationFlow:
    """Test complete authentication flow."""

    @pytest.mark.asyncio
    async def test_complete_auth_flow(self, clean_test_users):
        """Test registration -> login -> token refresh -> logout flow."""
        auth_service = get_auth_service()
        test_email = "integration_test_auth@example.com"
        test_password = "SecureTestPassword123!"

        # Step 1: Register a new user
        register_result = await auth_service.register(test_email, test_password)

        assert register_result.success is True
        assert register_result.user_id is not None
        assert register_result.tokens is not None
        assert register_result.tokens.access_token
        assert register_result.tokens.refresh_token

        user_id = register_result.user_id
        first_access_token = register_result.tokens.access_token
        first_refresh_token = register_result.tokens.refresh_token

        # Step 2: Validate the access token
        user = await auth_service.validate_access_token(first_access_token)

        assert user is not None
        assert user.id == user_id
        assert user.email == test_email
        assert user.is_active is True

        # Step 3: Login with credentials
        login_result = await auth_service.login(test_email, test_password)

        assert login_result.success is True
        assert login_result.user_id == user_id
        assert login_result.tokens is not None

        second_refresh_token = login_result.tokens.refresh_token

        # Step 4: Refresh tokens
        import asyncio
        await asyncio.sleep(1)  # Ensure different timestamp

        refresh_result = await auth_service.refresh_tokens(second_refresh_token)

        assert refresh_result.success is True
        assert refresh_result.tokens is not None
        assert refresh_result.tokens.access_token != login_result.tokens.access_token

        third_refresh_token = refresh_result.tokens.refresh_token

        # Step 5: Logout (revoke refresh token)
        logout_success = await auth_service.logout(third_refresh_token)

        assert logout_success is True

        # Step 6: Verify revoked token cannot be used
        revoked_refresh_result = await auth_service.refresh_tokens(third_refresh_token)

        assert revoked_refresh_result.success is False
        assert revoked_refresh_result.error == "Token has been revoked"

    @pytest.mark.asyncio
    async def test_password_change_flow(self, clean_test_users):
        """Test password change flow."""
        auth_service = get_auth_service()
        test_email = "integration_test_pwd_change@example.com"
        old_password = "OldPassword123!"
        new_password = "NewPassword456!"

        # Step 1: Register user
        register_result = await auth_service.register(test_email, old_password)
        user_id = register_result.user_id

        # Step 2: Change password
        change_result = await auth_service.change_password(
            user_id=user_id,
            current_password=old_password,
            new_password=new_password
        )

        assert change_result.success is True

        # Step 3: Verify old password no longer works
        old_login = await auth_service.login(test_email, old_password)

        assert old_login.success is False
        assert old_login.error == "Invalid credentials"

        # Step 4: Verify new password works
        new_login = await auth_service.login(test_email, new_password)

        assert new_login.success is True
        assert new_login.user_id == user_id

    @pytest.mark.asyncio
    async def test_password_reset_flow(self, clean_test_users):
        """Test password reset request flow."""
        auth_service = get_auth_service()
        test_email = "integration_test_pwd_reset@example.com"
        test_password = "TestPassword123!"

        # Step 1: Register user
        await auth_service.register(test_email, test_password)

        # Step 2: Request password reset
        reset_result = await auth_service.request_password_reset(test_email)

        assert reset_result is True

        # Step 3: Request reset for non-existent email (should still return True for security)
        fake_reset = await auth_service.request_password_reset("nonexistent@example.com")

        assert fake_reset is True

    @pytest.mark.asyncio
    async def test_revoke_all_tokens_flow(self, clean_test_users):
        """Test revoking all user tokens."""
        auth_service = get_auth_service()
        test_email = "integration_test_revoke_all@example.com"
        test_password = "TestPassword123!"

        # Step 1: Register user
        register_result = await auth_service.register(test_email, test_password)
        user_id = register_result.user_id
        token1 = register_result.tokens.refresh_token

        # Step 2: Login again to create another token
        login_result = await auth_service.login(test_email, test_password)
        token2 = login_result.tokens.refresh_token

        # Step 3: Verify both tokens work
        refresh1 = await auth_service.refresh_tokens(token1)
        assert refresh1.success is True

        refresh2 = await auth_service.refresh_tokens(token2)
        assert refresh2.success is True

        # Step 4: Revoke all tokens
        revoke_success = await auth_service.revoke_all_tokens(user_id)
        assert revoke_success is True

        # Step 5: Verify both tokens are now revoked
        revoked1 = await auth_service.refresh_tokens(token1)
        assert revoked1.success is False

        revoked2 = await auth_service.refresh_tokens(token2)
        assert revoked2.success is False

    @pytest.mark.asyncio
    async def test_duplicate_registration_prevention(self, clean_test_users):
        """Test that duplicate email registration is prevented."""
        auth_service = get_auth_service()
        test_email = "integration_test_duplicate@example.com"
        test_password = "TestPassword123!"

        # Step 1: First registration
        first_result = await auth_service.register(test_email, test_password)
        assert first_result.success is True

        # Step 2: Attempt duplicate registration
        second_result = await auth_service.register(test_email, "DifferentPassword456!")

        assert second_result.success is False
        assert second_result.error == "Email already registered"

    @pytest.mark.asyncio
    async def test_invalid_credentials_handling(self, clean_test_users):
        """Test handling of invalid credentials."""
        auth_service = get_auth_service()
        test_email = "integration_test_invalid@example.com"
        test_password = "CorrectPassword123!"

        # Step 1: Register user
        await auth_service.register(test_email, test_password)

        # Step 2: Try login with wrong password
        wrong_password = await auth_service.login(test_email, "WrongPassword456!")

        assert wrong_password.success is False
        assert wrong_password.error == "Invalid credentials"

        # Step 3: Try login with non-existent email
        wrong_email = await auth_service.login("nonexistent@example.com", test_password)

        assert wrong_email.success is False
        assert wrong_email.error == "Invalid credentials"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
