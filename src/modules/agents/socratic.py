"""Socratic Agent - The confused student for Feynman technique dialogues."""

import json
import re
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from src.modules.agents.interface import (
    AgentContext,
    AgentResponse,
    AgentType,
    BaseAgent,
    ISocraticAgent,
)
from src.modules.llm.service import LLMService, get_llm_service


@dataclass
class DialogueState:
    """State for an ongoing Socratic dialogue."""

    topic: str
    phase: str = "opening"  # opening, probing, deepening, testing, closing
    turn_count: int = 0
    gaps_identified: list[str] = field(default_factory=list)
    key_points_covered: list[str] = field(default_factory=list)
    user_explanations: list[str] = field(default_factory=list)


class SocraticAgent(BaseAgent, ISocraticAgent):
    """Agent that plays the confused student role in Feynman technique dialogues.

    This agent asks probing questions to help users truly understand concepts
    by explaining them simply. It identifies gaps in understanding and pushes
    back on jargon and hand-wavy explanations.
    """

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self._llm = llm_service or get_llm_service()
        self._dialogue_states: dict[str, DialogueState] = {}

    @property
    def agent_type(self) -> AgentType:
        return AgentType.SOCRATIC

    @property
    def system_prompt(self) -> str:
        template = self._llm.load_prompt_template("socratic/confused_student")
        return template.system

    async def respond(
        self,
        context: AgentContext,
        user_message: str,
    ) -> AgentResponse:
        """Generate a response to user's explanation or message.

        Determines the appropriate phase of the Socratic dialogue and
        generates questions or feedback accordingly.
        """
        # Get or create dialogue state
        state_key = f"{context.user_id}:{context.session_id or 'default'}"
        state = self._dialogue_states.get(state_key)

        if state is None:
            # No active dialogue - this shouldn't happen normally
            # but handle gracefully by starting a new dialogue
            topic = context.additional_data.get("topic", "this concept")
            return await self._start_new_dialogue(context, topic, state_key)

        # Update state with user's explanation
        state.user_explanations.append(user_message)
        state.turn_count += 1

        # Determine response based on dialogue phase
        if state.phase == "opening":
            # First explanation received - start probing
            state.phase = "probing"
            return await self._probe_explanation(context, user_message, state)

        elif state.phase == "probing":
            # Continue probing or move to deepening
            if state.turn_count >= 3:
                state.phase = "deepening"
            return await self._probe_explanation(context, user_message, state)

        elif state.phase == "deepening":
            # Deep questioning - test edge cases and analogies
            if state.turn_count >= 6:
                state.phase = "testing"
            return await self._deepen_understanding(context, user_message, state)

        elif state.phase == "testing":
            # Final testing phase
            if state.turn_count >= 8:
                state.phase = "closing"
                return await self._evaluate_and_close(context, user_message, state)
            return await self._test_understanding(context, user_message, state)

        else:
            # Closing phase
            return await self._evaluate_and_close(context, user_message, state)

    async def start_dialogue(
        self,
        topic: str,
        user_context: dict,
    ) -> str:
        """Start a new Feynman technique dialogue.

        Returns an opening message asking the user to explain the topic.
        """
        template = self._llm.load_prompt_template("socratic/confused_student")
        system_prompt, user_prompt = template.format(topic=topic)

        # Generate opening question
        response = await self._llm.complete(
            prompt=f"You're about to start a dialogue where someone will explain '{topic}' to you. "
            f"Generate a brief, natural opening that invites them to explain the concept. "
            f"Be curious and friendly. 2-3 sentences max.",
            system_prompt=system_prompt,
            temperature=0.7,
        )

        return response.content

    async def probe_explanation(
        self,
        explanation: str,
        dialogue_history: list[dict],
        topic: str,
    ) -> tuple[str, list[str]]:
        """Probe user's explanation with follow-up questions.

        Returns (response_message, gaps_identified).
        """
        # Build conversation history for context
        messages = self._build_message_history(dialogue_history)
        messages.append({"role": "user", "content": explanation})

        # First, analyze the explanation for gaps
        gaps = await self._identify_gaps(explanation, topic, dialogue_history)

        # Load probe template
        template = self._llm.load_prompt_template("socratic/probe_deeper")

        # Extract key points from explanation
        key_points = await self._extract_key_points(explanation)

        system_prompt, user_prompt = template.format(
            topic=topic,
            previous_explanation=explanation,
            key_points="\n".join(f"- {p}" for p in key_points),
        )

        # Generate probing questions
        response = await self._llm.complete_with_history(
            messages=[{"role": "user", "content": user_prompt}],
            system_prompt=system_prompt,
            temperature=0.7,
        )

        return response.content, gaps

    async def _start_new_dialogue(
        self,
        context: AgentContext,
        topic: str,
        state_key: str,
    ) -> AgentResponse:
        """Initialize a new Socratic dialogue with shared context awareness."""
        # Create new state
        state = DialogueState(topic=topic)
        self._dialogue_states[state_key] = state

        # Get shared learning context to understand how this topic fits the user's goals
        learning_ctx = context.additional_data.get("learning_context")
        user_context = context.user_profile.copy()

        # Enrich user context with learning goals
        if learning_ctx:
            user_context.update({
                "primary_goal": learning_ctx.primary_goal,
                "current_focus": learning_ctx.current_focus,
                "recent_topics": learning_ctx.recent_topics[:3] if learning_ctx.recent_topics else [],
            })

        # Generate opening
        opening = await self.start_dialogue(
            topic=topic,
            user_context=user_context,
        )

        return AgentResponse(
            agent_type=self.agent_type,
            message=opening,
            data={
                "dialogue_phase": "opening",
                "topic": topic,
            },
        )

    async def _probe_explanation(
        self,
        context: AgentContext,
        user_message: str,
        state: DialogueState,
    ) -> AgentResponse:
        """Probe the user's explanation with follow-up questions."""
        # Build history from context
        history = context.conversation_history

        response_text, gaps = await self.probe_explanation(
            explanation=user_message,
            dialogue_history=history,
            topic=state.topic,
        )

        # Update state
        state.gaps_identified.extend(gaps)

        return AgentResponse(
            agent_type=self.agent_type,
            message=response_text,
            data={
                "dialogue_phase": state.phase,
                "turn_count": state.turn_count,
                "gaps_identified": gaps,
            },
        )

    async def _deepen_understanding(
        self,
        context: AgentContext,
        user_message: str,
        state: DialogueState,
    ) -> AgentResponse:
        """Challenge with deeper questions about edge cases and analogies."""
        template = self._llm.load_prompt_template("socratic/analogy_testing")

        # Prepare context for deep probing
        system_prompt, user_prompt = template.format(
            topic=state.topic,
            current_explanation=user_message,
            previous_points="\n".join(f"- {p}" for p in state.key_points_covered[-3:]),
            identified_gaps="\n".join(f"- {g}" for g in state.gaps_identified[-3:]),
        )

        response = await self._llm.complete(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.7,
        )

        # Extract any new gaps
        new_gaps = await self._identify_gaps(user_message, state.topic, context.conversation_history)
        state.gaps_identified.extend(new_gaps)

        return AgentResponse(
            agent_type=self.agent_type,
            message=response.content,
            data={
                "dialogue_phase": state.phase,
                "turn_count": state.turn_count,
                "gaps_identified": new_gaps,
            },
        )

    async def _test_understanding(
        self,
        context: AgentContext,
        user_message: str,
        state: DialogueState,
    ) -> AgentResponse:
        """Test understanding with practical scenarios."""
        template = self._llm.load_prompt_template("socratic/test_understanding")

        system_prompt, user_prompt = template.format(
            topic=state.topic,
            explanation_summary="\n".join(state.user_explanations[-3:]),
            key_concepts="\n".join(f"- {p}" for p in state.key_points_covered),
        )

        response = await self._llm.complete(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.7,
        )

        return AgentResponse(
            agent_type=self.agent_type,
            message=response.content,
            data={
                "dialogue_phase": state.phase,
                "turn_count": state.turn_count,
            },
        )

    async def _evaluate_and_close(
        self,
        context: AgentContext,
        user_message: str,
        state: DialogueState,
    ) -> AgentResponse:
        """Evaluate the dialogue and provide closing feedback."""
        # Evaluate overall understanding
        evaluation = await self._evaluate_understanding(state)

        # Generate closing message
        closing_prompt = f"""
        The Feynman dialogue about "{state.topic}" is now complete.

        Based on the conversation, provide:
        1. A brief summary of how well they explained the concept (2-3 sentences)
        2. The key strengths in their explanation
        3. Areas that could use more clarity
        4. A score from 1-10 on explanation quality

        Be encouraging but honest. Focus on what they did well while noting areas for growth.
        """

        response = await self._llm.complete(
            prompt=closing_prompt,
            system_prompt="You are providing feedback after a Socratic dialogue. Be constructive and specific.",
            temperature=0.5,
        )

        # Clean up dialogue state
        state_key = f"{context.user_id}:{context.session_id or 'default'}"
        del self._dialogue_states[state_key]

        return AgentResponse(
            agent_type=self.agent_type,
            message=response.content,
            data={
                "dialogue_phase": "complete",
                "evaluation": evaluation,
                "total_turns": state.turn_count,
                "gaps_found": state.gaps_identified,
            },
            end_conversation=True,
            suggested_next_agent=AgentType.COACH,
        )

    async def _identify_gaps(
        self,
        explanation: str,
        topic: str,
        history: list[dict],
    ) -> list[str]:
        """Analyze explanation to identify knowledge gaps."""
        analysis_prompt = f"""
        Analyze this explanation of "{topic}" for knowledge gaps:

        Explanation: {explanation}

        Identify specific gaps or weaknesses:
        1. Concepts mentioned but not explained
        2. Jargon used without definition
        3. Logical leaps or missing connections
        4. Overly vague or hand-wavy parts
        5. Missing important aspects of the topic

        Return as a JSON array of strings, each describing a specific gap.
        Only return the JSON array, no other text.
        Example: ["Gap 1 description", "Gap 2 description"]
        """

        response = await self._llm.complete(
            prompt=analysis_prompt,
            system_prompt="You are an expert at identifying knowledge gaps in explanations. Be specific and actionable.",
            temperature=0.3,
        )

        # Parse JSON response
        try:
            # Extract JSON array from response
            content = response.content.strip()
            # Handle markdown code blocks
            if "```" in content:
                match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
                if match:
                    content = match.group(1)
            gaps = json.loads(content)
            if isinstance(gaps, list):
                return [str(g) for g in gaps]
        except (json.JSONDecodeError, ValueError):
            pass

        return []

    async def _extract_key_points(self, explanation: str) -> list[str]:
        """Extract key points from an explanation."""
        prompt = f"""
        Extract the key points from this explanation:

        {explanation}

        Return as a JSON array of 3-5 key points.
        Only return the JSON array, no other text.
        """

        response = await self._llm.complete(
            prompt=prompt,
            system_prompt="Extract key points concisely.",
            temperature=0.3,
        )

        try:
            content = response.content.strip()
            if "```" in content:
                match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
                if match:
                    content = match.group(1)
            points = json.loads(content)
            if isinstance(points, list):
                return [str(p) for p in points]
        except (json.JSONDecodeError, ValueError):
            pass

        return []

    async def _evaluate_understanding(self, state: DialogueState) -> dict[str, Any]:
        """Evaluate overall understanding from the dialogue."""
        evaluation_prompt = f"""
        Evaluate the understanding demonstrated in this Feynman dialogue:

        Topic: {state.topic}
        Number of turns: {state.turn_count}
        Gaps identified: {json.dumps(state.gaps_identified)}

        Provide evaluation as JSON:
        {{
            "overall_score": 1-10,
            "clarity_score": 1-10,
            "depth_score": 1-10,
            "accuracy_score": 1-10,
            "strengths": ["strength1", "strength2"],
            "areas_for_improvement": ["area1", "area2"],
            "mastery_level": "novice|developing|proficient|advanced|expert"
        }}

        Only return the JSON object.
        """

        response = await self._llm.complete(
            prompt=evaluation_prompt,
            system_prompt="You are an expert learning evaluator. Be fair and constructive.",
            temperature=0.3,
        )

        try:
            content = response.content.strip()
            if "```" in content:
                match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
                if match:
                    content = match.group(1)
            return json.loads(content)
        except (json.JSONDecodeError, ValueError):
            return {
                "overall_score": 5,
                "mastery_level": "developing",
                "strengths": [],
                "areas_for_improvement": state.gaps_identified,
            }

    def _build_message_history(self, history: list[dict]) -> list[dict[str, str]]:
        """Convert conversation history to LLM message format."""
        messages = []
        for entry in history:
            role = entry.get("role", "user")
            content = entry.get("content", "")
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": content})
        return messages

    def begin_dialogue(
        self,
        user_id: UUID,
        session_id: UUID | None,
        topic: str,
    ) -> None:
        """Initialize a new dialogue state for a user."""
        state_key = f"{user_id}:{session_id or 'default'}"
        self._dialogue_states[state_key] = DialogueState(topic=topic)

    def get_dialogue_state(
        self,
        user_id: UUID,
        session_id: UUID | None = None,
    ) -> DialogueState | None:
        """Get current dialogue state for a user."""
        state_key = f"{user_id}:{session_id or 'default'}"
        return self._dialogue_states.get(state_key)


# Factory function
_socratic_agent: SocraticAgent | None = None


def get_socratic_agent() -> SocraticAgent:
    """Get Socratic agent singleton."""
    global _socratic_agent
    if _socratic_agent is None:
        _socratic_agent = SocraticAgent()
    return _socratic_agent
