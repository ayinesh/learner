"""Handoff Generator - Helper functions for creating handoff context.

This module provides simple factory functions that agents can use to create
proper handoff context, actions, and discoveries without boilerplate.

Usage:
    from src.modules.agents.handoff_generator import create_handoff, create_action, create_discovery

    return AgentResponse(
        ...,
        handoff_context=create_handoff(
            from_agent=self.agent_type,
            summary="Completed quiz with 80% score",
            gaps_identified=["derivatives", "chain rule"],
            suggested_next_agent=AgentType.DRILL_SERGEANT,
        ),
        actions_taken=[
            create_action(self.agent_type, "complete_quiz", {"score": 0.8}),
        ],
        discoveries=create_discovery(needs_support=["derivatives"]),
    )
"""

from typing import Any

from src.modules.agents.interface import AgentType
from src.modules.agents.learning_context import (
    AgentAction,
    AgentDiscoveries,
    AgentHandoffContext,
)
from src.shared.datetime_utils import utc_now


def create_handoff(
    from_agent: AgentType,
    summary: str,
    *,
    outcomes: dict[str, Any] | None = None,
    gaps_identified: list[str] | None = None,
    learning_observations: list[str] | None = None,
    suggested_next_steps: list[str] | None = None,
    suggested_next_agent: AgentType | None = None,
    key_points: list[str] | None = None,
    topics_covered: list[str] | None = None,
    proficiency_observations: dict[str, float] | None = None,
) -> AgentHandoffContext:
    """Create a handoff context object for passing to the next agent.

    This is the primary function agents should use to create handoff context.
    The handoff context enables seamless transitions between agents by
    communicating what was accomplished, what gaps were found, and what
    should happen next.

    Args:
        from_agent: The agent creating this handoff
        summary: Brief summary of what the agent accomplished (1-2 sentences)
        outcomes: Key outcomes as key-value pairs
            Example: {"quiz_score": 0.8, "topics_assessed": ["math", "physics"]}
        gaps_identified: Knowledge gaps found during the interaction
            Example: ["matrix multiplication", "chain rule"]
        learning_observations: Observations about user's learning style
            Example: ["prefers visual explanations", "struggles with abstract concepts"]
        suggested_next_steps: Recommended actions for the next agent or user
            Example: ["Practice drills on derivatives", "Review calculus basics"]
        suggested_next_agent: Which agent should handle next (optional)
        key_points: Important conversation points worth preserving
            Example: ["User confused derivative with integral", "Mastered basic algebra"]
        topics_covered: Topics discussed in this interaction
            Example: ["calculus", "derivatives", "limits"]
        proficiency_observations: Estimated proficiency by topic (0.0 to 1.0)
            Example: {"calculus": 0.6, "algebra": 0.9}

    Returns:
        AgentHandoffContext ready to attach to AgentResponse
    """
    return AgentHandoffContext(
        from_agent=from_agent.value,
        summary=summary,
        outcomes=outcomes or {},
        gaps_identified=gaps_identified or [],
        learning_observations=learning_observations or [],
        suggested_next_steps=suggested_next_steps or [],
        suggested_next_agent=suggested_next_agent.value if suggested_next_agent else None,
        key_points=key_points or [],
        topics_covered=topics_covered or [],
        proficiency_observations=proficiency_observations or {},
        timestamp=utc_now(),
    )


def create_action(
    agent_type: AgentType,
    action: str,
    details: dict[str, Any] | None = None,
) -> AgentAction:
    """Create an action log entry.

    Actions are logged chronologically to enable cross-agent coordination.
    For example, Assessment can see that Socratic already identified gaps
    in "matrix operations" and focus the quiz accordingly.

    Args:
        agent_type: Which agent took this action
        action: Action name (should be a consistent identifier)
            Examples: "set_goal", "complete_quiz", "identify_gap",
                     "create_learning_path", "complete_drill", "evaluate_content"
        details: Action-specific details as key-value pairs
            Example: {"topic": "calculus", "score": 0.8, "duration_minutes": 15}

    Returns:
        AgentAction ready to attach to AgentResponse.actions_taken list
    """
    return AgentAction(
        agent_type=agent_type.value,
        action=action,
        details=details or {},
        timestamp=utc_now(),
    )


def create_discovery(
    *,
    misconceptions: list[dict[str, str]] | None = None,
    learning_observations: list[dict[str, Any]] | None = None,
    approach_results: list[dict[str, Any]] | None = None,
    strengths: list[str] | None = None,
    needs_support: list[str] | None = None,
) -> AgentDiscoveries:
    """Create a discoveries object for persistent cross-agent observations.

    Unlike handoff context (which is for immediate transitions), discoveries
    are persistent observations that any agent can reference at any time.
    These accumulate over time, building a comprehensive picture of the user.

    Args:
        misconceptions: User misconceptions found during interaction
            Format: [{"topic": "derivatives", "misconception": "thinks d/dx is division",
                     "discovered_by": "socratic"}]
        learning_observations: Observations about learning style/preferences
            Format: [{"observation": "prefers code examples over theory",
                     "confidence": 0.8, "discovered_by": "coach"}]
        approach_results: Record of what teaching approaches worked or didn't
            Format: [{"approach": "visual diagrams", "worked": True,
                     "topic": "recursion", "discovered_by": "drill_sergeant"}]
        strengths: Topics where user showed particular strength
            Example: ["algebra", "basic programming"]
        needs_support: Topics where user needs more support
            Example: ["calculus", "recursion"]

    Returns:
        AgentDiscoveries ready to attach to AgentResponse.discoveries
    """
    return AgentDiscoveries(
        misconceptions=misconceptions or [],
        learning_observations=learning_observations or [],
        approach_results=approach_results or [],
        strengths=strengths or [],
        needs_support=needs_support or [],
    )


def create_misconception(
    topic: str,
    misconception: str,
    discovered_by: AgentType,
) -> dict[str, str]:
    """Helper to create a properly formatted misconception entry.

    Args:
        topic: The topic area of the misconception
        misconception: Description of the misconception
        discovered_by: Agent that discovered this

    Returns:
        Dict ready to add to discoveries.misconceptions list
    """
    return {
        "topic": topic,
        "misconception": misconception,
        "discovered_by": discovered_by.value,
        "timestamp": utc_now().isoformat(),
    }


def create_learning_observation(
    observation: str,
    confidence: float,
    discovered_by: AgentType,
) -> dict[str, Any]:
    """Helper to create a properly formatted learning observation entry.

    Args:
        observation: The observation about learning style/preference
        confidence: Confidence level (0.0 to 1.0)
        discovered_by: Agent that made this observation

    Returns:
        Dict ready to add to discoveries.learning_observations list
    """
    return {
        "observation": observation,
        "confidence": min(1.0, max(0.0, confidence)),
        "discovered_by": discovered_by.value,
        "timestamp": utc_now().isoformat(),
    }


def create_approach_result(
    approach: str,
    worked: bool,
    topic: str,
    discovered_by: AgentType,
) -> dict[str, Any]:
    """Helper to create a properly formatted approach result entry.

    Args:
        approach: The teaching approach used (e.g., "code examples", "visual diagrams")
        worked: Whether the approach was effective
        topic: The topic being taught
        discovered_by: Agent that tried this approach

    Returns:
        Dict ready to add to discoveries.approach_results list
    """
    return {
        "approach": approach,
        "worked": worked,
        "topic": topic,
        "discovered_by": discovered_by.value,
        "timestamp": utc_now().isoformat(),
    }
