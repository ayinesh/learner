"""Adaptation repository for data access operations.

This module implements the repository pattern for Adaptation-related entities,
separating data access logic from business logic.
"""

from datetime import datetime, timedelta
from typing import Sequence
from uuid import UUID

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.adaptation.models import AdaptationEventModel
from src.shared.repository import BaseRepository


class AdaptationEventRepository(BaseRepository[AdaptationEventModel]):
    """Repository for AdaptationEvent entities."""

    @property
    def _model_class(self) -> type[AdaptationEventModel]:
        return AdaptationEventModel

    async def get_user_events(
        self,
        user_id: UUID,
        limit: int = 10,
    ) -> Sequence[AdaptationEventModel]:
        """Get adaptation events for a user.

        Args:
            user_id: User UUID
            limit: Maximum events

        Returns:
            Sequence of events, newest first
        """
        result = await self._session.execute(
            select(AdaptationEventModel)
            .where(AdaptationEventModel.user_id == user_id)
            .order_by(desc(AdaptationEventModel.created_at))
            .limit(limit)
        )
        return result.scalars().all()

    async def get_events_by_type(
        self,
        user_id: UUID,
        adaptation_type: str,
        limit: int = 10,
    ) -> Sequence[AdaptationEventModel]:
        """Get adaptation events of a specific type.

        Args:
            user_id: User UUID
            adaptation_type: Type of adaptation
            limit: Maximum events

        Returns:
            Sequence of events
        """
        result = await self._session.execute(
            select(AdaptationEventModel)
            .where(
                and_(
                    AdaptationEventModel.user_id == user_id,
                    AdaptationEventModel.adaptation_type == adaptation_type,
                )
            )
            .order_by(desc(AdaptationEventModel.created_at))
            .limit(limit)
        )
        return result.scalars().all()

    async def get_recent_events(
        self,
        user_id: UUID,
        days: int = 7,
    ) -> Sequence[AdaptationEventModel]:
        """Get adaptation events from the last N days.

        Args:
            user_id: User UUID
            days: Number of days to look back

        Returns:
            Sequence of recent events
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        result = await self._session.execute(
            select(AdaptationEventModel)
            .where(
                and_(
                    AdaptationEventModel.user_id == user_id,
                    AdaptationEventModel.created_at >= cutoff,
                )
            )
            .order_by(desc(AdaptationEventModel.created_at))
        )
        return result.scalars().all()

    async def get_last_event_of_type(
        self,
        user_id: UUID,
        adaptation_type: str,
    ) -> AdaptationEventModel | None:
        """Get the most recent event of a specific type.

        Args:
            user_id: User UUID
            adaptation_type: Type of adaptation

        Returns:
            Most recent event or None
        """
        result = await self._session.execute(
            select(AdaptationEventModel)
            .where(
                and_(
                    AdaptationEventModel.user_id == user_id,
                    AdaptationEventModel.adaptation_type == adaptation_type,
                )
            )
            .order_by(desc(AdaptationEventModel.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()
