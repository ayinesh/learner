"""Assessment repository for data access operations.

This module implements the repository pattern for Assessment-related entities,
separating data access logic from business logic.
"""

from datetime import datetime
from typing import Sequence
from uuid import UUID

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.assessment.models import (
    QuizModel,
    QuizAttemptModel,
    FeynmanSessionModel,
    FeynmanResultModel,
)
from src.shared.repository import BaseRepository


class QuizRepository(BaseRepository[QuizModel]):
    """Repository for Quiz entities."""

    @property
    def _model_class(self) -> type[QuizModel]:
        return QuizModel

    async def get_user_quizzes(
        self,
        user_id: UUID,
        limit: int = 10,
    ) -> Sequence[QuizModel]:
        """Get quizzes for a user.

        Args:
            user_id: User UUID
            limit: Maximum quizzes to return

        Returns:
            Sequence of quizzes, newest first
        """
        result = await self._session.execute(
            select(QuizModel)
            .where(QuizModel.user_id == user_id)
            .order_by(desc(QuizModel.created_at))
            .limit(limit)
        )
        return result.scalars().all()

    async def get_recent_quiz_scores(
        self,
        user_id: UUID,
        limit: int = 10,
    ) -> list[float]:
        """Get recent quiz scores for a user.

        Args:
            user_id: User UUID
            limit: Maximum scores to return

        Returns:
            List of scores, most recent first
        """
        result = await self._session.execute(
            select(QuizAttemptModel)
            .where(QuizAttemptModel.user_id == user_id)
            .order_by(desc(QuizAttemptModel.attempted_at))
            .limit(limit)
        )
        return [a.score for a in result.scalars().all() if a.score is not None]


class QuizAttemptRepository(BaseRepository[QuizAttemptModel]):
    """Repository for QuizAttempt entities."""

    @property
    def _model_class(self) -> type[QuizAttemptModel]:
        return QuizAttemptModel

    async def get_quiz_attempts(
        self,
        quiz_id: UUID,
    ) -> Sequence[QuizAttemptModel]:
        """Get all attempts for a quiz.

        Args:
            quiz_id: Quiz UUID

        Returns:
            Sequence of attempts
        """
        result = await self._session.execute(
            select(QuizAttemptModel)
            .where(QuizAttemptModel.quiz_id == quiz_id)
            .order_by(QuizAttemptModel.attempted_at)
        )
        return result.scalars().all()

    async def get_user_attempts(
        self,
        user_id: UUID,
        limit: int = 20,
    ) -> Sequence[QuizAttemptModel]:
        """Get all attempts for a user.

        Args:
            user_id: User UUID
            limit: Maximum attempts to return

        Returns:
            Sequence of attempts, newest first
        """
        result = await self._session.execute(
            select(QuizAttemptModel)
            .where(QuizAttemptModel.user_id == user_id)
            .order_by(desc(QuizAttemptModel.attempted_at))
            .limit(limit)
        )
        return result.scalars().all()

    async def get_low_score_attempts(
        self,
        user_id: UUID,
        threshold: float = 0.7,
        limit: int = 10,
    ) -> Sequence[QuizAttemptModel]:
        """Get attempts with scores below threshold.

        Args:
            user_id: User UUID
            threshold: Score threshold
            limit: Maximum attempts

        Returns:
            Sequence of low-score attempts
        """
        result = await self._session.execute(
            select(QuizAttemptModel)
            .where(
                and_(
                    QuizAttemptModel.user_id == user_id,
                    QuizAttemptModel.score < threshold,
                )
            )
            .order_by(desc(QuizAttemptModel.attempted_at))
            .limit(limit)
        )
        return result.scalars().all()


