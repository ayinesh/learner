"""User Module - Profile and preferences management."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from uuid import UUID

from src.shared.models import SourceType


@dataclass
class UserProfile:
    """User's learning profile."""

    user_id: UUID
    background: str  # Professional/educational background
    goals: list[str]  # Learning objectives
    time_budget_minutes: int  # Typical daily availability
    preferred_sources: list[SourceType]  # Selected content sources
    timezone: str
    onboarding_completed: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class UserLearningPattern:
    """Derived learning patterns from user behavior."""

    user_id: UUID
    avg_session_duration: float  # Minutes
    preferred_time_of_day: str | None  # morning, afternoon, evening, night
    completion_rate: float  # 0-1
    quiz_accuracy_trend: float  # Positive = improving
    feynman_score_trend: float  # Positive = improving
    days_since_last_session: int
    total_sessions: int
    current_streak: int
    longest_streak: int
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class OnboardingData:
    """Data collected during onboarding."""

    background: str
    goals: list[str]
    time_budget_minutes: int
    preferred_sources: list[SourceType]
    timezone: str
    initial_topics: list[str] | None = None  # Topics user wants to start with


class IUserService(Protocol):
    """Interface for user profile service.

    Manages user profiles, preferences, and derived learning patterns.
    """

    async def get_profile(self, user_id: UUID) -> UserProfile | None:
        """Get user's profile.

        Args:
            user_id: User's UUID

        Returns:
            UserProfile if exists, None otherwise
        """
        ...

    async def create_profile(self, user_id: UUID) -> UserProfile:
        """Create initial profile for new user.

        Args:
            user_id: User's UUID

        Returns:
            New UserProfile with defaults
        """
        ...

    async def update_profile(self, user_id: UUID, **updates) -> UserProfile:
        """Update user's profile.

        Args:
            user_id: User's UUID
            **updates: Fields to update

        Returns:
            Updated UserProfile
        """
        ...

    async def complete_onboarding(
        self, user_id: UUID, data: OnboardingData
    ) -> UserProfile:
        """Complete onboarding with collected data.

        Args:
            user_id: User's UUID
            data: Onboarding data

        Returns:
            Updated UserProfile with onboarding_completed=True
        """
        ...

    async def get_learning_pattern(self, user_id: UUID) -> UserLearningPattern | None:
        """Get user's derived learning patterns.

        Args:
            user_id: User's UUID

        Returns:
            UserLearningPattern if enough data exists, None otherwise
        """
        ...

    async def update_time_budget(self, user_id: UUID, minutes: int) -> UserProfile:
        """Update user's daily time budget.

        Args:
            user_id: User's UUID
            minutes: New time budget in minutes

        Returns:
            Updated UserProfile
        """
        ...

    async def add_source(self, user_id: UUID, source: SourceType, config: dict) -> bool:
        """Add a content source with configuration.

        Args:
            user_id: User's UUID
            source: Source type
            config: Source-specific configuration (feeds, accounts, etc.)

        Returns:
            True if added successfully
        """
        ...

    async def remove_source(self, user_id: UUID, source: SourceType) -> bool:
        """Remove a content source.

        Args:
            user_id: User's UUID
            source: Source type to remove

        Returns:
            True if removed successfully
        """
        ...

    async def get_source_config(self, user_id: UUID, source: SourceType) -> dict | None:
        """Get configuration for a content source.

        Args:
            user_id: User's UUID
            source: Source type

        Returns:
            Configuration dict if source is configured, None otherwise
        """
        ...
