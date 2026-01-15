"""Session Restoration Service - Restores user state on login.

This service handles loading user's previous session state when they log in,
so they can resume where they left off.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from src.modules.session.db_service import get_db_session_service
from src.modules.agents.context_service import get_context_service
from src.modules.agents.learning_context import SharedLearningContext


@dataclass
class WelcomeContext:
    """Context for displaying a personalized welcome message on login."""

    # Session info
    has_active_session: bool = False
    active_session_id: UUID | None = None
    active_session_started_at: datetime | None = None

    # Learning context
    primary_goal: str | None = None
    current_focus: str | None = None
    learning_progress: float = 0.0  # Overall progress 0.0 to 1.0

    # Streak info
    current_streak: int = 0
    longest_streak: int = 0
    streak_at_risk: bool = False

    # Recovery info
    days_since_last_session: int = 0
    needs_recovery: bool = False  # True if 3+ days away

    # Recent activity
    last_session_topic: str | None = None
    last_quiz_score: float | None = None


class SessionRestorationService:
    """Service for restoring user session state on login."""

    def __init__(self) -> None:
        self._session_service = get_db_session_service()
        self._context_service = get_context_service()

    async def get_welcome_context(self, user_id: UUID) -> WelcomeContext:
        """Load all relevant state for a personalized welcome message.

        Args:
            user_id: The user's UUID

        Returns:
            WelcomeContext with all relevant state for welcome message
        """
        welcome = WelcomeContext()

        # Load active session if any
        try:
            active_session = await self._session_service.get_current_session(user_id)
            if active_session:
                welcome.has_active_session = True
                welcome.active_session_id = active_session.id
                welcome.active_session_started_at = active_session.started_at
        except Exception:
            pass  # No active session

        # Load learning context
        try:
            learning_ctx = await self._context_service.get_context(user_id)
            welcome.primary_goal = learning_ctx.primary_goal
            welcome.current_focus = learning_ctx.current_focus

            # Calculate overall progress from learning path
            if learning_ctx.learning_path:
                total_progress = sum(
                    stage.progress for stage in learning_ctx.learning_path
                )
                welcome.learning_progress = total_progress / len(learning_ctx.learning_path)
        except Exception:
            pass  # No learning context yet

        # Load streak info
        try:
            streak_info = await self._session_service.get_streak_info(user_id)
            welcome.current_streak = streak_info.get("current_streak", 0)
            welcome.longest_streak = streak_info.get("longest_streak", 0)
            welcome.streak_at_risk = streak_info.get("streak_at_risk", False)
        except Exception:
            pass  # No streak info

        # Load session history for recovery check
        try:
            history = await self._session_service.get_session_history(user_id, limit=1)
            if history:
                last_session = history[0]
                if last_session.ended_at:
                    days_since = (datetime.utcnow() - last_session.ended_at).days
                    welcome.days_since_last_session = days_since
                    welcome.needs_recovery = days_since >= 3

                    # Get last session activities for topic/score info
                    activities = await self._session_service.get_session_activities(
                        last_session.id
                    )
                    for activity in activities:
                        perf = activity.performance_data or {}
                        if activity.activity_type.value == "quiz" and "score" in perf:
                            welcome.last_quiz_score = perf["score"]
                        if "topic" in perf:
                            welcome.last_session_topic = perf["topic"]
        except Exception:
            pass  # No session history

        return welcome

    async def get_learning_context(self, user_id: UUID) -> SharedLearningContext | None:
        """Load the user's learning context.

        Args:
            user_id: The user's UUID

        Returns:
            SharedLearningContext or None if not found
        """
        try:
            return await self._context_service.get_context(user_id)
        except Exception:
            return None

    def format_welcome_message(self, welcome: WelcomeContext, email: str) -> str:
        """Format a personalized welcome message.

        Args:
            welcome: WelcomeContext with user state
            email: User's email for greeting

        Returns:
            Formatted welcome message string
        """
        lines = [f"Welcome back! Logged in as {email}"]

        # Show learning goal if set
        if welcome.primary_goal:
            lines.append(f"\nLearning goal: {welcome.primary_goal}")

            # Show progress
            if welcome.learning_progress > 0:
                progress_pct = int(welcome.learning_progress * 100)
                lines.append(f"Progress: {progress_pct}%")

            # Show current focus
            if welcome.current_focus:
                lines.append(f"Currently working on: {welcome.current_focus}")

        # Show streak info
        if welcome.current_streak > 0:
            streak_status = " (at risk!)" if welcome.streak_at_risk else ""
            lines.append(f"\nStreak: {welcome.current_streak} days{streak_status}")

        # Show recovery message if needed
        if welcome.needs_recovery:
            lines.append(f"\nIt's been {welcome.days_since_last_session} days since your last session.")
            lines.append("Let's ease back in with a recovery session!")

        # Show active session if any
        if welcome.has_active_session:
            lines.append("\nYou have an active session in progress.")
            lines.append("Run 'learner start' to resume.")

        return "\n".join(lines)


# Singleton instance
_restoration_service: SessionRestorationService | None = None


def get_restoration_service() -> SessionRestorationService:
    """Get the session restoration service singleton."""
    global _restoration_service
    if _restoration_service is None:
        _restoration_service = SessionRestorationService()
    return _restoration_service
