"""Agents Module - AI agent definitions and orchestration."""

from src.modules.agents.interface import (
    AgentContext,
    AgentResponse,
    AgentType,
    BaseAgent,
    ConversationState,
    IAgentOrchestrator,
    ICoachAgent,
    ICurriculumAgent,
    ISocraticAgent,
)
from src.modules.agents.socratic import SocraticAgent, get_socratic_agent
from src.modules.agents.coach import CoachAgent, get_coach_agent
from src.modules.agents.assessment_agent import AssessmentAgent, get_assessment_agent
from src.modules.agents.curriculum import CurriculumAgent, get_curriculum_agent
from src.modules.agents.scout import ScoutAgent, get_scout_agent
from src.modules.agents.drill_sergeant import DrillSergeantAgent, get_drill_sergeant_agent
from src.modules.agents.orchestrator import AgentOrchestrator, get_orchestrator

__all__ = [
    # Interface types
    "AgentContext",
    "AgentResponse",
    "AgentType",
    "BaseAgent",
    "ConversationState",
    "IAgentOrchestrator",
    "ICoachAgent",
    "ICurriculumAgent",
    "ISocraticAgent",
    # Implementations
    "SocraticAgent",
    "CoachAgent",
    "AssessmentAgent",
    "CurriculumAgent",
    "ScoutAgent",
    "DrillSergeantAgent",
    "AgentOrchestrator",
    # Factory functions
    "get_socratic_agent",
    "get_coach_agent",
    "get_assessment_agent",
    "get_curriculum_agent",
    "get_scout_agent",
    "get_drill_sergeant_agent",
    "get_orchestrator",
]
