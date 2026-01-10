"""Adaptation Module - Learning pattern analysis and system adjustments."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from src.shared.models import AdaptationType


@dataclass
class AdaptationTrigger:
    """A detected condition that triggers adaptation."""

    type: AdaptationType
    reason: str
    severity: float  # 0-1, how urgent is this adaptation
    data: dict = field(default_factory=dict)


@dataclass
class AdaptationResult:
    """Result of applying an adaptation."""

    success: bool
    type: AdaptationType
    description: str
    old_value: Any
    new_value: Any
    applied_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RecoveryPlan:
    """Plan for recovering from missed days."""

    user_id: UUID
    days_missed: int
    review_topics: list[UUID]  # Topics to review
    reduced_new_content: bool  # Should we reduce new content?
    suggested_session_count: int  # Recommended sessions to catch up
    priority_gaps: list[UUID]  # Gaps to address first
    message: str  # Encouraging message for user


@dataclass
class PaceRecommendation:
    """Recommendation for learning pace adjustment."""

    current_pace: str  # "slow", "normal", "fast"
    recommended_pace: str
    reason: str
    confidence: float  # 0-1


@dataclass
class AdaptationEvent:
    """Record of a system adaptation."""

    id: UUID
    user_id: UUID
    type: AdaptationType
    trigger_reason: str
    old_value: dict
    new_value: dict
    created_at: datetime = field(default_factory=datetime.utcnow)


class IAdaptationService(Protocol):
    """Interface for adaptation service.

    Analyzes learning patterns and generates system adjustments.
    """

    async def analyze_patterns(self, user_id: UUID) -> dict:
        """Analyze user's learning patterns.

        Examines session history, quiz performance, Feynman scores,
        engagement patterns, and time-of-day preferences.

        Args:
            user_id: User to analyze

        Returns:
            Pattern analysis dict with metrics and trends
        """
        ...

    async def check_triggers(self, user_id: UUID) -> list[AdaptationTrigger]:
        """Check for adaptation triggers.

        Triggers include:
        - PACE_ADJUSTMENT: Quiz accuracy consistently high/low
        - DIFFICULTY_CHANGE: Feynman scores plateauing
        - RECOVERY_PLAN: Multiple missed days
        - CURRICULUM_CHANGE: Goal modification or ecosystem change

        Args:
            user_id: User to check

        Returns:
            List of triggered adaptations, sorted by severity
        """
        ...

    async def apply_adaptation(
        self,
        user_id: UUID,
        trigger: AdaptationTrigger,
    ) -> AdaptationResult:
        """Apply an adaptation based on trigger.

        Args:
            user_id: User to adapt for
            trigger: Trigger to respond to

        Returns:
            AdaptationResult with changes made
        """
        ...

    async def generate_recovery_plan(
        self,
        user_id: UUID,
        days_missed: int,
    ) -> RecoveryPlan:
        """Generate a recovery plan after missed days.

        Args:
            user_id: User
            days_missed: Number of days missed

        Returns:
            RecoveryPlan with recommendations
        """
        ...

    async def get_pace_recommendation(self, user_id: UUID) -> PaceRecommendation:
        """Get recommendation for learning pace.

        Args:
            user_id: User

        Returns:
            PaceRecommendation
        """
        ...

    async def get_adaptation_history(
        self,
        user_id: UUID,
        limit: int = 10,
    ) -> list[AdaptationEvent]:
        """Get history of adaptations for user.

        Args:
            user_id: User
            limit: Maximum events

        Returns:
            List of AdaptationEvents, newest first
        """
        ...

    async def override_adaptation(
        self,
        user_id: UUID,
        adaptation_type: AdaptationType,
        new_value: Any,
        reason: str,
    ) -> AdaptationResult:
        """Manually override an adaptation setting.

        Allows user to override system's automatic adjustments.

        Args:
            user_id: User
            adaptation_type: Type of adaptation to override
            new_value: Value to set
            reason: User's reason for override

        Returns:
            AdaptationResult
        """
        ...

    async def predict_next_adaptation(self, user_id: UUID) -> AdaptationTrigger | None:
        """Predict the next likely adaptation.

        Args:
            user_id: User

        Returns:
            Predicted trigger or None if no adaptation expected soon
        """
        ...
