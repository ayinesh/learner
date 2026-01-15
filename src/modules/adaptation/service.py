"""Adaptation Service - Learning pattern analysis and system adjustments.

This service provides:
- Learning pattern analysis (performance trends, engagement metrics)
- Automatic pace and difficulty adjustments
- Recovery plans after missed learning days
- Session planning with personalized recommendations
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Any
from uuid import UUID, uuid4
import logging

from src.modules.adaptation.interface import (
    AdaptationEvent,
    AdaptationResult,
    AdaptationTrigger,
    IAdaptationService,
    PaceRecommendation,
    RecoveryPlan,
)
from src.modules.llm.service import LLMService, get_llm_service
from src.shared.models import AdaptationType

logger = logging.getLogger(__name__)


@dataclass
class UserLearningMetrics:
    """User's learning metrics for adaptation analysis."""

    user_id: UUID
    # Performance metrics (rolling averages)
    avg_quiz_score: float = 0.7
    avg_feynman_score: float = 0.7
    quiz_score_trend: str = "stable"  # "improving", "declining", "stable"
    feynman_score_trend: str = "stable"
    # Engagement metrics
    sessions_last_7_days: int = 0
    sessions_last_30_days: int = 0
    avg_session_duration: int = 30  # minutes
    completion_rate: float = 0.8  # % of started sessions completed
    # Time patterns
    preferred_time: str = "evening"  # "morning", "afternoon", "evening", "night"
    most_productive_time: str = "evening"
    # Pace settings
    current_pace: str = "normal"  # "slow", "normal", "fast"
    difficulty_level: int = 3  # 1-5
    # Recovery state
    last_session_date: date | None = None
    consecutive_missed_days: int = 0
    # History
    recent_quiz_scores: list[float] = field(default_factory=list)
    recent_feynman_scores: list[float] = field(default_factory=list)
    identified_gaps: list[UUID] = field(default_factory=list)


@dataclass
class SessionPlan:
    """A personalized learning session plan."""

    user_id: UUID
    recommended_duration: int  # minutes
    session_type: str  # "regular", "drill", "review", "recovery"
    activities: list[dict]  # [{type, topic, duration, priority}]
    focus_areas: list[str]  # Topics to emphasize
    skip_areas: list[str]  # Topics user has mastered
    difficulty_level: int  # 1-5
    include_quiz: bool
    include_feynman: bool
    review_ratio: float  # Ratio of review vs new content (0-1)
    reasoning: str  # Why this plan was chosen
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "user_id": str(self.user_id),
            "recommended_duration": self.recommended_duration,
            "session_type": self.session_type,
            "activities": self.activities,
            "focus_areas": self.focus_areas,
            "skip_areas": self.skip_areas,
            "difficulty_level": self.difficulty_level,
            "include_quiz": self.include_quiz,
            "include_feynman": self.include_feynman,
            "review_ratio": self.review_ratio,
            "reasoning": self.reasoning,
            "created_at": self.created_at.isoformat(),
        }


