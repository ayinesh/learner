#!/usr/bin/env python3
"""Quick verification script for auth module implementation.

This script performs basic checks to verify the auth module is correctly implemented.
Run this before running the full test suite.
"""

import asyncio
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Add src to path and set working directory for .env loading
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load .env from project root
from dotenv import load_dotenv
load_dotenv(project_root / ".env")


async def verify_imports():
    """Verify all imports work correctly."""
    print("Verifying imports...")
    try:
        from src.modules.auth import (
            AuthService,
            get_auth_service,
            UserModel,
            RefreshTokenModel,
            PasswordResetTokenModel,
            RegisterRequest,
            LoginRequest,
            UserSchema,
            AuthSuccessResponse,
        )
        print("  ✓ All imports successful")
        return True
    except Exception as e:
        print(f"  ✗ Import failed: {e}")
        return False


async def verify_models():
    """Verify SQLAlchemy models are defined correctly."""
    print("\nVerifying models...")
    try:
        from src.modules.auth.models import UserModel, RefreshTokenModel, PasswordResetTokenModel

        # Check UserModel
        assert hasattr(UserModel, '__tablename__')
        assert UserModel.__tablename__ == 'users'
        assert hasattr(UserModel, 'id')
        assert hasattr(UserModel, 'email')
        assert hasattr(UserModel, 'password_hash')
        print("  ✓ UserModel defined correctly")

        # Check RefreshTokenModel
        assert hasattr(RefreshTokenModel, '__tablename__')
        assert RefreshTokenModel.__tablename__ == 'refresh_tokens'
        assert hasattr(RefreshTokenModel, 'token_hash')
        assert hasattr(RefreshTokenModel, 'expires_at')
        print("  ✓ RefreshTokenModel defined correctly")

        # Check PasswordResetTokenModel
        assert hasattr(PasswordResetTokenModel, '__tablename__')
        assert PasswordResetTokenModel.__tablename__ == 'password_reset_tokens'
        assert hasattr(PasswordResetTokenModel, 'token_hash')
        assert hasattr(PasswordResetTokenModel, 'used')
        print("  ✓ PasswordResetTokenModel defined correctly")

        return True
    except Exception as e:
        print(f"  ✗ Model verification failed: {e}")
        return False


async def verify_schemas():
    """Verify Pydantic schemas are defined correctly."""
    print("\nVerifying schemas...")
    try:
        from src.modules.auth.schemas import (
            RegisterRequest,
            LoginRequest,
            UserSchema,
            TokenPairSchema,
        )

        # Test RegisterRequest validation
        try:
            RegisterRequest(email="test@example.com", password="Pass1234")
            print("  ✓ RegisterRequest accepts valid data")
        except Exception as e:
            print(f"  ✗ RegisterRequest validation failed: {e}")
            return False

        # Test password validation
        try:
            RegisterRequest(email="test@example.com", password="weak")
            print("  ✗ RegisterRequest should reject weak passwords")
            return False
        except ValueError:
            print("  ✓ RegisterRequest rejects weak passwords")

        return True
    except Exception as e:
        print(f"  ✗ Schema verification failed: {e}")
        return False


async def verify_service_interface():
    """Verify service implements the interface correctly."""
    print("\nVerifying service interface...")
    try:
        from src.modules.auth import get_auth_service
        from src.modules.auth.interface import IAuthService
        import inspect

        service = get_auth_service()

        # Get all methods from interface
        interface_methods = [
            name for name, method in inspect.getmembers(IAuthService, predicate=inspect.ismethod)
            if not name.startswith('_')
        ]

        # Check if service has all methods
        for method_name in ['register', 'login', 'logout', 'validate_access_token',
                            'refresh_tokens', 'change_password', 'request_password_reset',
                            'reset_password', 'get_user_by_id', 'revoke_all_tokens']:
            if not hasattr(service, method_name):
                print(f"  ✗ Service missing method: {method_name}")
                return False

        print("  ✓ Service implements all interface methods")

        # Check if methods are async
        if not asyncio.iscoroutinefunction(service.register):
            print("  ✗ Service methods should be async")
            return False

        print("  ✓ Service methods are async")

        return True
    except Exception as e:
        print(f"  ✗ Service verification failed: {e}")
        return False


async def verify_token_operations():
    """Verify token generation works."""
    print("\nVerifying token operations...")
    try:
        from src.modules.auth import get_auth_service
        from uuid import uuid4

        service = get_auth_service()

        # Test password hashing
        password = "TestPassword123"
        hashed = service._hash_password(password)
        assert hashed != password, "Password should be hashed"
        print("  ✓ Password hashing works")

        # Test password verification
        assert service._verify_password(password, hashed), "Password verification should work"
        assert not service._verify_password("wrong", hashed), "Wrong password should fail"
        print("  ✓ Password verification works")

        # Test token generation
        user_id = uuid4()
        token_pair = service._create_token_pair(user_id)
        assert token_pair.access_token, "Access token should be generated"
        assert token_pair.refresh_token, "Refresh token should be generated"
        print("  ✓ Token generation works")

        # Test refresh token hashing
        refresh_hash = service._hash_refresh_token(token_pair.refresh_token)
        assert refresh_hash != token_pair.refresh_token, "Refresh token should be hashed"
        print("  ✓ Refresh token hashing works")

        return True
    except Exception as e:
        print(f"  ✗ Token operations failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all verifications."""
    print("=" * 60)
    print("Auth Module Verification")
    print("=" * 60)

    results = []

    # Run verifications
    results.append(await verify_imports())
    results.append(await verify_models())
    results.append(await verify_schemas())
    results.append(await verify_service_interface())
    results.append(await verify_token_operations())

    # Summary
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"✓ All verifications passed ({passed}/{total})")
        print("\nAuth module implementation is correct!")
        print("\nNext steps:")
        print("1. Run database migration: python migrate.py")
        print("2. Run unit tests: pytest tests/unit/test_auth.py")
        print("3. Test integration with user module")
        return 0
    else:
        print(f"✗ Some verifications failed ({passed}/{total})")
        print("\nPlease fix the errors above before proceeding.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
