"""Auth module - JWT-based authentication."""

from src.modules.auth.interface import AuthResult, IAuthService, TokenPair, User
from src.modules.auth.models import (
    PasswordResetTokenModel,
    RefreshTokenModel,
    UserModel,
)
from src.modules.auth.schemas import (
    AuthErrorResponse,
    AuthSuccessResponse,
    ChangePasswordRequest,
    ChangePasswordResponse,
    LoginRequest,
    LogoutRequest,
    PasswordResetRequestResponse,
    RefreshTokenRequest,
    RegisterRequest,
    RequestPasswordResetRequest,
    ResetPasswordRequest,
    TokenPairSchema,
    UserSchema,
)
from src.modules.auth.service import AuthService, get_auth_service

__all__ = [
    # Interface
    "IAuthService",
    "AuthResult",
    "TokenPair",
    "User",
    # Service
    "AuthService",
    "get_auth_service",
    # Models
    "UserModel",
    "RefreshTokenModel",
    "PasswordResetTokenModel",
    # Schemas
    "RegisterRequest",
    "LoginRequest",
    "RefreshTokenRequest",
    "LogoutRequest",
    "ChangePasswordRequest",
    "RequestPasswordResetRequest",
    "ResetPasswordRequest",
    "TokenPairSchema",
    "UserSchema",
    "AuthSuccessResponse",
    "AuthErrorResponse",
    "PasswordResetRequestResponse",
    "ChangePasswordResponse",
]