class FeynmanSessionRepository(BaseRepository[FeynmanSessionModel]):
    """Repository for FeynmanSession entities."""

    @property
    def _model_class(self) -> type[FeynmanSessionModel]:
        return FeynmanSessionModel

    async def get_user_sessions(
        self,
        user_id: UUID,
        limit: int = 10,
    ) -> Sequence[FeynmanSessionModel]:
        """Get Feynman sessions for a user.

        Args:
            user_id: User UUID
            limit: Maximum sessions

        Returns:
            Sequence of sessions, newest first
        """
        result = await self._session.execute(
            select(FeynmanSessionModel)
            .where(FeynmanSessionModel.user_id == user_id)
            .order_by(desc(FeynmanSessionModel.started_at))
            .limit(limit)
        )
        return result.scalars().all()

    async def get_active_session(
        self,
        user_id: UUID,
    ) -> FeynmanSessionModel | None:
        """Get user's active Feynman session.

        Args:
            user_id: User UUID

        Returns:
            Active session or None
        """
        result = await self._session.execute(
            select(FeynmanSessionModel).where(
                and_(
                    FeynmanSessionModel.user_id == user_id,
                    FeynmanSessionModel.status == "active",
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_sessions_for_topic(
        self,
        user_id: UUID,
        topic_id: UUID,
    ) -> Sequence[FeynmanSessionModel]:
        """Get Feynman sessions for a specific topic.

        Args:
            user_id: User UUID
            topic_id: Topic UUID

        Returns:
            Sequence of sessions for the topic
        """
        result = await self._session.execute(
            select(FeynmanSessionModel).where(
                and_(
                    FeynmanSessionModel.user_id == user_id,
                    FeynmanSessionModel.topic_id == topic_id,
                )
            ).order_by(desc(FeynmanSessionModel.started_at))
        )
        return result.scalars().all()


class FeynmanResultRepository(BaseRepository[FeynmanResultModel]):
    """Repository for FeynmanResult entities."""

    @property
    def _model_class(self) -> type[FeynmanResultModel]:
        return FeynmanResultModel

    async def get_by_session_id(
        self,
        session_id: UUID,
    ) -> FeynmanResultModel | None:
        """Get result for a Feynman session.

        Args:
            session_id: Feynman session UUID

        Returns:
            Result or None
        """
        result = await self._session.execute(
            select(FeynmanResultModel).where(
                FeynmanResultModel.feynman_session_id == session_id
            )
        )
        return result.scalar_one_or_none()

    async def get_user_results(
        self,
        user_id: UUID,
        limit: int = 10,
    ) -> Sequence[tuple[FeynmanResultModel, FeynmanSessionModel]]:
        """Get Feynman results with session info for a user.

        Args:
            user_id: User UUID
            limit: Maximum results

        Returns:
            Sequence of (result, session) tuples
        """
        result = await self._session.execute(
            select(FeynmanResultModel, FeynmanSessionModel)
            .join(
                FeynmanSessionModel,
                FeynmanResultModel.feynman_session_id == FeynmanSessionModel.id
            )
            .where(FeynmanSessionModel.user_id == user_id)
            .order_by(desc(FeynmanResultModel.evaluated_at))
            .limit(limit)
        )
        return result.all()

    async def get_low_score_results(
        self,
        user_id: UUID,
        threshold: float = 0.7,
        limit: int = 10,
    ) -> Sequence[tuple[FeynmanResultModel, FeynmanSessionModel]]:
        """Get Feynman results with scores below threshold.

        Args:
            user_id: User UUID
            threshold: Score threshold
            limit: Maximum results

        Returns:
            Sequence of (result, session) tuples
        """
        result = await self._session.execute(
            select(FeynmanResultModel, FeynmanSessionModel)
            .join(
                FeynmanSessionModel,
                FeynmanResultModel.feynman_session_id == FeynmanSessionModel.id
            )
            .where(
                and_(
                    FeynmanSessionModel.user_id == user_id,
                    FeynmanResultModel.overall_score < threshold,
                )
            )
            .order_by(desc(FeynmanResultModel.evaluated_at))
            .limit(limit)
        )
        return result.all()
