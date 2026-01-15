"""Authentication API routes."""

from fastapi import APIRouter, HTTPException, status

from src.api.dependencies import AuthServiceDep, CurrentUser
from src.api.schemas.auth import (
    AuthResponse,
    ChangePasswordRequest,
    LoginRequest,
    LogoutRequest,
    PasswordResetResponse,
    RefreshTokenRequest,
    RegisterRequest,
    RequestPasswordResetRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
)
from src.api.schemas.common import SuccessResponse

router = APIRouter()


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Create a new user account with email and password.",
)
async def register(
    request: RegisterRequest,
    auth_service: AuthServiceDep,
) -> AuthResponse:
    """Register a new user account.

    Args:
        request: Registration data with email and password
        auth_service: Auth service instance

    Returns:
        AuthResponse with user info and tokens

    Raises:
        HTTPException: If email is already registered
    """
    result = await auth_service.register(
        email=request.email,
        password=request.password,
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=result.error or "Registration failed",
        )

    # Get user details
    user = await auth_service.get_user_by_id(result.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User creation failed",
        )

    return AuthResponse(
        user=UserResponse(
            id=user.id,
            email=user.email,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at,
            last_login=user.last_login,
        ),
        tokens=TokenResponse(
            access_token=result.tokens.access_token,
            refresh_token=result.tokens.refresh_token,
            token_type="bearer",
            expires_in=result.tokens.expires_in,
        ),
    )


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Login user",
    description="Authenticate user with email and password.",
)
async def login(
    request: LoginRequest,
    auth_service: AuthServiceDep,
) -> AuthResponse:
    """Authenticate user and return tokens.

    Args:
        request: Login credentials
        auth_service: Auth service instance

    Returns:
        AuthResponse with user info and tokens

    Raises:
        HTTPException: If credentials are invalid
    """
    result = await auth_service.login(
        email=request.email,
        password=request.password,
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result.error or "Invalid credentials",
        )

    # Get user details
    user = await auth_service.get_user_by_id(result.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user",
        )

    return AuthResponse(
        user=UserResponse(
            id=user.id,
            email=user.email,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at,
            last_login=user.last_login,
        ),
        tokens=TokenResponse(
            access_token=result.tokens.access_token,
            refresh_token=result.tokens.refresh_token,
            token_type="bearer",
            expires_in=result.tokens.expires_in,
        ),
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Get new access token using refresh token.",
)
async def refresh_token(
    request: RefreshTokenRequest,
    auth_service: AuthServiceDep,
) -> TokenResponse:
    """Refresh access token using refresh token.

    Args:
        request: Refresh token
        auth_service: Auth service instance

    Returns:
        New token pair

    Raises:
        HTTPException: If refresh token is invalid
    """
    result = await auth_service.refresh_tokens(request.refresh_token)

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result.error or "Invalid refresh token",
        )

    return TokenResponse(
        access_token=result.tokens.access_token,
        refresh_token=result.tokens.refresh_token,
        token_type="bearer",
        expires_in=result.tokens.expires_in,
    )


@router.post(
    "/logout",
    response_model=SuccessResponse,
    summary="Logout user",
    description="Revoke refresh token to logout.",
)
async def logout(
    request: LogoutRequest,
    auth_service: AuthServiceDep,
    current_user: CurrentUser,
) -> SuccessResponse:
    """Logout user by revoking refresh token.

    Args:
        request: Refresh token to revoke
        auth_service: Auth service instance
        current_user: Currently authenticated user

    Returns:
        Success response
    """
    await auth_service.logout(request.refresh_token)
    return SuccessResponse(message="Logged out successfully")


@router.post(
    "/password/change",
    response_model=SuccessResponse,
    summary="Change password",
    description="Change password for authenticated user.",
)
async def change_password(
    request: ChangePasswordRequest,
    auth_service: AuthServiceDep,
    current_user: CurrentUser,
) -> SuccessResponse:
    """Change password for current user.

    Args:
        request: Current and new password
        auth_service: Auth service instance
        current_user: Currently authenticated user

    Returns:
        Success response

    Raises:
        HTTPException: If current password is wrong
    """
    result = await auth_service.change_password(
        user_id=current_user.id,
        current_password=request.current_password,
        new_password=request.new_password,
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error or "Password change failed",
        )

    return SuccessResponse(message="Password changed successfully")


@router.post(
    "/password/reset-request",
    response_model=PasswordResetResponse,
    summary="Request password reset",
    description="Request password reset email. Always returns success to prevent email enumeration.",
)
async def request_password_reset(
    request: RequestPasswordResetRequest,
    auth_service: AuthServiceDep,
) -> PasswordResetResponse:
    """Request password reset email.

    Always returns success to prevent email enumeration.

    Args:
        request: Email address
        auth_service: Auth service instance

    Returns:
        Generic success response
    """
    await auth_service.request_password_reset(request.email)
    return PasswordResetResponse()


@router.post(
    "/password/reset",
    response_model=SuccessResponse,
    summary="Reset password",
    description="Complete password reset with token from email.",
)
async def reset_password(
    request: ResetPasswordRequest,
    auth_service: AuthServiceDep,
) -> SuccessResponse:
    """Complete password reset.

    Args:
        request: Reset token and new password
        auth_service: Auth service instance

    Returns:
        Success response

    Raises:
        HTTPException: If reset token is invalid
    """
    result = await auth_service.reset_password(
        reset_token=request.reset_token,
        new_password=request.new_password,
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error or "Password reset failed",
        )

    return SuccessResponse(message="Password reset successfully")


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Get information about the currently authenticated user.",
)
async def get_current_user_info(
    current_user: CurrentUser,
) -> UserResponse:
    """Get current user information.

    Args:
        current_user: Currently authenticated user

    Returns:
        User information
    """
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at,
        last_login=current_user.last_login,
    )
