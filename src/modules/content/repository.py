"""Content repository for data access operations.

This module implements the repository pattern for Content-related entities,
separating data access logic from business logic.
"""

from datetime import datetime
from typing import Sequence
from uuid import UUID

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.content.models import (
    ContentModel,
    TopicModel,
    UserContentInteractionModel,
    UserTopicProgressModel,
)
from src.shared.repository import BaseRepository


class ContentRepository(BaseRepository[ContentModel]):
    """Repository for Content entities."""

    @property
    def _model_class(self) -> type[ContentModel]:
        return ContentModel

    async def get_by_url(self, url: str) -> ContentModel | None:
        """Get content by source URL.

        Args:
            url: Source URL

        Returns:
            Content or None
        """
        result = await self._session.execute(
            select(ContentModel).where(ContentModel.source_url == url)
        )
        return result.scalar_one_or_none()

    async def get_processed_content(
        self,
        limit: int = 100,
        source_types: list[str] | None = None,
    ) -> Sequence[ContentModel]:
        """Get processed content items.

        Args:
            limit: Maximum items to return
            source_types: Filter by source types

        Returns:
            Sequence of processed content
        """
        query = select(ContentModel).where(
            ContentModel.processed_at.isnot(None)
        )

        if source_types:
            query = query.where(ContentModel.source_type.in_(source_types))

        query = query.order_by(
            desc(ContentModel.importance_score),
            desc(ContentModel.created_at),
        ).limit(limit)

        result = await self._session.execute(query)
        return result.scalars().all()

    async def get_by_ids_batch(self, ids: list[UUID]) -> Sequence[ContentModel]:
        """Batch load content by IDs.

        Args:
            ids: List of content UUIDs

        Returns:
            Sequence of content items
        """
        if not ids:
            return []

        result = await self._session.execute(
            select(ContentModel).where(ContentModel.id.in_(ids))
        )
        return result.scalars().all()

    async def search_content(
        self,
        keywords: list[str],
        limit: int = 20,
    ) -> Sequence[ContentModel]:
        """Search content by keywords in title and summary.

        Args:
            keywords: Keywords to search for
            limit: Maximum results

        Returns:
            Sequence of matching content
        """
        if not keywords:
            return []

        conditions = []
        for kw in keywords:
            conditions.append(
                or_(
                    func.lower(ContentModel.title).contains(kw.lower()),
                    func.lower(ContentModel.summary).contains(kw.lower()),
                )
            )

        result = await self._session.execute(
            select(ContentModel)
            .where(ContentModel.processed_at.isnot(None))
            .where(or_(*conditions))
            .limit(limit)
        )
        return result.scalars().all()

    async def get_by_topic(
        self,
        topic_id: UUID,
        limit: int = 20,
    ) -> Sequence[ContentModel]:
        """Get content for a specific topic.

        Args:
            topic_id: Topic UUID
            limit: Maximum results

        Returns:
            Sequence of content for the topic
        """
        result = await self._session.execute(
            select(ContentModel)
            .where(ContentModel.processed_at.isnot(None))
            .where(ContentModel.topics.contains([topic_id]))
            .limit(limit)
        )
        return result.scalars().all()


class TopicRepository(BaseRepository[TopicModel]):
    """Repository for Topic entities."""

    @property
    def _model_class(self) -> type[TopicModel]:
        return TopicModel

    async def get_by_name(self, name: str) -> TopicModel | None:
        """Get topic by name (case-insensitive).

        Args:
            name: Topic name

        Returns:
            Topic or None
        """
        result = await self._session.execute(
            select(TopicModel).where(
                func.lower(TopicModel.name) == name.lower()
            )
        )
        return result.scalar_one_or_none()

    async def get_by_ids_batch(self, ids: list[UUID]) -> dict[UUID, TopicModel]:
        """Batch load topics by IDs.

        Args:
            ids: List of topic UUIDs

        Returns:
            Dict mapping topic ID to TopicModel
        """
        if not ids:
            return {}

        result = await self._session.execute(
            select(TopicModel).where(TopicModel.id.in_(ids))
        )
        return {t.id: t for t in result.scalars().all()}

    async def get_or_create(self, name: str) -> TopicModel:
        """Get or create a topic by name.

        Args:
            name: Topic name

        Returns:
            Existing or new topic
        """
        from uuid import uuid4

        topic = await self.get_by_name(name)
        if topic is None:
            topic = TopicModel(
                id=uuid4(),
                name=name.lower(),
            )
            self._session.add(topic)
            await self._session.flush()
            await self._session.refresh(topic)
        return topic


