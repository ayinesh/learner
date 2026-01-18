"""Agents Module - AI agent definitions and orchestration."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID

from src.shared.datetime_utils import utc_now

if TYPE_CHECKING:
    from src.modules.agents.learning_context import (
        AgentAction,
        AgentDiscoveries,
        AgentHandoffContext,
    )


class AgentType(str, Enum):
    """Types of learning agents."""

    CURRICULUM = "curriculum"
    SOCRATIC = "socratic"
    ASSESSMENT = "assessment"
    COACH = "coach"
    SCOUT = "scout"
    DRILL_SERGEANT = "drill_sergeant"


@dataclass
class AgentContext:
    """Context provided to agents for generating responses."""

    user_id: UUID
    session_id: UUID | None = None
    topic_id: UUID | None = None
    conversation_history: list[dict] = field(default_factory=list)
    user_profile: dict = field(default_factory=dict)
    learning_pattern: dict = field(default_factory=dict)
    current_progress: dict = field(default_factory=dict)
    additional_data: dict = field(default_factory=dict)


@dataclass
class MenuOption:
    """Represents a numbered option presented to the user.

    When agents present menus with numbered options (e.g., "1. Learn concepts"),
    they should include MenuOption objects so the orchestrator can route
    numeric inputs correctly.
    """

    number: str  # "1", "2", "3"
    label: str  # "Learn about ML concepts"
    agent: AgentType  # Target agent if this option is selected
    action: str | None = None  # Optional action hint for the target agent


@dataclass
class AgentResponse:
    """Response from an agent."""

    agent_type: AgentType
    message: str
    data: dict = field(default_factory=dict)  # Structured data (e.g., quiz, plan)
    suggested_next_agent: AgentType | None = None
    menu_options: list[MenuOption] | None = None  # Numbered options for routing
    end_conversation: bool = False
    timestamp: datetime = field(default_factory=utc_now)

    # Handoff context for next agent - enables seamless transitions
    # Contains summary of what this agent accomplished, gaps identified, etc.
    handoff_context: "AgentHandoffContext | None" = None

    # Discoveries made during this interaction (misconceptions, learning observations)
    # These are persisted and shared across all agents
    discoveries: "AgentDiscoveries | None" = None

    # Actions taken by this agent (for cross-agent coordination and logging)
    actions_taken: "list[AgentAction] | None" = None


@dataclass
class ConversationState:
    """State of an ongoing conversation."""

    user_id: UUID
    session_id: UUID | None
    current_agent: AgentType
    history: list[dict]  # [{role, content, agent_type, timestamp}]
    context: dict
    started_at: datetime
    last_activity: datetime


class BaseAgent(ABC):
    """Abstract base class for all learning agents.

    Each agent is a specialized prompt configuration with specific
    behaviors and responsibilities.
    """

    @property
    @abstractmethod
    def agent_type(self) -> AgentType:
        """Return the type of this agent."""
        ...

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Return the system prompt for this agent."""
        ...

    @abstractmethod
    async def respond(
        self,
        context: AgentContext,
        user_message: str,
    ) -> AgentResponse:
        """Generate a response to user message.

        Args:
            context: Agent context with user/session info
            user_message: User's message

        Returns:
            AgentResponse
        """
        ...


class IAgentOrchestrator(Protocol):
    """Interface for agent orchestration.

    The orchestrator manages conversation flow, routes messages to
    appropriate agents, and maintains conversation state. Users
    experience a single coherent AI while the orchestrator switches
    between specialized agents.
    """

    async def route_message(
        self,
        user_id: UUID,
        message: str,
        session_id: UUID | None = None,
    ) -> AgentResponse:
        """Route a message to the appropriate agent.

        The orchestrator decides which agent should handle the message
        based on conversation state and message content.

        Args:
            user_id: User sending the message
            message: User's message
            session_id: Optional session context

        Returns:
            AgentResponse from the handling agent
        """
        ...

    async def get_conversation_state(self, user_id: UUID) -> ConversationState | None:
        """Get current conversation state for user.

        Args:
            user_id: User

        Returns:
            ConversationState or None if no active conversation
        """
        ...

    async def reset_conversation(self, user_id: UUID) -> None:
        """Reset conversation state for user.

        Args:
            user_id: User
        """
        ...

    async def force_agent(
        self,
        user_id: UUID,
        agent_type: AgentType,
        message: str,
        session_id: UUID | None = None,
    ) -> AgentResponse:
        """Force routing to a specific agent.

        Used when a specific agent is needed regardless of context
        (e.g., starting a Feynman dialogue).

        Args:
            user_id: User
            agent_type: Agent to route to
            message: User's message
            session_id: Optional session context

        Returns:
            AgentResponse from the specified agent
        """
        ...

    async def transition_to(
        self,
        user_id: UUID,
        agent_type: AgentType,
        transition_message: str | None = None,
    ) -> AgentResponse:
        """Transition conversation to a different agent.

        Used for smooth handoffs between agents during a session.

        Args:
            user_id: User
            agent_type: Agent to transition to
            transition_message: Optional message to provide context

        Returns:
            AgentResponse from the new agent
        """
        ...


# Individual agent interfaces for specific behaviors


class ICurriculumAgent(Protocol):
    """Curriculum agent - plans learning paths."""

    async def generate_learning_path(
        self,
        user_id: UUID,
        goals: list[str],
        time_horizon_days: int = 30,
    ) -> dict:
        """Generate a learning path for user's goals.

        Returns:
            Learning path with topics, sequence, and timeline
        """
        ...

    async def recommend_next_topic(self, user_id: UUID) -> dict:
        """Recommend the next topic to learn.

        Returns:
            Topic recommendation with reasoning
        """
        ...


class ISocraticAgent(Protocol):
    """Socratic agent - the confused student for Feynman dialogues."""

    async def start_dialogue(
        self,
        topic: str,
        user_context: dict,
    ) -> str:
        """Start a Feynman dialogue.

        Returns:
            Opening message asking user to explain
        """
        ...

    async def probe_explanation(
        self,
        explanation: str,
        dialogue_history: list[dict],
        topic: str,
    ) -> tuple[str, list[str]]:
        """Probe user's explanation with follow-up questions.

        Returns:
            (response_message, gaps_identified)
        """
        ...


class ICoachAgent(Protocol):
    """Coach agent - motivation and session management."""

    async def generate_session_opening(
        self,
        user_id: UUID,
        session_context: dict,
    ) -> str:
        """Generate session opening message.

        Returns:
            Personalized greeting and context
        """
        ...

    async def generate_session_closing(
        self,
        session_summary: dict,
    ) -> str:
        """Generate session closing message.

        Returns:
            Summary and encouragement
        """
        ...

    async def generate_recovery_message(
        self,
        days_missed: int,
        recovery_plan: dict,
    ) -> str:
        """Generate message for returning after missed days.

        Returns:
            Encouraging message with recovery plan
        """
        ...
