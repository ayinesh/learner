"""Unit tests for user module."""

import pytest
from datetime import datetime
from uuid import uuid4
from sqlalchemy import text

from src.modules.user import get_user_service
from src.modules.user.interface import OnboardingData
from src.modules.user.models import (
    UserProfileModel,
    UserSourceConfigModel,
)
from src.modules.session.models import UserLearningPatternModel
from src.modules.auth import get_auth_service
from src.shared.database import get_db_session
from src.shared.models import SourceType


@pytest.fixture
async def user_service():
    """Get user service instance."""
    return get_user_service()


@pytest.fixture
async def auth_service():
    """Get auth service instance."""
    return get_auth_service()


@pytest.fixture
async def clean_db():
    """Clean database before each test."""
    async with get_db_session() as session:
        # Clean up test data
        await session.execute(text("DELETE FROM user_source_configs WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'test%@example.com')"))
        await session.execute(text("DELETE FROM user_learning_patterns WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'test%@example.com')"))
        await session.execute(text("DELETE FROM user_profiles WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'test%@example.com')"))
        await session.execute(text("DELETE FROM password_reset_tokens"))
        await session.execute(text("DELETE FROM refresh_tokens"))
        await session.execute(text("DELETE FROM users WHERE email LIKE 'test%@example.com'"))
        await session.commit()
    yield
    # Cleanup after test
    async with get_db_session() as session:
        await session.execute(text("DELETE FROM user_source_configs WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'test%@example.com')"))
        await session.execute(text("DELETE FROM user_learning_patterns WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'test%@example.com')"))
        await session.execute(text("DELETE FROM user_profiles WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'test%@example.com')"))
        await session.execute(text("DELETE FROM password_reset_tokens"))
        await session.execute(text("DELETE FROM refresh_tokens"))
        await session.execute(text("DELETE FROM users WHERE email LIKE 'test%@example.com'"))
        await session.commit()


@pytest.fixture
async def test_user(auth_service, clean_db):
    """Create a test user for profile testing."""
    result = await auth_service.register(
        email="testuser@example.com",
        password="TestPass123"
    )
    return result.user_id


class TestProfileCreation:
    """Test user profile creation."""

    @pytest.mark.asyncio
    async def test_create_profile_success(self, user_service, test_user):
        """Test successful profile creation."""
        # Note: Profile is auto-created by database trigger when user is created
        # But we test manual creation for users without auto-created profiles

        # Get the auto-created profile
        profile = await user_service.get_profile(test_user)

        assert profile is not None
        assert profile.user_id == test_user
        assert profile.time_budget_minutes == 30  # Default value
        assert profile.timezone == "UTC"
        assert profile.onboarding_completed is False
        assert profile.goals == []
        assert profile.preferred_sources == []

    @pytest.mark.asyncio
    async def test_create_profile_duplicate(self, user_service, test_user):
        """Test creating duplicate profile raises error."""
        with pytest.raises(ValueError, match="Profile already exists"):
            await user_service.create_profile(test_user)

    @pytest.mark.asyncio
    async def test_get_nonexistent_profile(self, user_service):
        """Test getting profile for non-existent user."""
        fake_user_id = uuid4()
        profile = await user_service.get_profile(fake_user_id)

        assert profile is None


class TestProfileUpdate:
    """Test profile update operations."""

    @pytest.mark.asyncio
    async def test_update_profile_basic_fields(self, user_service, test_user):
        """Test updating basic profile fields."""
        updated = await user_service.update_profile(
            test_user,
            background="Software Engineer with 5 years experience",
            goals=["Learn AI/ML", "Build production systems"],
            timezone="America/New_York"
        )

        assert updated.background == "Software Engineer with 5 years experience"
        assert len(updated.goals) == 2
        assert "Learn AI/ML" in updated.goals
        assert updated.timezone == "America/New_York"

    @pytest.mark.asyncio
    async def test_update_profile_sources(self, user_service, test_user):
        """Test updating preferred sources."""
        updated = await user_service.update_profile(
            test_user,
            preferred_sources=[SourceType.ARXIV, SourceType.YOUTUBE]
        )

        assert len(updated.preferred_sources) == 2
        assert SourceType.ARXIV in updated.preferred_sources
        assert SourceType.YOUTUBE in updated.preferred_sources

    @pytest.mark.asyncio
    async def test_update_nonexistent_profile(self, user_service):
        """Test updating non-existent profile raises error."""
        fake_user_id = uuid4()

        with pytest.raises(ValueError, match="Profile not found"):
            await user_service.update_profile(
                fake_user_id,
                background="Test"
            )

    @pytest.mark.asyncio
    async def test_update_time_budget(self, user_service, test_user):
        """Test updating time budget."""
        updated = await user_service.update_time_budget(test_user, 60)

        assert updated.time_budget_minutes == 60

    @pytest.mark.asyncio
    async def test_update_time_budget_invalid(self, user_service, test_user):
        """Test updating time budget with invalid values."""
        with pytest.raises(ValueError, match="Time budget must be between"):
            await user_service.update_time_budget(test_user, 500)

        with pytest.raises(ValueError, match="Time budget must be between"):
            await user_service.update_time_budget(test_user, 2)