class UserContentInteractionRepository(BaseRepository[UserContentInteractionModel]):
    """Repository for UserContentInteraction entities."""

    @property
    def _model_class(self) -> type[UserContentInteractionModel]:
        return UserContentInteractionModel

    async def get_user_interaction(
        self,
        user_id: UUID,
        content_id: UUID,
    ) -> UserContentInteractionModel | None:
        """Get user's interaction with specific content.

        Args:
            user_id: User UUID
            content_id: Content UUID

        Returns:
            Interaction or None
        """
        result = await self._session.execute(
            select(UserContentInteractionModel).where(
                and_(
                    UserContentInteractionModel.user_id == user_id,
                    UserContentInteractionModel.content_id == content_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_user_interactions_batch(
        self,
        user_id: UUID,
        content_ids: list[UUID],
    ) -> dict[UUID, bool]:
        """Batch load user interactions for multiple content items.

        Args:
            user_id: User UUID
            content_ids: List of content UUIDs

        Returns:
            Dict mapping content_id to completed status
        """
        if not content_ids:
            return {}

        result = await self._session.execute(
            select(UserContentInteractionModel).where(
                and_(
                    UserContentInteractionModel.user_id == user_id,
                    UserContentInteractionModel.content_id.in_(content_ids),
                )
            )
        )
        return {
            i.content_id: i.completed
            for i in result.scalars().all()
        }


class UserTopicProgressRepository(BaseRepository[UserTopicProgressModel]):
    """Repository for UserTopicProgress entities."""

    @property
    def _model_class(self) -> type[UserTopicProgressModel]:
        return UserTopicProgressModel

    async def get_user_progress(
        self,
        user_id: UUID,
        topic_id: UUID,
    ) -> UserTopicProgressModel | None:
        """Get user's progress for a specific topic.

        Args:
            user_id: User UUID
            topic_id: Topic UUID

        Returns:
            Progress or None
        """
        result = await self._session.execute(
            select(UserTopicProgressModel).where(
                and_(
                    UserTopicProgressModel.user_id == user_id,
                    UserTopicProgressModel.topic_id == topic_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_user_topics(self, user_id: UUID) -> Sequence[UserTopicProgressModel]:
        """Get all topic progress for a user.

        Args:
            user_id: User UUID

        Returns:
            Sequence of topic progress records
        """
        result = await self._session.execute(
            select(UserTopicProgressModel).where(
                UserTopicProgressModel.user_id == user_id
            )
        )
        return result.scalars().all()

    async def get_user_topics_as_dict(self, user_id: UUID) -> dict[UUID, float]:
        """Get user's topic proficiency as a dictionary.

        Args:
            user_id: User UUID

        Returns:
            Dict mapping topic_id to proficiency_level
        """
        progress = await self.get_user_topics(user_id)
        return {p.topic_id: p.proficiency_level for p in progress}

    async def get_due_reviews(
        self,
        user_id: UUID,
        limit: int = 10,
    ) -> Sequence[UserTopicProgressModel]:
        """Get topics due for review.

        Args:
            user_id: User UUID
            limit: Maximum items to return

        Returns:
            Sequence of topics due for review
        """
        now = datetime.utcnow()
        result = await self._session.execute(
            select(UserTopicProgressModel).where(
                and_(
                    UserTopicProgressModel.user_id == user_id,
                    UserTopicProgressModel.next_review <= now,
                )
            ).order_by(
                UserTopicProgressModel.next_review.asc()
            ).limit(limit)
        )
        return result.scalars().all()
