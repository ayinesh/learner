"""Agent Orchestrator - Manages conversation flow between agents."""

import logging
import re
from typing import Any
from uuid import UUID

from src.modules.agents.interface import (
    AgentContext,
    AgentResponse,
    AgentType,
    BaseAgent,
    ConversationState,
    IAgentOrchestrator,
    MenuOption,
)
from src.modules.agents.socratic import SocraticAgent, get_socratic_agent
from src.modules.agents.coach import CoachAgent, get_coach_agent
from src.modules.agents.assessment_agent import AssessmentAgent, get_assessment_agent
from src.modules.agents.curriculum import CurriculumAgent, get_curriculum_agent
from src.modules.agents.scout import ScoutAgent, get_scout_agent
from src.modules.agents.drill_sergeant import DrillSergeantAgent, get_drill_sergeant_agent
from src.modules.agents.context_service import LearningContextService, get_context_service
from src.modules.agents.context_extractor import ContextExtractor, apply_context_updates, get_context_extractor
from src.modules.llm.service import LLMService, get_llm_service
from src.shared.feature_flags import FeatureFlags, get_feature_flags
from src.shared.datetime_utils import utc_now

logger = logging.getLogger(__name__)


class AgentOrchestrator(IAgentOrchestrator):
    """Orchestrates conversation flow between specialized learning agents.

    The orchestrator maintains conversation state, routes messages to the
    appropriate agent, and handles transitions between agents. Users
    experience a single coherent AI while the orchestrator intelligently
    switches between specialized agents based on context.
    """

    def __init__(
        self,
        llm_service: LLMService | None = None,
        socratic_agent: SocraticAgent | None = None,
        coach_agent: CoachAgent | None = None,
        assessment_agent: AssessmentAgent | None = None,
        curriculum_agent: CurriculumAgent | None = None,
        scout_agent: ScoutAgent | None = None,
        drill_sergeant_agent: DrillSergeantAgent | None = None,
        context_service: LearningContextService | None = None,
        context_extractor: ContextExtractor | None = None,
    ) -> None:
        self._llm = llm_service or get_llm_service()
        self._agents: dict[AgentType, BaseAgent] = {}
        self._flags = get_feature_flags()

        # Initialize agents
        self._agents[AgentType.SOCRATIC] = socratic_agent or get_socratic_agent()
        self._agents[AgentType.COACH] = coach_agent or get_coach_agent()
        self._agents[AgentType.ASSESSMENT] = assessment_agent or get_assessment_agent()
        self._agents[AgentType.CURRICULUM] = curriculum_agent or get_curriculum_agent()
        self._agents[AgentType.SCOUT] = scout_agent or get_scout_agent()
        self._agents[AgentType.DRILL_SERGEANT] = drill_sergeant_agent or get_drill_sergeant_agent()

        # In-memory state storage (fallback)
        self._conversation_states: dict[UUID, ConversationState] = {}

        # Persistent state store (used when FF_USE_DATABASE_PERSISTENCE enabled)
        self._state_store = None

        # Shared learning context service - enables agents to work together
        self._context_service = context_service or get_context_service()
        self._context_extractor = context_extractor or get_context_extractor()

        # Default agent for new conversations
        self._default_agent = AgentType.COACH

    async def route_message(
        self,
        user_id: UUID,
        message: str,
        session_id: UUID | None = None,
    ) -> AgentResponse:
        """Route a message to the appropriate agent.

        The orchestrator decides which agent should handle the message
        based on conversation state and message content.
        """
        # Get or create conversation state
        state = await self.get_conversation_state(user_id)

        if state is None:
            # New conversation - start with coach for session opening
            state = await self._create_conversation_state(user_id, session_id)

        # Update last activity
        state.last_activity = utc_now()

        # Determine which agent should handle this message
        target_agent = await self._determine_agent(state, message)

        # Update state with new agent if changed
        if target_agent != state.current_agent:
            state.current_agent = target_agent

        # Build context for the agent
        context = await self._build_agent_context(user_id, session_id, state)

        # Get the agent and generate response
        agent = self._agents.get(target_agent)
        if agent is None:
            # Fallback to coach if agent not found
            agent = self._agents[AgentType.COACH]

        response = await agent.respond(context, message)

        # Update conversation history
        state.history.append({
            "role": "user",
            "content": message,
            "agent_type": None,
            "timestamp": utc_now().isoformat(),
        })
        state.history.append({
            "role": "assistant",
            "content": response.message,
            "agent_type": response.agent_type.value,
            "timestamp": response.timestamp.isoformat(),
        })

        # Extract context updates from user message (LLM-based)
        # This enables agents to discover goals, preferences, and focus areas
        try:
            learning_context = await self._context_service.get_context(user_id)
            updates = await self._context_extractor.extract_from_message(
                message=message,
                current_context=learning_context,
                agent_type=state.current_agent,
            )
            if updates:
                applied = await apply_context_updates(user_id, updates, min_confidence=0.7)
                if applied:
                    logger.info(f"Applied context updates for user {user_id}: {list(applied.keys())}")
        except Exception as e:
            logger.warning(f"Context extraction failed: {e}")

        # Handle conversation end or agent transition
        if response.end_conversation:
            await self.reset_conversation(user_id)
        else:
            # Store menu options for numeric input routing
            if response.menu_options:
                state.context["menu_options"] = {
                    opt.number: {
                        "agent": opt.agent.value,  # Store as string for serialization safety
                        "action": opt.action,
                        "label": opt.label,
                    }
                    for opt in response.menu_options
                }
                logger.debug(f"Stored menu_options: {state.context['menu_options']}")

            # Store pending suggestion as fallback for ambiguous inputs
            if response.suggested_next_agent:
                state.current_agent = response.suggested_next_agent
                state.context["pending_next_agent"] = response.suggested_next_agent

        # Save state (in-memory and optionally to Redis)
        await self._save_conversation_state(user_id, state)

        return response

    async def get_conversation_state(self, user_id: UUID) -> ConversationState | None:
        """Get current conversation state for user.

        Uses Redis-backed state store when FF_USE_DATABASE_PERSISTENCE is enabled,
        falls back to in-memory storage otherwise.
        """
        if self._flags.is_enabled(FeatureFlags.USE_DATABASE_PERSISTENCE):
            try:
                store = await self._get_state_store()
                return await store.get(user_id)
            except Exception as e:
                logger.warning(f"Failed to get state from Redis, using in-memory: {e}")
                return self._conversation_states.get(user_id)
        return self._conversation_states.get(user_id)

    async def reset_conversation(self, user_id: UUID) -> None:
        """Reset conversation state for user."""
        if self._flags.is_enabled(FeatureFlags.USE_DATABASE_PERSISTENCE):
            try:
                store = await self._get_state_store()
                await store.delete(user_id)
            except Exception as e:
                logger.warning(f"Failed to delete state from Redis: {e}")

        # Always clear in-memory state as fallback
        if user_id in self._conversation_states:
            del self._conversation_states[user_id]

    async def _get_state_store(self):
        """Get the persistent state store (lazy initialization)."""
        if self._state_store is None:
            from src.modules.agents.state_store import get_state_store
            self._state_store = get_state_store()
        return self._state_store

    async def _save_conversation_state(self, user_id: UUID, state: ConversationState) -> None:
        """Save conversation state."""
        # Always save to in-memory for fast access
        self._conversation_states[user_id] = state

        # Also persist if feature flag enabled
        if self._flags.is_enabled(FeatureFlags.USE_DATABASE_PERSISTENCE):
            try:
                store = await self._get_state_store()
                await store.set(user_id, state)
            except Exception as e:
                logger.warning(f"Failed to persist state to Redis: {e}")

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
        """
        # Get or create state
        state = await self.get_conversation_state(user_id)
        if state is None:
            state = await self._create_conversation_state(user_id, session_id)

        # Force the agent type
        state.current_agent = agent_type
        await self._save_conversation_state(user_id, state)

        # Build context
        context = await self._build_agent_context(user_id, session_id, state)

        # Get agent and respond
        agent = self._agents.get(agent_type)
        if agent is None:
            raise ValueError(f"Agent type {agent_type} not available")

        response = await agent.respond(context, message)

        # Update history
        state.history.append({
            "role": "user",
            "content": message,
            "agent_type": None,
            "timestamp": utc_now().isoformat(),
        })
        state.history.append({
            "role": "assistant",
            "content": response.message,
            "agent_type": response.agent_type.value,
            "timestamp": response.timestamp.isoformat(),
        })

        return response

    async def transition_to(
        self,
        user_id: UUID,
        agent_type: AgentType,
        transition_message: str | None = None,
    ) -> AgentResponse:
        """Transition conversation to a different agent.

        Used for smooth handoffs between agents during a session.
        """
        state = await self.get_conversation_state(user_id)
        if state is None:
            raise ValueError(f"No active conversation for user {user_id}")

        old_agent = state.current_agent
        state.current_agent = agent_type

        # Build context
        context = await self._build_agent_context(user_id, state.session_id, state)

        # Add transition context
        if transition_message:
            context.additional_data["transition_from"] = old_agent.value
            context.additional_data["transition_message"] = transition_message

        # Get new agent
        agent = self._agents.get(agent_type)
        if agent is None:
            raise ValueError(f"Agent type {agent_type} not available")

        # Generate transition response
        intro_message = transition_message or f"Let me help you with that."
        response = await agent.respond(context, intro_message)

        # Update history with transition
        state.history.append({
            "role": "system",
            "content": f"Transitioned from {old_agent.value} to {agent_type.value}",
            "agent_type": None,
            "timestamp": utc_now().isoformat(),
        })
        state.history.append({
            "role": "assistant",
            "content": response.message,
            "agent_type": response.agent_type.value,
            "timestamp": response.timestamp.isoformat(),
        })

        await self._save_conversation_state(user_id, state)

        return response

    async def start_feynman_dialogue(
        self,
        user_id: UUID,
        topic: str,
        session_id: UUID | None = None,
    ) -> AgentResponse:
        """Start a Feynman technique dialogue for a specific topic."""
        # Create or get state
        state = await self.get_conversation_state(user_id)
        if state is None:
            state = await self._create_conversation_state(user_id, session_id)

        # Set up for Socratic agent
        state.current_agent = AgentType.SOCRATIC
        state.context["feynman_topic"] = topic
        state.context["dialogue_mode"] = "feynman"

        # Initialize the Socratic agent's dialogue state
        socratic = self._agents.get(AgentType.SOCRATIC)
        if isinstance(socratic, SocraticAgent):
            socratic.begin_dialogue(user_id, session_id, topic)

        # Build context
        context = await self._build_agent_context(user_id, session_id, state)
        context.additional_data["topic"] = topic
        context.additional_data["action"] = "start_dialogue"

        # Get opening message
        response = await socratic.respond(context, f"I want to explain {topic}")

        # Update history
        state.history.append({
            "role": "system",
            "content": f"Started Feynman dialogue on: {topic}",
            "agent_type": None,
            "timestamp": utc_now().isoformat(),
        })
        state.history.append({
            "role": "assistant",
            "content": response.message,
            "agent_type": response.agent_type.value,
            "timestamp": response.timestamp.isoformat(),
        })

        await self._save_conversation_state(user_id, state)

        return response

    async def start_quiz(
        self,
        user_id: UUID,
        topics: list[str],
        question_count: int = 5,
        session_id: UUID | None = None,
    ) -> AgentResponse:
        """Start a quiz session on specified topics."""
        state = await self.get_conversation_state(user_id)
        if state is None:
            state = await self._create_conversation_state(user_id, session_id)

        state.current_agent = AgentType.ASSESSMENT
        state.context["quiz_topics"] = topics
        state.context["quiz_mode"] = True

        # Build context
        context = await self._build_agent_context(user_id, session_id, state)
        context.additional_data["action"] = "generate_quiz"
        context.additional_data["topics"] = topics
        context.additional_data["question_count"] = question_count

        # Get quiz
        assessment = self._agents.get(AgentType.ASSESSMENT)
        response = await assessment.respond(context, "Start quiz")

        # Update history
        state.history.append({
            "role": "system",
            "content": f"Started quiz on: {', '.join(topics)}",
            "agent_type": None,
            "timestamp": utc_now().isoformat(),
        })
        state.history.append({
            "role": "assistant",
            "content": response.message,
            "agent_type": response.agent_type.value,
            "timestamp": response.timestamp.isoformat(),
        })

        await self._save_conversation_state(user_id, state)

        return response

    async def _create_conversation_state(
        self,
        user_id: UUID,
        session_id: UUID | None,
    ) -> ConversationState:
        """Create a new conversation state with shared learning context."""
        now = utc_now()

        # Load shared learning context from database
        try:
            learning_context = await self._context_service.get_context(user_id)

            # If context is empty, try to populate from user profile
            if not learning_context.primary_goal:
                await self._context_service.load_from_user_profile(user_id)
                learning_context = await self._context_service.get_context(user_id)

            # Populate state.context with learning context data
            context_data = {
                "learning_context": learning_context,
                "primary_goal": learning_context.primary_goal,
                "current_focus": learning_context.current_focus,
                "user_goals": [learning_context.primary_goal] if learning_context.primary_goal else [],
                "preferences": learning_context.preferences,
                "constraints": learning_context.constraints,
            }
        except Exception as e:
            logger.warning(f"Failed to load learning context for user {user_id}: {e}")
            context_data = {}

        state = ConversationState(
            user_id=user_id,
            session_id=session_id,
            current_agent=self._default_agent,
            history=[],
            context=context_data,
            started_at=now,
            last_activity=now,
        )
        await self._save_conversation_state(user_id, state)
        return state

    async def _build_agent_context(
        self,
        user_id: UUID,
        session_id: UUID | None,
        state: ConversationState,
    ) -> AgentContext:
        """Build context for an agent call with shared learning context.

        This method ensures all agents receive the same shared context about
        the user's goals, current focus, and learning progress.
        """
        # Fetch fresh learning context from database
        try:
            learning_context = await self._context_service.get_context(user_id)
        except Exception as e:
            logger.warning(f"Failed to fetch learning context: {e}")
            learning_context = None

        # Build user profile with learning context data
        user_profile = state.context.get("user_profile", {})
        if learning_context:
            user_profile.update({
                "primary_goal": learning_context.primary_goal,
                "preferences": learning_context.preferences,
                "constraints": learning_context.constraints,
            })

        # Build current progress with learning context
        current_progress = state.context.get("current_progress", {})
        if learning_context:
            current_progress.update({
                "primary_goal": learning_context.primary_goal,
                "current_focus": learning_context.current_focus,
                "learning_path": [
                    {
                        "topic": s.topic,
                        "status": s.status,
                        "progress": s.progress,
                    }
                    for s in learning_context.learning_path
                ],
                "proficiency_levels": learning_context.proficiency_levels,
                "identified_gaps": learning_context.identified_gaps,
                "recent_topics": learning_context.recent_topics,
            })

        # Include full learning context in additional_data for agents that need it
        additional_data = state.context.copy()
        if learning_context:
            additional_data["learning_context"] = learning_context

        return AgentContext(
            user_id=user_id,
            session_id=session_id,
            topic_id=state.context.get("current_topic_id"),
            conversation_history=state.history,
            user_profile=user_profile,
            learning_pattern=state.context.get("learning_pattern", {}),
            current_progress=current_progress,
            additional_data=additional_data,
        )

    async def _determine_agent(
        self,
        state: ConversationState,
        message: str,
    ) -> AgentType:
        """Determine which agent should handle the message.

        Uses a combination of:
        1. Menu option selection (numeric inputs like "1", "2", "3")
        2. Pending agent suggestion for ambiguous inputs
        3. Current conversation mode (e.g., Feynman dialogue, quiz)
        4. Message content analysis (keywords)
        5. LLM-based intent classification (fallback)
        """
        msg = message.strip()

        # 1. Check if this is a menu selection (e.g., user typed "1", "2", "3")
        menu_options = state.context.get("menu_options", {})
        logger.debug(f"Checking menu_options: {menu_options}, user input: '{msg}'")
        if msg in menu_options:
            option = menu_options[msg]
            # Clear menu after selection
            state.context.pop("menu_options", None)
            state.context.pop("pending_next_agent", None)
            # Store selected action for the target agent to use
            if option.get("action"):
                state.context["selected_action"] = option["action"]

            # Convert string back to AgentType enum (stored as string for serialization)
            agent = option["agent"]
            if isinstance(agent, str):
                agent = AgentType(agent)

            logger.info(f"Menu selection '{msg}' -> {agent} (action: {option.get('action')})")
            return agent

        # 2. For other ambiguous inputs, use pending suggestion from previous agent
        if self._is_ambiguous_input(msg):
            pending = state.context.get("pending_next_agent")
            if pending:
                state.context.pop("pending_next_agent", None)
                state.context.pop("menu_options", None)
                logger.info(f"Ambiguous input '{msg}' -> using pending agent {pending}")
                return pending

        # 3. Clear stale menu/pending state for explicit inputs
        state.context.pop("menu_options", None)
        state.context.pop("pending_next_agent", None)

        # 4. Check for explicit mode
        if state.context.get("dialogue_mode") == "feynman":
            return AgentType.SOCRATIC

        if state.context.get("quiz_mode"):
            return AgentType.ASSESSMENT

        # 5. Check for explicit agent requests by keyword
        message_lower = msg.lower()

        if any(kw in message_lower for kw in ["explain", "teach me", "feynman", "understand"]):
            return AgentType.SOCRATIC

        if any(kw in message_lower for kw in ["quiz", "test", "assess", "check my"]):
            return AgentType.ASSESSMENT

        if any(kw in message_lower for kw in ["motivation", "struggling", "help me", "stuck", "tired"]):
            return AgentType.COACH

        if any(kw in message_lower for kw in ["plan", "path", "curriculum", "schedule", "roadmap"]):
            return AgentType.CURRICULUM

        if any(kw in message_lower for kw in ["content", "article", "read", "recommend reading", "what should i read"]):
            return AgentType.SCOUT

        if any(kw in message_lower for kw in ["practice", "drill", "exercise", "project", "hands-on", "weak"]):
            return AgentType.DRILL_SERGEANT

        # 6. Use LLM for more nuanced routing
        return await self._classify_intent_internal(message, state)

    def _is_ambiguous_input(self, message: str) -> bool:
        """Check if input is too short/vague for intent classification.

        Short inputs like "1", "ok", "yes" shouldn't trigger re-routing
        when an agent has already suggested the next agent.
        """
        msg = message.strip().lower()
        # Numeric inputs (menu selections that didn't match registered options)
        if msg.isdigit():
            return True
        # Very short affirmative/negative responses
        if len(msg) <= 4 and msg in ("ok", "yes", "no", "y", "n", "sure", "go", "yep", "nope", "okay"):
            return True
        return False

    async def classify_intent(
        self,
        message: str,
        state: ConversationState | None = None,
    ) -> AgentType:
        """Use LLM to classify user intent and route to appropriate agent.

        This method is exposed for use by the NLP command parser.

        Args:
            message: User message to classify
            state: Optional conversation state for context

        Returns:
            AgentType that should handle the message
        """
        return await self._classify_intent_internal(message, state)

    async def _classify_intent_internal(
        self,
        message: str,
        state: ConversationState | None,
    ) -> AgentType:
        """Internal implementation of intent classification."""
        # Get recent context
        recent_history = []
        if state and state.history:
            recent_history = state.history[-5:]
        context_summary = "\n".join(
            f"{h['role']}: {h['content'][:100]}..."
            for h in recent_history
        ) if recent_history else "No previous context."

        classification_prompt = f"""
        Classify this user message to determine which learning agent should handle it.

        User message: "{message}"

        Recent conversation context:
        {context_summary}

        Available agents:
        - SOCRATIC: For Feynman technique, explanations, understanding concepts
        - ASSESSMENT: For quizzes, testing knowledge, evaluating understanding
        - COACH: For motivation, session management, encouragement, general questions
        - CURRICULUM: For learning path planning, topic recommendations, scheduling
        - SCOUT: For content discovery, reading recommendations, summarization
        - DRILL_SERGEANT: For targeted practice, exercises, hands-on projects

        Which agent should handle this? Respond with just the agent name.
        """

        response = await self._llm.complete(
            prompt=classification_prompt,
            system_prompt="You are a routing classifier. Respond with exactly one agent name.",
            temperature=0.1,
            max_tokens=20,
        )

        # Parse response
        result = response.content.strip().upper()

        if "SOCRATIC" in result:
            return AgentType.SOCRATIC
        elif "ASSESSMENT" in result:
            return AgentType.ASSESSMENT
        elif "CURRICULUM" in result:
            return AgentType.CURRICULUM
        elif "SCOUT" in result:
            return AgentType.SCOUT
        elif "DRILL" in result or "SERGEANT" in result:
            return AgentType.DRILL_SERGEANT
        else:
            return AgentType.COACH

    def register_agent(self, agent: BaseAgent) -> None:
        """Register a new agent with the orchestrator."""
        self._agents[agent.agent_type] = agent

    def get_available_agents(self) -> list[AgentType]:
        """Get list of available agent types."""
        return list(self._agents.keys())


# Factory function
_orchestrator: AgentOrchestrator | None = None


def get_orchestrator() -> AgentOrchestrator:
    """Get orchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator

