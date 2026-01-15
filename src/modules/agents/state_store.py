"""Conversation State Store.

This module provides Redis-backed storage for conversation states,
replacing the in-memory dict in the orchestrator.
"""

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncGenerator
from uuid import UUID

from src.modules.agents.interface import AgentType, ConversationState
from src.shared.database import get_redis
from src.shared.constants import (
    CONVERSATION_STATE_TTL_SECONDS,
    DISTRIBUTED_LOCK_TTL_SECONDS,
    DISTRIBUTED_LOCK_RETRY_DELAY_SECONDS,
    DISTRIBUTED_LOCK_MAX_RETRIES,
)

logger = logging.getLogger(__name__)


class ConversationStateStore:
    """Redis-backed conversation state storage.

    Stores conversation states with TTL for automatic cleanup.
    Enables horizontal scaling of the application.
    """

    # Key prefix for conversation states
    KEY_PREFIX = "conversation:state:"

    # Key prefix for locks
    LOCK_PREFIX = "conversation:lock:"

    # Default TTL from constants
    DEFAULT_TTL = CONVERSATION_STATE_TTL_SECONDS

    # Lock settings from constants
    LOCK_TTL = DISTRIBUTED_LOCK_TTL_SECONDS
    LOCK_RETRY_DELAY = DISTRIBUTED_LOCK_RETRY_DELAY_SECONDS
    LOCK_MAX_RETRIES = DISTRIBUTED_LOCK_MAX_RETRIES

    def __init__(self, ttl_seconds: int = DEFAULT_TTL) -> None:
        """Initialize state store.

        Args:
            ttl_seconds: Time-to-live for state entries
        """
        self._ttl = ttl_seconds

    @asynccontextmanager
    async def acquire_lock(self, user_id: UUID) -> AsyncGenerator[bool, None]:
        """Acquire a distributed lock for a user's conversation state.

        Uses Redis SETNX for atomic lock acquisition to prevent race conditions
        when multiple requests try to modify the same user's state.

        Args:
            user_id: User UUID to lock

        Yields:
            True if lock was acquired, False otherwise
        """
        import asyncio

        redis = await get_redis()
        lock_key = f"{self.LOCK_PREFIX}{user_id}"
        lock_acquired = False

        try:
            # Try to acquire lock with retries
            for _ in range(self.LOCK_MAX_RETRIES):
                # SETNX returns True if key was set (lock acquired)
                lock_acquired = await redis.set(
                    lock_key,
                    "1",
                    nx=True,  # Only set if not exists
                    ex=self.LOCK_TTL,  # Auto-expire to prevent deadlocks
                )
                if lock_acquired:
                    break
                await asyncio.sleep(self.LOCK_RETRY_DELAY)

            if not lock_acquired:
                logger.warning(f"Failed to acquire lock for user {user_id} after {self.LOCK_MAX_RETRIES} retries")

            yield lock_acquired
        finally:
            # Release lock only if we acquired it
            if lock_acquired:
                try:
                    await redis.delete(lock_key)
                except Exception as e:
                    logger.warning(f"Error releasing lock for user {user_id}: {e}")

    async def get(self, user_id: UUID) -> ConversationState | None:
        """Get conversation state for a user.

        Args:
            user_id: User UUID

        Returns:
            ConversationState or None if not found
        """
        redis = await get_redis()
        key = f"{self.KEY_PREFIX}{user_id}"

        data = await redis.get(key)
        if data is None:
            return None

        return self._deserialize(data)

    async def set(
        self,
        user_id: UUID,
        state: ConversationState,
        ttl_seconds: int | None = None,
    ) -> None:
        """Store conversation state for a user.

        Args:
            user_id: User UUID
            state: ConversationState to store
            ttl_seconds: Optional custom TTL
        """
        redis = await get_redis()
        key = f"{self.KEY_PREFIX}{user_id}"
        ttl = ttl_seconds or self._ttl

        data = self._serialize(state)
        await redis.setex(key, ttl, data)

    async def delete(self, user_id: UUID) -> bool:
        """Delete conversation state for a user.

        Args:
            user_id: User UUID

        Returns:
            True if state was deleted, False if not found
        """
        redis = await get_redis()
        key = f"{self.KEY_PREFIX}{user_id}"

        result = await redis.delete(key)
        return result > 0

    async def exists(self, user_id: UUID) -> bool:
        """Check if conversation state exists for a user.

        Args:
            user_id: User UUID

        Returns:
            True if state exists
        """
        redis = await get_redis()
        key = f"{self.KEY_PREFIX}{user_id}"

        return await redis.exists(key) > 0

    async def extend_ttl(
        self,
        user_id: UUID,
        ttl_seconds: int | None = None,
    ) -> bool:
        """Extend the TTL for a conversation state.

        Args:
            user_id: User UUID
            ttl_seconds: New TTL in seconds

        Returns:
            True if TTL was extended, False if state not found
        """
        redis = await get_redis()
        key = f"{self.KEY_PREFIX}{user_id}"
        ttl = ttl_seconds or self._ttl

        return await redis.expire(key, ttl)

    async def get_and_update(
        self,
        user_id: UUID,
        update_fn: callable,
        ttl_seconds: int | None = None,
    ) -> tuple[ConversationState | None, bool]:
        """Atomically get, update, and store conversation state.

        Uses distributed locking to prevent race conditions when multiple
        requests try to modify the same user's state simultaneously.

        Args:
            user_id: User UUID
            update_fn: Function that takes ConversationState and returns modified state
            ttl_seconds: Optional custom TTL

        Returns:
            Tuple of (updated_state, success). If lock couldn't be acquired,
            returns (None, False).
        """
        async with self.acquire_lock(user_id) as lock_acquired:
            if not lock_acquired:
                return None, False

            # Get current state
            state = await self.get(user_id)
            if state is None:
                return None, True  # No state to update, but lock was acquired

            # Apply update function
            updated_state = update_fn(state)

            # Store updated state
            await self.set(user_id, updated_state, ttl_seconds)

            return updated_state, True

    async def get_all_user_ids(self) -> list[UUID]:
        """Get all user IDs with active conversations.

        Note: Use sparingly, scans Redis keys.

        Returns:
            List of user UUIDs
        """
        redis = await get_redis()
        pattern = f"{self.KEY_PREFIX}*"

        user_ids = []
        async for key in redis.scan_iter(pattern):
            # Extract user_id from key
            user_id_str = key.replace(self.KEY_PREFIX, "")
            try:
                user_ids.append(UUID(user_id_str))
            except ValueError:
                continue

        return user_ids

    def _serialize(self, state: ConversationState) -> str:
        """Serialize ConversationState to JSON.

        Args:
            state: ConversationState to serialize

        Returns:
            JSON string
        """
        data = {
            "user_id": str(state.user_id),
            "session_id": str(state.session_id) if state.session_id else None,
            "current_agent": state.current_agent.value,
            "history": state.history,
            "context": self._serialize_context(state.context),
            "started_at": state.started_at.isoformat(),
            "last_activity": state.last_activity.isoformat(),
        }
        return json.dumps(data)

    def _deserialize(self, data: str) -> ConversationState:
        """Deserialize JSON to ConversationState.

        Args:
            data: JSON string

        Returns:
            ConversationState
        """
        parsed = json.loads(data)

        return ConversationState(
            user_id=UUID(parsed["user_id"]),
            session_id=UUID(parsed["session_id"]) if parsed["session_id"] else None,
            current_agent=AgentType(parsed["current_agent"]),
            history=parsed["history"],
            context=self._deserialize_context(parsed["context"]),
            started_at=datetime.fromisoformat(parsed["started_at"]),
            last_activity=datetime.fromisoformat(parsed["last_activity"]),
        )

    def _serialize_context(self, context: dict[str, Any]) -> dict[str, Any]:
        """Serialize context dict, converting UUIDs to strings.

        Args:
            context: Context dict

        Returns:
            Serializable dict
        """
        result = {}
        for key, value in context.items():
            if isinstance(value, UUID):
                result[key] = str(value)
            elif isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, dict):
                result[key] = self._serialize_context(value)
            elif isinstance(value, list):
                result[key] = [
                    str(v) if isinstance(v, UUID) else v
                    for v in value
                ]
            else:
                result[key] = value
        return result

    def _deserialize_context(self, context: dict[str, Any]) -> dict[str, Any]:
        """Deserialize context dict.

        Args:
            context: Serialized context dict

        Returns:
            Context dict (UUIDs remain as strings for flexibility)
        """
        return context


# Factory function
_state_store: ConversationStateStore | None = None


def get_state_store() -> ConversationStateStore:
    """Get the conversation state store.

    Returns:
        ConversationStateStore instance
    """
    global _state_store
    if _state_store is None:
        _state_store = ConversationStateStore()
    return _state_store
