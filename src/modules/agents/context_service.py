"""Learning Context Service - CRUD operations for shared learning context.

This service manages the SharedLearningContext that enables agents to work
together toward user goals. It handles:
- Creating/retrieving context from database
- Updating context fields
- Loading initial context from user profile
"""

import json
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text

from src.modules.agents.learning_context import (
    LearningPathStage,
    OnboardingState,
    SharedLearningContext,
)
from src.shared.database import get_db_session

logger = logging.getLogger(__name__)


class LearningContextService:
    """Service for managing shared learning context across agents."""

    async def get_context(self, user_id: UUID) -> SharedLearningContext:
        """Get or create learning context for a user.

        Args:
            user_id: The user's UUID

        Returns:
            SharedLearningContext for the user
        """
        async with get_db_session() as session:
            result = await session.execute(
                text("""
                    SELECT
                        user_id,
                        primary_goal,
                        current_focus,
                        learning_path,
                        preferences,
                        recent_topics,
                        identified_gaps,
                        constraints,
                        proficiency_levels,
                        created_at,
                        updated_at
                    FROM user_learning_context
                    WHERE user_id = :user_id
                """),
                {"user_id": user_id},
            )
            row = result.fetchone()

            if row:
                return self._row_to_context(row)

            # Create new context if none exists
            return await self._create_context(user_id)

    async def _create_context(self, user_id: UUID) -> SharedLearningContext:
        """Create a new learning context for a user."""
        async with get_db_session() as session:
            await session.execute(
                text("""
                    INSERT INTO user_learning_context (user_id)
                    VALUES (:user_id)
                    ON CONFLICT (user_id) DO NOTHING
                """),
                {"user_id": user_id},
            )

        return SharedLearningContext(user_id=user_id)

    async def update_context(
        self,
        user_id: UUID,
        updates: dict[str, Any],
    ) -> SharedLearningContext:
        """Update specific fields of the context.

        Args:
            user_id: The user's UUID
            updates: Dictionary of field names to new values

        Returns:
            Updated SharedLearningContext
        """
        # Validate and prepare updates
        allowed_fields = {
            "primary_goal",
            "current_focus",
            "learning_path",
            "preferences",
            "recent_topics",
            "identified_gaps",
            "constraints",
            "proficiency_levels",
        }

        valid_updates = {k: v for k, v in updates.items() if k in allowed_fields}

        if not valid_updates:
            return await self.get_context(user_id)

        # Build dynamic update query
        set_clauses = []
        params = {"user_id": user_id}

        for field, value in valid_updates.items():
            if field in ("learning_path", "preferences", "constraints", "proficiency_levels"):
                # JSONB fields - use CAST() instead of :: to avoid parameter confusion
                set_clauses.append(f"{field} = CAST(:{field} AS jsonb)")
                params[field] = json.dumps(value) if not isinstance(value, str) else value
            elif field in ("recent_topics", "identified_gaps"):
                # TEXT[] fields
                set_clauses.append(f"{field} = :{field}")
                params[field] = value
            else:
                # TEXT fields
                set_clauses.append(f"{field} = :{field}")
                params[field] = value

        query = f"""
            UPDATE user_learning_context
            SET {', '.join(set_clauses)}, updated_at = NOW()
            WHERE user_id = :user_id
        """

        async with get_db_session() as session:
            await session.execute(text(query), params)

        logger.debug(f"Updated context for user {user_id}: {list(valid_updates.keys())}")
        return await self.get_context(user_id)

    async def set_primary_goal(self, user_id: UUID, goal: str) -> None:
        """Set the user's primary learning goal.

        Args:
            user_id: The user's UUID
            goal: The primary learning goal (e.g., "become an ML expert")
        """
        await self.update_context(user_id, {"primary_goal": goal})
        logger.info(f"Set primary goal for user {user_id}: {goal}")

    async def update_current_focus(self, user_id: UUID, focus: str) -> None:
        """Update what the user is currently focusing on.

        Args:
            user_id: The user's UUID
            focus: The current focus area (e.g., "math foundations")
        """
        # Also add to recent topics
        context = await self.get_context(user_id)
        recent = context.recent_topics.copy()
        if focus not in recent:
            recent.insert(0, focus)
            recent = recent[:10]  # Keep max 10

        await self.update_context(
            user_id,
            {"current_focus": focus, "recent_topics": recent},
        )
        logger.info(f"Updated focus for user {user_id}: {focus}")

    async def add_learning_path_stage(
        self,
        user_id: UUID,
        stage: LearningPathStage,
    ) -> None:
        """Add a stage to the learning path.

        Args:
            user_id: The user's UUID
            stage: The learning path stage to add
        """
        context = await self.get_context(user_id)
        path = context.learning_path.copy()

        # Check if stage already exists
        existing_idx = next(
            (i for i, s in enumerate(path) if s.topic == stage.topic),
            None,
        )

        if existing_idx is not None:
            path[existing_idx] = stage
        else:
            path.append(stage)

        # Serialize for database
        path_data = [
            {
                "topic": s.topic,
                "status": s.status,
                "progress": s.progress,
                "milestone": s.milestone,
                "parent_goal": s.parent_goal,
            }
            for s in path
        ]

        await self.update_context(user_id, {"learning_path": path_data})

    async def update_stage_progress(
        self,
        user_id: UUID,
        topic: str,
        progress: float,
        status: str | None = None,
    ) -> None:
        """Update progress for a learning path stage.

        Args:
            user_id: The user's UUID
            topic: The topic to update
            progress: Progress value (0.0 to 1.0)
            status: Optional new status
        """
        context = await self.get_context(user_id)
        path = context.learning_path.copy()

        for stage in path:
            if stage.topic == topic:
                stage.progress = progress
                if status:
                    stage.status = status
                elif progress >= 1.0:
                    stage.status = "completed"
                elif progress > 0:
                    stage.status = "in_progress"
                break

        path_data = [
            {
                "topic": s.topic,
                "status": s.status,
                "progress": s.progress,
                "milestone": s.milestone,
                "parent_goal": s.parent_goal,
            }
            for s in path
        ]

        await self.update_context(user_id, {"learning_path": path_data})

    async def record_preference(
        self,
        user_id: UUID,
        key: str,
        value: Any,
    ) -> None:
        """Record a discovered preference.

        Args:
            user_id: The user's UUID
            key: Preference key (e.g., "learning_style")
            value: Preference value (e.g., "hands-on")
        """
        context = await self.get_context(user_id)
        prefs = context.preferences.copy()
        prefs[key] = value
        await self.update_context(user_id, {"preferences": prefs})

    async def record_gap(self, user_id: UUID, gap: str) -> None:
        """Record an identified knowledge gap.

        Args:
            user_id: The user's UUID
            gap: The knowledge gap description
        """
        context = await self.get_context(user_id)
        gaps = context.identified_gaps.copy()
        if gap not in gaps:
            gaps.append(gap)
        await self.update_context(user_id, {"identified_gaps": gaps})

    async def update_proficiency(
        self,
        user_id: UUID,
        topic: str,
        level: float,
    ) -> None:
        """Update proficiency for a topic.

        Args:
            user_id: The user's UUID
            topic: The topic
            level: Proficiency level (0.0 to 1.0)
        """
        context = await self.get_context(user_id)
        levels = context.proficiency_levels.copy()
        levels[topic] = max(0.0, min(1.0, level))  # Clamp to 0-1
        await self.update_context(user_id, {"proficiency_levels": levels})

    async def load_from_user_profile(self, user_id: UUID) -> None:
        """Initialize context from existing user profile data.

        Loads goals, background, and preferences from the user_profiles table
        and populates the learning context.

        Args:
            user_id: The user's UUID
        """
        try:
            from src.modules.user import get_user_service

            user_service = get_user_service()
            profile = await user_service.get_profile(user_id)

            if not profile:
                return

            updates = {}

            # Extract primary goal from profile goals
            if hasattr(profile, "goals") and profile.goals:
                if isinstance(profile.goals, list) and len(profile.goals) > 0:
                    updates["primary_goal"] = profile.goals[0]
                elif isinstance(profile.goals, str):
                    updates["primary_goal"] = profile.goals

            # Extract constraints from profile
            constraints = {}
            if hasattr(profile, "time_budget_minutes") and profile.time_budget_minutes:
                constraints["time_per_day_minutes"] = profile.time_budget_minutes
            if hasattr(profile, "background") and profile.background:
                constraints["background"] = profile.background

            if constraints:
                updates["constraints"] = constraints

            # Extract preferences from profile
            preferences = {}
            if hasattr(profile, "learning_style") and profile.learning_style:
                preferences["learning_style"] = profile.learning_style

            if preferences:
                updates["preferences"] = preferences

            if updates:
                await self.update_context(user_id, updates)
                logger.info(f"Loaded context from profile for user {user_id}")

        except Exception as e:
            logger.warning(f"Could not load profile for user {user_id}: {e}")

    def _row_to_context(self, row) -> SharedLearningContext:
        """Convert database row to SharedLearningContext."""
        learning_path = []
        if row.learning_path:
            path_data = row.learning_path if isinstance(row.learning_path, list) else json.loads(row.learning_path)
            learning_path = [
                LearningPathStage(
                    topic=stage["topic"],
                    status=stage.get("status", "not_started"),
                    progress=stage.get("progress", 0.0),
                    milestone=stage.get("milestone"),
                    parent_goal=stage.get("parent_goal"),
                )
                for stage in path_data
            ]

        preferences = row.preferences if isinstance(row.preferences, dict) else json.loads(row.preferences or "{}")
        constraints = row.constraints if isinstance(row.constraints, dict) else json.loads(row.constraints or "{}")
        proficiency = row.proficiency_levels if isinstance(row.proficiency_levels, dict) else json.loads(row.proficiency_levels or "{}")

        return SharedLearningContext(
            user_id=row.user_id,
            primary_goal=row.primary_goal,
            current_focus=row.current_focus,
            learning_path=learning_path,
            preferences=preferences,
            recent_topics=list(row.recent_topics) if row.recent_topics else [],
            identified_gaps=list(row.identified_gaps) if row.identified_gaps else [],
            constraints=constraints,
            proficiency_levels=proficiency,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    # ===================
    # Onboarding State Management
    # ===================

    async def get_onboarding_state(
        self,
        user_id: UUID,
        agent_type: str,
    ) -> OnboardingState | None:
        """Get onboarding state for a specific agent.

        Args:
            user_id: The user's UUID
            agent_type: The agent type (e.g., "curriculum", "coach")

        Returns:
            OnboardingState if exists, None otherwise
        """
        async with get_db_session() as session:
            result = await session.execute(
                text("""
                    SELECT onboarding_states->:agent_type AS state
                    FROM user_learning_context
                    WHERE user_id = :user_id
                """),
                {"user_id": user_id, "agent_type": agent_type},
            )
            row = result.fetchone()

            if row and row.state:
                state_data = row.state if isinstance(row.state, dict) else json.loads(row.state)
                return OnboardingState.from_dict(state_data)

        return None

    async def save_onboarding_state(
        self,
        user_id: UUID,
        state: OnboardingState,
    ) -> None:
        """Save onboarding state for an agent.

        Args:
            user_id: The user's UUID
            state: The onboarding state to save
        """
        agent_type = state.agent_type

        async with get_db_session() as session:
            # Update the onboarding_states JSONB field
            # Use CAST() instead of :: to avoid SQLAlchemy parameter confusion
            await session.execute(
                text("""
                    UPDATE user_learning_context
                    SET onboarding_states = COALESCE(onboarding_states, CAST('{}' AS jsonb)) || CAST(:state_update AS jsonb),
                        updated_at = NOW()
                    WHERE user_id = :user_id
                """),
                {
                    "user_id": user_id,
                    "state_update": json.dumps({agent_type: state.to_dict()}),
                },
            )

        logger.debug(f"Saved onboarding state for user {user_id}, agent {agent_type}")

    async def clear_onboarding_state(
        self,
        user_id: UUID,
        agent_type: str,
    ) -> None:
        """Clear onboarding state for an agent.

        Args:
            user_id: The user's UUID
            agent_type: The agent type to clear
        """
        async with get_db_session() as session:
            await session.execute(
                text("""
                    UPDATE user_learning_context
                    SET onboarding_states = onboarding_states - :agent_type,
                        updated_at = NOW()
                    WHERE user_id = :user_id
                """),
                {"user_id": user_id, "agent_type": agent_type},
            )

        logger.debug(f"Cleared onboarding state for user {user_id}, agent {agent_type}")


# Singleton instance
_context_service: LearningContextService | None = None


def get_context_service() -> LearningContextService:
    """Get the singleton LearningContextService instance."""
    global _context_service
    if _context_service is None:
        _context_service = LearningContextService()
    return _context_service