class TestOnboarding:
    """Test onboarding completion."""

    @pytest.mark.asyncio
    async def test_complete_onboarding_success(self, user_service, test_user):
        """Test successful onboarding completion."""
        onboarding_data = OnboardingData(
            background="PhD in Computer Science, focusing on distributed systems",
            goals=[
                "Master modern AI architectures",
                "Build production ML systems",
                "Understand transformer models"
            ],
            time_budget_minutes=45,
            preferred_sources=[SourceType.ARXIV, SourceType.YOUTUBE, SourceType.GITHUB],
            timezone="Europe/London",
            initial_topics=["attention mechanisms", "transformers", "RAG"]
        )

        profile = await user_service.complete_onboarding(test_user, onboarding_data)

        assert profile.onboarding_completed is True
        assert profile.background == onboarding_data.background
        assert profile.goals == onboarding_data.goals
        assert profile.time_budget_minutes == 45
        assert len(profile.preferred_sources) == 3
        assert profile.timezone == "Europe/London"

    @pytest.mark.asyncio
    async def test_complete_onboarding_updates_existing(self, user_service, test_user):
        """Test onboarding updates existing profile."""
        # First update
        await user_service.update_profile(test_user, background="Initial background")

        # Complete onboarding
        onboarding_data = OnboardingData(
            background="Updated background",
            goals=["Goal 1"],
            time_budget_minutes=30,
            preferred_sources=[SourceType.ARXIV],
            timezone="UTC"
        )

        profile = await user_service.complete_onboarding(test_user, onboarding_data)

        assert profile.background == "Updated background"
        assert profile.onboarding_completed is True


class TestLearningPatterns:
    """Test learning pattern retrieval."""

    @pytest.mark.asyncio
    async def test_get_learning_pattern_no_sessions(self, user_service, test_user):
        """Test getting learning pattern with no sessions returns None."""
        pattern = await user_service.get_learning_pattern(test_user)

        # Should return None because total_sessions is 0
        assert pattern is None

    @pytest.mark.asyncio
    async def test_get_learning_pattern_with_data(self, user_service, test_user):
        """Test getting learning pattern with session data."""
        # Manually update learning pattern to simulate sessions
        async with get_db_session() as session:
            result = await session.execute(
                text("UPDATE user_learning_patterns SET total_sessions = 5, avg_session_duration = 25.5, current_streak = 3 WHERE user_id = :user_id"),
                {"user_id": test_user}
            )
            await session.commit()

        pattern = await user_service.get_learning_pattern(test_user)

        assert pattern is not None
        assert pattern.total_sessions == 5
        assert pattern.avg_session_duration == 25.5
        assert pattern.current_streak == 3

    @pytest.mark.asyncio
    async def test_get_learning_pattern_nonexistent_user(self, user_service):
        """Test getting pattern for non-existent user."""
        fake_user_id = uuid4()
        pattern = await user_service.get_learning_pattern(fake_user_id)

        assert pattern is None


