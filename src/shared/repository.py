"""Base repository pattern for data access.

This module provides a base repository class and utilities for implementing
the repository pattern across all modules, separating data access from
business logic.
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Sequence
from uuid import UUID

from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database import Base

# Generic type for SQLAlchemy models
ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(ABC, Generic[ModelT]):
    """Base repository providing common CRUD operations.

    All module-specific repositories should inherit from this class
    and implement the required abstract methods.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session for database operations
        """
        self._session = session

    @property
    @abstractmethod
    def _model_class(self) -> type[ModelT]:
        """Return the SQLAlchemy model class for this repository."""
        pass

    async def get_by_id(self, id: UUID) -> ModelT | None:
        """Get a single entity by ID.

        Args:
            id: Entity UUID

        Returns:
            Entity if found, None otherwise
        """
        result = await self._session.execute(
            select(self._model_class).where(self._model_class.id == id)
        )
        return result.scalar_one_or_none()

    async def get_all(self, limit: int = 100, offset: int = 0) -> Sequence[ModelT]:
        """Get all entities with pagination.

        Args:
            limit: Maximum number of entities to return
            offset: Number of entities to skip

        Returns:
            Sequence of entities
        """
        result = await self._session.execute(
            select(self._model_class).limit(limit).offset(offset)
        )
        return result.scalars().all()

    async def create(self, entity: ModelT) -> ModelT:
        """Create a new entity.

        Args:
            entity: Entity to create

        Returns:
            Created entity with generated ID
        """
        self._session.add(entity)
        await self._session.flush()
        await self._session.refresh(entity)
        return entity

    async def update(self, entity: ModelT) -> ModelT:
        """Update an existing entity.

        Args:
            entity: Entity with updated values

        Returns:
            Updated entity
        """
        await self._session.flush()
        await self._session.refresh(entity)
        return entity

    async def delete(self, id: UUID) -> bool:
        """Delete an entity by ID.

        Args:
            id: Entity UUID to delete

        Returns:
            True if entity was deleted, False if not found
        """
        result = await self._session.execute(
            delete(self._model_class).where(self._model_class.id == id)
        )
        return result.rowcount > 0

    async def exists(self, id: UUID) -> bool:
        """Check if an entity exists.

        Args:
            id: Entity UUID

        Returns:
            True if entity exists, False otherwise
        """
        result = await self._session.execute(
            select(self._model_class.id).where(self._model_class.id == id)
        )
        return result.scalar_one_or_none() is not None


class UnitOfWork:
    """Unit of Work pattern for managing transactions.

    Provides a way to group multiple repository operations into a single
    transaction with automatic commit/rollback.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize Unit of Work with session.

        Args:
            session: SQLAlchemy async session
        """
        self._session = session

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self._session.commit()

    async def rollback(self) -> None:
        """Rollback the current transaction."""
        await self._session.rollback()

    async def __aenter__(self) -> "UnitOfWork":
        """Enter async context."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context with automatic commit/rollback."""
        if exc_type is not None:
            await self.rollback()
        else:
            await self.commit()
