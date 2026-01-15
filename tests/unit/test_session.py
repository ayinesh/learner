"""Tests for Session module - service and planning."""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

from src.modules.session.interface import (
    Session,
    SessionActivity,
    SessionPlan,
    SessionPlanItem,
    SessionSummary,
)
from src.modules.session.service import SessionService
from src.shared.models import ActivityType, SessionStatus, SessionType


class TestSessionService:
    """Tests for SessionService."""

    @pytest.fixture
    def mock_llm(self) -> MagicMock:
        """Create mock LLM service."""
        llm = MagicMock()
        llm.complete = AsyncMock(return_value=MagicMock(content="Test response"))
        return llm

    @pytest.fixture
    def service(self, mock_llm: MagicMock) -> SessionService:
        """Create SessionService with mocked dependencies."""
        return SessionService(llm_service=mock_llm)

    @pytest.fixture
    def user_id(self) -> UUID:
        """Create a test user ID."""
        return uuid4()

    # --- Session Lifecycle Tests ---

    @pytest.mark.asyncio
    async def test_start_session(self, service: SessionService, user_id: UUID):
        """Test starting a new session."""
        session = await service.start_session(user_id, available_minutes=30)

        assert session.id is not None
        assert session.user_id == user_id
        assert session.status == SessionStatus.IN_PROGRESS
        assert session.planned_duration_minutes == 30
        assert session.session_type == SessionType.REGULAR

    @pytest.mark.asyncio
    async def test_start_session_catchup(self, service: SessionService, user_id: UUID):
        """Test starting a catchup session."""
        session = await service.start_session(
            user_id,
            available_minutes=45,
            session_type=SessionType.CATCHUP,
        )

        assert session.session_type == SessionType.CATCHUP

    @pytest.mark.asyncio
    async def test_start_session_drill(self, service: SessionService, user_id: UUID):
        """Test starting a drill session."""
        session = await service.start_session(
            user_id,
            available_minutes=20,
            session_type=SessionType.DRILL,
        )

        assert session.session_type == SessionType.DRILL

    @pytest.mark.asyncio
    async def test_start_session_already_active(self, service: SessionService, user_id: UUID):
        """Test that starting a session fails if one is already active."""
        await service.start_session(user_id)

        with pytest.raises(ValueError, match="already has an active session"):
            await service.start_session(user_id)

    @pytest.mark.asyncio
    async def test_get_current_session(self, service: SessionService, user_id: UUID):
        """Test getting current active session."""
        # No session initially
        assert await service.get_current_session(user_id) is None

        # Start session
        session = await service.start_session(user_id)

        # Should return the session
        current = await service.get_current_session(user_id)
        assert current is not None
        assert current.id == session.id

    @pytest.mark.asyncio
    async def test_end_session(self, service: SessionService, user_id: UUID):
        """Test ending a session."""
        session = await service.start_session(user_id, available_minutes=30)

        summary = await service.end_session(session.id)

        assert summary.session_id == session.id
        assert summary.activities_completed >= 0

        # Session should no longer be active
        current = await service.get_current_session(user_id)
        assert current is None

    @pytest.mark.asyncio
    async def test_end_session_not_found(self, service: SessionService):
        """Test ending non-existent session."""
        fake_id = uuid4()
        with pytest.raises(ValueError, match="Session not found"):
            await service.end_session(fake_id)

    @pytest.mark.asyncio
    async def test_abandon_session(self, service: SessionService, user_id: UUID):
        """Test abandoning a session."""
        session = await service.start_session(user_id)

        await service.abandon_session(session.id, reason="Testing")

        # Session should no longer be active
        current = await service.get_current_session(user_id)
        assert current is None

        # Check session status in storage
        stored = service._sessions.get(session.id)
        assert stored.session.status == SessionStatus.ABANDONED
        assert stored.abandon_reason == "Testing"

    # --- Session Plan Tests ---

    @pytest.mark.asyncio
    async def test_get_session_plan(self, service: SessionService, user_id: UUID):
        """Test getting session plan."""
        session = await service.start_session(user_id, available_minutes=30)

        plan = await service.get_session_plan(session.id)

        assert plan.session_id == session.id
        assert plan.total_duration_minutes == 30
        assert len(plan.items) > 0

    @pytest.mark.asyncio
    async def test_session_plan_regular(self, service: SessionService, user_id: UUID):
        """Test plan for regular session."""
        session = await service.start_session(
            user_id,
            available_minutes=30,
            session_type=SessionType.REGULAR,
        )

        plan = await service.get_session_plan(session.id)

        # Regular session should have consumption and production
        activity_types = [item.activity_type for item in plan.items]
        assert ActivityType.CONTENT_READ in activity_types

    @pytest.mark.asyncio
    async def test_session_plan_drill(self, service: SessionService, user_id: UUID):
        """Test plan for drill session."""
        session = await service.start_session(
            user_id,
            available_minutes=30,
            session_type=SessionType.DRILL,
        )

        plan = await service.get_session_plan(session.id)

        # Drill session should focus on practice
        activity_types = [item.activity_type for item in plan.items]
        assert ActivityType.DRILL in activity_types

    @pytest.mark.asyncio
    async def test_session_plan_cached(self, service: SessionService, user_id: UUID):
        """Test that plan is cached."""
        session = await service.start_session(user_id)

        plan1 = await service.get_session_plan(session.id)
        plan2 = await service.get_session_plan(session.id)

        assert plan1 is plan2  # Same object

    # --- Activity Recording Tests ---

    @pytest.mark.asyncio
    async def test_record_activity(self, service: SessionService, user_id: UUID):
        """Test recording an activity."""
        session = await service.start_session(user_id)

        activity = await service.record_activity(
            session_id=session.id,
            activity_type=ActivityType.QUIZ,
            performance_data={"score": 0.8},
        )

        assert activity.id is not None
        assert activity.session_id == session.id
        assert activity.activity_type == ActivityType.QUIZ
        assert activity.performance_data["score"] == 0.8

    @pytest.mark.asyncio
    async def test_record_activity_session_not_found(self, service: SessionService):
        """Test recording activity for non-existent session."""
        fake_id = uuid4()
        with pytest.raises(ValueError, match="Session not found"):
            await service.record_activity(
                session_id=fake_id,
                activity_type=ActivityType.QUIZ,
            )

    @pytest.mark.asyncio
    async def test_complete_activity(self, service: SessionService, user_id: UUID):
        """Test completing an activity."""
        session = await service.start_session(user_id)

        activity = await service.record_activity(
            session_id=session.id,
            activity_type=ActivityType.FEYNMAN_DIALOGUE,
        )

        completed = await service.complete_activity(
            activity_id=activity.id,
            performance_data={"score": 0.9, "gaps": ["concept A"]},
        )

        assert completed.ended_at is not None
        assert completed.performance_data["score"] == 0.9
        assert "concept A" in completed.performance_data["gaps"]

    @pytest.mark.asyncio
    async def test_complete_activity_not_found(self, service: SessionService):
        """Test completing non-existent activity."""
        fake_id = uuid4()
        with pytest.raises(ValueError, match="Activity not found"):
            await service.complete_activity(fake_id)

    @pytest.mark.asyncio
    async def test_get_session_activities(self, service: SessionService, user_id: UUID):
        """Test getting all activities for a session."""
        session = await service.start_session(user_id)

        # Record multiple activities
        await service.record_activity(session.id, ActivityType.CONTENT_READ)
        await service.record_activity(session.id, ActivityType.QUIZ)

        activities = await service.get_session_activities(session.id)

        assert len(activities) == 2

    # --- Session History Tests ---

    @pytest.mark.asyncio
    async def test_get_session_history_empty(self, service: SessionService, user_id: UUID):
        """Test getting history when none exists."""
        history = await service.get_session_history(user_id)
        assert history == []

    @pytest.mark.asyncio
    async def test_get_session_history(self, service: SessionService, user_id: UUID):
        """Test getting session history."""
        # Create and complete sessions
        session1 = await service.start_session(user_id)
        await service.end_session(session1.id)

        session2 = await service.start_session(user_id)
        await service.end_session(session2.id)

        history = await service.get_session_history(user_id, limit=10)

        assert len(history) == 2
        # Newest first
        assert history[0].id == session2.id

    @pytest.mark.asyncio
    async def test_get_session_history_excludes_abandoned(
        self,
        service: SessionService,
        user_id: UUID,
    ):
        """Test that abandoned sessions are excluded by default."""
        session1 = await service.start_session(user_id)
        await service.end_session(session1.id)

        session2 = await service.start_session(user_id)
        await service.abandon_session(session2.id)

        history = await service.get_session_history(user_id, include_abandoned=False)
        assert len(history) == 1
        assert history[0].id == session1.id

    @pytest.mark.asyncio
    async def test_get_session_history_includes_abandoned(
        self,
        service: SessionService,
        user_id: UUID,
    ):
        """Test including abandoned sessions in history."""
        session1 = await service.start_session(user_id)
        await service.end_session(session1.id)

        session2 = await service.start_session(user_id)
        await service.abandon_session(session2.id)

        history = await service.get_session_history(user_id, include_abandoned=True)
        assert len(history) == 2

    # --- Streak Tests ---

    @pytest.mark.asyncio
    async def test_get_streak_info_new_user(self, service: SessionService, user_id: UUID):
        """Test streak info for new user."""
        streak = await service.get_streak_info(user_id)

        assert streak["current_streak"] == 0
        assert streak["longest_streak"] == 0
        assert streak["last_session_date"] is None
        assert streak["streak_at_risk"] is False

    @pytest.mark.asyncio
    async def test_streak_updated_on_session_complete(
        self,
        service: SessionService,
        user_id: UUID,
    ):
        """Test that streak is updated when session completes."""
        session = await service.start_session(user_id)
        summary = await service.end_session(session.id)

        assert summary.streak_updated is True

        streak = await service.get_streak_info(user_id)
        assert streak["current_streak"] == 1
        assert streak["last_session_date"] == date.today()

    @pytest.mark.asyncio
    async def test_streak_at_risk(self, service: SessionService, user_id: UUID):
        """Test streak at risk detection."""
        # Complete a session
        session = await service.start_session(user_id)
        await service.end_session(session.id)

        # Manually set last session to yesterday to simulate streak at risk
        profile = service._user_profiles[user_id]
        profile.last_session_date = date.today() - timedelta(days=1)

        streak = await service.get_streak_info(user_id)
        assert streak["streak_at_risk"] is True


