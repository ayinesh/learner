"""User Service - Profile and learning pattern management implementation."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update, delete

from src.modules.user.interface import OnboardingData, UserLearningPattern, UserProfile
from src.modules.user.models import (
    UserProfileModel,
    UserSourceConfigModel,
)
# UserLearningPatternModel is in session module to avoid duplicate table definitions
from src.modules.session.models import UserLearningPatternModel
from src.shared.database import get_db_session
from src.shared.models import SourceType


class UserService:
    """User profile and learning pattern service implementation.

    Manages user profiles, preferences, content source configurations,
    and derived learning patterns.
    """

    # ===================
    # Model Conversions
    # ===================

    def _profile_model_to_profile(self, profile_model: UserProfileModel) -> UserProfile:
        """Convert UserProfileModel to UserProfile interface object."""
        # Convert database enum values to SourceType objects
        # Database stores lowercase values like "arxiv", convert to SourceType enum
        preferred_sources = []
        for source in profile_model.preferred_sources:
            # Source might be string or already SourceType
            if isinstance(source, str):
                preferred_sources.append(SourceType(source))
            else:
                preferred_sources.append(source)

        return UserProfile(
            user_id=profile_model.user_id,
            background=profile_model.background or "",
            goals=list(profile_model.goals),
            time_budget_minutes=profile_model.time_budget_minutes,
            preferred_sources=preferred_sources,
            timezone=profile_model.timezone,
            onboarding_completed=profile_model.onboarding_completed,
            created_at=profile_model.created_at,
            updated_at=profile_model.updated_at,
        )

    def _pattern_model_to_pattern(
        self, pattern_model: UserLearningPatternModel
    ) -> UserLearningPattern:
        """Convert UserLearningPatternModel to UserLearningPattern interface object."""
        return UserLearningPattern(
            user_id=pattern_model.user_id,
            avg_session_duration=pattern_model.avg_session_duration,
            preferred_time_of_day=pattern_model.preferred_time_of_day,
            completion_rate=pattern_model.completion_rate,
            quiz_accuracy_trend=pattern_model.quiz_accuracy_trend,
            feynman_score_trend=pattern_model.feynman_score_trend,
            days_since_last_session=pattern_model.days_since_last_session,
            total_sessions=pattern_model.total_sessions,
            current_streak=pattern_model.current_streak,
            longest_streak=pattern_model.longest_streak,
            updated_at=pattern_model.updated_at,
        )

    # ===================
    # Profile Methods
    # ===================

    async def get_profile(self, user_id: UUID) -> UserProfile | None:
        """Get user's profile.

        Args:
            user_id: User's UUID

        Returns:
            UserProfile if exists, None otherwise
        """
        async with get_db_session() as session:
            result = await session.execute(
                select(UserProfileModel).where(UserProfileModel.user_id == user_id)
            )
            profile_model = result.scalar_one_or_none()

            if not profile_model:
                return None

            return self._profile_model_to_profile(profile_model)

    async def create_profile(self, user_id: UUID) -> UserProfile:
        """Create initial profile for new user.

        Args:
            user_id: User's UUID

        Returns:
            New UserProfile with defaults
        """
        async with get_db_session() as session:
            # Check if profile already exists
            existing = await session.execute(
                select(UserProfileModel).where(UserProfileModel.user_id == user_id)
            )
            if existing.scalar_one_or_none():
                raise ValueError(f"Profile already exists for user {user_id}")

            # Create new profile with defaults
            new_profile = UserProfileModel(
                user_id=user_id,
                background=None,
                goals=[],
                time_budget_minutes=30,
                preferred_sources=[],
                timezone="UTC",
                onboarding_completed=False,
            )

            session.add(new_profile)
            await session.flush()

            # Also create learning pattern entry
            learning_pattern = UserLearningPatternModel(
                user_id=user_id,
            )
            session.add(learning_pattern)

            await session.commit()

            return self._profile_model_to_profile(new_profile)

    async def update_profile(self, user_id: UUID, **updates) -> UserProfile:
        """Update user's profile.

        Args:
            user_id: User's UUID
            **updates: Fields to update

        Returns:
            Updated UserProfile

        Raises:
            ValueError: If profile not found
        """
        async with get_db_session() as session:
            # Get existing profile
            result = await session.execute(
                select(UserProfileModel).where(UserProfileModel.user_id == user_id)
            )
            profile_model = result.scalar_one_or_none()

            if not profile_model:
                raise ValueError(f"Profile not found for user {user_id}")

            # Convert SourceType enum to lowercase string values for database
            if "preferred_sources" in updates:
                converted_sources = []
                for source in updates["preferred_sources"]:
                    if isinstance(source, SourceType):
                        # Use .value to get lowercase string like "arxiv"
                        converted_sources.append(source.value)
                    elif isinstance(source, str):
                        # If it's already a string, ensure it's lowercase
                        converted_sources.append(source.lower())
                    else:
                        converted_sources.append(source)
                updates["preferred_sources"] = converted_sources

            # Update fields
            for key, value in updates.items():
                if hasattr(profile_model, key):
                    setattr(profile_model, key, value)

            # Update timestamp
            profile_model.updated_at = datetime.now(timezone.utc)

            await session.commit()
            await session.refresh(profile_model)

            return self._profile_model_to_profile(profile_model)

    async def complete_onboarding(
        self, user_id: UUID, data: OnboardingData
    ) -> UserProfile:
        """Complete onboarding with collected data.

        Args:
            user_id: User's UUID
            data: Onboarding data

        Returns:
            Updated UserProfile with onboarding_completed=True

        Raises:
            ValueError: If profile not found
        """
        # Convert SourceType list to string list for database
        preferred_sources = [source.value for source in data.preferred_sources]

        updates = {
            "background": data.background,
            "goals": data.goals,
            "time_budget_minutes": data.time_budget_minutes,
            "preferred_sources": preferred_sources,
            "timezone": data.timezone,
            "onboarding_completed": True,
        }

        # Store initial topics if provided (could be used by curriculum module)
        # For now, we'll just update the profile
        # In a full implementation, initial_topics would be passed to curriculum service

        return await self.update_profile(user_id, **updates)

    # ===================
    # Learning Pattern Methods
    # ===================

    async def get_learning_pattern(self, user_id: UUID) -> UserLearningPattern | None:
        """Get user's derived learning patterns.

        Args:
            user_id: User's UUID

        Returns:
            UserLearningPattern if enough data exists, None otherwise
        """
        async with get_db_session() as session:
            result = await session.execute(
                select(UserLearningPatternModel).where(
                    UserLearningPatternModel.user_id == user_id
                )
            )
            pattern_model = result.scalar_one_or_none()

            if not pattern_model:
                return None

            # Only return pattern if user has completed at least one session
            if pattern_model.total_sessions == 0:
                return None

            return self._pattern_model_to_pattern(pattern_model)

    # ===================
    # Convenience Methods
    # ===================

    async def update_time_budget(self, user_id: UUID, minutes: int) -> UserProfile:
        """Update user's daily time budget.

        Args:
            user_id: User's UUID
            minutes: New time budget in minutes

        Returns:
            Updated UserProfile

        Raises:
            ValueError: If profile not found or minutes invalid
        """
        if minutes < 5 or minutes > 480:
            raise ValueError("Time budget must be between 5 and 480 minutes")

        return await self.update_profile(user_id, time_budget_minutes=minutes)

    # ===================
    # Source Configuration Methods
    # ===================

    async def add_source(self, user_id: UUID, source: SourceType, config: dict) -> bool:
        """Add a content source with configuration.

        Args:
            user_id: User's UUID
            source: Source type
            config: Source-specific configuration (feeds, accounts, etc.)

        Returns:
            True if added successfully
        """
        async with get_db_session() as session:
            # Check if source config already exists
            result = await session.execute(
                select(UserSourceConfigModel).where(
                    UserSourceConfigModel.user_id == user_id,
                    UserSourceConfigModel.source_type == source.value,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing configuration
                existing.config = config
                existing.enabled = True
                existing.updated_at = datetime.now(timezone.utc)
            else:
                # Create new source configuration
                source_config = UserSourceConfigModel(
                    user_id=user_id,
                    source_type=source.value,
                    config=config,
                    enabled=True,
                )
                session.add(source_config)

            # Also add to profile's preferred_sources if not already there
            profile_result = await session.execute(
                select(UserProfileModel).where(UserProfileModel.user_id == user_id)
            )
            profile = profile_result.scalar_one_or_none()

            if profile and source.value not in profile.preferred_sources:
                # Get current sources and add new one
                current_sources = list(profile.preferred_sources)
                current_sources.append(source.value)
                profile.preferred_sources = current_sources
                profile.updated_at = datetime.now(timezone.utc)

            await session.commit()
            return True

    async def remove_source(self, user_id: UUID, source: SourceType) -> bool:
        """Remove a content source.

        Args:
            user_id: User's UUID
            source: Source type to remove

        Returns:
            True if removed successfully
        """
        async with get_db_session() as session:
            # Delete source configuration
            result = await session.execute(
                delete(UserSourceConfigModel).where(
                    UserSourceConfigModel.user_id == user_id,
                    UserSourceConfigModel.source_type == source.value,
                )
            )

            # Also remove from profile's preferred_sources
            profile_result = await session.execute(
                select(UserProfileModel).where(UserProfileModel.user_id == user_id)
            )
            profile = profile_result.scalar_one_or_none()

            if profile and source.value in profile.preferred_sources:
                # Remove source from list
                current_sources = [s for s in profile.preferred_sources if s != source.value]
                profile.preferred_sources = current_sources
                profile.updated_at = datetime.now(timezone.utc)

            await session.commit()
            return result.rowcount > 0

    async def get_source_config(self, user_id: UUID, source: SourceType) -> dict | None:
        """Get configuration for a content source.

        Args:
            user_id: User's UUID
            source: Source type

        Returns:
            Configuration dict if source is configured, None otherwise
        """
        async with get_db_session() as session:
            result = await session.execute(
                select(UserSourceConfigModel).where(
                    UserSourceConfigModel.user_id == user_id,
                    UserSourceConfigModel.source_type == source.value,
                    UserSourceConfigModel.enabled == True,
                )
            )
            source_config = result.scalar_one_or_none()

            if not source_config:
                return None

            return dict(source_config.config)


# Singleton instance
_user_service: UserService | None = None


def get_user_service() -> UserService:
    """Get user service singleton."""
    global _user_service
    if _user_service is None:
        _user_service = UserService()
    return _user_service
