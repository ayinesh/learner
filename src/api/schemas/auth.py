"""Authentication API schemas."""

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


# Security constants
COMMON_PASSWORDS = {
    "password", "12345678", "qwertyui", "letmein1", "welcome1",
    "password1", "admin123", "changeme", "testtest", "trustno1",
}


def validate_password_security(password: str) -> str:
    """Validate password meets security requirements.

    Requirements:
    - At least 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    - Not in common passwords list
    """
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if not any(c.isupper() for c in password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not any(c.islower() for c in password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not any(c.isdigit() for c in password):
        raise ValueError("Password must contain at least one digit")
    if not re.search(r'[!@#$%^&*(),.?":{}|<>\-_=+\[\]\\;\'`~]', password):
        raise ValueError("Password must contain at least one special character (!@#$%^&*(),.?\":{}|<>-_=+[]\\;'`~)")
    if password.lower() in COMMON_PASSWORDS:
        raise ValueError("Password is too common. Please choose a stronger password.")
    return password


class RegisterRequest(BaseModel):
    """User registration request."""

    email: EmailStr = Field(
        ...,
        description="User's email address",
        examples=["user@example.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password (min 8 chars, must include uppercase, lowercase, digit, and special char)",
    )

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password meets security requirements."""
        return validate_password_security(v)


class LoginRequest(BaseModel):
    """User login request."""

    email: EmailStr = Field(
        ...,
        description="User's email address",
    )
    password: str = Field(
        ...,
        description="User's password",
    )


class RefreshTokenRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str = Field(
        ...,
        description="Valid refresh token",
    )


class LogoutRequest(BaseModel):
    """Logout request."""

    refresh_token: str = Field(
        ...,
        description="Refresh token to revoke",
    )


class ChangePasswordRequest(BaseModel):
    """Password change request."""

    current_password: str = Field(
        ...,
        description="Current password for verification",
    )
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="New password (must include uppercase, lowercase, digit, and special char)",
    )

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password meets security requirements."""
        return validate_password_security(v)


class RequestPasswordResetRequest(BaseModel):
    """Password reset request."""

    email: EmailStr = Field(
        ...,
        description="User's email address",
    )


class ResetPasswordRequest(BaseModel):
    """Complete password reset."""

    reset_token: str = Field(
        ...,
        description="Password reset token from email",
    )
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="New password (must include uppercase, lowercase, digit, and special char)",
    )

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password meets security requirements."""
        return validate_password_security(v)


class TokenResponse(BaseModel):
    """Token pair response."""

    access_token: str = Field(
        ...,
        description="JWT access token",
    )
    refresh_token: str = Field(
        ...,
        description="Refresh token for obtaining new access tokens",
    )
    token_type: Literal["bearer"] = Field(
        default="bearer",
        description="Token type",
    )
    expires_in: int = Field(
        ...,
        description="Access token expiration time in seconds",
        examples=[86400],
    )


class UserResponse(BaseModel):
    """User information response."""

    id: UUID = Field(
        ...,
        description="User's unique identifier",
    )
    email: str = Field(
        ...,
        description="User's email address",
    )
    is_active: bool = Field(
        default=True,
        description="Whether the account is active",
    )
    is_verified: bool = Field(
        default=False,
        description="Whether the email is verified",
    )
    created_at: datetime = Field(
        ...,
        description="Account creation timestamp",
    )
    last_login: datetime | None = Field(
        default=None,
        description="Last login timestamp",
    )

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    """Successful authentication response."""

    success: bool = True
    user: UserResponse = Field(
        ...,
        description="Authenticated user information",
    )
    tokens: TokenResponse = Field(
        ...,
        description="Access and refresh tokens",
    )


class PasswordResetResponse(BaseModel):
    """Password reset request response."""

    success: bool = True
    message: str = Field(
        default="If an account exists with this email, a password reset link has been sent",
        description="Generic success message (prevents email enumeration)",
    )