class TestSessionSummary:
    """Tests for session summary generation."""

    @pytest.fixture
    def mock_llm(self) -> MagicMock:
        """Create mock LLM service."""
        llm = MagicMock()
        llm.complete = AsyncMock(return_value=MagicMock(content="Preview text"))
        return llm

    @pytest.fixture
    def service(self, mock_llm: MagicMock) -> SessionService:
        """Create SessionService with mocked dependencies."""
        return SessionService(llm_service=mock_llm)

    @pytest.mark.asyncio
    async def test_summary_includes_activities(self, service: SessionService):
        """Test that summary includes activity count."""
        user_id = uuid4()
        session = await service.start_session(user_id)

        # Record and complete some activities
        activity = await service.record_activity(session.id, ActivityType.QUIZ)
        await service.complete_activity(activity.id)

        summary = await service.end_session(session.id)

        assert summary.activities_completed == 1

    @pytest.mark.asyncio
    async def test_summary_includes_quiz_score(self, service: SessionService):
        """Test that summary includes quiz score."""
        user_id = uuid4()
        session = await service.start_session(user_id)

        activity = await service.record_activity(session.id, ActivityType.QUIZ)
        await service.complete_activity(activity.id, {"score": 0.85})

        summary = await service.end_session(session.id)

        assert summary.quiz_score == 0.85

    @pytest.mark.asyncio
    async def test_summary_includes_feynman_score(self, service: SessionService):
        """Test that summary includes Feynman score."""
        user_id = uuid4()
        session = await service.start_session(user_id)

        activity = await service.record_activity(session.id, ActivityType.FEYNMAN_DIALOGUE)
        await service.complete_activity(activity.id, {"score": 0.9})

        summary = await service.end_session(session.id)

        assert summary.feynman_score == 0.9

    @pytest.mark.asyncio
    async def test_summary_includes_gaps(self, service: SessionService):
        """Test that summary includes identified gaps."""
        user_id = uuid4()
        session = await service.start_session(user_id)

        activity = await service.record_activity(session.id, ActivityType.QUIZ)
        await service.complete_activity(activity.id, {"gaps": ["concept X", "concept Y"]})

        summary = await service.end_session(session.id)

        assert "concept X" in summary.new_gaps_identified
        assert "concept Y" in summary.new_gaps_identified


