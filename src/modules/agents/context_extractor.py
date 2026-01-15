"""Context Extractor - LLM-based extraction of learning context from conversations.

This module analyzes user messages to extract:
- Learning goals ("I want to learn ML" -> primary_goal)
- Focus shifts ("Let's focus on math" -> current_focus)
- Preferences ("I prefer hands-on learning" -> preferences)
- Constraints ("I have 30 min/day" -> constraints)
"""

import json
import logging
from typing import Any
from uuid import UUID

from src.modules.agents.interface import AgentType
from src.modules.agents.learning_context import ContextUpdate, SharedLearningContext
from src.modules.llm.service import LLMService, get_llm_service

logger = logging.getLogger(__name__)


class ContextExtractor:
    """Extracts learning context updates from user messages using LLM analysis."""

    def __init__(self, llm_service: LLMService | None = None):
        self._llm = llm_service or get_llm_service()
        self._cache: dict[str, list[ContextUpdate]] = {}

    async def extract_from_message(
        self,
        message: str,
        current_context: SharedLearningContext,
        agent_type: AgentType | None = None,
    ) -> list[ContextUpdate]:
        """Extract context updates from a user message.

        Args:
            message: The user's message
            current_context: Current learning context
            agent_type: Which agent is handling the message

        Returns:
            List of ContextUpdate objects to apply
        """
        # Skip very short messages
        if len(message.strip()) < 5:
            return []

        # Check cache to avoid duplicate extraction
        cache_key = f"{current_context.user_id}:{hash(message)}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            updates = await self._extract_with_llm(message, current_context)
            self._cache[cache_key] = updates

            # Limit cache size
            if len(self._cache) > 100:
                # Remove oldest entries
                keys_to_remove = list(self._cache.keys())[:50]
                for key in keys_to_remove:
                    del self._cache[key]

            return updates

        except Exception as e:
            logger.warning(f"Context extraction failed: {e}")
            return []

    async def _extract_with_llm(
        self,
        message: str,
        context: SharedLearningContext,
    ) -> list[ContextUpdate]:
        """Use LLM to extract context updates from a message."""

        system_prompt = """You are a learning context analyzer. Your job is to extract learning-related information from user messages.

Analyze the user's message and identify if they have stated or implied any of the following:

1. PRIMARY_GOAL - A learning goal (e.g., "I want to learn machine learning", "I want to become a data scientist")
2. CURRENT_FOCUS - A shift in focus area (e.g., "Let's start with math", "I want to focus on Python now")
3. PREFERENCE - A learning preference (e.g., "I prefer hands-on projects", "I like visual explanations")
4. CONSTRAINT - A time or resource constraint (e.g., "I have 30 minutes per day", "I need to learn this in 3 months")
5. BACKGROUND - Their current knowledge level (e.g., "I'm a complete beginner", "I know Python but not ML")

Return a JSON array of updates. Each update should have:
- field: The field name (primary_goal, current_focus, preference_*, constraint_*, background)
- value: The extracted value
- confidence: A number from 0.0 to 1.0 indicating confidence
- reason: Brief explanation of why you extracted this

If no relevant information is found, return an empty array: []

IMPORTANT:
- Only extract information that is explicitly stated or strongly implied
- Do not infer goals from questions (asking "what is ML?" is not a goal to learn ML)
- Set confidence appropriately: explicit statements = 0.9+, implied = 0.6-0.8
- For current_focus, only extract if the user is clearly shifting to a new topic within their learning path"""

        user_prompt = f"""Current context:
- Primary goal: {context.primary_goal or 'Not set'}
- Current focus: {context.current_focus or 'Not set'}
- Recent topics: {', '.join(context.recent_topics[:3]) if context.recent_topics else 'None'}

User message:
"{message}"

Extract any learning context updates from this message. Return JSON array only."""

        try:
            response = await self._llm.complete(
                prompt=user_prompt,
                system_prompt=system_prompt,
                max_tokens=500,
                temperature=0.1,  # Low temperature for consistent extraction
            )

            # Parse JSON response
            content = response.content.strip()

            # Handle markdown code blocks
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            updates_data = json.loads(content)

            if not isinstance(updates_data, list):
                return []

            updates = []
            for item in updates_data:
                if not isinstance(item, dict):
                    continue

                field = item.get("field", "")
                value = item.get("value")
                confidence = float(item.get("confidence", 0.5))
                reason = item.get("reason", "")

                # Map extracted fields to our context fields
                mapped_field, mapped_value = self._map_extraction(field, value)

                if mapped_field and mapped_value:
                    updates.append(
                        ContextUpdate(
                            field=mapped_field,
                            value=mapped_value,
                            confidence=confidence,
                            source="user_stated" if confidence >= 0.8 else "inferred",
                            reason=reason,
                        )
                    )

            return updates

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse extraction response: {e}")
            return []
        except Exception as e:
            logger.warning(f"Extraction error: {e}")
            return []

    def _map_extraction(
        self,
        field: str,
        value: Any,
    ) -> tuple[str | None, Any]:
        """Map extracted field names to our context field names."""
        field_lower = field.lower()

        if "primary_goal" in field_lower or field_lower == "goal":
            return "primary_goal", str(value)

        if "current_focus" in field_lower or "focus" in field_lower:
            return "current_focus", str(value)

        if "preference" in field_lower:
            # Extract preference key from field name
            # e.g., "preference_learning_style" -> ("learning_style", value)
            key = field_lower.replace("preference_", "").replace("preference", "").strip("_")
            if not key:
                key = "general"
            return f"preference:{key}", value

        if "constraint" in field_lower:
            key = field_lower.replace("constraint_", "").replace("constraint", "").strip("_")
            if not key:
                key = "general"
            return f"constraint:{key}", value

        if "background" in field_lower or "experience" in field_lower:
            return "constraint:background", str(value)

        return None, None


