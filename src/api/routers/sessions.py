"""Session API routes."""

from uuid import UUID
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query, status

from src.api.dependencies import CurrentUser, CurrentUserId, SessionServiceDep

if TYPE_CHECKING:
    from src.modules.session.interface import SessionServiceInterface


async def _verify_session_ownership(
    session_id: UUID,
    user_id: UUID,
    session_service: "SessionServiceInterface",
) -> None:
    """Verify that the user owns the specified session.

    Args:
        session_id: The session to verify
        user_id: The user who should own the session
        session_service: Session service instance

    Raises:
        HTTPException: 403 if user doesn't own session, 404 if session not found
    """
    # Check if it's the user's active session
    current_session = await session_service.get_current_session(user_id)
    if current_session and current_session.id == session_id:
        return  # User owns this active session

    # Check if it's in user's history
    history = await session_service.get_session_history(
        user_id=user_id,
        limit=1000,  # Check all sessions
        include_abandoned=True,
    )

    if any(s.id == session_id for s in history):
        return  # User owns this historical session

    # Session either doesn't exist or belongs to another user
    # Return 403 to avoid leaking information about session existence
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied: you don't have permission to access this session",
    )


from src.api.schemas.sessions import (
    ActivityResponse,
    CompleteActivityRequest,
    RecordActivityRequest,
    SessionHistoryResponse,
    SessionPlanItemResponse,
    SessionPlanResponse,
    SessionResponse,
    SessionSummaryResponse,
    StartSessionRequest,
    StreakInfoResponse,
)
from src.api.schemas.common import SuccessResponse

router = APIRouter()


@router.post(
    "",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start new session",
    description="Start a new learning session.",
)
async def start_session(
    request: StartSessionRequest,
    current_user: CurrentUser,
    session_service: SessionServiceDep,
) -> SessionResponse:
    """Start a new learning session.

    Args:
        request: Session parameters
        current_user: Currently authenticated user
        session_service: Session service instance

    Returns:
        New session

    Raises:
        HTTPException: If user already has active session
    """
    try:
        session = await session_service.start_session(
            user_id=current_user.id,
            available_minutes=request.available_minutes,
            session_type=request.session_type,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )

    return SessionResponse(
        id=session.id,
        user_id=session.user_id,
        session_type=session.session_type,
        status=session.status,
        planned_duration_minutes=session.planned_duration_minutes,
        actual_duration_minutes=session.actual_duration_minutes,
        started_at=session.started_at,
        ended_at=session.ended_at,
    )


@router.get(
    "/active",
    response_model=SessionResponse | None,
    summary="Get active session",
    description="Get current active session if any.",
)
async def get_active_session(
    current_user: CurrentUser,
    session_service: SessionServiceDep,
) -> SessionResponse | None:
    """Get current active session.

    Args:
        current_user: Currently authenticated user
        session_service: Session service instance

    Returns:
        Active session or None
    """
    session = await session_service.get_current_session(current_user.id)

    if session is None:
        return None

    return SessionResponse(
        id=session.id,
        user_id=session.user_id,
        session_type=session.session_type,
        status=session.status,
        planned_duration_minutes=session.planned_duration_minutes,
        actual_duration_minutes=session.actual_duration_minutes,
        started_at=session.started_at,
        ended_at=session.ended_at,
    )


@router.get(
    "/{session_id}",
    response_model=SessionResponse,
    summary="Get session",
    description="Get session details by ID.",
)
async def get_session(
    session_id: UUID,
    current_user: CurrentUser,
    session_service: SessionServiceDep,
) -> SessionResponse:
    """Get session by ID.

    Args:
        session_id: Session UUID
        current_user: Currently authenticated user
        session_service: Session service instance

    Returns:
        Session details

    Raises:
        HTTPException: If session not found
    """
    try:
        # Get from history to find the session
        history = await session_service.get_session_history(
            user_id=current_user.id,
            limit=100,
            include_abandoned=True,
        )

        session = next((s for s in history if s.id == session_id), None)
        if session is None:
            raise ValueError("Session not found")

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return SessionResponse(
        id=session.id,
        user_id=session.user_id,
        session_type=session.session_type,
        status=session.status,
        planned_duration_minutes=session.planned_duration_minutes,
        actual_duration_minutes=session.actual_duration_minutes,
        started_at=session.started_at,
        ended_at=session.ended_at,
    )


