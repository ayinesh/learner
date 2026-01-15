"""Session repository for data access operations.

This module implements the repository pattern for Session-related entities,
separating data access logic from business logic.
"""

from datetime import datetime
from typing import Sequence
from uuid import UUID

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.modules.session.models import (
    SessionModel,
    SessionActivityModel,
    UserLearningPatternModel,
)
from src.shared.repository import BaseRepository


class SessionRepository(BaseRepository[SessionModel]):
    """Repository for Session entities."""

    @property
    def _model_class(self) -> type[SessionModel]:
        return SessionModel

    async def get_by_id_with_activities(self, session_id: UUID) -> SessionModel | None:
        """Get session with activities eagerly loaded.

        Args:
            session_id: Session UUID

        Returns:
            Session with activities or None
        """
        result = await self._session.execute(
            select(SessionModel)
            .options(selectinload(SessionModel.activities))
            .where(SessionModel.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_active_session(self, user_id: UUID) -> SessionModel | None:
        """Get user's active (in_progress) session.

        Args:
            user_id: User UUID

        Returns:
            Active session or None
        """
        result = await self._session.execute(
            select(SessionModel).where(
                and_(
                    SessionModel.user_id == user_id,
                    SessionModel.status == "in_progress",
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_user_sessions(
        self,
        user_id: UUID,
        limit: int = 10,
        include_abandoned: bool = False,
    ) -> Sequence[SessionModel]:
        """Get user's session history.

        Args:
            user_id: User UUID
            limit: Maximum sessions to return
            include_abandoned: Whether to include abandoned sessions

        Returns:
            Sequence of sessions, newest first
        """
        query = select(SessionModel).where(SessionModel.user_id == user_id)

        if not include_abandoned:
            query = query.where(SessionModel.status != "abandoned")

        query = query.order_by(desc(SessionModel.started_at)).limit(limit)

        result = await self._session.execute(query)
        return result.scalars().all()

    async def get_completed_sessions_in_range(
        self,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> Sequence[SessionModel]:
        """Get completed sessions within a date range.

        Args:
            user_id: User UUID
            start_date: Start of date range
            end_date: End of date range

        Returns:
            Sequence of completed sessions
        """
        result = await self._session.execute(
            select(SessionModel).where(
                and_(
                    SessionModel.user_id == user_id,
                    SessionModel.status == "completed",
                    SessionModel.started_at >= start_date,
                    SessionModel.started_at <= end_date,
                )
            ).order_by(desc(SessionModel.started_at))
        )
        return result.scalars().all()


class SessionActivityRepository(BaseRepository[SessionActivityModel]):
    """Repository for SessionActivity entities."""

    @property
    def _model_class(self) -> type[SessionActivityModel]:
        return SessionActivityModel

    async def get_session_activities(
        self,
        session_id: UUID,
    ) -> Sequence[SessionActivityModel]:
        """Get all activities for a session.

        Args:
            session_id: Session UUID

        Returns:
            Sequence of activities ordered by start time
        """
        result = await self._session.execute(
            select(SessionActivityModel)
            .where(SessionActivityModel.session_id == session_id)
            .order_by(SessionActivityModel.started_at)
        )
        return result.scalars().all()

    async def get_completed_activities(
        self,
        session_id: UUID,
    ) -> Sequence[SessionActivityModel]:
        """Get completed activities for a session.

        Args:
            session_id: Session UUID

        Returns:
            Sequence of completed activities
        """
        result = await self._session.execute(
            select(SessionActivityModel).where(
                and_(
                    SessionActivityModel.session_id == session_id,
                    SessionActivityModel.ended_at.isnot(None),
                )
            ).order_by(SessionActivityModel.started_at)
        )
        return result.scalars().all()


class UserLearningPatternRepository(BaseRepository[UserLearningPatternModel]):
    """Repository for UserLearningPattern entities."""

    @property
    def _model_class(self) -> type[UserLearningPatternModel]:
        return UserLearningPatternModel

    async def get_by_user_id(self, user_id: UUID) -> UserLearningPatternModel | None:
        """Get learning pattern for a user.

        Args:
            user_id: User UUID

        Returns:
            Learning pattern or None
        """
        result = await self._session.execute(
            select(UserLearningPatternModel).where(
                UserLearningPatternModel.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create(self, user_id: UUID) -> UserLearningPatternModel:
        """Get or create learning pattern for a user.

        Args:
            user_id: User UUID

        Returns:
            Existing or new learning pattern
        """
        from uuid import uuid4

        pattern = await self.get_by_user_id(user_id)
        if pattern is None:
            pattern = UserLearningPatternModel(
                id=uuid4(),
                user_id=user_id,
            )
            self._session.add(pattern)
            await self._session.flush()
            await self._session.refresh(pattern)
        return pattern