async def apply_context_updates(
    user_id: UUID,
    updates: list[ContextUpdate],
    min_confidence: float = 0.7,
) -> dict[str, Any]:
    """Apply context updates to the database.

    Args:
        user_id: User's UUID
        updates: List of ContextUpdate objects
        min_confidence: Minimum confidence to apply an update

    Returns:
        Dictionary of applied updates
    """
    from src.modules.agents.context_service import get_context_service

    context_service = get_context_service()
    applied = {}

    for update in updates:
        if update.confidence < min_confidence:
            logger.debug(
                f"Skipping low-confidence update: {update.field}={update.value} "
                f"(confidence={update.confidence})"
            )
            continue

        try:
            if update.field == "primary_goal":
                await context_service.set_primary_goal(user_id, update.value)
                applied["primary_goal"] = update.value

            elif update.field == "current_focus":
                await context_service.update_current_focus(user_id, update.value)
                applied["current_focus"] = update.value

            elif update.field.startswith("preference:"):
                key = update.field.split(":", 1)[1]
                await context_service.record_preference(user_id, key, update.value)
                applied[f"preference_{key}"] = update.value

            elif update.field.startswith("constraint:"):
                key = update.field.split(":", 1)[1]
                context = await context_service.get_context(user_id)
                constraints = context.constraints.copy()
                constraints[key] = update.value
                await context_service.update_context(user_id, {"constraints": constraints})
                applied[f"constraint_{key}"] = update.value

            logger.info(
                f"Applied context update for user {user_id}: "
                f"{update.field}={update.value} (confidence={update.confidence})"
            )

        except Exception as e:
            logger.error(f"Failed to apply update {update.field}: {e}")

    return applied


# Singleton instance
_extractor: ContextExtractor | None = None


def get_context_extractor() -> ContextExtractor:
    """Get the singleton ContextExtractor instance."""
    global _extractor
    if _extractor is None:
        _extractor = ContextExtractor()
    return _extractor
