"""User profile API routes."""

from fastapi import APIRouter, HTTPException, status

from src.api.dependencies import CurrentUser, CurrentUserId, UserServiceDep
from src.api.schemas.users import (
    LearningPatternResponse,
    OnboardingRequest,
    SourceConfigRequest,
    SourceConfigResponse,
    SourcesListResponse,
    UpdateProfileRequest,
    UpdateTimeBudgetRequest,
    UserProfileResponse,
)
from src.api.schemas.common import SuccessResponse
from src.modules.user.interface import OnboardingData

router = APIRouter()


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get user profile",
    description="Get the current user's profile information.",
)
async def get_profile(
    current_user: CurrentUser,
    user_service: UserServiceDep,
) -> UserProfileResponse:
    """Get current user's profile.

    Args:
        current_user: Currently authenticated user
        user_service: User service instance

    Returns:
        User profile

    Raises:
        HTTPException: If profile not found
    """
    profile = await user_service.get_profile(current_user.id)

    if profile is None:
        # Create profile if doesn't exist
        profile = await user_service.create_profile(current_user.id)

    return UserProfileResponse(
        user_id=profile.user_id,
        background=profile.background,
        goals=profile.goals,
        time_budget_minutes=profile.time_budget_minutes,
        preferred_sources=profile.preferred_sources,
        timezone=profile.timezone,
        onboarding_completed=profile.onboarding_completed,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.put(
    "/me/profile",
    response_model=UserProfileResponse,
    summary="Update user profile",
    description="Update the current user's profile.",
)
async def update_profile(
    request: UpdateProfileRequest,
    current_user: CurrentUser,
    user_service: UserServiceDep,
) -> UserProfileResponse:
    """Update current user's profile.

    Args:
        request: Profile update data
        current_user: Currently authenticated user
        user_service: User service instance

    Returns:
        Updated profile
    """
    # Build update dict from non-None fields
    updates = {}
    if request.background is not None:
        updates["background"] = request.background
    if request.goals is not None:
        updates["goals"] = request.goals
    if request.timezone is not None:
        updates["timezone"] = request.timezone

    if not updates:
        # No updates provided, return current profile
        profile = await user_service.get_profile(current_user.id)
    else:
        profile = await user_service.update_profile(current_user.id, **updates)

    return UserProfileResponse(
        user_id=profile.user_id,
        background=profile.background,
        goals=profile.goals,
        time_budget_minutes=profile.time_budget_minutes,
        preferred_sources=profile.preferred_sources,
        timezone=profile.timezone,
        onboarding_completed=profile.onboarding_completed,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.post(
    "/me/onboarding",
    response_model=UserProfileResponse,
    summary="Complete onboarding",
    description="Complete user onboarding with initial preferences.",
)
async def complete_onboarding(
    request: OnboardingRequest,
    current_user: CurrentUser,
    user_service: UserServiceDep,
) -> UserProfileResponse:
    """Complete user onboarding.

    Args:
        request: Onboarding data
        current_user: Currently authenticated user
        user_service: User service instance

    Returns:
        Updated profile with onboarding complete
    """
    # Ensure profile exists
    profile = await user_service.get_profile(current_user.id)
    if profile is None:
        await user_service.create_profile(current_user.id)

    # Create onboarding data object
    onboarding_data = OnboardingData(
        background=request.background,
        goals=request.goals,
        time_budget_minutes=request.time_budget_minutes,
        timezone=request.timezone,
        preferred_sources=request.preferred_sources,
        initial_topics=request.initial_topics,
    )

    profile = await user_service.complete_onboarding(
        user_id=current_user.id,
        data=onboarding_data,
    )

    return UserProfileResponse(
        user_id=profile.user_id,
        background=profile.background,
        goals=profile.goals,
        time_budget_minutes=profile.time_budget_minutes,
        preferred_sources=profile.preferred_sources,
        timezone=profile.timezone,
        onboarding_completed=profile.onboarding_completed,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.get(
    "/me/learning-pattern",
    response_model=LearningPatternResponse | None,
    summary="Get learning patterns",
    description="Get derived learning patterns for the current user.",
)
async def get_learning_pattern(
    current_user: CurrentUser,
    user_service: UserServiceDep,
) -> LearningPatternResponse | None:
    """Get current user's learning patterns.

    Returns None if user hasn't completed enough sessions.

    Args:
        current_user: Currently authenticated user
        user_service: User service instance

    Returns:
        Learning patterns or None
    """
    pattern = await user_service.get_learning_pattern(current_user.id)

    if pattern is None:
        return None

    return LearningPatternResponse(
        user_id=pattern.user_id,
        avg_session_duration=pattern.avg_session_duration,
        preferred_time_of_day=pattern.preferred_time_of_day,
        completion_rate=pattern.completion_rate,
        quiz_accuracy_trend=pattern.quiz_accuracy_trend,
        feynman_score_trend=pattern.feynman_score_trend,
        days_since_last_session=pattern.days_since_last_session,
        total_sessions=pattern.total_sessions,
        current_streak=pattern.current_streak,
        longest_streak=pattern.longest_streak,
        updated_at=pattern.updated_at,
    )


@router.put(
    "/me/time-budget",
    response_model=UserProfileResponse,
    summary="Update time budget",
    description="Update daily learning time budget.",
)
async def update_time_budget(
    request: UpdateTimeBudgetRequest,
    current_user: CurrentUser,
    user_service: UserServiceDep,
) -> UserProfileResponse:
    """Update user's daily time budget.

    Args:
        request: New time budget
        current_user: Currently authenticated user
        user_service: User service instance

    Returns:
        Updated profile
    """
    profile = await user_service.update_time_budget(
        user_id=current_user.id,
        minutes=request.minutes,
    )

    return UserProfileResponse(
        user_id=profile.user_id,
        background=profile.background,
        goals=profile.goals,
        time_budget_minutes=profile.time_budget_minutes,
        preferred_sources=profile.preferred_sources,
        timezone=profile.timezone,
        onboarding_completed=profile.onboarding_completed,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.get(
    "/me/sources",
    response_model=SourcesListResponse,
    summary="Get content sources",
    description="Get configured content sources for the user.",
)
async def get_sources(
    current_user: CurrentUser,
    user_service: UserServiceDep,
) -> SourcesListResponse:
    """Get user's configured content sources.

    Args:
        current_user: Currently authenticated user
        user_service: User service instance

    Returns:
        List of configured sources
    """
    profile = await user_service.get_profile(current_user.id)
    if profile is None:
        return SourcesListResponse(sources=[])

    sources = []
    for source_type in profile.preferred_sources:
        config = await user_service.get_source_config(current_user.id, source_type)
        sources.append(SourceConfigResponse(
            source_type=source_type,
            config=config or {},
            enabled=config is not None,
        ))

    return SourcesListResponse(sources=sources)


@router.post(
    "/me/sources",
    response_model=SuccessResponse,
    summary="Add content source",
    description="Add or update a content source configuration.",
)
async def add_source(
    request: SourceConfigRequest,
    current_user: CurrentUser,
    user_service: UserServiceDep,
) -> SuccessResponse:
    """Add or update a content source.

    Args:
        request: Source configuration
        current_user: Currently authenticated user
        user_service: User service instance

    Returns:
        Success response
    """
    await user_service.add_source(
        user_id=current_user.id,
        source=request.source_type,
        config=request.config,
    )

    return SuccessResponse(message=f"Source {request.source_type.value} configured")


@router.delete(
    "/me/sources/{source_type}",
    response_model=SuccessResponse,
    summary="Remove content source",
    description="Remove a content source configuration.",
)
async def remove_source(
    source_type: str,
    current_user: CurrentUser,
    user_service: UserServiceDep,
) -> SuccessResponse:
    """Remove a content source.

    Args:
        source_type: Source type to remove
        current_user: Currently authenticated user
        user_service: User service instance

    Returns:
        Success response
    """
    from src.shared.models import SourceType

    try:
        source = SourceType(source_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source type: {source_type}",
        )

    await user_service.remove_source(
        user_id=current_user.id,
        source=source,
    )

    return SuccessResponse(message=f"Source {source_type} removed")
