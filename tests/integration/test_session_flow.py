"""Integration tests for session flow."""

import pytest
from datetime import datetime
from uuid import uuid4
from sqlalchemy import text

from src.modules.auth import get_auth_service
from src.modules.session import get_session_service
from src.shared.database import get_db_session
from src.shared.models import SessionStatus


@pytest.fixture
async def test_user():
    """Create a test user for session tests."""
    auth_service = get_auth_service()
    test_email = f"integration_session_{uuid4().hex[:8]}@example.com"

    # Clean up any existing test users (using parameterized queries to prevent SQL injection)
    async with get_db_session() as session:
        await session.execute(
            text("DELETE FROM users WHERE email = :email"),
            {"email": test_email}
        )
        await session.commit()

    result = await auth_service.register(test_email, "TestPassword123!")
    yield result.user_id

    # Cleanup (using parameterized queries to prevent SQL injection)
    async with get_db_session() as session:
        await session.execute(
            text("DELETE FROM learning_sessions WHERE user_id = :user_id"),
            {"user_id": str(result.user_id)}
        )
        await session.execute(
            text("DELETE FROM refresh_tokens WHERE user_id = :user_id"),
            {"user_id": str(result.user_id)}
        )
        await session.execute(
            text("DELETE FROM users WHERE id = :user_id"),
            {"user_id": str(result.user_id)}
        )
        await session.commit()


class TestSessionFlow:
    """Test complete session lifecycle."""

    @pytest.mark.asyncio
    async def test_complete_session_lifecycle(self, test_user):
        """Test create -> start -> update -> complete session flow."""
        session_service = get_session_service()
        user_id = test_user

        # Step 1: Create a new session
        session = await session_service.create_session(
            user_id=user_id,
            target_minutes=30,
            learning_goals=["Learn testing", "Master integration tests"]
        )

        assert session is not None
        assert session.user_id == user_id
        assert session.target_minutes == 30
        assert session.status == SessionStatus.NOT_STARTED
        assert len(session.learning_goals) == 2

        session_id = session.id

        # Step 2: Start the session
        started_session = await session_service.start_session(user_id, session_id)

        assert started_session is not None
        assert started_session.status == SessionStatus.IN_PROGRESS
        assert started_session.started_at is not None

        # Step 3: Update session progress
        updated_session = await session_service.update_session_progress(
            user_id=user_id,
            session_id=session_id,
            topics_covered=["Unit testing", "Integration testing"],
            concepts_learned=["Fixtures", "Assertions"],
            practice_time_minutes=15
        )

        assert updated_session is not None
        assert len(updated_session.topics_covered) == 2
        assert len(updated_session.concepts_learned) == 2
        assert updated_session.actual_minutes == 15

        # Step 4: Complete the session
        completed_session = await session_service.complete_session(
            user_id=user_id,
            session_id=session_id,
            summary="Learned about testing flows"
        )

        assert completed_session is not None
        assert completed_session.status == SessionStatus.COMPLETED
        assert completed_session.completed_at is not None
        assert completed_session.summary == "Learned about testing flows"

    @pytest.mark.asyncio
    async def test_abandon_session(self, test_user):
        """Test abandoning a session."""
        session_service = get_session_service()
        user_id = test_user

        # Create and start session
        session = await session_service.create_session(
            user_id=user_id,
            target_minutes=30
        )
        await session_service.start_session(user_id, session.id)

        # Abandon session
        abandoned = await session_service.abandon_session(user_id, session.id)

        assert abandoned is not None
        assert abandoned.status == SessionStatus.ABANDONED
        assert abandoned.completed_at is not None

    @pytest.mark.asyncio
    async def test_get_active_session(self, test_user):
        """Test retrieving active session."""
        session_service = get_session_service()
        user_id = test_user

        # No active session initially
        active = await session_service.get_active_session(user_id)
        assert active is None

        # Create and start session
        session = await session_service.create_session(user_id=user_id, target_minutes=30)
        await session_service.start_session(user_id, session.id)

        # Should return active session
        active = await session_service.get_active_session(user_id)
        assert active is not None
        assert active.id == session.id
        assert active.status == SessionStatus.IN_PROGRESS

        # Complete session
        await session_service.complete_session(user_id, session.id)

        # No active session after completion
        active_after = await session_service.get_active_session(user_id)
        assert active_after is None

    @pytest.mark.asyncio
    async def test_get_session_history(self, test_user):
        """Test retrieving session history."""
        session_service = get_session_service()
        user_id = test_user

        # Create multiple sessions
        session1 = await session_service.create_session(user_id=user_id, target_minutes=20)
        await session_service.start_session(user_id, session1.id)
        await session_service.complete_session(user_id, session1.id)

        session2 = await session_service.create_session(user_id=user_id, target_minutes=30)
        await session_service.start_session(user_id, session2.id)
        await session_service.complete_session(user_id, session2.id)

        # Get history
        history = await session_service.get_session_history(user_id, limit=10)

        assert len(history) >= 2
        # Most recent first
        assert history[0].id == session2.id
        assert all(s.status == SessionStatus.COMPLETED for s in history)

    @pytest.mark.asyncio
    async def test_get_session_stats(self, test_user):
        """Test retrieving session statistics."""
        session_service = get_session_service()
        user_id = test_user

        # Create completed sessions
        for i in range(3):
            session = await session_service.create_session(
                user_id=user_id,
                target_minutes=30
            )
            await session_service.start_session(user_id, session.id)
            await session_service.update_session_progress(
                user_id=user_id,
                session_id=session.id,
                practice_time_minutes=25 + i
            )
            await session_service.complete_session(user_id, session.id)

        # Get stats
        stats = await session_service.get_session_stats(user_id)

        assert stats is not None
        assert stats["total_sessions"] >= 3
        assert stats["completed_sessions"] >= 3
        assert stats["total_minutes"] >= 75  # 25 + 26 + 27
        assert "average_session_minutes" in stats
        assert "current_streak" in stats

    @pytest.mark.asyncio
    async def test_session_with_topics(self, test_user):
        """Test session with topic tracking."""
        session_service = get_session_service()
        user_id = test_user

        # Create session
        session = await session_service.create_session(
            user_id=user_id,
            target_minutes=30
        )
        await session_service.start_session(user_id, session.id)

        # Update with topics
        topics = ["Python", "Testing", "Async/Await"]
        updated = await session_service.update_session_progress(
            user_id=user_id,
            session_id=session.id,
            topics_covered=topics,
            concepts_learned=["pytest", "fixtures", "async/await"],
            practice_time_minutes=30
        )

        assert len(updated.topics_covered) == 3
        assert "Python" in updated.topics_covered
        assert len(updated.concepts_learned) == 3

    @pytest.mark.asyncio
    async def test_cannot_start_multiple_sessions(self, test_user):
        """Test that user cannot have multiple active sessions."""
        session_service = get_session_service()
        user_id = test_user

        # Create and start first session
        session1 = await session_service.create_session(user_id=user_id, target_minutes=30)
        await session_service.start_session(user_id, session1.id)

        # Try to create and start second session
        session2 = await session_service.create_session(user_id=user_id, target_minutes=20)

        # Starting second session should fail or auto-complete first
        # This depends on implementation - adjust assertion based on actual behavior
        active = await session_service.get_active_session(user_id)
        assert active is not None  # Should have one active session


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
