"""Session Service - Learning session lifecycle management."""

from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Any
from uuid import UUID, uuid4

from src.modules.session.interface import (
    ISessionService,
    Session,
    SessionActivity,
    SessionPlan,
    SessionPlanItem,
    SessionSummary,
)
from src.modules.llm.service import LLMService, get_llm_service
from src.shared.models import ActivityType, SessionStatus, SessionType


@dataclass
class UserSessionProfile:
    """User's session preferences and history."""

    user_id: UUID
    default_session_minutes: int = 30
    preferred_consumption_ratio: float = 0.5  # 50% consumption, 50% production
    current_streak: int = 0
    longest_streak: int = 0
    last_session_date: date | None = None
    total_sessions: int = 0
    topics_in_progress: list[UUID] = field(default_factory=list)
    gaps_identified: list[str] = field(default_factory=list)


@dataclass
class StoredSession:
    """Session with associated data."""

    session: Session
    plan: SessionPlan | None = None
    activities: list[SessionActivity] = field(default_factory=list)
    abandon_reason: str | None = None


class SessionService(ISessionService):
    """Service for managing learning session lifecycle.

    Handles:
    - Session creation and planning
    - Activity tracking within sessions
    - Session completion and summarization
    - Streak management
    """

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self._llm = llm_service or get_llm_service()

        # In-memory storage (use DB in production)
        self._sessions: dict[UUID, StoredSession] = {}
        self._user_sessions: dict[UUID, list[UUID]] = {}  # user_id -> session_ids
        self._active_sessions: dict[UUID, UUID] = {}  # user_id -> active session_id
        self._user_profiles: dict[UUID, UserSessionProfile] = {}
        self._activities: dict[UUID, SessionActivity] = {}

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
        # Check for existing active session
        if user_id in self._active_sessions:
            raise ValueError("User already has an active session")

        # Get user profile
        profile = await self._get_or_create_profile(user_id)

        # Determine duration
        duration = available_minutes or profile.default_session_minutes

        # Create session
        session_id = uuid4()
        session = Session(
            id=session_id,
            user_id=user_id,
            session_type=session_type,
            status=SessionStatus.IN_PROGRESS,
            planned_duration_minutes=duration,
            started_at=datetime.utcnow(),
        )

        # Store session
        stored = StoredSession(session=session)
        self._sessions[session_id] = stored

        # Update indices
        if user_id not in self._user_sessions:
            self._user_sessions[user_id] = []
        self._user_sessions[user_id].append(session_id)
        self._active_sessions[user_id] = session_id

        return session

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
        stored = self._sessions.get(session_id)
        if stored is None:
            raise ValueError(f"Session not found: {session_id}")

        # Return cached plan if available
        if stored.plan is not None:
            return stored.plan

        session = stored.session
        profile = await self._get_or_create_profile(session.user_id)

        # Calculate time allocation
        total_minutes = session.planned_duration_minutes
        consumption_ratio = profile.preferred_consumption_ratio
        consumption_minutes = int(total_minutes * consumption_ratio)
        production_minutes = total_minutes - consumption_minutes

        # Build plan items
        items: list[SessionPlanItem] = []
        order = 0

        # Check if we need review items (spaced repetition)
        has_review = len(profile.gaps_identified) > 0 or profile.current_streak > 0

        # Plan structure varies by session type
        if session.session_type == SessionType.DRILL:
            # Drill sessions focus on production
            items.extend(self._plan_drill_items(
                order,
                total_minutes,
                profile,
            ))
        elif session.session_type == SessionType.CATCHUP:
            # Catch-up sessions focus on review
            items.extend(self._plan_catchup_items(
                order,
                total_minutes,
                profile,
            ))
        else:
            # Regular session: balanced approach
            items.extend(self._plan_regular_items(
                order,
                consumption_minutes,
                production_minutes,
                profile,
                has_review,
            ))

        # Collect topics covered
        topics_covered = list(set(
            item.topic_name for item in items if item.topic_name
        ))

        plan = SessionPlan(
            session_id=session_id,
            total_duration_minutes=total_minutes,
            consumption_minutes=consumption_minutes,
            production_minutes=production_minutes,
            items=items,
            topics_covered=topics_covered,
            includes_review=has_review,
        )

        stored.plan = plan
        return plan

    async def get_current_session(self, user_id: UUID) -> Session | None:
        """Get user's current active session if any."""
        session_id = self._active_sessions.get(user_id)
        if session_id is None:
            return None

        stored = self._sessions.get(session_id)
        return stored.session if stored else None

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
        stored = self._sessions.get(session_id)
        if stored is None:
            raise ValueError(f"Session not found: {session_id}")

        if stored.session.status != SessionStatus.IN_PROGRESS:
            raise ValueError("Cannot record activity for inactive session")

        activity = SessionActivity(
            id=uuid4(),
            session_id=session_id,
            activity_type=activity_type,
            topic_id=topic_id,
            content_id=content_id,
            started_at=datetime.utcnow(),
            performance_data=performance_data or {},
        )

        stored.activities.append(activity)
        self._activities[activity.id] = activity

        return activity

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
        activity = self._activities.get(activity_id)
        if activity is None:
            raise ValueError(f"Activity not found: {activity_id}")

        activity.ended_at = datetime.utcnow()
        if performance_data:
            activity.performance_data.update(performance_data)

        return activity

    async def end_session(self, session_id: UUID) -> SessionSummary:
        """End a session and generate summary.

        Args:
            session_id: Session to end

        Returns:
            SessionSummary with results
        """
        stored = self._sessions.get(session_id)
        if stored is None:
            raise ValueError(f"Session not found: {session_id}")

        session = stored.session
        if session.status != SessionStatus.IN_PROGRESS:
            raise ValueError("Session is not in progress")

        # Update session
        session.status = SessionStatus.COMPLETED
        session.ended_at = datetime.utcnow()
        session.actual_duration_minutes = int(
            (session.ended_at - session.started_at).total_seconds() / 60
        )

        # Remove from active sessions
        if session.user_id in self._active_sessions:
            del self._active_sessions[session.user_id]

        # Update user profile and streak
        profile = await self._get_or_create_profile(session.user_id)
        streak_updated = await self._update_streak(profile)

        # Calculate summary metrics
        summary = await self._generate_summary(stored, profile, streak_updated)

        return summary

    async def abandon_session(
        self,
        session_id: UUID,
        reason: str | None = None,
    ) -> None:
        """Abandon a session without completing.

        Args:
            session_id: Session to abandon
            reason: Optional reason for abandonment
        """
        stored = self._sessions.get(session_id)
        if stored is None:
            raise ValueError(f"Session not found: {session_id}")

        session = stored.session
        session.status = SessionStatus.ABANDONED
        session.ended_at = datetime.utcnow()
        stored.abandon_reason = reason

        # Remove from active sessions
        if session.user_id in self._active_sessions:
            del self._active_sessions[session.user_id]

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
        session_ids = self._user_sessions.get(user_id, [])

        sessions: list[Session] = []
        for sid in reversed(session_ids):  # Newest first
            stored = self._sessions.get(sid)
            if stored is None:
                continue

            if not include_abandoned and stored.session.status == SessionStatus.ABANDONED:
                continue

            sessions.append(stored.session)
            if len(sessions) >= limit:
                break

        return sessions

    async def get_session_activities(self, session_id: UUID) -> list[SessionActivity]:
        """Get all activities for a session.

        Args:
            session_id: Session

        Returns:
            List of SessionActivities
        """
        stored = self._sessions.get(session_id)
        if stored is None:
            raise ValueError(f"Session not found: {session_id}")

        return stored.activities.copy()

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
        profile = await self._get_or_create_profile(user_id)

        streak_at_risk = False
        if profile.last_session_date:
            days_since = (date.today() - profile.last_session_date).days
            streak_at_risk = days_since >= 1 and profile.current_streak > 0

        return {
            "current_streak": profile.current_streak,
            "longest_streak": profile.longest_streak,
            "last_session_date": profile.last_session_date,
            "streak_at_risk": streak_at_risk,
        }

    # --- Private methods ---

    async def _get_or_create_profile(self, user_id: UUID) -> UserSessionProfile:
        """Get or create user session profile."""
        if user_id not in self._user_profiles:
            self._user_profiles[user_id] = UserSessionProfile(user_id=user_id)
        return self._user_profiles[user_id]

    def _plan_regular_items(
        self,
        start_order: int,
        consumption_minutes: int,
        production_minutes: int,
        profile: UserSessionProfile,
        has_review: bool,
    ) -> list[SessionPlanItem]:
        """Plan items for a regular session."""
        items: list[SessionPlanItem] = []
        order = start_order

        # Start with review if needed (10% of production time)
        if has_review and profile.gaps_identified:
            review_time = min(int(production_minutes * 0.2), 10)
            items.append(SessionPlanItem(
                order=order,
                activity_type=ActivityType.DRILL,
                duration_minutes=review_time,
                description="Review previously challenging concepts",
            ))
            order += 1
            production_minutes -= review_time

        # Content consumption (reading/video)
        if consumption_minutes > 0:
            items.append(SessionPlanItem(
                order=order,
                activity_type=ActivityType.CONTENT_READ,
                duration_minutes=consumption_minutes,
                description="Learn new material",
            ))
            order += 1

        # Production: Feynman dialogue
        feynman_time = int(production_minutes * 0.5)
        if feynman_time >= 5:
            items.append(SessionPlanItem(
                order=order,
                activity_type=ActivityType.FEYNMAN_DIALOGUE,
                duration_minutes=feynman_time,
                description="Explain concepts in your own words",
            ))
            order += 1

        # Production: Quiz
        quiz_time = production_minutes - feynman_time
        if quiz_time >= 5:
            items.append(SessionPlanItem(
                order=order,
                activity_type=ActivityType.QUIZ,
                duration_minutes=quiz_time,
                description="Test your understanding",
            ))
            order += 1

        # End with reflection
        if len(items) > 0:
            items.append(SessionPlanItem(
                order=order,
                activity_type=ActivityType.REFLECTION,
                duration_minutes=2,
                description="Reflect on what you learned",
            ))

        return items

    def _plan_drill_items(
        self,
        start_order: int,
        total_minutes: int,
        profile: UserSessionProfile,
    ) -> list[SessionPlanItem]:
        """Plan items for a drill session (focused practice)."""
        items: list[SessionPlanItem] = []
        order = start_order

        # Brief warmup
        warmup_time = min(5, int(total_minutes * 0.1))
        items.append(SessionPlanItem(
            order=order,
            activity_type=ActivityType.QUIZ,
            duration_minutes=warmup_time,
            description="Quick warmup quiz",
        ))
        order += 1

        # Main drill time
        drill_time = total_minutes - warmup_time - 2
        items.append(SessionPlanItem(
            order=order,
            activity_type=ActivityType.DRILL,
            duration_minutes=drill_time,
            description="Focused practice on weak areas",
        ))
        order += 1

        # Brief reflection
        items.append(SessionPlanItem(
            order=order,
            activity_type=ActivityType.REFLECTION,
            duration_minutes=2,
            description="Quick reflection",
        ))

        return items

    def _plan_catchup_items(
        self,
        start_order: int,
        total_minutes: int,
        profile: UserSessionProfile,
    ) -> list[SessionPlanItem]:
        """Plan items for a catch-up session (spaced repetition)."""
        items: list[SessionPlanItem] = []
        order = start_order

        # Heavy on review
        review_time = int(total_minutes * 0.6)
        items.append(SessionPlanItem(
            order=order,
            activity_type=ActivityType.DRILL,
            duration_minutes=review_time,
            description="Review due items (spaced repetition)",
        ))
        order += 1

        # Some new learning
        learn_time = int(total_minutes * 0.3)
        if learn_time >= 5:
            items.append(SessionPlanItem(
                order=order,
                activity_type=ActivityType.CONTENT_READ,
                duration_minutes=learn_time,
                description="Light new material",
            ))
            order += 1

        # Wrap up
        items.append(SessionPlanItem(
            order=order,
            activity_type=ActivityType.REFLECTION,
            duration_minutes=total_minutes - review_time - learn_time,
            description="Session wrap-up",
        ))

        return items

    async def _update_streak(self, profile: UserSessionProfile) -> bool:
        """Update user's streak after completing a session.

        Returns:
            True if streak was incremented
        """
        today = date.today()
        streak_updated = False

        if profile.last_session_date is None:
            # First session
            profile.current_streak = 1
            streak_updated = True
        elif profile.last_session_date == today:
            # Already studied today, no change
            pass
        elif profile.last_session_date == today - timedelta(days=1):
            # Consecutive day
            profile.current_streak += 1
            streak_updated = True
        else:
            # Streak broken, start fresh
            profile.current_streak = 1
            streak_updated = True

        # Update longest streak
        if profile.current_streak > profile.longest_streak:
            profile.longest_streak = profile.current_streak

        profile.last_session_date = today
        profile.total_sessions += 1

        return streak_updated

    async def _generate_summary(
        self,
        stored: StoredSession,
        profile: UserSessionProfile,
        streak_updated: bool,
    ) -> SessionSummary:
        """Generate session summary."""
        session = stored.session

        # Count completed activities
        activities_completed = sum(
            1 for a in stored.activities if a.ended_at is not None
        )

        # Collect topics
        topics_covered: list[str] = []
        if stored.plan:
            topics_covered = stored.plan.topics_covered.copy()

        # Calculate scores from activities
        quiz_score: float | None = None
        feynman_score: float | None = None
        content_consumed = 0

        for activity in stored.activities:
            if activity.activity_type == ActivityType.QUIZ:
                if "score" in activity.performance_data:
                    quiz_score = activity.performance_data["score"]
            elif activity.activity_type == ActivityType.FEYNMAN_DIALOGUE:
                if "score" in activity.performance_data:
                    feynman_score = activity.performance_data["score"]
            elif activity.activity_type == ActivityType.CONTENT_READ:
                content_consumed += 1

        # Identify new gaps from quiz/feynman performance
        new_gaps: list[str] = []
        for activity in stored.activities:
            gaps = activity.performance_data.get("gaps", [])
            new_gaps.extend(gaps)

        # Update profile with new gaps
        profile.gaps_identified.extend(new_gaps)

        # Generate next session preview using LLM
        next_preview = await self._generate_next_preview(stored, profile)

        return SessionSummary(
            session_id=session.id,
            duration_minutes=session.actual_duration_minutes or 0,
            activities_completed=activities_completed,
            topics_covered=topics_covered,
            quiz_score=quiz_score,
            feynman_score=feynman_score,
            content_consumed=content_consumed,
            new_gaps_identified=new_gaps,
            streak_updated=streak_updated,
            next_session_preview=next_preview,
        )

    async def _generate_next_preview(
        self,
        stored: StoredSession,
        profile: UserSessionProfile,
    ) -> str:
        """Generate preview for next session."""
        if not profile.gaps_identified and not stored.plan:
            return "Continue with your learning path"

        # Simple preview based on gaps
        if profile.gaps_identified:
            gap_preview = profile.gaps_identified[-1] if profile.gaps_identified else ""
            return f"Next: Review {gap_preview} and continue learning"

        return "Next: Continue where you left off"


# Factory function
_session_service: SessionService | None = None


def get_session_service() -> SessionService:
    """Get session service singleton."""
    global _session_service
    if _session_service is None:
        _session_service = SessionService()
    return _session_service
