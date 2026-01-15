"""Unit tests for session planning integration in adaptation service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date
from uuid import uuid4

from src.modules.adaptation.service import (
    AdaptationService,
    SessionPlan,
    UserLearningMetrics,
)


class TestSessionPlan:
    """Tests for SessionPlan dataclass."""

    def test_to_dict(self):
        """Test SessionPlan.to_dict() conversion."""
        user_id = uuid4()
        plan = SessionPlan(
            user_id=user_id,
            recommended_duration=45,
            session_type="regular",
            activities=[{"type": "warmup", "duration": 5}],
            focus_areas=["machine_learning"],
            skip_areas=["basics"],
            difficulty_level=3,
            include_quiz=True,
            include_feynman=True,
            review_ratio=0.4,
            reasoning="Standard session based on your progress.",
        )

        result = plan.to_dict()

        assert result["user_id"] == str(user_id)
        assert result["recommended_duration"] == 45
        assert result["session_type"] == "regular"
        assert result["include_quiz"] is True
        assert "created_at" in result


class TestSessionPlanning:
    """Tests for session planning methods in AdaptationService."""

    @pytest.fixture
    def service(self):
        """Create adaptation service with mock LLM."""
        mock_llm = AsyncMock()
        return AdaptationService(llm_service=mock_llm)

    @pytest.fixture
    def user_id(self):
        """Create test user ID."""
        return uuid4()

    @pytest.mark.asyncio
    async def test_plan_session_basic(self, service, user_id):
        """Test basic session planning."""
        plan = await service.plan_session(user_id)

        assert plan.user_id == user_id
        assert plan.recommended_duration > 0
        assert plan.session_type in ("regular", "drill", "review", "recovery")
        assert len(plan.activities) > 0
        assert plan.reasoning

    @pytest.mark.asyncio
    async def test_plan_session_with_requested_duration(self, service, user_id):
        """Test session planning with requested duration."""
        plan = await service.plan_session(user_id, requested_duration=60)

        assert plan.recommended_duration == 60

    @pytest.mark.asyncio
    async def test_plan_session_with_requested_type(self, service, user_id):
        """Test session planning with requested type."""
        plan = await service.plan_session(user_id, requested_type="drill")

        assert plan.session_type == "drill"

    @pytest.mark.asyncio
    async def test_plan_session_with_topics(self, service, user_id):
        """Test session planning with specific topics."""
        topics = ["transformers", "attention"]
        plan = await service.plan_session(user_id, topics=topics)

        assert "transformers" in plan.focus_areas
        assert "attention" in plan.focus_areas

    @pytest.mark.asyncio
    async def test_plan_recovery_session(self, service, user_id):
        """Test session planning triggers recovery for missed days."""
        # Set up metrics with missed days
        metrics = await service._get_or_create_metrics(user_id)
        metrics.consecutive_missed_days = 5

        plan = await service.plan_session(user_id)

        assert plan.session_type == "recovery"
        assert plan.review_ratio >= 0.7  # Recovery should be review-heavy

    @pytest.mark.asyncio
    async def test_plan_review_session_for_declining_performance(
        self, service, user_id
    ):
        """Test session planning suggests review for declining scores."""
        metrics = await service._get_or_create_metrics(user_id)
        metrics.quiz_score_trend = "declining"
        metrics.identified_gaps = [uuid4(), uuid4(), uuid4()]

        plan = await service.plan_session(user_id)

        assert plan.session_type == "review"

    @pytest.mark.asyncio
    async def test_plan_drill_session_for_high_performers(self, service, user_id):
        """Test session planning suggests drill for high performers."""
        metrics = await service._get_or_create_metrics(user_id)
        metrics.avg_quiz_score = 0.9
        metrics.current_pace = "fast"

        plan = await service.plan_session(user_id)

        assert plan.session_type == "drill"


class TestDetermineSessionType:
    """Tests for _determine_session_type method."""

    @pytest.fixture
    def service(self):
        """Create adaptation service."""
        return AdaptationService()

    def test_recovery_for_missed_days(self, service):
        """Test recovery type for missed days."""
        metrics = UserLearningMetrics(user_id=uuid4())
        metrics.consecutive_missed_days = 5

        session_type = service._determine_session_type(metrics)

        assert session_type == "recovery"

    def test_review_for_many_gaps(self, service):
        """Test review type for many gaps."""
        metrics = UserLearningMetrics(user_id=uuid4())
        metrics.identified_gaps = [uuid4() for _ in range(5)]

        session_type = service._determine_session_type(metrics)

        assert session_type == "review"

    def test_review_for_declining_trend(self, service):
        """Test review type for declining performance."""
        metrics = UserLearningMetrics(user_id=uuid4())
        metrics.quiz_score_trend = "declining"

        session_type = service._determine_session_type(metrics)

        assert session_type == "review"

    def test_drill_for_high_performance(self, service):
        """Test drill type for high performers."""
        metrics = UserLearningMetrics(user_id=uuid4())
        metrics.avg_quiz_score = 0.9
        metrics.current_pace = "fast"

        session_type = service._determine_session_type(metrics)

        assert session_type == "drill"

    def test_regular_default(self, service):
        """Test regular as default type."""
        metrics = UserLearningMetrics(user_id=uuid4())

        session_type = service._determine_session_type(metrics)

        assert session_type == "regular"


class TestRecommendDuration:
    """Tests for _recommend_duration method."""

    @pytest.fixture
    def service(self):
        """Create adaptation service."""
        return AdaptationService()

    def test_recovery_shorter(self, service):
        """Test recovery sessions are shorter."""
        metrics = UserLearningMetrics(user_id=uuid4())
        metrics.avg_session_duration = 60

        duration = service._recommend_duration(metrics, "recovery")

        assert duration < 60  # Should be shorter than average

    def test_drill_focused(self, service):
        """Test drill sessions are focused (shorter)."""
        metrics = UserLearningMetrics(user_id=uuid4())
        metrics.avg_session_duration = 60

        duration = service._recommend_duration(metrics, "drill")

        assert duration < 60

    def test_low_completion_rate_shorter(self, service):
        """Test low completion rate leads to shorter sessions."""
        metrics = UserLearningMetrics(user_id=uuid4())
        metrics.avg_session_duration = 60
        metrics.completion_rate = 0.5  # User often doesn't finish

        duration = service._recommend_duration(metrics, "regular")

        assert duration < 60

    def test_high_completion_rate_longer(self, service):
        """Test high completion rate allows longer sessions."""
        metrics = UserLearningMetrics(user_id=uuid4())
        metrics.avg_session_duration = 60
        metrics.completion_rate = 0.98

        duration = service._recommend_duration(metrics, "regular")

        assert duration >= 60

    def test_duration_clamped(self, service):
        """Test duration is clamped to reasonable bounds."""
        metrics = UserLearningMetrics(user_id=uuid4())
        metrics.avg_session_duration = 200  # Very long average

        duration = service._recommend_duration(metrics, "regular")

        assert 15 <= duration <= 120


class TestCalculateReviewRatio:
    """Tests for _calculate_review_ratio method."""

    @pytest.fixture
    def service(self):
        """Create adaptation service."""
        return AdaptationService()

    def test_recovery_high_review(self, service):
        """Test recovery has high review ratio."""
        metrics = UserLearningMetrics(user_id=uuid4())

        ratio = service._calculate_review_ratio(metrics, "recovery")

        assert ratio >= 0.7

    def test_drill_low_review(self, service):
        """Test drill has low review ratio."""
        metrics = UserLearningMetrics(user_id=uuid4())

        ratio = service._calculate_review_ratio(metrics, "drill")

        assert ratio <= 0.4

    def test_declining_trend_increases_review(self, service):
        """Test declining trend increases review."""
        metrics = UserLearningMetrics(user_id=uuid4())
        metrics.quiz_score_trend = "declining"

        ratio_declining = service._calculate_review_ratio(metrics, "regular")

        metrics.quiz_score_trend = "stable"
        ratio_stable = service._calculate_review_ratio(metrics, "regular")

        assert ratio_declining > ratio_stable

    def test_gaps_increase_review(self, service):
        """Test identified gaps increase review ratio."""
        metrics = UserLearningMetrics(user_id=uuid4())

        ratio_no_gaps = service._calculate_review_ratio(metrics, "regular")

        metrics.identified_gaps = [uuid4() for _ in range(5)]
        ratio_with_gaps = service._calculate_review_ratio(metrics, "regular")

        assert ratio_with_gaps > ratio_no_gaps


class TestPlanActivities:
    """Tests for _plan_activities method."""

    @pytest.fixture
    def service(self):
        """Create adaptation service."""
        return AdaptationService()

    @pytest.fixture
    def user_id(self):
        """Create test user ID."""
        return uuid4()

    @pytest.mark.asyncio
    async def test_activities_include_warmup(self, service, user_id):
        """Test activities start with warmup."""
        metrics = UserLearningMetrics(user_id=user_id)

        activities = await service._plan_activities(
            user_id=user_id,
            duration=30,
            session_type="regular",
            focus_areas=["topic1"],
            review_ratio=0.4,
            metrics=metrics,
        )

        assert activities[0]["type"] == "warmup"

    @pytest.mark.asyncio
    async def test_activities_include_review(self, service, user_id):
        """Test activities include review."""
        metrics = UserLearningMetrics(user_id=user_id)

        activities = await service._plan_activities(
            user_id=user_id,
            duration=60,
            session_type="regular",
            focus_areas=["topic1"],
            review_ratio=0.5,
            metrics=metrics,
        )

        types = [a["type"] for a in activities]
        assert "review" in types

    @pytest.mark.asyncio
    async def test_activities_total_duration(self, service, user_id):
        """Test activities don't exceed requested duration."""
        metrics = UserLearningMetrics(user_id=user_id)

        activities = await service._plan_activities(
            user_id=user_id,
            duration=45,
            session_type="regular",
            focus_areas=["topic1"],
            review_ratio=0.4,
            metrics=metrics,
        )

        total_duration = sum(a["duration"] for a in activities)
        assert total_duration <= 45


class TestGetOptimalSessionTime:
    """Tests for get_optimal_session_time method."""

    @pytest.fixture
    def service(self):
        """Create adaptation service."""
        return AdaptationService()

    @pytest.mark.asyncio
    async def test_returns_recommendation(self, service):
        """Test returns time recommendation."""
        user_id = uuid4()

        result = await service.get_optimal_session_time(user_id)

        assert "recommendation" in result
        assert "confidence" in result
        assert "reasoning" in result

    @pytest.mark.asyncio
    async def test_confidence_higher_with_more_sessions(self, service):
        """Test confidence increases with more session history."""
        user_id = uuid4()
        metrics = await service._get_or_create_metrics(user_id)
        metrics.sessions_last_30_days = 5

        result_few = await service.get_optimal_session_time(user_id)

        metrics.sessions_last_30_days = 20
        result_many = await service.get_optimal_session_time(user_id)

        assert result_many["confidence"] > result_few["confidence"]