class TestSourceConfiguration:
    """Test content source configuration."""

    @pytest.mark.asyncio
    async def test_add_source_new(self, user_service, test_user):
        """Test adding a new content source."""
        config = {
            "feeds": ["cs.AI", "cs.LG"],
            "max_papers_per_day": 5
        }

        success = await user_service.add_source(
            test_user,
            SourceType.ARXIV,
            config
        )

        assert success is True

        # Verify it was added
        retrieved_config = await user_service.get_source_config(test_user, SourceType.ARXIV)
        assert retrieved_config is not None
        assert retrieved_config["feeds"] == ["cs.AI", "cs.LG"]
        assert retrieved_config["max_papers_per_day"] == 5

    @pytest.mark.asyncio
    async def test_add_source_updates_existing(self, user_service, test_user):
        """Test adding source updates existing configuration."""
        # Add initial config
        initial_config = {"channels": ["channel1"]}
        await user_service.add_source(test_user, SourceType.YOUTUBE, initial_config)

        # Update config
        updated_config = {"channels": ["channel1", "channel2"], "max_videos": 10}
        await user_service.add_source(test_user, SourceType.YOUTUBE, updated_config)

        # Verify updated
        retrieved = await user_service.get_source_config(test_user, SourceType.YOUTUBE)
        assert len(retrieved["channels"]) == 2
        assert retrieved["max_videos"] == 10

    @pytest.mark.asyncio
    async def test_add_source_updates_profile_preferences(self, user_service, test_user):
        """Test adding source updates profile's preferred_sources."""
        config = {"repos": ["owner/repo1"]}
        await user_service.add_source(test_user, SourceType.GITHUB, config)

        # Check profile was updated
        profile = await user_service.get_profile(test_user)
        assert SourceType.GITHUB in profile.preferred_sources

    @pytest.mark.asyncio
    async def test_remove_source_success(self, user_service, test_user):
        """Test removing a content source."""
        # Add source first
        config = {"subreddits": ["MachineLearning", "learnpython"]}
        await user_service.add_source(test_user, SourceType.REDDIT, config)

        # Verify it exists
        assert await user_service.get_source_config(test_user, SourceType.REDDIT) is not None

        # Remove it
        success = await user_service.remove_source(test_user, SourceType.REDDIT)
        assert success is True

        # Verify it's gone
        assert await user_service.get_source_config(test_user, SourceType.REDDIT) is None

    @pytest.mark.asyncio
    async def test_remove_source_updates_profile(self, user_service, test_user):
        """Test removing source updates profile's preferred_sources."""
        # Add source
        config = {"feeds": ["feed1"]}
        await user_service.add_source(test_user, SourceType.NEWSLETTER, config)

        # Verify in profile
        profile = await user_service.get_profile(test_user)
        assert SourceType.NEWSLETTER in profile.preferred_sources

        # Remove source
        await user_service.remove_source(test_user, SourceType.NEWSLETTER)

        # Verify removed from profile
        updated_profile = await user_service.get_profile(test_user)
        assert SourceType.NEWSLETTER not in updated_profile.preferred_sources

    @pytest.mark.asyncio
    async def test_remove_nonexistent_source(self, user_service, test_user):
        """Test removing non-existent source."""
        success = await user_service.remove_source(test_user, SourceType.TWITTER)

        # Should return False (no rows deleted)
        assert success is False

    @pytest.mark.asyncio
    async def test_get_source_config_nonexistent(self, user_service, test_user):
        """Test getting config for non-configured source."""
        config = await user_service.get_source_config(test_user, SourceType.DISCORD)

        assert config is None


class TestMultipleSources:
    """Test managing multiple content sources."""

    @pytest.mark.asyncio
    async def test_add_multiple_sources(self, user_service, test_user):
        """Test adding multiple different sources."""
        # Add multiple sources
        await user_service.add_source(
            test_user,
            SourceType.ARXIV,
            {"feeds": ["cs.AI"]}
        )
        await user_service.add_source(
            test_user,
            SourceType.YOUTUBE,
            {"channels": ["channel1"]}
        )
        await user_service.add_source(
            test_user,
            SourceType.GITHUB,
            {"repos": ["repo1"]}
        )

        # Verify all are configured
        arxiv_config = await user_service.get_source_config(test_user, SourceType.ARXIV)
        youtube_config = await user_service.get_source_config(test_user, SourceType.YOUTUBE)
        github_config = await user_service.get_source_config(test_user, SourceType.GITHUB)

        assert arxiv_config is not None
        assert youtube_config is not None
        assert github_config is not None

        # Verify profile has all sources
        profile = await user_service.get_profile(test_user)
        assert len(profile.preferred_sources) == 3
        assert SourceType.ARXIV in profile.preferred_sources
        assert SourceType.YOUTUBE in profile.preferred_sources
        assert SourceType.GITHUB in profile.preferred_sources


class TestProfilePersistence:
    """Test profile data persistence and retrieval."""

    @pytest.mark.asyncio
    async def test_profile_timestamps(self, user_service, test_user):
        """Test profile timestamps are set correctly."""
        profile = await user_service.get_profile(test_user)

        assert profile.created_at is not None
        assert profile.updated_at is not None
        assert isinstance(profile.created_at, datetime)
        assert isinstance(profile.updated_at, datetime)

    @pytest.mark.asyncio
    async def test_profile_updated_at_changes(self, user_service, test_user):
        """Test updated_at changes when profile is modified."""
        initial_profile = await user_service.get_profile(test_user)
        initial_updated = initial_profile.updated_at

        # Small delay to ensure timestamp difference
        import asyncio
        await asyncio.sleep(0.1)

        # Update profile
        await user_service.update_profile(test_user, background="New background")

        # Check updated_at changed
        updated_profile = await user_service.get_profile(test_user)
        assert updated_profile.updated_at > initial_updated

    @pytest.mark.asyncio
    async def test_profile_data_integrity(self, user_service, test_user):
        """Test profile data is correctly stored and retrieved."""
        # Update with comprehensive data
        goals = ["Goal 1", "Goal 2", "Goal 3"]
        sources = [SourceType.ARXIV, SourceType.YOUTUBE, SourceType.GITHUB]

        await user_service.update_profile(
            test_user,
            background="Test background",
            goals=goals,
            time_budget_minutes=45,
            preferred_sources=sources,
            timezone="America/Los_Angeles"
        )

        # Retrieve and verify
        profile = await user_service.get_profile(test_user)

        assert profile.background == "Test background"
        assert profile.goals == goals
        assert profile.time_budget_minutes == 45
        assert set(profile.preferred_sources) == set(sources)
        assert profile.timezone == "America/Los_Angeles"
