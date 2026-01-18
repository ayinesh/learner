"""Conversation Context Builder - Optimized context management for agents.

This module provides utilities for building conversation context that:
1. Uses sliding window to limit history (saves tokens)
2. Summarizes learning context into a compact format
3. Formats history for Claude's native multi-turn API
4. Prevents agents from "forgetting" previous conversation

Usage:
    builder = ConversationContextBuilder(context)

    # Option 1: Get formatted messages for complete_with_history()
    messages = builder.build_messages(current_message)
    response = await llm.complete_with_history(messages, system_prompt)

    # Option 2: Get context summary to inject into a prompt
    summary = builder.build_context_summary()
    prompt = f"{summary}\n\nUser: {message}"
"""

import logging
from dataclasses import dataclass
from typing import Any

from src.modules.agents.interface import AgentContext
from src.modules.agents.learning_context import (
    AgentDiscoveries,
    AgentHandoffContext,
    OnboardingState,
    SharedLearningContext,
)
from src.shared.constants import (
    CONTEXT_HISTORY_WINDOW_SIZE,
    CONTEXT_SUMMARY_MAX_CHARS,
)

logger = logging.getLogger(__name__)


# Default values if constants not defined
DEFAULT_HISTORY_WINDOW = 10  # Last 10 exchanges
DEFAULT_SUMMARY_MAX_CHARS = 500


@dataclass
class ContextSummary:
    """Compact summary of user's learning context."""

    primary_goal: str | None
    current_focus: str | None
    learning_style: str | None
    background: str | None
    onboarding_complete: bool
    questions_answered: list[str]
    path_created: bool
    recent_topics: list[str]

    def to_text(self) -> str:
        """Format as compact text for injection into prompts."""
        parts = []

        if self.primary_goal:
            parts.append(f"Goal: {self.primary_goal}")
        if self.current_focus:
            parts.append(f"Focus: {self.current_focus}")
        if self.learning_style:
            parts.append(f"Style: {self.learning_style}")
        if self.background:
            parts.append(f"Background: {self.background}")
        if self.recent_topics:
            parts.append(f"Recent: {', '.join(self.recent_topics[:3])}")

        # Status flags
        status = []
        if self.onboarding_complete:
            status.append("onboarding done")
        if self.path_created:
            status.append("path created")
        if self.questions_answered:
            status.append(f"answered: {', '.join(self.questions_answered)}")

        if status:
            parts.append(f"Status: {', '.join(status)}")

        return " | ".join(parts) if parts else "New user, no context yet"


