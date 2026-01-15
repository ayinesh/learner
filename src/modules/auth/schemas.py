"""Pydantic schemas for authentication requests and responses."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


# ==================
# Request Schemas
# ==================


class RegisterRequest(BaseModel):
    """Request schema for user registration."""

    email: EmailStr = Field(
        ...,
        description="User's email address",
        examples=["user@example.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="User's password (min 8 characters)",
    )

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password meets security requirements."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class LoginRequest(BaseModel):
    """Request schema for user login."""

    email: EmailStr = Field(
        ...,
        description="User's email address",
    )
    password: str = Field(
        ...,
        description="User's password",
    )


class RefreshTokenRequest(BaseModel):
    """Request schema for refreshing tokens."""

    refresh_token: str = Field(
        ...,
        description="Valid refresh token",
    )


class LogoutRequest(BaseModel):
    """Request schema for user logout."""

    refresh_token: str = Field(
        ...,
        description="Refresh token to revoke",
    )


class ChangePasswordRequest(BaseModel):
    """Request schema for changing password."""

    current_password: str = Field(
        ...,
        description="Current password for verification",
    )
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="New password (min 8 characters)",
    )

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password meets security requirements."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class RequestPasswordResetRequest(BaseModel):
    """Request schema for requesting password reset."""

    email: EmailStr = Field(
        ...,
        description="User's email address",
    )


class ResetPasswordRequest(BaseModel):
    """Request schema for resetting password."""

    reset_token: str = Field(
        ...,
        description="Password reset token from email",
    )
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="New password (min 8 characters)",
    )

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password meets security requirements."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


# ==================
# Response Schemas
# ==================


class TokenPairSchema(BaseModel):
    """Schema for access and refresh token pair."""

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
        description="Token type (always 'bearer')",
    )
    expires_in: int = Field(
        ...,
        description="Access token expiration time in seconds",
        examples=[86400],
    )


class UserSchema(BaseModel):
    """Schema for authenticated user information."""

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
        description="Whether the user account is active",
    )
    is_verified: bool = Field(
        default=False,
        description="Whether the user's email is verified",
    )
    created_at: datetime = Field(
        ...,
        description="Account creation timestamp",
    )
    last_login: datetime | None = Field(
        default=None,
        description="Last login timestamp",
    )

    model_config = {
        "from_attributes": True,  # Allow creating from ORM models
    }


class AuthSuccessResponse(BaseModel):
    """Schema for successful authentication response."""

    success: Literal[True] = True
    user: UserSchema = Field(
        ...,
        description="Authenticated user information",
    )
    tokens: TokenPairSchema = Field(
        ...,
        description="Access and refresh tokens",
    )


class AuthErrorResponse(BaseModel):
    """Schema for authentication error response."""

    success: Literal[False] = False
    error: str = Field(
        ...,
        description="Error message",
        examples=["Invalid credentials", "Email already registered"],
    )


class PasswordResetRequestResponse(BaseModel):
    """Schema for password reset request response."""

    success: bool = Field(
        default=True,
        description="Always true to prevent email enumeration",
    )
    message: str = Field(
        default="If an account exists with this email, a password reset link has been sent",
        description="Generic success message",
    )


class ChangePasswordResponse(BaseModel):
    """Schema for password change response."""

    success: bool = Field(
        ...,
        description="Whether the password change was successful",
    )
    message: str | None = Field(
        default=None,
        description="Success or error message",
    )