class AdaptationService(IAdaptationService):
    """Service for analyzing learning patterns and adapting the system.

    Monitors user performance and engagement to automatically adjust:
    - Learning pace (faster/slower content introduction)
    - Difficulty level
    - Session recommendations
    - Recovery plans after missed days
    """

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self._llm = llm_service or get_llm_service()

        # In-memory storage (use DB in production)
        self._user_metrics: dict[UUID, UserLearningMetrics] = {}
        self._adaptation_history: dict[UUID, list[AdaptationEvent]] = {}

        # Thresholds for triggering adaptations
        self._pace_up_threshold = 0.85  # Quiz score above this suggests faster pace
        self._pace_down_threshold = 0.55  # Quiz score below suggests slower pace
        self._difficulty_up_threshold = 0.9  # Consistently high scores
        self._difficulty_down_threshold = 0.5  # Struggling
        self._recovery_trigger_days = 3  # Days missed to trigger recovery

    async def analyze_patterns(self, user_id: UUID) -> dict:
        """Analyze user's learning patterns.

        Examines session history, quiz performance, Feynman scores,
        engagement patterns, and time-of-day preferences.

        Args:
            user_id: User to analyze

        Returns:
            Pattern analysis dict with metrics and trends
        """
        metrics = await self._get_or_create_metrics(user_id)

        # Calculate trends
        quiz_trend = self._calculate_trend(metrics.recent_quiz_scores)
        feynman_trend = self._calculate_trend(metrics.recent_feynman_scores)

        # Update metrics with calculated trends
        metrics.quiz_score_trend = quiz_trend
        metrics.feynman_score_trend = feynman_trend

        return {
            "user_id": str(user_id),
            "performance": {
                "quiz_score_avg": metrics.avg_quiz_score,
                "quiz_score_trend": quiz_trend,
                "feynman_score_avg": metrics.avg_feynman_score,
                "feynman_score_trend": feynman_trend,
            },
            "engagement": {
                "sessions_last_7_days": metrics.sessions_last_7_days,
                "sessions_last_30_days": metrics.sessions_last_30_days,
                "avg_session_duration": metrics.avg_session_duration,
                "completion_rate": metrics.completion_rate,
            },
            "time_patterns": {
                "preferred_time": metrics.preferred_time,
                "most_productive_time": metrics.most_productive_time,
            },
            "current_settings": {
                "pace": metrics.current_pace,
                "difficulty_level": metrics.difficulty_level,
            },
            "gaps_count": len(metrics.identified_gaps),
            "streak_status": {
                "last_session": metrics.last_session_date.isoformat() if metrics.last_session_date else None,
                "missed_days": metrics.consecutive_missed_days,
            },
        }

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
        metrics = await self._get_or_create_metrics(user_id)
        triggers: list[AdaptationTrigger] = []

        # Check for pace adjustment need
        pace_trigger = self._check_pace_trigger(metrics)
        if pace_trigger:
            triggers.append(pace_trigger)

        # Check for difficulty adjustment need
        diff_trigger = self._check_difficulty_trigger(metrics)
        if diff_trigger:
            triggers.append(diff_trigger)

        # Check for recovery plan need
        recovery_trigger = self._check_recovery_trigger(metrics)
        if recovery_trigger:
            triggers.append(recovery_trigger)

        # Sort by severity (most urgent first)
        triggers.sort(key=lambda t: t.severity, reverse=True)

        return triggers

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
        metrics = await self._get_or_create_metrics(user_id)

        old_value: Any = None
        new_value: Any = None
        description = ""

        if trigger.type == AdaptationType.PACE_ADJUSTMENT:
            old_value = metrics.current_pace
            new_value = trigger.data.get("recommended_pace", metrics.current_pace)
            metrics.current_pace = new_value
            description = f"Adjusted learning pace from {old_value} to {new_value}"

        elif trigger.type == AdaptationType.DIFFICULTY_CHANGE:
            old_value = metrics.difficulty_level
            new_value = trigger.data.get("recommended_difficulty", metrics.difficulty_level)
            metrics.difficulty_level = new_value
            description = f"Adjusted difficulty level from {old_value} to {new_value}"

        elif trigger.type == AdaptationType.RECOVERY_PLAN:
            old_value = {"missed_days": metrics.consecutive_missed_days}
            new_value = {"recovery_initiated": True}
            description = f"Initiated recovery plan after {metrics.consecutive_missed_days} missed days"

        elif trigger.type == AdaptationType.CURRICULUM_CHANGE:
            old_value = trigger.data.get("old_curriculum")
            new_value = trigger.data.get("new_curriculum")
            description = "Curriculum adjusted based on goal changes"

        # Record the adaptation event
        event = AdaptationEvent(
            id=uuid4(),
            user_id=user_id,
            type=trigger.type,
            trigger_reason=trigger.reason,
            old_value={"value": old_value} if not isinstance(old_value, dict) else old_value,
            new_value={"value": new_value} if not isinstance(new_value, dict) else new_value,
        )

        if user_id not in self._adaptation_history:
            self._adaptation_history[user_id] = []
        self._adaptation_history[user_id].append(event)

        return AdaptationResult(
            success=True,
            type=trigger.type,
            description=description,
            old_value=old_value,
            new_value=new_value,
        )

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
        metrics = await self._get_or_create_metrics(user_id)

        # Determine review topics (prioritize identified gaps)
        review_topics = metrics.identified_gaps[:5] if metrics.identified_gaps else []

        # Calculate recovery intensity
        if days_missed <= 3:
            reduced_new_content = False
            suggested_sessions = 1
            message = "Welcome back! Let's do a quick review and continue learning."
        elif days_missed <= 7:
            reduced_new_content = True
            suggested_sessions = 2
            message = "Good to see you again! We'll focus on reviewing before adding new material."
        else:
            reduced_new_content = True
            suggested_sessions = min(days_missed // 3, 5)
            message = "Welcome back! Don't worry about the break - we'll ease back in with review sessions."

        # Generate encouraging message using LLM
        try:
            prompt = f"""Generate a brief, encouraging message (2-3 sentences) for a learner who has
returned after missing {days_missed} days of their learning routine.
Be warm and supportive, not guilt-inducing. Focus on the positive step of returning."""

            response = await self._llm.complete(
                prompt=prompt,
                system_prompt="You are a supportive learning coach. Be encouraging and positive.",
                temperature=0.7,
                max_tokens=100,
            )
            message = response.content.strip()
        except Exception:
            pass  # Use default message

        return RecoveryPlan(
            user_id=user_id,
            days_missed=days_missed,
            review_topics=review_topics,
            reduced_new_content=reduced_new_content,
            suggested_session_count=suggested_sessions,
            priority_gaps=metrics.identified_gaps[:3],
            message=message,
        )

    async def get_pace_recommendation(self, user_id: UUID) -> PaceRecommendation:
        """Get recommendation for learning pace.

        Args:
            user_id: User

        Returns:
            PaceRecommendation
        """
        metrics = await self._get_or_create_metrics(user_id)

        current_pace = metrics.current_pace
        recommended_pace = current_pace
        reason = "Your current pace seems appropriate."
        confidence = 0.5

        # Analyze recent performance
        if len(metrics.recent_quiz_scores) >= 3:
            recent_avg = sum(metrics.recent_quiz_scores[-3:]) / 3

            if recent_avg >= self._pace_up_threshold and metrics.quiz_score_trend == "improving":
                if current_pace == "slow":
                    recommended_pace = "normal"
                elif current_pace == "normal":
                    recommended_pace = "fast"
                reason = "Your recent quiz scores are consistently high, suggesting you can handle more challenging content."
                confidence = 0.8

            elif recent_avg <= self._pace_down_threshold and metrics.quiz_score_trend == "declining":
                if current_pace == "fast":
                    recommended_pace = "normal"
                elif current_pace == "normal":
                    recommended_pace = "slow"
                reason = "Slowing down will help you build stronger foundations."
                confidence = 0.75

        return PaceRecommendation(
            current_pace=current_pace,
            recommended_pace=recommended_pace,
            reason=reason,
            confidence=confidence,
        )

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
        history = self._adaptation_history.get(user_id, [])
        return list(reversed(history[-limit:]))

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
        metrics = await self._get_or_create_metrics(user_id)

        old_value: Any = None

        if adaptation_type == AdaptationType.PACE_ADJUSTMENT:
            old_value = metrics.current_pace
            metrics.current_pace = new_value
        elif adaptation_type == AdaptationType.DIFFICULTY_CHANGE:
            old_value = metrics.difficulty_level
            metrics.difficulty_level = new_value
        else:
            return AdaptationResult(
                success=False,
                type=adaptation_type,
                description=f"Cannot override {adaptation_type.value}",
                old_value=None,
                new_value=new_value,
            )

        # Record override event
        event = AdaptationEvent(
            id=uuid4(),
            user_id=user_id,
            type=adaptation_type,
            trigger_reason=f"User override: {reason}",
            old_value={"value": old_value},
            new_value={"value": new_value},
        )

        if user_id not in self._adaptation_history:
            self._adaptation_history[user_id] = []
        self._adaptation_history[user_id].append(event)

        return AdaptationResult(
            success=True,
            type=adaptation_type,
            description=f"User override applied: {old_value} -> {new_value}",
            old_value=old_value,
            new_value=new_value,
        )

    async def predict_next_adaptation(self, user_id: UUID) -> AdaptationTrigger | None:
        """Predict the next likely adaptation.

        Args:
            user_id: User

        Returns:
            Predicted trigger or None if no adaptation expected soon
        """
        metrics = await self._get_or_create_metrics(user_id)

        # Check if any trigger is close to activating
        if len(metrics.recent_quiz_scores) >= 2:
            recent_avg = sum(metrics.recent_quiz_scores[-2:]) / 2

            # Predict pace adjustment
            if recent_avg >= self._pace_up_threshold - 0.05:
                return AdaptationTrigger(
                    type=AdaptationType.PACE_ADJUSTMENT,
                    reason="Performance trending towards pace increase threshold",
                    severity=0.3,
                    data={"predicted_direction": "faster"},
                )
            elif recent_avg <= self._pace_down_threshold + 0.05:
                return AdaptationTrigger(
                    type=AdaptationType.PACE_ADJUSTMENT,
                    reason="Performance trending towards pace decrease threshold",
                    severity=0.3,
                    data={"predicted_direction": "slower"},
                )

        # Predict recovery need
        if metrics.consecutive_missed_days >= self._recovery_trigger_days - 1:
            return AdaptationTrigger(
                type=AdaptationType.RECOVERY_PLAN,
                reason=f"May need recovery plan if session is missed ({metrics.consecutive_missed_days} days already missed)",
                severity=0.4,
                data={"days_missed": metrics.consecutive_missed_days},
            )

        return None

    # --- Session Planning Methods ---

    async def plan_session(
        self,
        user_id: UUID,
        requested_duration: int | None = None,
        requested_type: str | None = None,
        topics: list[str] | None = None,
    ) -> SessionPlan:
        """Generate a personalized session plan based on user's learning state.

        This method considers:
        - User's current performance and trends
        - Knowledge gaps and areas needing review
        - Time since last session (recovery needs)
        - Preferred learning patterns
        - Requested constraints from user

        Args:
            user_id: User to plan for.
            requested_duration: Optional duration in minutes (overrides recommendation).
            requested_type: Optional session type (overrides automatic selection).
            topics: Optional topics to focus on.

        Returns:
            A personalized SessionPlan.
        """
        metrics = await self._get_or_create_metrics(user_id)

        # Determine session type
        session_type = requested_type or self._determine_session_type(metrics)

        # Determine duration
        duration = requested_duration or self._recommend_duration(metrics, session_type)

        # Determine focus areas (gaps, requested topics, or auto-select)
        focus_areas, skip_areas = await self._determine_focus_areas(
            metrics, topics or []
        )

        # Calculate review ratio based on session type and user state
        review_ratio = self._calculate_review_ratio(metrics, session_type)

        # Plan activities
        activities = await self._plan_activities(
            user_id=user_id,
            duration=duration,
            session_type=session_type,
            focus_areas=focus_areas,
            review_ratio=review_ratio,
            metrics=metrics,
        )

        # Decide on quiz/feynman inclusion
        include_quiz = session_type in ("regular", "drill", "review")
        include_feynman = (
            session_type in ("regular",) and
            duration >= 30 and
            metrics.avg_feynman_score >= 0.5  # Don't add if user struggles with Feynman
        )

        # Generate reasoning
        reasoning = self._generate_plan_reasoning(
            metrics=metrics,
            session_type=session_type,
            focus_areas=focus_areas,
            review_ratio=review_ratio,
        )

        return SessionPlan(
            user_id=user_id,
            recommended_duration=duration,
            session_type=session_type,
            activities=activities,
            focus_areas=focus_areas,
            skip_areas=skip_areas,
            difficulty_level=metrics.difficulty_level,
            include_quiz=include_quiz,
            include_feynman=include_feynman,
            review_ratio=review_ratio,
            reasoning=reasoning,
        )

    def _determine_session_type(self, metrics: UserLearningMetrics) -> str:
        """Determine the best session type based on user state."""
        # Recovery takes priority
        if metrics.consecutive_missed_days >= self._recovery_trigger_days:
            return "recovery"

        # Review if many items due or declining performance
        if len(metrics.identified_gaps) >= 3 or metrics.quiz_score_trend == "declining":
            return "review"

        # Drill if performance is high and user wants challenge
        if metrics.avg_quiz_score >= 0.85 and metrics.current_pace == "fast":
            return "drill"

        return "regular"

    def _recommend_duration(self, metrics: UserLearningMetrics, session_type: str) -> int:
        """Recommend session duration based on user patterns and session type."""
        base_duration = metrics.avg_session_duration

        # Adjust based on session type
        type_multipliers = {
            "recovery": 0.7,  # Shorter for recovery
            "drill": 0.8,    # Focused and intense
            "review": 0.9,   # Moderate
            "regular": 1.0,
        }
        multiplier = type_multipliers.get(session_type, 1.0)

        # Adjust based on recent engagement
        if metrics.completion_rate < 0.7:
            # User often doesn't finish, suggest shorter
            multiplier *= 0.8
        elif metrics.completion_rate >= 0.95:
            # User always finishes, can suggest longer
            multiplier *= 1.1

        recommended = int(base_duration * multiplier)

        # Clamp to reasonable bounds
        return max(15, min(recommended, 120))

    async def _determine_focus_areas(
        self,
        metrics: UserLearningMetrics,
        requested_topics: list[str],
    ) -> tuple[list[str], list[str]]:
        """Determine focus areas and areas to skip.

        Returns:
            Tuple of (focus_areas, skip_areas)
        """
        focus_areas = []
        skip_areas = []

        # Add requested topics to focus
        focus_areas.extend(requested_topics)

        # Add gap topics to focus (convert UUIDs to strings)
        for gap_id in metrics.identified_gaps[:5]:
            focus_areas.append(f"gap:{gap_id}")

        # Areas to skip (high mastery topics)
        # In a real implementation, this would query the content service
        if metrics.avg_quiz_score >= 0.9:
            # User is doing well, can skip easier topics
            skip_areas.append("recently_mastered")

        return focus_areas, skip_areas

    def _calculate_review_ratio(
        self,
        metrics: UserLearningMetrics,
        session_type: str,
    ) -> float:
        """Calculate the ratio of review vs new content."""
        # Session type defaults
        type_ratios = {
            "recovery": 0.8,  # Mostly review
            "review": 0.7,
            "drill": 0.3,     # Mostly new/challenging
            "regular": 0.4,
        }
        base_ratio = type_ratios.get(session_type, 0.4)

        # Adjust based on performance trend
        if metrics.quiz_score_trend == "declining":
            base_ratio += 0.15  # More review if struggling
        elif metrics.quiz_score_trend == "improving":
            base_ratio -= 0.1  # Less review if doing well

        # Adjust based on gap count
        gap_adjustment = min(len(metrics.identified_gaps) * 0.05, 0.2)
        base_ratio += gap_adjustment

        return max(0.1, min(base_ratio, 0.9))

    async def _plan_activities(
        self,
        user_id: UUID,
        duration: int,
        session_type: str,
        focus_areas: list[str],
        review_ratio: float,
        metrics: UserLearningMetrics,
    ) -> list[dict]:
        """Plan specific activities for the session."""
        activities = []
        remaining_time = duration

        # Always start with a brief warmup
        warmup_time = min(5, remaining_time // 6)
        if warmup_time > 0:
            activities.append({
                "type": "warmup",
                "topic": "review_recent",
                "duration": warmup_time,
                "priority": 1,
                "description": "Quick review of recent material",
            })
            remaining_time -= warmup_time

        # Plan review activities
        review_time = int(remaining_time * review_ratio)
        if review_time >= 10:
            activities.append({
                "type": "review",
                "topic": focus_areas[0] if focus_areas else "spaced_repetition",
                "duration": review_time,
                "priority": 2,
                "description": "Review and reinforce previous learning",
            })
            remaining_time -= review_time

        # Plan new content learning
        new_content_time = remaining_time - 10  # Reserve time for assessment
        if new_content_time > 0:
            activity_type = "drill" if session_type == "drill" else "learn"
            activities.append({
                "type": activity_type,
                "topic": focus_areas[1] if len(focus_areas) > 1 else "next_in_curriculum",
                "duration": new_content_time,
                "priority": 3,
                "description": "New content or challenging exercises",
            })
            remaining_time = 10

        # End with assessment if time permits
        if remaining_time >= 5:
            assessment_type = "quiz" if metrics.avg_feynman_score < 0.7 else "feynman"
            activities.append({
                "type": assessment_type,
                "topic": "session_content",
                "duration": remaining_time,
                "priority": 4,
                "description": f"{'Quiz' if assessment_type == 'quiz' else 'Feynman dialogue'} to test understanding",
            })

        return activities

    def _generate_plan_reasoning(
        self,
        metrics: UserLearningMetrics,
        session_type: str,
        focus_areas: list[str],
        review_ratio: float,
    ) -> str:
        """Generate human-readable reasoning for the plan."""
        reasons = []

        # Session type reasoning
        type_reasons = {
            "recovery": f"You've been away for {metrics.consecutive_missed_days} days, so we'll ease back in with a review-focused session.",
            "review": "Your recent performance suggests some topics need reinforcement.",
            "drill": "You're doing great! Time for some challenging exercises.",
            "regular": "Standard balanced session with mix of review and new content.",
        }
        reasons.append(type_reasons.get(session_type, "Personalized session based on your learning patterns."))

        # Performance-based reasoning
        if metrics.quiz_score_trend == "improving":
            reasons.append("Your scores are improving, so we're introducing more new material.")
        elif metrics.quiz_score_trend == "declining":
            reasons.append("We're adding extra review to help solidify recent concepts.")

        # Gap-based reasoning
        if metrics.identified_gaps:
            reasons.append(f"Focusing on {len(metrics.identified_gaps)} identified knowledge gaps.")

        return " ".join(reasons)

    async def get_optimal_session_time(self, user_id: UUID) -> dict[str, Any]:
        """Get the optimal time for the user's next session.

        Based on historical productivity patterns.

        Args:
            user_id: User to analyze.

        Returns:
            Dict with recommended time and reasoning.
        """
        metrics = await self._get_or_create_metrics(user_id)

        return {
            "preferred_time": metrics.preferred_time,
            "most_productive_time": metrics.most_productive_time,
            "recommendation": metrics.most_productive_time,
            "confidence": 0.7 if metrics.sessions_last_30_days >= 10 else 0.4,
            "reasoning": f"Based on your past {metrics.sessions_last_30_days} sessions, "
                        f"you tend to perform best during {metrics.most_productive_time} hours.",
        }

    # --- Helper methods for updating metrics ---

    async def record_quiz_score(self, user_id: UUID, score: float) -> None:
        """Record a quiz score for the user."""
        metrics = await self._get_or_create_metrics(user_id)
        metrics.recent_quiz_scores.append(score)
        # Keep only last 10 scores
        if len(metrics.recent_quiz_scores) > 10:
            metrics.recent_quiz_scores = metrics.recent_quiz_scores[-10:]
        # Update average
        metrics.avg_quiz_score = sum(metrics.recent_quiz_scores) / len(metrics.recent_quiz_scores)

    async def record_feynman_score(self, user_id: UUID, score: float) -> None:
        """Record a Feynman evaluation score."""
        metrics = await self._get_or_create_metrics(user_id)
        metrics.recent_feynman_scores.append(score)
        if len(metrics.recent_feynman_scores) > 10:
            metrics.recent_feynman_scores = metrics.recent_feynman_scores[-10:]
        metrics.avg_feynman_score = sum(metrics.recent_feynman_scores) / len(metrics.recent_feynman_scores)

    async def record_session(self, user_id: UUID, duration_minutes: int) -> None:
        """Record a completed session."""
        metrics = await self._get_or_create_metrics(user_id)
        metrics.sessions_last_7_days += 1
        metrics.sessions_last_30_days += 1
        metrics.last_session_date = date.today()
        metrics.consecutive_missed_days = 0
        # Update average duration
        old_avg = metrics.avg_session_duration
        total_sessions = metrics.sessions_last_30_days
        metrics.avg_session_duration = int((old_avg * (total_sessions - 1) + duration_minutes) / total_sessions)

    async def record_gap(self, user_id: UUID, gap_id: UUID) -> None:
        """Record an identified learning gap."""
        metrics = await self._get_or_create_metrics(user_id)
        if gap_id not in metrics.identified_gaps:
            metrics.identified_gaps.append(gap_id)

    async def remove_gap(self, user_id: UUID, gap_id: UUID) -> None:
        """Remove a resolved learning gap."""
        metrics = await self._get_or_create_metrics(user_id)
        if gap_id in metrics.identified_gaps:
            metrics.identified_gaps.remove(gap_id)

    # --- Private methods ---

    async def _get_or_create_metrics(self, user_id: UUID) -> UserLearningMetrics:
        """Get or create user learning metrics."""
        if user_id not in self._user_metrics:
            self._user_metrics[user_id] = UserLearningMetrics(user_id=user_id)
        return self._user_metrics[user_id]

    def _calculate_trend(self, scores: list[float]) -> str:
        """Calculate trend from recent scores."""
        if len(scores) < 3:
            return "stable"

        recent = scores[-3:]
        older = scores[-6:-3] if len(scores) >= 6 else scores[:3]

        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older)

        diff = recent_avg - older_avg
        if diff > 0.1:
            return "improving"
        elif diff < -0.1:
            return "declining"
        return "stable"

    def _check_pace_trigger(self, metrics: UserLearningMetrics) -> AdaptationTrigger | None:
        """Check if pace adjustment is needed."""
        if len(metrics.recent_quiz_scores) < 3:
            return None

        recent_avg = sum(metrics.recent_quiz_scores[-3:]) / 3

        if recent_avg >= self._pace_up_threshold and metrics.current_pace != "fast":
            new_pace = "fast" if metrics.current_pace == "normal" else "normal"
            return AdaptationTrigger(
                type=AdaptationType.PACE_ADJUSTMENT,
                reason=f"Quiz scores consistently above {self._pace_up_threshold:.0%}",
                severity=0.6,
                data={
                    "current_pace": metrics.current_pace,
                    "recommended_pace": new_pace,
                    "recent_avg": recent_avg,
                },
            )

        if recent_avg <= self._pace_down_threshold and metrics.current_pace != "slow":
            new_pace = "slow" if metrics.current_pace == "normal" else "normal"
            return AdaptationTrigger(
                type=AdaptationType.PACE_ADJUSTMENT,
                reason=f"Quiz scores consistently below {self._pace_down_threshold:.0%}",
                severity=0.7,
                data={
                    "current_pace": metrics.current_pace,
                    "recommended_pace": new_pace,
                    "recent_avg": recent_avg,
                },
            )

        return None

    def _check_difficulty_trigger(self, metrics: UserLearningMetrics) -> AdaptationTrigger | None:
        """Check if difficulty adjustment is needed."""
        if len(metrics.recent_feynman_scores) < 3:
            return None

        recent_avg = sum(metrics.recent_feynman_scores[-3:]) / 3

        if recent_avg >= self._difficulty_up_threshold and metrics.difficulty_level < 5:
            return AdaptationTrigger(
                type=AdaptationType.DIFFICULTY_CHANGE,
                reason="Consistently high Feynman scores indicate readiness for harder content",
                severity=0.5,
                data={
                    "current_difficulty": metrics.difficulty_level,
                    "recommended_difficulty": min(metrics.difficulty_level + 1, 5),
                    "recent_avg": recent_avg,
                },
            )

        if recent_avg <= self._difficulty_down_threshold and metrics.difficulty_level > 1:
            return AdaptationTrigger(
                type=AdaptationType.DIFFICULTY_CHANGE,
                reason="Lower Feynman scores suggest content may be too challenging",
                severity=0.6,
                data={
                    "current_difficulty": metrics.difficulty_level,
                    "recommended_difficulty": max(metrics.difficulty_level - 1, 1),
                    "recent_avg": recent_avg,
                },
            )

        return None

    def _check_recovery_trigger(self, metrics: UserLearningMetrics) -> AdaptationTrigger | None:
        """Check if recovery plan is needed."""
        if metrics.consecutive_missed_days >= self._recovery_trigger_days:
            return AdaptationTrigger(
                type=AdaptationType.RECOVERY_PLAN,
                reason=f"User has missed {metrics.consecutive_missed_days} consecutive days",
                severity=0.8,
                data={
                    "days_missed": metrics.consecutive_missed_days,
                    "last_session": metrics.last_session_date.isoformat() if metrics.last_session_date else None,
                },
            )

        return None


# Factory function
_adaptation_service: AdaptationService | None = None


def get_adaptation_service() -> AdaptationService:
    """Get adaptation service singleton."""
    global _adaptation_service
    if _adaptation_service is None:
        _adaptation_service = AdaptationService()
    return _adaptation_service