class ConversationContextBuilder:
    """Builds optimized context for agent LLM calls.

    This class solves the "amnesia" problem where agents forget previous
    conversation by:
    1. Extracting relevant history within a sliding window
    2. Compacting learning context into a token-efficient summary
    3. Formatting messages for Claude's native multi-turn API
    """

    def __init__(
        self,
        context: AgentContext,
        history_window: int | None = None,
        max_summary_chars: int | None = None,
    ) -> None:
        """Initialize context builder.

        Args:
            context: The AgentContext from orchestrator
            history_window: Number of recent exchanges to include (default: 10)
            max_summary_chars: Max chars for context summary (default: 500)
        """
        self.context = context
        self.history_window = history_window or self._get_window_size()
        self.max_summary_chars = max_summary_chars or self._get_max_chars()

        # Extract learning context if available
        self.learning_ctx: SharedLearningContext | None = context.additional_data.get(
            "learning_context"
        )

    def _get_window_size(self) -> int:
        """Get history window size from constants or default."""
        try:
            return CONTEXT_HISTORY_WINDOW_SIZE
        except (ImportError, AttributeError):
            return DEFAULT_HISTORY_WINDOW

    def _get_max_chars(self) -> int:
        """Get max summary chars from constants or default."""
        try:
            return CONTEXT_SUMMARY_MAX_CHARS
        except (ImportError, AttributeError):
            return DEFAULT_SUMMARY_MAX_CHARS

    def build_context_summary(self) -> ContextSummary:
        """Build a compact summary of the user's learning context.

        Returns:
            ContextSummary with key information about the user
        """
        # Extract onboarding state if available
        onboarding_states = self.context.additional_data.get("onboarding_states", {})

        # Check both coach and curriculum onboarding
        questions_answered = []
        onboarding_complete = False

        for agent_type in ["coach", "curriculum"]:
            state_data = onboarding_states.get(agent_type, {})
            if state_data:
                if state_data.get("is_complete"):
                    onboarding_complete = True
                answers = state_data.get("answers_collected", {})
                questions_answered.extend(answers.keys())

        # Also check if onboarding state is in the context directly
        # (some agents store it differently)
        if not onboarding_complete:
            for key in self.context.additional_data:
                if "onboarding" in key.lower() and "complete" in str(
                    self.context.additional_data[key]
                ).lower():
                    onboarding_complete = True
                    break

        # Extract learning path status
        path_created = False
        if self.learning_ctx and self.learning_ctx.learning_path:
            path_created = len(self.learning_ctx.learning_path) > 0

        return ContextSummary(
            primary_goal=self.learning_ctx.primary_goal if self.learning_ctx else None,
            current_focus=self.learning_ctx.current_focus if self.learning_ctx else None,
            learning_style=(
                self.learning_ctx.preferences.get("learning_style")
                if self.learning_ctx else None
            ),
            background=(
                self.learning_ctx.constraints.get("background")
                or self.learning_ctx.constraints.get("programming_background")
                if self.learning_ctx else None
            ),
            onboarding_complete=onboarding_complete,
            questions_answered=list(set(questions_answered)),
            path_created=path_created,
            recent_topics=(
                self.learning_ctx.recent_topics[:5]
                if self.learning_ctx else []
            ),
        )

    def get_recent_history(self) -> list[dict]:
        """Get recent conversation history within the sliding window.

        Returns:
            List of recent history entries [{role, content, agent_type}]
        """
        history = self.context.conversation_history or []

        # Get last N entries (window size)
        return history[-self.history_window:] if history else []

    def build_messages(
        self,
        current_message: str,
        include_context_summary: bool = True,
    ) -> list[dict[str, str]]:
        """Build messages list for complete_with_history() API.

        This formats the conversation history as Claude expects:
        - Alternating user/assistant messages
        - Context summary prepended to first user message

        Args:
            current_message: The current user message
            include_context_summary: Whether to include context summary

        Returns:
            List of {"role": "user"|"assistant", "content": "..."}
        """
        messages = []

        # Get recent history
        recent = self.get_recent_history()

        # Convert history to Claude message format
        for entry in recent:
            role = entry.get("role", "user")
            content = entry.get("content", "")

            # Skip system messages, map to user/assistant only
            if role == "system":
                continue
            elif role == "assistant":
                messages.append({"role": "assistant", "content": content})
            else:
                messages.append({"role": "user", "content": content})

        # Ensure alternating pattern (Claude requires this)
        messages = self._ensure_alternating(messages)

        # Build current message with optional context
        current_content = current_message
        if include_context_summary:
            summary = self.build_context_summary()
            summary_text = summary.to_text()
            if summary_text and summary_text != "New user, no context yet":
                current_content = f"[Context: {summary_text}]\n\n{current_message}"

        messages.append({"role": "user", "content": current_content})

        return messages

    def _ensure_alternating(
        self,
        messages: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        """Ensure messages alternate between user and assistant.

        Claude API requires strict alternation. This merges consecutive
        same-role messages and ensures proper ordering.
        """
        if not messages:
            return []

        result = []
        prev_role = None

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == prev_role and result:
                # Merge with previous message of same role
                result[-1]["content"] += f"\n\n{content}"
            else:
                result.append({"role": role, "content": content})
                prev_role = role

        # Ensure first message is from user (add placeholder if needed)
        if result and result[0]["role"] == "assistant":
            result.insert(0, {"role": "user", "content": "[Starting conversation]"})

        return result

    def build_history_text(self, max_entries: int | None = None) -> str:
        """Build conversation history as formatted text.

        Use this when you need history as a string in a prompt,
        rather than as Claude API messages.

        Args:
            max_entries: Override for number of entries (default: history_window)

        Returns:
            Formatted history text
        """
        entries = max_entries or self.history_window
        recent = self.get_recent_history()[-entries:]

        if not recent:
            return "No previous conversation."

        lines = []
        for entry in recent:
            role = entry.get("role", "user").upper()
            content = entry.get("content", "")
            agent = entry.get("agent_type")

            # Truncate long messages
            if len(content) > 200:
                content = content[:200] + "..."

            if agent:
                lines.append(f"{role} ({agent}): {content}")
            else:
                lines.append(f"{role}: {content}")

        return "\n".join(lines)

    def get_what_we_know(self) -> str:
        """Get a summary of what's already been established.

        This is useful for preventing agents from re-asking questions.

        Returns:
            Text summary of established facts
        """
        summary = self.build_context_summary()

        facts = []

        if summary.primary_goal:
            facts.append(f"- User's goal: {summary.primary_goal}")
        if summary.learning_style:
            facts.append(f"- Prefers: {summary.learning_style} learning")
        if summary.background:
            facts.append(f"- Background: {summary.background}")
        if summary.questions_answered:
            facts.append(f"- Already asked about: {', '.join(summary.questions_answered)}")
        if summary.onboarding_complete:
            facts.append("- Onboarding is COMPLETE - don't re-ask setup questions")
        if summary.path_created:
            facts.append("- Learning path already created")

        if not facts:
            return "Nothing established yet - this may be a new conversation."

        return "What we already know:\n" + "\n".join(facts)


def build_agent_system_prompt(
    base_prompt: str,
    context: AgentContext,
) -> str:
    """Build an enhanced system prompt with context awareness.

    Injects context summary and handoff context into the system prompt
    so the LLM is aware of the user's state and what previous agents
    accomplished from the start.

    Args:
        base_prompt: The agent's base system prompt
        context: The AgentContext from orchestrator

    Returns:
        Enhanced system prompt with context and handoff information
    """
    builder = ConversationContextBuilder(context)
    what_we_know = builder.get_what_we_know()

    # Build handoff section if available
    handoff_section = _build_handoff_section(context)

    # Build discoveries section if available
    discoveries_section = _build_discoveries_section(context)

    return f"""{base_prompt}

IMPORTANT CONTEXT:
{what_we_know}
{handoff_section}
{discoveries_section}
CRITICAL: Do NOT re-ask questions that have already been answered.
Continue the conversation naturally based on what's established above.
If gaps were identified by a previous agent, prioritize addressing those gaps.
If you need to ask about something, first check if it's already known."""


def _build_handoff_section(context: AgentContext) -> str:
    """Build the handoff section for the system prompt.

    Args:
        context: The AgentContext containing handoff data

    Returns:
        Formatted handoff section or empty string
    """
    handoff: AgentHandoffContext | None = context.additional_data.get("handoff_context")

    if not handoff:
        return ""

    parts = [f"\nHANDOFF FROM PREVIOUS AGENT ({handoff.from_agent}):"]
    parts.append(f"Summary: {handoff.summary}")

    if handoff.gaps_identified:
        gaps_str = ", ".join(handoff.gaps_identified[:5])  # Limit to 5 for token efficiency
        parts.append(f"Gaps to address: {gaps_str}")

    if handoff.suggested_next_steps:
        steps_str = "; ".join(handoff.suggested_next_steps[:3])  # Limit to 3
        parts.append(f"Suggested actions: {steps_str}")

    if handoff.proficiency_observations:
        prof_items = list(handoff.proficiency_observations.items())[:5]  # Limit to 5
        prof_str = ", ".join(f"{topic}: {level:.0%}" for topic, level in prof_items)
        parts.append(f"Proficiency observations: {prof_str}")

    if handoff.key_points:
        points_str = "; ".join(handoff.key_points[:3])  # Limit to 3
        parts.append(f"Key points: {points_str}")

    if handoff.topics_covered:
        topics_str = ", ".join(handoff.topics_covered[:5])  # Limit to 5
        parts.append(f"Topics covered: {topics_str}")

    return "\n".join(parts)


def _build_discoveries_section(context: AgentContext) -> str:
    """Build the discoveries section for the system prompt.

    Args:
        context: The AgentContext containing discoveries data

    Returns:
        Formatted discoveries section or empty string
    """
    discoveries: AgentDiscoveries | None = context.additional_data.get("agent_discoveries")

    if not discoveries:
        return ""

    parts = ["\nAGENT DISCOVERIES (from previous interactions):"]

    if discoveries.needs_support:
        needs_str = ", ".join(discoveries.needs_support[:5])
        parts.append(f"Needs support in: {needs_str}")

    if discoveries.strengths:
        strengths_str = ", ".join(discoveries.strengths[:5])
        parts.append(f"Strong in: {strengths_str}")

    if discoveries.misconceptions:
        # Format misconceptions concisely
        misc_items = discoveries.misconceptions[:3]
        misc_strs = [
            f"{m.get('topic', 'unknown')}: {m.get('misconception', 'unknown')}"
            for m in misc_items
        ]
        parts.append(f"Misconceptions to address: {'; '.join(misc_strs)}")

    if discoveries.learning_observations:
        # Format observations concisely
        obs_items = discoveries.learning_observations[:3]
        obs_strs = [o.get("observation", "") for o in obs_items if o.get("observation")]
        if obs_strs:
            parts.append(f"Learning style notes: {'; '.join(obs_strs)}")

    # Only return if we have something beyond the header
    if len(parts) > 1:
        return "\n".join(parts)

    return ""
