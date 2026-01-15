"""Tests for Adaptation module - pattern analysis and adaptations."""

import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

from src.modules.adaptation.interface import (
    AdaptationEvent,
    AdaptationResult,
    AdaptationTrigger,
    PaceRecommendation,
    RecoveryPlan,
)
from src.modules.adaptation.service import AdaptationService
from src.shared.models import AdaptationType


class TestAdaptationService:
    """Tests for AdaptationService."""

    @pytest.fixture
    def mock_llm(self) -> MagicMock:
        """Create mock LLM service."""
        llm = MagicMock()
        llm.complete = AsyncMock(return_value=MagicMock(
            content="Welcome back! Let's continue learning together."
        ))
        return llm

    @pytest.fixture
    def service(self, mock_llm: MagicMock) -> AdaptationService:
        """Create AdaptationService with mocked dependencies."""
        return AdaptationService(llm_service=mock_llm)

    @pytest.fixture
    def user_id(self) -> UUID:
        """Create a test user ID."""
        return uuid4()

    # --- Pattern Analysis Tests ---

    @pytest.mark.asyncio
    async def test_analyze_patterns_new_user(
        self,
        service: AdaptationService,
        user_id: UUID,
    ):
        """Test pattern analysis for new user."""
        patterns = await service.analyze_patterns(user_id)

        assert "user_id" in patterns
        assert "performance" in patterns
        assert "engagement" in patterns
        assert "current_settings" in patterns

    @pytest.mark.asyncio
    async def test_analyze_patterns_with_history(
        self,
        service: AdaptationService,
        user_id: UUID,
    ):
        """Test pattern analysis with quiz history."""
        # Record some quiz scores
        await service.record_quiz_score(user_id, 0.8)
        await service.record_quiz_score(user_id, 0.85)
        await service.record_quiz_score(user_id, 0.9)

        patterns = await service.analyze_patterns(user_id)

        assert patterns["performance"]["quiz_score_avg"] > 0.8

    @pytest.mark.asyncio
    async def test_trend_calculation_improving(
        self,
        service: AdaptationService,
        user_id: UUID,
    ):
        """Test trend calculation for improving scores."""
        # Record improving scores
        scores = [0.5, 0.55, 0.6, 0.7, 0.8, 0.9]
        for score in scores:
            await service.record_quiz_score(user_id, score)

        patterns = await service.analyze_patterns(user_id)
        assert patterns["performance"]["quiz_score_trend"] == "improving"

    @pytest.mark.asyncio
    async def test_trend_calculation_declining(
        self,
        service: AdaptationService,
        user_id: UUID,
    ):
        """Test trend calculation for declining scores."""
        # Record declining scores
        scores = [0.9, 0.85, 0.8, 0.6, 0.5, 0.4]
        for score in scores:
            await service.record_quiz_score(user_id, score)

        patterns = await service.analyze_patterns(user_id)
        assert patterns["performance"]["quiz_score_trend"] == "declining"

    # --- Trigger Detection Tests ---

    @pytest.mark.asyncio
    async def test_check_triggers_no_data(
        self,
        service: AdaptationService,
        user_id: UUID,
    ):
        """Test trigger checking with no data."""
        triggers = await service.check_triggers(user_id)
        assert triggers == []

    @pytest.mark.asyncio
    async def test_pace_up_trigger(
        self,
        service: AdaptationService,
        user_id: UUID,
    ):
        """Test pace increase trigger detection."""
        # Record high quiz scores
        for _ in range(5):
            await service.record_quiz_score(user_id, 0.9)

        triggers = await service.check_triggers(user_id)

        pace_triggers = [t for t in triggers if t.type == AdaptationType.PACE_ADJUSTMENT]
        assert len(pace_triggers) > 0
        assert pace_triggers[0].data["recommended_pace"] in ["normal", "fast"]

    @pytest.mark.asyncio
    async def test_pace_down_trigger(
        self,
        service: AdaptationService,
        user_id: UUID,
    ):
        """Test pace decrease trigger detection."""
        # Record low quiz scores
        for _ in range(5):
            await service.record_quiz_score(user_id, 0.4)

        triggers = await service.check_triggers(user_id)

        pace_triggers = [t for t in triggers if t.type == AdaptationType.PACE_ADJUSTMENT]
        assert len(pace_triggers) > 0
        assert pace_triggers[0].data["recommended_pace"] in ["slow", "normal"]

    @pytest.mark.asyncio
    async def test_difficulty_up_trigger(
        self,
        service: AdaptationService,
        user_id: UUID,
    ):
        """Test difficulty increase trigger detection."""
        # Record high Feynman scores
        for _ in range(5):
            await service.record_feynman_score(user_id, 0.95)

        triggers = await service.check_triggers(user_id)

        diff_triggers = [t for t in triggers if t.type == AdaptationType.DIFFICULTY_CHANGE]
        assert len(diff_triggers) > 0

    @pytest.mark.asyncio
    async def test_recovery_trigger(
        self,
        service: AdaptationService,
        user_id: UUID,
    ):
        """Test recovery plan trigger detection."""
        # Set up metrics with missed days
        metrics = await service._get_or_create_metrics(user_id)
        metrics.consecutive_missed_days = 5
        metrics.last_session_date = date.today() - timedelta(days=5)

        triggers = await service.check_triggers(user_id)

        recovery_triggers = [t for t in triggers if t.type == AdaptationType.RECOVERY_PLAN]
        assert len(recovery_triggers) > 0

    @pytest.mark.asyncio
    async def test_triggers_sorted_by_severity(
        self,
        service: AdaptationService,
        user_id: UUID,
    ):
        """Test that triggers are sorted by severity."""
        # Create multiple triggers
        metrics = await service._get_or_create_metrics(user_id)
        metrics.consecutive_missed_days = 5

        for _ in range(5):
            await service.record_quiz_score(user_id, 0.4)

        triggers = await service.check_triggers(user_id)

        if len(triggers) >= 2:
            for i in range(len(triggers) - 1):
                assert triggers[i].severity >= triggers[i + 1].severity

    # --- Adaptation Application Tests ---

    @pytest.mark.asyncio
    async def test_apply_pace_adaptation(
        self,
        service: AdaptationService,
        user_id: UUID,
    ):
        """Test applying pace adaptation."""
        trigger = AdaptationTrigger(
            type=AdaptationType.PACE_ADJUSTMENT,
            reason="Test reason",
            severity=0.7,
            data={"recommended_pace": "fast"},
        )

        result = await service.apply_adaptation(user_id, trigger)

        assert result.success is True
        assert result.type == AdaptationType.PACE_ADJUSTMENT
        assert result.new_value == "fast"

        # Verify metrics updated
        metrics = await service._get_or_create_metrics(user_id)
        assert metrics.current_pace == "fast"

    @pytest.mark.asyncio
    async def test_apply_difficulty_adaptation(
        self,
        service: AdaptationService,
        user_id: UUID,
    ):
        """Test applying difficulty adaptation."""
        trigger = AdaptationTrigger(
            type=AdaptationType.DIFFICULTY_CHANGE,
            reason="Test reason",
            severity=0.6,
            data={"recommended_difficulty": 4},
        )

        result = await service.apply_adaptation(user_id, trigger)

        assert result.success is True
        assert result.new_value == 4

        metrics = await service._get_or_create_metrics(user_id)
        assert metrics.difficulty_level == 4

    @pytest.mark.asyncio
    async def test_adaptation_recorded_in_history(
        self,
        service: AdaptationService,
        user_id: UUID,
    ):
        """Test that adaptations are recorded in history."""
        trigger = AdaptationTrigger(
            type=AdaptationType.PACE_ADJUSTMENT,
            reason="Test",
            severity=0.5,
            data={"recommended_pace": "slow"},
        )

        await service.apply_adaptation(user_id, trigger)

        history = await service.get_adaptation_history(user_id)
        assert len(history) == 1
        assert history[0].type == AdaptationType.PACE_ADJUSTMENT

    # --- Recovery Plan Tests ---

    @pytest.mark.asyncio
    async def test_generate_recovery_plan_short_absence(
        self,
        service: AdaptationService,
        user_id: UUID,
    ):
        """Test recovery plan for short absence."""
        plan = await service.generate_recovery_plan(user_id, days_missed=2)

        assert plan.user_id == user_id
        assert plan.days_missed == 2
        assert plan.reduced_new_content is False
        assert plan.suggested_session_count == 1

    @pytest.mark.asyncio
    async def test_generate_recovery_plan_medium_absence(
        self,
        service: AdaptationService,
        user_id: UUID,
    ):
        """Test recovery plan for medium absence."""
        plan = await service.generate_recovery_plan(user_id, days_missed=5)

        assert plan.reduced_new_content is True
        assert plan.suggested_session_count == 2

    @pytest.mark.asyncio
    async def test_generate_recovery_plan_long_absence(
        self,
        service: AdaptationService,
        user_id: UUID,
    ):
        """Test recovery plan for long absence."""
        plan = await service.generate_recovery_plan(user_id, days_missed=14)

        assert plan.reduced_new_content is True
        assert plan.suggested_session_count >= 3

    @pytest.mark.asyncio
    async def test_recovery_plan_includes_gaps(
        self,
        service: AdaptationService,
        user_id: UUID,
    ):
        """Test that recovery plan includes identified gaps."""
        # Add some gaps
        gap_id = uuid4()
        await service.record_gap(user_id, gap_id)

        plan = await service.generate_recovery_plan(user_id, days_missed=5)

        assert gap_id in plan.priority_gaps

    # --- Pace Recommendation Tests ---

    @pytest.mark.asyncio
    async def test_get_pace_recommendation_no_data(
        self,
        service: AdaptationService,
        user_id: UUID,
    ):
        """Test pace recommendation with no data."""
        rec = await service.get_pace_recommendation(user_id)

        assert rec.current_pace == "normal"
        assert rec.recommended_pace == "normal"
        assert rec.confidence == 0.5

    @pytest.mark.asyncio
    async def test_get_pace_recommendation_increase(
        self,
        service: AdaptationService,
        user_id: UUID,
    ):
        """Test pace recommendation for increase."""
        # Record high scores with improving trend
        for score in [0.8, 0.85, 0.9]:
            await service.record_quiz_score(user_id, score)

        rec = await service.get_pace_recommendation(user_id)

        # Should recommend faster pace
        assert rec.recommended_pace in ["normal", "fast"]

    # --- Override Tests ---

    @pytest.mark.asyncio
    async def test_override_pace(
        self,
        service: AdaptationService,
        user_id: UUID,
    ):
        """Test manual pace override."""
        result = await service.override_adaptation(
            user_id=user_id,
            adaptation_type=AdaptationType.PACE_ADJUSTMENT,
            new_value="slow",
            reason="User preference",
        )

        assert result.success is True
        assert result.new_value == "slow"

        # Verify recorded in history
        history = await service.get_adaptation_history(user_id)
        assert len(history) == 1
        assert "User override" in history[0].trigger_reason

    @pytest.mark.asyncio
    async def test_override_difficulty(
        self,
        service: AdaptationService,
        user_id: UUID,
    ):
        """Test manual difficulty override."""
        result = await service.override_adaptation(
            user_id=user_id,
            adaptation_type=AdaptationType.DIFFICULTY_CHANGE,
            new_value=2,
            reason="Want easier content",
        )

        assert result.success is True
        assert result.new_value == 2

    @pytest.mark.asyncio
    async def test_override_unsupported_type(
        self,
        service: AdaptationService,
        user_id: UUID,
    ):
        """Test override for unsupported adaptation type."""
        result = await service.override_adaptation(
            user_id=user_id,
            adaptation_type=AdaptationType.RECOVERY_PLAN,
            new_value="test",
            reason="Test",
        )

        assert result.success is False

    # --- Prediction Tests ---

    @pytest.mark.asyncio
    async def test_predict_next_adaptation_none(
        self,
        service: AdaptationService,
        user_id: UUID,
    ):
        """Test prediction when no adaptation is likely."""
        prediction = await service.predict_next_adaptation(user_id)
        # New user with no data - may or may not have prediction
        # Just verify it doesn't error

    @pytest.mark.asyncio
    async def test_predict_pace_increase(
        self,
        service: AdaptationService,
        user_id: UUID,
    ):
        """Test prediction of pace increase."""
        # Record scores close to threshold
        await service.record_quiz_score(user_id, 0.82)
        await service.record_quiz_score(user_id, 0.83)

        prediction = await service.predict_next_adaptation(user_id)

        if prediction:
            assert prediction.type == AdaptationType.PACE_ADJUSTMENT

    @pytest.mark.asyncio
    async def test_predict_recovery_need(
        self,
        service: AdaptationService,
        user_id: UUID,
    ):
        """Test prediction of recovery need."""
        # Set up metrics close to recovery threshold
        metrics = await service._get_or_create_metrics(user_id)
        metrics.consecutive_missed_days = 2  # One day from threshold

        prediction = await service.predict_next_adaptation(user_id)

        if prediction:
            assert prediction.type == AdaptationType.RECOVERY_PLAN

    # --- Helper Method Tests ---

    @pytest.mark.asyncio
    async def test_record_quiz_score(
        self,
        service: AdaptationService,
        user_id: UUID,
    ):
        """Test recording quiz scores."""
        await service.record_quiz_score(user_id, 0.8)

        metrics = await service._get_or_create_metrics(user_id)
        assert 0.8 in metrics.recent_quiz_scores
        assert metrics.avg_quiz_score == 0.8

    @pytest.mark.asyncio
    async def test_record_feynman_score(
        self,
        service: AdaptationService,
        user_id: UUID,
    ):
        """Test recording Feynman scores."""
        await service.record_feynman_score(user_id, 0.75)

        metrics = await service._get_or_create_metrics(user_id)
        assert 0.75 in metrics.recent_feynman_scores

    @pytest.mark.asyncio
    async def test_record_session(
        self,
        service: AdaptationService,
        user_id: UUID,
    ):
        """Test recording session completion."""
        await service.record_session(user_id, 30)

        metrics = await service._get_or_create_metrics(user_id)
        assert metrics.sessions_last_7_days == 1
        assert metrics.last_session_date == date.today()
        assert metrics.consecutive_missed_days == 0

    @pytest.mark.asyncio
    async def test_record_gap(
        self,
        service: AdaptationService,
        user_id: UUID,
    ):
        """Test recording learning gap."""
        gap_id = uuid4()
        await service.record_gap(user_id, gap_id)

        metrics = await service._get_or_create_metrics(user_id)
        assert gap_id in metrics.identified_gaps

    @pytest.mark.asyncio
    async def test_remove_gap(
        self,
        service: AdaptationService,
        user_id: UUID,
    ):
        """Test removing resolved gap."""
        gap_id = uuid4()
        await service.record_gap(user_id, gap_id)
        await service.remove_gap(user_id, gap_id)

        metrics = await service._get_or_create_metrics(user_id)
        assert gap_id not in metrics.identified_gaps

    @pytest.mark.asyncio
    async def test_score_history_limited(
        self,
        service: AdaptationService,
        user_id: UUID,
    ):
        """Test that score history is limited to 10 entries."""
        # Record 15 scores
        for i in range(15):
            await service.record_quiz_score(user_id, 0.7 + i * 0.01)

        metrics = await service._get_or_create_metrics(user_id)
        assert len(metrics.recent_quiz_scores) == 10