@router.get(
    "/{session_id}/plan",
    response_model=SessionPlanResponse,
    summary="Get session plan",
    description="Get the learning plan for a session.",
)
async def get_session_plan(
    session_id: UUID,
    current_user: CurrentUser,
    session_service: SessionServiceDep,
) -> SessionPlanResponse:
    """Get session plan.

    Args:
        session_id: Session UUID
        current_user: Currently authenticated user
        session_service: Session service instance

    Returns:
        Session plan

    Raises:
        HTTPException: If session not found or access denied
    """
    # Verify user owns this session
    await _verify_session_ownership(session_id, current_user.id, session_service)

    try:
        plan = await session_service.get_session_plan(session_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return SessionPlanResponse(
        session_id=plan.session_id,
        total_duration_minutes=plan.total_duration_minutes,
        consumption_minutes=plan.consumption_minutes,
        production_minutes=plan.production_minutes,
        items=[
            SessionPlanItemResponse(
                order=item.order,
                activity_type=item.activity_type,
                duration_minutes=item.duration_minutes,
                description=item.description,
                topic_name=item.topic_name,
                topic_id=item.topic_id,
                content_id=item.content_id,
            )
            for item in plan.items
        ],
        topics_covered=plan.topics_covered,
        includes_review=plan.includes_review,
    )


@router.post(
    "/{session_id}/activities",
    response_model=ActivityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record activity",
    description="Record a new activity within a session.",
)
async def record_activity(
    session_id: UUID,
    request: RecordActivityRequest,
    current_user: CurrentUser,
    session_service: SessionServiceDep,
) -> ActivityResponse:
    """Record an activity within a session.

    Args:
        session_id: Session UUID
        request: Activity data
        current_user: Currently authenticated user
        session_service: Session service instance

    Returns:
        Created activity

    Raises:
        HTTPException: If session not found, inactive, or access denied
    """
    # Verify user owns this session
    await _verify_session_ownership(session_id, current_user.id, session_service)

    try:
        activity = await session_service.record_activity(
            session_id=session_id,
            activity_type=request.activity_type,
            topic_id=request.topic_id,
            content_id=request.content_id,
            performance_data=request.performance_data,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return ActivityResponse(
        id=activity.id,
        session_id=activity.session_id,
        activity_type=activity.activity_type,
        topic_id=activity.topic_id,
        content_id=activity.content_id,
        started_at=activity.started_at,
        ended_at=activity.ended_at,
        performance_data=activity.performance_data,
    )


@router.put(
    "/{session_id}/activities/{activity_id}/complete",
    response_model=ActivityResponse,
    summary="Complete activity",
    description="Mark an activity as complete.",
)
async def complete_activity(
    session_id: UUID,
    activity_id: UUID,
    request: CompleteActivityRequest,
    current_user: CurrentUser,
    session_service: SessionServiceDep,
) -> ActivityResponse:
    """Complete an activity.

    Args:
        session_id: Session UUID
        activity_id: Activity UUID
        request: Completion data
        current_user: Currently authenticated user
        session_service: Session service instance

    Returns:
        Updated activity

    Raises:
        HTTPException: If activity not found or access denied
    """
    # Verify user owns this session
    await _verify_session_ownership(session_id, current_user.id, session_service)

    try:
        activity = await session_service.complete_activity(
            activity_id=activity_id,
            performance_data=request.performance_data,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity not found",
        )

    return ActivityResponse(
        id=activity.id,
        session_id=activity.session_id,
        activity_type=activity.activity_type,
        topic_id=activity.topic_id,
        content_id=activity.content_id,
        started_at=activity.started_at,
        ended_at=activity.ended_at,
        performance_data=activity.performance_data,
    )


@router.put(
    "/{session_id}/end",
    response_model=SessionSummaryResponse,
    summary="End session",
    description="End current session and get summary.",
)
async def end_session(
    session_id: UUID,
    current_user: CurrentUser,
    session_service: SessionServiceDep,
) -> SessionSummaryResponse:
    """End session and get summary.

    Args:
        session_id: Session UUID
        current_user: Currently authenticated user
        session_service: Session service instance

    Returns:
        Session summary

    Raises:
        HTTPException: If session not found, already ended, or access denied
    """
    # Verify user owns this session
    await _verify_session_ownership(session_id, current_user.id, session_service)

    try:
        summary = await session_service.end_session(session_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return SessionSummaryResponse(
        session_id=summary.session_id,
        duration_minutes=summary.duration_minutes,
        activities_completed=summary.activities_completed,
        topics_covered=summary.topics_covered,
        quiz_score=summary.quiz_score,
        feynman_score=summary.feynman_score,
        content_consumed=summary.content_consumed,
        new_gaps_identified=summary.new_gaps_identified,
        streak_updated=summary.streak_updated,
        next_session_preview=summary.next_session_preview,
    )


@router.delete(
    "/{session_id}",
    response_model=SuccessResponse,
    summary="Abandon session",
    description="Abandon current session without completing.",
)
async def abandon_session(
    session_id: UUID,
    current_user: CurrentUser,
    session_service: SessionServiceDep,
    reason: str | None = Query(default=None, description="Reason for abandonment"),
) -> SuccessResponse:
    """Abandon session.

    Args:
        session_id: Session UUID
        current_user: Currently authenticated user
        session_service: Session service instance
        reason: Optional reason

    Returns:
        Success response

    Raises:
        HTTPException: If session not found or access denied
    """
    # Verify user owns this session
    await _verify_session_ownership(session_id, current_user.id, session_service)

    try:
        await session_service.abandon_session(session_id, reason)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return SuccessResponse(message="Session abandoned")


@router.get(
    "/history",
    response_model=SessionHistoryResponse,
    summary="Get session history",
    description="Get user's session history.",
)
async def get_session_history(
    current_user: CurrentUser,
    session_service: SessionServiceDep,
    limit: int = Query(default=10, ge=1, le=50),
    include_abandoned: bool = Query(default=False),
) -> SessionHistoryResponse:
    """Get session history.

    Args:
        current_user: Currently authenticated user
        session_service: Session service instance
        limit: Maximum sessions to return
        include_abandoned: Include abandoned sessions

    Returns:
        Session history
    """
    sessions = await session_service.get_session_history(
        user_id=current_user.id,
        limit=limit,
        include_abandoned=include_abandoned,
    )

    return SessionHistoryResponse(
        sessions=[
            SessionResponse(
                id=s.id,
                user_id=s.user_id,
                session_type=s.session_type,
                status=s.status,
                planned_duration_minutes=s.planned_duration_minutes,
                actual_duration_minutes=s.actual_duration_minutes,
                started_at=s.started_at,
                ended_at=s.ended_at,
            )
            for s in sessions
        ],
        total=len(sessions),
    )


@router.get(
    "/streak",
    response_model=StreakInfoResponse,
    summary="Get streak info",
    description="Get user's learning streak information.",
)
async def get_streak_info(
    current_user: CurrentUser,
    session_service: SessionServiceDep,
) -> StreakInfoResponse:
    """Get streak information.

    Args:
        current_user: Currently authenticated user
        session_service: Session service instance

    Returns:
        Streak information
    """
    streak = await session_service.get_streak_info(current_user.id)

    return StreakInfoResponse(
        current_streak=streak["current_streak"],
        longest_streak=streak["longest_streak"],
        last_session_date=streak["last_session_date"],
        streak_at_risk=streak["streak_at_risk"],
    )