class TestSessionRestorationService:
    """Tests for SessionRestorationService - session state restoration on login."""

    def test_welcome_context_defaults(self):
        """Test that WelcomeContext has sensible defaults."""
        from src.modules.session.restoration_service import WelcomeContext

        ctx = WelcomeContext()

        assert ctx.has_active_session is False
        assert ctx.active_session_id is None
        assert ctx.primary_goal is None
        assert ctx.current_focus is None
        assert ctx.learning_progress == 0.0
        assert ctx.current_streak == 0
        assert ctx.needs_recovery is False

    def test_welcome_context_with_values(self):
        """Test WelcomeContext with populated values."""
        from src.modules.session.restoration_service import WelcomeContext

        ctx = WelcomeContext(
            has_active_session=True,
            primary_goal="Learn ML",
            current_focus="Linear algebra",
            learning_progress=0.45,
            current_streak=5,
            streak_at_risk=True,
            days_since_last_session=1,
            needs_recovery=False,
        )

        assert ctx.has_active_session is True
        assert ctx.primary_goal == "Learn ML"
        assert ctx.learning_progress == 0.45
        assert ctx.current_streak == 5
        assert ctx.streak_at_risk is True

    def test_format_welcome_message_new_user(self):
        """Test welcome message for new user with no history."""
        from src.modules.session.restoration_service import (
            SessionRestorationService,
            WelcomeContext,
        )

        service = SessionRestorationService()
        ctx = WelcomeContext()  # Empty context for new user

        message = service.format_welcome_message(ctx, "test@example.com")

        assert "test@example.com" in message
        assert "Welcome back" in message

    def test_format_welcome_message_returning_user(self):
        """Test welcome message for user with learning history."""
        from src.modules.session.restoration_service import (
            SessionRestorationService,
            WelcomeContext,
        )

        service = SessionRestorationService()
        ctx = WelcomeContext(
            primary_goal="Machine Learning",
            current_focus="Neural networks",
            learning_progress=0.35,
            current_streak=7,
        )

        message = service.format_welcome_message(ctx, "user@example.com")

        assert "user@example.com" in message
        assert "Machine Learning" in message
        assert "35%" in message
        assert "7 days" in message

    def test_format_welcome_message_recovery_needed(self):
        """Test welcome message when recovery is needed."""
        from src.modules.session.restoration_service import (
            SessionRestorationService,
            WelcomeContext,
        )

        service = SessionRestorationService()
        ctx = WelcomeContext(
            primary_goal="Python",
            days_since_last_session=5,
            needs_recovery=True,
        )

        message = service.format_welcome_message(ctx, "user@example.com")

        assert "5 days" in message
        assert "recovery" in message.lower()

    def test_format_welcome_message_active_session(self):
        """Test welcome message when there's an active session."""
        from src.modules.session.restoration_service import (
            SessionRestorationService,
            WelcomeContext,
        )

        service = SessionRestorationService()
        ctx = WelcomeContext(
            has_active_session=True,
            active_session_id=uuid4(),
            primary_goal="Data Science",
        )

        message = service.format_welcome_message(ctx, "user@example.com")

        assert "active session" in message.lower()
        assert "learner start" in message.lower()
