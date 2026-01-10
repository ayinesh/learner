"""Session Module - Learning session lifecycle management."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from src.shared.models import ActivityType, SessionStatus, SessionType


@dataclass
class SessionPlanItem:
    """A planned item in a session."""

    order: int
    activity_type: ActivityType
    duration_minutes: int
    topic_id: UUID | None = None
    topic_name: str | None = None
    content_id: UUID | None = None
    description: str = ""


@dataclass
class SessionPlan:
    """Complete plan for a learning session."""

    session_id: UUID
    total_duration_minutes: int
    consumption_minutes: int  # Time for reading/watching
    production_minutes: int  # Time for quizzes/Feynman
    items: list[SessionPlanItem]
    topics_covered: list[str]
    includes_review: bool  # Has spaced repetition items


@dataclass
class Session:
    """A learning session."""

    id: UUID
    user_id: UUID
    session_type: SessionType
    status: SessionStatus
    planned_duration_minutes: int
    actual_duration_minutes: int | None = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    ended_at: datetime | None = None


@dataclass
class SessionActivity:
    """An activity within a session."""

    id: UUID
    session_id: UUID
    activity_type: ActivityType
    topic_id: UUID | None
    content_id: UUID | None
    started_at: datetime
    ended_at: datetime | None = None
    performance_data: dict = field(default_factory=dict)


@dataclass
class SessionSummary:
    """Summary of a completed session."""

    session_id: UUID
    duration_minutes: int
    activities_completed: int
    topics_covered: list[str]
    quiz_score: float | None = None
    feynman_score: float | None = None
    content_consumed: int
    new_gaps_identified: list[str]
    streak_updated: bool = False
    next_session_preview: str | None = None


class ISessionService(Protocol):
    """Interface for session service.

    Manages learning session lifecycle and activity tracking.
    """

    async def start_session(
        self,
        user_id: UUID,
        available_minutes: int | None = None,
        session_type: SessionType = SessionType.REGULAR,
    ) -> Session:
        """Start a new learning session.

        Args:
            user_id: User starting the session
            available_minutes: Time available (or use user's default)
            session_type: Type of session

        Returns:
            New Session
        """
        ...

    async def get_session_plan(self, session_id: UUID) -> SessionPlan:
        """Get the plan for a session.

        The plan balances consumption (50%) and production (50%) time,
        incorporates spaced repetition reviews, and adapts to user's
        current progress and identified gaps.

        Args:
            session_id: Session to plan

        Returns:
            SessionPlan with ordered activities
        """
        ...

    async def get_current_session(self, user_id: UUID) -> Session | None:
        """Get user's current active session if any.

        Args:
            user_id: User

        Returns:
            Active Session or None
        """
        ...

    async def record_activity(
        self,
        session_id: UUID,
        activity_type: ActivityType,
        topic_id: UUID | None = None,
        content_id: UUID | None = None,
        performance_data: dict[str, Any] | None = None,
    ) -> SessionActivity:
        """Record an activity within a session.

        Args:
            session_id: Session
            activity_type: Type of activity
            topic_id: Related topic
            content_id: Related content
            performance_data: Activity-specific metrics

        Returns:
            Created SessionActivity
        """
        ...

    async def complete_activity(
        self,
        activity_id: UUID,
        performance_data: dict[str, Any] | None = None,
    ) -> SessionActivity:
        """Mark an activity as complete.

        Args:
            activity_id: Activity to complete
            performance_data: Final performance metrics

        Returns:
            Updated SessionActivity
        """
        ...

    async def end_session(self, session_id: UUID) -> SessionSummary:
        """End a session and generate summary.

        Args:
            session_id: Session to end

        Returns:
            SessionSummary with results
        """
        ...

    async def abandon_session(self, session_id: UUID, reason: str | None = None) -> None:
        """Abandon a session without completing.

        Args:
            session_id: Session to abandon
            reason: Optional reason for abandonment
        """
        ...

    async def get_session_history(
        self,
        user_id: UUID,
        limit: int = 10,
        include_abandoned: bool = False,
    ) -> list[Session]:
        """Get user's session history.

        Args:
            user_id: User
            limit: Maximum sessions to return
            include_abandoned: Include abandoned sessions

        Returns:
            List of Sessions, newest first
        """
        ...

    async def get_session_activities(self, session_id: UUID) -> list[SessionActivity]:
        """Get all activities for a session.

        Args:
            session_id: Session

        Returns:
            List of SessionActivities
        """
        ...

    async def get_streak_info(self, user_id: UUID) -> dict:
        """Get user's streak information.

        Returns:
            {
                current_streak: int,
                longest_streak: int,
                last_session_date: date,
                streak_at_risk: bool
            }
        """
        ...
