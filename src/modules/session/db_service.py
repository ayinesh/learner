"""Session Service - Database-backed implementation."""

from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import and_, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.session.interface import (
    ISessionService,
    Session,
    SessionActivity,
    SessionPlan,
    SessionPlanItem,
    SessionSummary,
)
from src.modules.session.models import (
    SessionActivityModel,
    SessionModel,
    UserLearningPatternModel,
)
from src.modules.llm.service import LLMService, get_llm_service
from src.shared.database import get_db_session
from src.shared.models import ActivityType, SessionStatus, SessionType


class DatabaseSessionService(ISessionService):
    """Database-backed session service.

    Handles:
    - Session creation and planning
    - Activity tracking within sessions
    - Session completion and summarization
    - Streak management
    """

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self._llm = llm_service or get_llm_service()

        # Cache for session plans (in-memory since they're transient)
        self._session_plans: dict[UUID, SessionPlan] = {}

    async def start_session(
        self,
        user_id: UUID,
        available_minutes: int | None = None,
        session_type: SessionType = SessionType.REGULAR,
    ) -> Session:
        """Start a new learning session."""
        async with get_db_session() as db:
            # Check for existing active session
            active_result = await db.execute(
                select(SessionModel).where(
                    and_(
                        SessionModel.user_id == user_id,
                        SessionModel.status == "in_progress",
                    )
                )
            )
            if active_result.scalar_one_or_none():
                raise ValueError("User already has an active session")

            # Get user's learning pattern for default duration
            pattern = await self._get_or_create_pattern(db, user_id)
            duration = available_minutes or 30

            # Create session
            session = SessionModel(
                id=uuid4(),
                user_id=user_id,
                session_type=session_type.value,
                status=SessionStatus.IN_PROGRESS.value,
                planned_duration_minutes=duration,
                started_at=datetime.utcnow(),
            )
            db.add(session)
            await db.flush()
            await db.refresh(session)

            return self._model_to_session(session)

    async def get_session_plan(self, session_id: UUID) -> SessionPlan:
        """Get the plan for a session."""
        # Check cache
        if session_id in self._session_plans:
            return self._session_plans[session_id]

        async with get_db_session() as db:
            result = await db.execute(
                select(SessionModel).where(SessionModel.id == session_id)
            )
            session = result.scalar_one_or_none()

            if session is None:
                raise ValueError(f"Session not found: {session_id}")

            pattern = await self._get_or_create_pattern(db, session.user_id)

            # Calculate time allocation
            total_minutes = session.planned_duration_minutes
            consumption_ratio = 0.5  # 50% consumption, 50% production
            consumption_minutes = int(total_minutes * consumption_ratio)
            production_minutes = total_minutes - consumption_minutes

            # Build plan items based on session type
            items: list[SessionPlanItem] = []

            stype = SessionType(session.session_type)
            if stype == SessionType.DRILL:
                items = self._plan_drill_items(total_minutes, pattern)
            elif stype == SessionType.CATCHUP:
                items = self._plan_catchup_items(total_minutes, pattern)
            else:
                items = self._plan_regular_items(
                    consumption_minutes,
                    production_minutes,
                    pattern,
                )

            plan = SessionPlan(
                session_id=session_id,
                total_duration_minutes=total_minutes,
                consumption_minutes=consumption_minutes,
                production_minutes=production_minutes,
                items=items,
                topics_covered=[],
                includes_review=pattern.current_streak > 0,
            )

            # Cache the plan
            self._session_plans[session_id] = plan

            return plan

    async def get_current_session(self, user_id: UUID) -> Session | None:
        """Get user's current active session if any."""
        async with get_db_session() as db:
            result = await db.execute(
                select(SessionModel).where(
                    and_(
                        SessionModel.user_id == user_id,
                        SessionModel.status == "in_progress",
                    )
                )
            )
            session = result.scalar_one_or_none()

            if session is None:
                return None

            return self._model_to_session(session)

    async def record_activity(
        self,
        session_id: UUID,
        activity_type: ActivityType,
        topic_id: UUID | None = None,
        content_id: UUID | None = None,
        performance_data: dict[str, Any] | None = None,
    ) -> SessionActivity:
        """Record an activity within a session."""
        async with get_db_session() as db:
            # Verify session exists and is active
            result = await db.execute(
                select(SessionModel).where(SessionModel.id == session_id)
            )
            session = result.scalar_one_or_none()

            if session is None:
                raise ValueError(f"Session not found: {session_id}")

            if session.status != "in_progress":
                raise ValueError("Cannot record activity for inactive session")

            activity = SessionActivityModel(
                id=uuid4(),
                session_id=session_id,
                activity_type=activity_type.value,
                topic_id=topic_id,
                content_id=content_id,
                started_at=datetime.utcnow(),
                performance_data=performance_data or {},
            )
            db.add(activity)
            await db.flush()
            await db.refresh(activity)

            return self._model_to_activity(activity)

    async def complete_activity(
        self,
        activity_id: UUID,
        performance_data: dict[str, Any] | None = None,
    ) -> SessionActivity:
        """Mark an activity as complete."""
        async with get_db_session() as db:
            result = await db.execute(
                select(SessionActivityModel).where(
                    SessionActivityModel.id == activity_id
                )
            )
            activity = result.scalar_one_or_none()

            if activity is None:
                raise ValueError(f"Activity not found: {activity_id}")

            activity.ended_at = datetime.utcnow()
            if performance_data:
                current_data = activity.performance_data or {}
                current_data.update(performance_data)
                activity.performance_data = current_data

            return self._model_to_activity(activity)

    async def end_session(self, session_id: UUID) -> SessionSummary:
        """End a session and generate summary."""
        async with get_db_session() as db:
            result = await db.execute(
                select(SessionModel).where(SessionModel.id == session_id)
            )
            session = result.scalar_one_or_none()

            if session is None:
                raise ValueError(f"Session not found: {session_id}")

            if session.status != "in_progress":
                raise ValueError("Session is not in progress")

            # Update session
            session.status = "completed"
            session.ended_at = datetime.utcnow()
            session.actual_duration_minutes = int(
                (session.ended_at - session.started_at).total_seconds() / 60
            )

            # Get activities
            activities_result = await db.execute(
                select(SessionActivityModel).where(
                    SessionActivityModel.session_id == session_id
                )
            )
            activities = activities_result.scalars().all()

            # Update streak
            pattern = await self._get_or_create_pattern(db, session.user_id)
            streak_updated = await self._update_streak(pattern)

            # Calculate summary
            activities_completed = sum(
                1 for a in activities if a.ended_at is not None
            )

            # Extract performance data
            quiz_score: float | None = None
            feynman_score: float | None = None
            content_consumed = 0
            new_gaps: list[str] = []

            for activity in activities:
                perf = activity.performance_data or {}
                # Type safety: ensure perf is a dict before accessing
                if not isinstance(perf, dict):
                    perf = {}

                if activity.activity_type == "quiz":
                    # Type safety: validate score is numeric
                    if "score" in perf and isinstance(perf["score"], (int, float)):
                        quiz_score = float(perf["score"])
                    # Type safety: validate gaps is a list
                    gaps = perf.get("gaps", [])
                    if isinstance(gaps, list):
                        new_gaps.extend(str(g) for g in gaps if g is not None)
                elif activity.activity_type == "feynman_dialogue":
                    # Type safety: validate score is numeric
                    if "score" in perf and isinstance(perf["score"], (int, float)):
                        feynman_score = float(perf["score"])
                    # Type safety: validate gaps is a list
                    gaps = perf.get("gaps", [])
                    if isinstance(gaps, list):
                        new_gaps.extend(str(g) for g in gaps if g is not None)
                elif activity.activity_type == "content_read":
                    content_consumed += 1

            # Get topics from plan
            plan = self._session_plans.get(session_id)
            topics_covered = plan.topics_covered if plan else []

            # Clear plan cache
            if session_id in self._session_plans:
                del self._session_plans[session_id]

            return SessionSummary(
                session_id=session_id,
                duration_minutes=session.actual_duration_minutes or 0,
                activities_completed=activities_completed,
                topics_covered=topics_covered,
                quiz_score=quiz_score,
                feynman_score=feynman_score,
                content_consumed=content_consumed,
                new_gaps_identified=new_gaps,
                streak_updated=streak_updated,
                next_session_preview="Continue with your learning path",
            )

    async def abandon_session(
        self,
        session_id: UUID,
        reason: str | None = None,
    ) -> None:
        """Abandon a session without completing."""
        async with get_db_session() as db:
            result = await db.execute(
                select(SessionModel).where(SessionModel.id == session_id)
            )
            session = result.scalar_one_or_none()

            if session is None:
                raise ValueError(f"Session not found: {session_id}")

            session.status = "abandoned"
            session.ended_at = datetime.utcnow()

            # Clear plan cache
            if session_id in self._session_plans:
                del self._session_plans[session_id]

    async def get_session_history(
        self,
        user_id: UUID,
        limit: int = 10,
        include_abandoned: bool = False,
    ) -> list[Session]:
        """Get user's session history."""
        async with get_db_session() as db:
            query = select(SessionModel).where(
                SessionModel.user_id == user_id
            )

            if not include_abandoned:
                query = query.where(SessionModel.status != "abandoned")

            query = query.order_by(desc(SessionModel.started_at)).limit(limit)

            result = await db.execute(query)
            sessions = result.scalars().all()

            return [self._model_to_session(s) for s in sessions]

    async def get_session_activities(self, session_id: UUID) -> list[SessionActivity]:
        """Get all activities for a session."""
        async with get_db_session() as db:
            result = await db.execute(
                select(SessionActivityModel)
                .where(SessionActivityModel.session_id == session_id)
                .order_by(SessionActivityModel.started_at)
            )
            activities = result.scalars().all()

            return [self._model_to_activity(a) for a in activities]

    async def get_streak_info(self, user_id: UUID) -> dict:
        """Get user's streak information."""
        async with get_db_session() as db:
            pattern = await self._get_or_create_pattern(db, user_id)

            # Check if streak is at risk
            streak_at_risk = False
            if pattern.days_since_last_session >= 1 and pattern.current_streak > 0:
                streak_at_risk = True

            return {
                "current_streak": pattern.current_streak,
                "longest_streak": pattern.longest_streak,
                "last_session_date": pattern.updated_at.date() if pattern.updated_at else None,
                "streak_at_risk": streak_at_risk,
            }

    # --- Private methods ---

    async def _get_or_create_pattern(
        self,
        db: AsyncSession,
        user_id: UUID,
    ) -> UserLearningPatternModel:
        """Get or create user learning pattern."""
        result = await db.execute(
            select(UserLearningPatternModel).where(
                UserLearningPatternModel.user_id == user_id
            )
        )
        pattern = result.scalar_one_or_none()

        if pattern is None:
            pattern = UserLearningPatternModel(
                id=uuid4(),
                user_id=user_id,
            )
            db.add(pattern)
            await db.flush()
            await db.refresh(pattern)

        return pattern

    async def _update_streak(self, pattern: UserLearningPatternModel) -> bool:
        """Update user's streak after completing a session."""
        today = date.today()
        streak_updated = False

        # Determine last session date from days_since_last_session
        if pattern.days_since_last_session == 0:
            # Already studied today
            pass
        elif pattern.days_since_last_session == 1:
            # Consecutive day
            pattern.current_streak += 1
            streak_updated = True
        else:
            # Streak broken or first session
            pattern.current_streak = 1
            streak_updated = True

        # Update longest streak
        if pattern.current_streak > pattern.longest_streak:
            pattern.longest_streak = pattern.current_streak

        pattern.days_since_last_session = 0
        pattern.total_sessions += 1
        pattern.updated_at = datetime.utcnow()

        return streak_updated

    def _plan_regular_items(
        self,
        consumption_minutes: int,
        production_minutes: int,
        pattern: UserLearningPatternModel,
    ) -> list[SessionPlanItem]:
        """Plan items for a regular session."""
        items: list[SessionPlanItem] = []
        order = 0

        # Review if streak exists
        if pattern.current_streak > 0:
            review_time = min(int(production_minutes * 0.2), 10)
            items.append(SessionPlanItem(
                order=order,
                activity_type=ActivityType.DRILL,
                duration_minutes=review_time,
                description="Review previously challenging concepts",
            ))
            order += 1
            production_minutes -= review_time

        # Content consumption
        if consumption_minutes > 0:
            items.append(SessionPlanItem(
                order=order,
                activity_type=ActivityType.CONTENT_READ,
                duration_minutes=consumption_minutes,
                description="Learn new material",
            ))
            order += 1

        # Feynman dialogue
        feynman_time = int(production_minutes * 0.5)
        if feynman_time >= 5:
            items.append(SessionPlanItem(
                order=order,
                activity_type=ActivityType.FEYNMAN_DIALOGUE,
                duration_minutes=feynman_time,
                description="Explain concepts in your own words",
            ))
            order += 1

        # Quiz
        quiz_time = production_minutes - feynman_time
        if quiz_time >= 5:
            items.append(SessionPlanItem(
                order=order,
                activity_type=ActivityType.QUIZ,
                duration_minutes=quiz_time,
                description="Test your understanding",
            ))
            order += 1

        # Reflection
        if items:
            items.append(SessionPlanItem(
                order=order,
                activity_type=ActivityType.REFLECTION,
                duration_minutes=2,
                description="Reflect on what you learned",
            ))

        return items

    def _plan_drill_items(
        self,
        total_minutes: int,
        pattern: UserLearningPatternModel,
    ) -> list[SessionPlanItem]:
        """Plan items for a drill session."""
        items: list[SessionPlanItem] = []

        warmup_time = min(5, int(total_minutes * 0.1))
        items.append(SessionPlanItem(
            order=0,
            activity_type=ActivityType.QUIZ,
            duration_minutes=warmup_time,
            description="Quick warmup quiz",
        ))

        drill_time = total_minutes - warmup_time - 2
        items.append(SessionPlanItem(
            order=1,
            activity_type=ActivityType.DRILL,
            duration_minutes=drill_time,
            description="Focused practice on weak areas",
        ))

        items.append(SessionPlanItem(
            order=2,
            activity_type=ActivityType.REFLECTION,
            duration_minutes=2,
            description="Quick reflection",
        ))

        return items

    def _plan_catchup_items(
        self,
        total_minutes: int,
        pattern: UserLearningPatternModel,
    ) -> list[SessionPlanItem]:
        """Plan items for a catch-up session."""
        items: list[SessionPlanItem] = []

        review_time = int(total_minutes * 0.6)
        items.append(SessionPlanItem(
            order=0,
            activity_type=ActivityType.DRILL,
            duration_minutes=review_time,
            description="Review due items (spaced repetition)",
        ))

        learn_time = int(total_minutes * 0.3)
        if learn_time >= 5:
            items.append(SessionPlanItem(
                order=1,
                activity_type=ActivityType.CONTENT_READ,
                duration_minutes=learn_time,
                description="Light new material",
            ))

        remaining = total_minutes - review_time - learn_time
        items.append(SessionPlanItem(
            order=2,
            activity_type=ActivityType.REFLECTION,
            duration_minutes=remaining,
            description="Session wrap-up",
        ))

        return items

    def _model_to_session(self, model: SessionModel) -> Session:
        """Convert SessionModel to Session."""
        return Session(
            id=model.id,
            user_id=model.user_id,
            session_type=SessionType(model.session_type),
            status=SessionStatus(model.status),
            planned_duration_minutes=model.planned_duration_minutes,
            actual_duration_minutes=model.actual_duration_minutes,
            started_at=model.started_at,
            ended_at=model.ended_at,
        )

    def _model_to_activity(self, model: SessionActivityModel) -> SessionActivity:
        """Convert SessionActivityModel to SessionActivity."""
        return SessionActivity(
            id=model.id,
            session_id=model.session_id,
            activity_type=ActivityType(model.activity_type),
            topic_id=model.topic_id,
            content_id=model.content_id,
            started_at=model.started_at,
            ended_at=model.ended_at,
            performance_data=model.performance_data or {},
        )


# Factory function
_db_session_service: DatabaseSessionService | None = None


def get_db_session_service() -> DatabaseSessionService:
    """Get database session service singleton."""
    global _db_session_service
    if _db_session_service is None:
        _db_session_service = DatabaseSessionService()
    return _db_session_service
