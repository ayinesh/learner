"""Adaptation Service - Database-backed implementation."""

from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.adaptation.interface import (
    AdaptationEvent,
    AdaptationResult,
    AdaptationTrigger,
    IAdaptationService,
    PaceRecommendation,
    RecoveryPlan,
)
from src.modules.adaptation.models import AdaptationEventModel
from src.modules.assessment.models import QuizAttemptModel, FeynmanResultModel, FeynmanSessionModel
from src.modules.content.models import UserTopicProgressModel
from src.modules.session.models import SessionModel, UserLearningPatternModel
from src.shared.database import get_db_session
from src.shared.models import AdaptationType


class DatabaseAdaptationService(IAdaptationService):
    """Database-backed adaptation service.

    Analyzes learning patterns and generates system adjustments.
    """

    async def analyze_patterns(self, user_id: UUID) -> dict:
        """Analyze user's learning patterns."""
        async with get_db_session() as db:
            pattern = await self._get_or_create_pattern(db, user_id)

            # Get recent sessions
            sessions_result = await db.execute(
                select(SessionModel).where(
                    and_(
                        SessionModel.user_id == user_id,
                        SessionModel.status == "completed",
                    )
                ).order_by(desc(SessionModel.started_at)).limit(30)
            )
            sessions = sessions_result.scalars().all()

            # Get recent quiz attempts
            quiz_result = await db.execute(
                select(QuizAttemptModel).where(
                    QuizAttemptModel.user_id == user_id
                ).order_by(desc(QuizAttemptModel.attempted_at)).limit(20)
            )
            quiz_attempts = quiz_result.scalars().all()

            # Get recent Feynman results
            feynman_result = await db.execute(
                select(FeynmanResultModel, FeynmanSessionModel).join(
                    FeynmanSessionModel,
                    FeynmanResultModel.feynman_session_id == FeynmanSessionModel.id
                ).where(
                    FeynmanSessionModel.user_id == user_id
                ).order_by(desc(FeynmanResultModel.evaluated_at)).limit(10)
            )
            feynman_data = feynman_result.all()

            # Calculate performance metrics
            quiz_scores = [a.score for a in quiz_attempts if a.score is not None]
            quiz_avg = sum(quiz_scores) / len(quiz_scores) if quiz_scores else 0
            quiz_trend = self._calculate_trend(quiz_scores)

            feynman_scores = [fr.overall_score for fr, _ in feynman_data if fr.overall_score]
            feynman_avg = sum(feynman_scores) / len(feynman_scores) if feynman_scores else 0
            feynman_trend = self._calculate_trend(feynman_scores)

            # Calculate engagement metrics
            now = datetime.utcnow()
            week_ago = now - timedelta(days=7)
            month_ago = now - timedelta(days=30)

            sessions_7d = sum(1 for s in sessions if s.started_at >= week_ago)
            sessions_30d = len(sessions)

            total_duration = sum(
                s.actual_duration_minutes or s.planned_duration_minutes
                for s in sessions
            )
            avg_duration = total_duration / len(sessions) if sessions else 0

            completed_count = sum(1 for s in sessions if s.status == "completed")
            completion_rate = completed_count / len(sessions) if sessions else 0

            # Get current settings from pattern
            pace = self._get_pace_from_pattern(pattern)

            return {
                "performance": {
                    "quiz_score_avg": quiz_avg,
                    "quiz_score_trend": quiz_trend,
                    "feynman_score_avg": feynman_avg,
                    "feynman_score_trend": feynman_trend,
                },
                "engagement": {
                    "sessions_last_7_days": sessions_7d,
                    "sessions_last_30_days": sessions_30d,
                    "avg_session_duration": avg_duration,
                    "completion_rate": completion_rate,
                },
                "current_settings": {
                    "pace": pace,
                    "difficulty_level": 3,  # Default
                },
                "streak": {
                    "current": pattern.current_streak,
                    "longest": pattern.longest_streak,
                    "days_since_last": pattern.days_since_last_session,
                },
            }

    async def check_triggers(self, user_id: UUID) -> list[AdaptationTrigger]:
        """Check for adaptation triggers."""
        triggers: list[AdaptationTrigger] = []
        patterns = await self.analyze_patterns(user_id)

        perf = patterns.get("performance", {})
        eng = patterns.get("engagement", {})
        streak = patterns.get("streak", {})

        # Check for pace adjustment trigger
        quiz_avg = perf.get("quiz_score_avg", 0.5)
        if quiz_avg > 0.9:
            triggers.append(AdaptationTrigger(
                type=AdaptationType.PACE_ADJUSTMENT,
                reason="Consistently high quiz scores - consider increasing pace",
                severity=0.6,
                data={"direction": "increase", "current_avg": quiz_avg},
            ))
        elif quiz_avg < 0.5:
            triggers.append(AdaptationTrigger(
                type=AdaptationType.PACE_ADJUSTMENT,
                reason="Low quiz scores - consider reducing pace",
                severity=0.8,
                data={"direction": "decrease", "current_avg": quiz_avg},
            ))

        # Check for difficulty adjustment trigger
        feynman_trend = perf.get("feynman_score_trend", "stable")
        if feynman_trend == "declining" and perf.get("feynman_score_avg", 0.5) < 0.5:
            triggers.append(AdaptationTrigger(
                type=AdaptationType.DIFFICULTY_CHANGE,
                reason="Feynman scores declining - reduce difficulty",
                severity=0.7,
                data={"direction": "decrease"},
            ))

        # Check for recovery plan trigger
        days_missed = streak.get("days_since_last", 0)
        if days_missed >= 3:
            triggers.append(AdaptationTrigger(
                type=AdaptationType.RECOVERY_PLAN,
                reason=f"Missed {days_missed} days - recovery plan needed",
                severity=min(0.5 + (days_missed * 0.1), 1.0),
                data={"days_missed": days_missed},
            ))

        # Check for low engagement
        sessions_7d = eng.get("sessions_last_7_days", 0)
        if sessions_7d < 2:
            triggers.append(AdaptationTrigger(
                type=AdaptationType.CURRICULUM_CHANGE,
                reason="Low engagement - consider curriculum adjustments",
                severity=0.5,
                data={"sessions_7d": sessions_7d},
            ))

        # Sort by severity
        triggers.sort(key=lambda t: t.severity, reverse=True)

        return triggers

    async def apply_adaptation(
        self,
        user_id: UUID,
        trigger: AdaptationTrigger,
    ) -> AdaptationResult:
        """Apply an adaptation based on trigger."""
        async with get_db_session() as db:
            pattern = await self._get_or_create_pattern(db, user_id)
            old_value: dict = {}
            new_value: dict = {}

            if trigger.type == AdaptationType.PACE_ADJUSTMENT:
                direction = trigger.data.get("direction", "maintain")
                old_pace = self._get_pace_from_pattern(pattern)

                if direction == "increase":
                    new_pace = "fast" if old_pace == "normal" else "normal"
                elif direction == "decrease":
                    new_pace = "slow" if old_pace == "normal" else "normal"
                else:
                    new_pace = old_pace

                old_value = {"pace": old_pace}
                new_value = {"pace": new_pace}
                description = f"Pace adjusted from {old_pace} to {new_pace}"

            elif trigger.type == AdaptationType.DIFFICULTY_CHANGE:
                # Get current difficulty from topic progress
                result = await db.execute(
                    select(func.avg(UserTopicProgressModel.proficiency_level)).where(
                        UserTopicProgressModel.user_id == user_id
                    )
                )
                avg_prof = result.scalar() or 0.5
                old_diff = int(avg_prof * 5) + 1

                direction = trigger.data.get("direction", "maintain")
                new_diff = max(1, old_diff - 1) if direction == "decrease" else min(5, old_diff + 1)

                old_value = {"difficulty": old_diff}
                new_value = {"difficulty": new_diff}
                description = f"Difficulty adjusted from {old_diff} to {new_diff}"

            elif trigger.type == AdaptationType.RECOVERY_PLAN:
                days_missed = trigger.data.get("days_missed", 1)
                recovery = await self.generate_recovery_plan(user_id, days_missed)

                old_value = {"recovery_active": False}
                new_value = {
                    "recovery_active": True,
                    "sessions_to_catch_up": recovery.suggested_session_count,
                }
                description = f"Recovery plan activated: {recovery.message}"

            else:
                old_value = {}
                new_value = {}
                description = "No changes applied"

            # Record adaptation event
            event = AdaptationEventModel(
                id=uuid4(),
                user_id=user_id,
                adaptation_type=trigger.type.value,
                trigger_reason=trigger.reason,
                old_value=old_value,
                new_value=new_value,
                created_at=datetime.utcnow(),
            )
            db.add(event)

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
        """Generate a recovery plan after missed days."""
        async with get_db_session() as db:
            # Get topics that need review
            result = await db.execute(
                select(UserTopicProgressModel).where(
                    and_(
                        UserTopicProgressModel.user_id == user_id,
                        UserTopicProgressModel.next_review <= datetime.utcnow(),
                    )
                ).order_by(UserTopicProgressModel.proficiency_level.asc()).limit(5)
            )
            overdue_topics = result.scalars().all()
            review_topics = [t.topic_id for t in overdue_topics]

            # Calculate recovery parameters
            reduce_new = days_missed >= 5
            sessions_needed = min(days_missed, 7)  # Max 7 catchup sessions

            # Get priority gaps
            gaps_result = await db.execute(
                select(UserTopicProgressModel).where(
                    and_(
                        UserTopicProgressModel.user_id == user_id,
                        UserTopicProgressModel.proficiency_level < 0.5,
                    )
                ).order_by(UserTopicProgressModel.proficiency_level.asc()).limit(3)
            )
            priority_gaps = [g.topic_id for g in gaps_result.scalars().all()]

            # Generate encouraging message
            if days_missed < 3:
                message = "Welcome back! Let's do a quick review to get back on track."
            elif days_missed < 7:
                message = "Good to see you! We'll ease back in with some review sessions."
            else:
                message = "Welcome back! Don't worry - we'll help you catch up gradually."

            return RecoveryPlan(
                user_id=user_id,
                days_missed=days_missed,
                review_topics=review_topics,
                reduced_new_content=reduce_new,
                suggested_session_count=sessions_needed,
                priority_gaps=priority_gaps,
                message=message,
            )

    async def get_pace_recommendation(self, user_id: UUID) -> PaceRecommendation:
        """Get recommendation for learning pace."""
        patterns = await self.analyze_patterns(user_id)
        perf = patterns.get("performance", {})
        current = patterns.get("current_settings", {}).get("pace", "normal")

        quiz_avg = perf.get("quiz_score_avg", 0.5)
        quiz_trend = perf.get("quiz_score_trend", "stable")

        if quiz_avg > 0.85 and quiz_trend in ["improving", "stable"]:
            recommended = "fast"
            reason = "Your strong performance indicates you can handle more challenging content."
            confidence = 0.8
        elif quiz_avg < 0.6 or quiz_trend == "declining":
            recommended = "slow"
            reason = "Slowing down will help solidify understanding before moving on."
            confidence = 0.75
        else:
            recommended = "normal"
            reason = "Your current pace seems appropriate for your learning progress."
            confidence = 0.7

        return PaceRecommendation(
            current_pace=current,
            recommended_pace=recommended,
            reason=reason,
            confidence=confidence,
        )

    async def get_adaptation_history(
        self,
        user_id: UUID,
        limit: int = 10,
    ) -> list[AdaptationEvent]:
        """Get history of adaptations for user."""
        async with get_db_session() as db:
            result = await db.execute(
                select(AdaptationEventModel).where(
                    AdaptationEventModel.user_id == user_id
                ).order_by(desc(AdaptationEventModel.created_at)).limit(limit)
            )
            events = result.scalars().all()

            return [
                AdaptationEvent(
                    id=e.id,
                    user_id=e.user_id,
                    type=AdaptationType(e.adaptation_type),
                    trigger_reason=e.trigger_reason,
                    old_value=e.old_value or {},
                    new_value=e.new_value or {},
                    created_at=e.created_at,
                )
                for e in events
            ]

    async def override_adaptation(
        self,
        user_id: UUID,
        adaptation_type: AdaptationType,
        new_value: Any,
        reason: str,
    ) -> AdaptationResult:
        """Manually override an adaptation setting."""
        async with get_db_session() as db:
            # Record the override as an adaptation event
            event = AdaptationEventModel(
                id=uuid4(),
                user_id=user_id,
                adaptation_type=adaptation_type.value,
                trigger_reason=f"User override: {reason}",
                old_value={"previous": "auto"},
                new_value={"value": new_value, "user_override": True},
                created_at=datetime.utcnow(),
            )
            db.add(event)

            return AdaptationResult(
                success=True,
                type=adaptation_type,
                description=f"Manual override applied: {reason}",
                old_value={"previous": "auto"},
                new_value=new_value,
            )

    async def predict_next_adaptation(self, user_id: UUID) -> Optional[AdaptationTrigger]:
        """Predict the next likely adaptation."""
        triggers = await self.check_triggers(user_id)

        # Return the highest severity trigger if any
        if triggers:
            return triggers[0]

        return None

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

        return pattern

    def _calculate_trend(self, scores: list[float]) -> str:
        """Calculate trend from recent scores."""
        if len(scores) < 3:
            return "stable"

        recent = scores[:5]
        older = scores[5:10] if len(scores) > 5 else scores[len(scores)//2:]

        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older) if older else recent_avg

        diff = recent_avg - older_avg

        if diff > 0.1:
            return "improving"
        elif diff < -0.1:
            return "declining"
        else:
            return "stable"

    def _get_pace_from_pattern(self, pattern: UserLearningPatternModel) -> str:
        """Determine pace from learning pattern."""
        # Use completion rate and quiz trends to determine pace
        if pattern.completion_rate > 0.9 and pattern.quiz_accuracy_trend > 0.1:
            return "fast"
        elif pattern.completion_rate < 0.6 or pattern.quiz_accuracy_trend < -0.1:
            return "slow"
        else:
            return "normal"


# Factory function
_db_adaptation_service: DatabaseAdaptationService | None = None


def get_db_adaptation_service() -> DatabaseAdaptationService:
    """Get database adaptation service singleton."""
    global _db_adaptation_service
    if _db_adaptation_service is None:
        _db_adaptation_service = DatabaseAdaptationService()
    return _db_adaptation_service
