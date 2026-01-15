"""Unit tests for Curriculum, Scout, and Drill Sergeant agents."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from src.modules.agents.interface import (
    AgentContext,
    AgentResponse,
    AgentType,
)
from src.modules.agents.curriculum import CurriculumAgent, UserLearningState
from src.modules.agents.scout import ScoutAgent, ContentItem, UserContentProfile
from src.modules.agents.drill_sergeant import DrillSergeantAgent, WeaknessAnalysis
from src.modules.llm.service import LLMResponse, PromptTemplate


# Fixtures


@pytest.fixture
def mock_llm_service():
    """Create a mock LLM service."""
    mock = MagicMock()

    # Mock complete method - use AsyncMock without side_effect so it can be overridden
    mock.complete = AsyncMock(return_value=LLMResponse(
        content="Mock LLM response",
        model="claude-sonnet-4-20250514",
        usage={"input_tokens": 100, "output_tokens": 50},
    ))
    mock.complete_with_history = AsyncMock(return_value=LLMResponse(
        content="Mock LLM response",
        model="claude-sonnet-4-20250514",
        usage={"input_tokens": 100, "output_tokens": 50},
    ))
    mock.load_prompt_template = MagicMock(return_value=PromptTemplate(
        name="test",
        system="Test system prompt",
        user="Test user prompt",
        variables=[],
    ))

    return mock


@pytest.fixture
def agent_context():
    """Create a basic agent context."""
    return AgentContext(
        user_id=uuid4(),
        session_id=uuid4(),
        conversation_history=[],
        user_profile={"name": "Test User"},
        learning_pattern={},
        current_progress={"streak": 5},
        additional_data={},
    )


# Curriculum Agent Tests


class TestCurriculumAgent:
    """Tests for CurriculumAgent."""

    def test_agent_type(self, mock_llm_service):
        """Test that agent reports correct type."""
        agent = CurriculumAgent(llm_service=mock_llm_service)
        assert agent.agent_type == AgentType.CURRICULUM

    def test_system_prompt(self, mock_llm_service):
        """Test system prompt loading."""
        agent = CurriculumAgent(llm_service=mock_llm_service)
        prompt = agent.system_prompt
        assert prompt == "Test system prompt"
        mock_llm_service.load_prompt_template.assert_called_with("curriculum/learning_path")

    @pytest.mark.asyncio
    async def test_generate_learning_path(self, mock_llm_service):
        """Test learning path generation."""
        # Mock JSON response
        mock_llm_service.complete.return_value = LLMResponse(
            content='{"title": "Test Path", "duration_weeks": 4, "total_hours": 20, "phases": [], "weekly_schedule": [], "success_criteria": []}',
            model="claude-sonnet-4-20250514",
            usage={"input_tokens": 100, "output_tokens": 200},
        )

        agent = CurriculumAgent(llm_service=mock_llm_service)
        user_id = uuid4()

        path = await agent.generate_learning_path(
            user_id=user_id,
            goals=["Learn Python", "Build web apps"],
            time_horizon_days=30,
        )

        assert path["title"] == "Test Path"
        assert path["duration_weeks"] == 4

    @pytest.mark.asyncio
    async def test_recommend_next_topic(self, mock_llm_service):
        """Test topic recommendation."""
        # Mock JSON response
        mock_llm_service.complete.return_value = LLMResponse(
            content='{"recommended_topic_id": "123", "topic_title": "Functions", "recommendation_type": "path_continuation", "rationale": "Next step", "activity_type": "read", "estimated_minutes": 30, "difficulty_level": 3, "goal_alignment": "Good fit", "session_structure": []}',
            model="claude-sonnet-4-20250514",
            usage={"input_tokens": 100, "output_tokens": 150},
        )

        agent = CurriculumAgent(llm_service=mock_llm_service)
        user_id = uuid4()

        recommendation = await agent.recommend_next_topic(user_id)

        assert recommendation["topic_title"] == "Functions"
        assert recommendation["recommendation_type"] == "path_continuation"

    @pytest.mark.asyncio
    async def test_respond_path_generation(self, mock_llm_service, agent_context):
        """Test respond method for path generation."""
        mock_llm_service.complete.return_value = LLMResponse(
            content='{"title": "AI Learning Path", "duration_weeks": 4, "total_hours": 20, "phases": [{"title": "Phase 1", "milestone": "Basic understanding"}], "weekly_schedule": [], "success_criteria": []}',
            model="claude-sonnet-4-20250514",
            usage={"input_tokens": 100, "output_tokens": 200},
        )

        agent = CurriculumAgent(llm_service=mock_llm_service)
        agent_context.additional_data["action"] = "generate_path"
        agent_context.additional_data["goals"] = ["Learn AI"]

        response = await agent.respond(agent_context, "Create a learning path")

        assert response.agent_type == AgentType.CURRICULUM
        assert "learning path" in response.message.lower()

    def test_get_user_path(self, mock_llm_service):
        """Test retrieving user's learning path."""
        agent = CurriculumAgent(llm_service=mock_llm_service)
        user_id = uuid4()

        # No path yet
        path = agent.get_user_path(user_id)
        assert path is None


# Scout Agent Tests


class TestScoutAgent:
    """Tests for ScoutAgent."""

    def test_agent_type(self, mock_llm_service):
        """Test that agent reports correct type."""
        agent = ScoutAgent(llm_service=mock_llm_service)
        assert agent.agent_type == AgentType.SCOUT

    @pytest.mark.asyncio
    async def test_evaluate_content(self, mock_llm_service):
        """Test content evaluation."""
        mock_llm_service.complete.return_value = LLMResponse(
            content='{"relevance_score": 0.8, "timing_assessment": "perfect_timing", "recommended_action": "read_now", "rationale": "Highly relevant", "goal_alignment": {}, "prerequisite_check": {}, "practical_value": {}, "when_to_consume": "immediate", "estimated_time_investment": 15, "key_takeaways": ["Key point"]}',
            model="claude-sonnet-4-20250514",
            usage={"input_tokens": 100, "output_tokens": 150},
        )

        agent = ScoutAgent(llm_service=mock_llm_service)

        content = ContentItem(
            id=uuid4(),
            title="Intro to Neural Networks",
            source="Blog",
            content_type="tutorial",
            summary="A beginner-friendly intro",
            topics=["neural networks", "deep learning"],
            difficulty="beginner",
            length_minutes=15,
        )

        user_profile = UserContentProfile(
            user_id=uuid4(),
            goals=["Learn deep learning"],
            current_phase="Foundations",
            current_topics=["neural networks"],
            proficiency_levels={"basics": 0.7},
            identified_gaps=[],
            interests=["AI"],
            available_time_weekly=120,
            backlog_size=5,
            upcoming_milestones=["Complete foundations"],
            priority_topics=["neural networks"],
        )

        evaluation = await agent.evaluate_content(content, user_profile)

        assert evaluation.relevance_score == 0.8
        assert evaluation.recommended_action == "read_now"

    @pytest.mark.asyncio
    async def test_summarize_content(self, mock_llm_service):
        """Test content summarization."""
        mock_llm_service.complete.return_value = LLMResponse(
            content='{"headline": "Key insight here", "core_insight": "Main point explained", "key_concepts": [{"concept": "Backprop", "explanation": "How gradients flow"}], "practical_application": {}, "prerequisites": {}, "technical_details": {}, "connections": {}, "full_summary": "Full summary text", "follow_up_questions": ["Question 1"], "time_saved": 10}',
            model="claude-sonnet-4-20250514",
            usage={"input_tokens": 100, "output_tokens": 200},
        )

        agent = ScoutAgent(llm_service=mock_llm_service)

        content = ContentItem(
            id=uuid4(),
            title="Deep Learning Basics",
            source="Article",
            content_type="conceptual",
            summary="Intro to deep learning",
            topics=["deep learning"],
            difficulty="intermediate",
            length_minutes=20,
            full_text="Full article text here...",
        )

        summary = await agent.summarize_content(
            content=content,
            user_context={"level": "intermediate", "goals": ["Learn DL"]},
        )

        assert summary.headline == "Key insight here"
        assert len(summary.key_concepts) > 0

    def test_reading_list_management(self, mock_llm_service):
        """Test reading list add/remove."""
        agent = ScoutAgent(llm_service=mock_llm_service)
        user_id = uuid4()
        content_id = uuid4()

        # Add to list
        agent.add_to_reading_list(user_id, content_id)
        assert content_id in agent._user_reading_lists[user_id]

        # Remove from list
        agent.remove_from_reading_list(user_id, content_id)
        assert content_id not in agent._user_reading_lists[user_id]


# Drill Sergeant Agent Tests


class TestDrillSergeantAgent:
    """Tests for DrillSergeantAgent."""

    def test_agent_type(self, mock_llm_service):
        """Test that agent reports correct type."""
        agent = DrillSergeantAgent(llm_service=mock_llm_service)
        assert agent.agent_type == AgentType.DRILL_SERGEANT

    @pytest.mark.asyncio
    async def test_create_targeted_drill(self, mock_llm_service):
        """Test targeted drill creation."""
        mock_llm_service.complete.return_value = LLMResponse(
            content='{"drill_title": "Backpropagation Practice", "target_skill": "Understanding gradients", "rationale": "Address identified gap", "estimated_duration": 15, "exercises": [{"exercise_number": 1, "type": "explain", "difficulty": 2, "prompt": "Explain backprop", "correct_answer": "Correct explanation", "common_mistakes": ["Mistake 1"], "feedback_if_wrong": "Try again", "feedback_if_correct": "Good!"}], "progression_rule": "3 correct", "mastery_criteria": "80%", "follow_up_plan": {}}',
            model="claude-sonnet-4-20250514",
            usage={"input_tokens": 100, "output_tokens": 200},
        )

        agent = DrillSergeantAgent(llm_service=mock_llm_service)

        weakness = WeaknessAnalysis(
            topic_name="Backpropagation",
            specific_gap="Understanding gradient flow",
            gap_source="quiz",
            severity=0.6,
            evidence="Missed 3 questions on gradients",
            current_proficiency=0.4,
            related_proficiency={"calculus": 0.7},
            recent_mistakes=["gradient direction", "chain rule"],
            error_pattern="Conceptual confusion",
        )

        drill = await agent.create_targeted_drill(
            weakness=weakness,
            available_minutes=15,
        )

        assert drill.title == "Backpropagation Practice"
        assert len(drill.exercises) > 0

    @pytest.mark.asyncio
    async def test_create_skill_project(self, mock_llm_service):
        """Test skill project creation."""
        mock_llm_service.complete.return_value = LLMResponse(
            content='{"project_title": "Build a Neural Net", "difficulty_level": "intermediate", "estimated_hours": 4, "skills_practiced": ["Python", "NumPy"], "overview": {"context": "Apply learning", "objective": "Build from scratch"}, "requirements": {}, "phases": [{"phase": 1, "title": "Setup", "estimated_hours": 1, "objectives": ["Install deps"], "tasks": [], "common_pitfalls": [], "checkpoint_validation": "Check setup"}], "resources": {}, "checkpoints": [], "extensions": [], "reflection_questions": [], "next_steps": "Continue learning"}',
            model="claude-sonnet-4-20250514",
            usage={"input_tokens": 100, "output_tokens": 250},
        )

        agent = DrillSergeantAgent(llm_service=mock_llm_service)

        user_context = {
            "recent_topics": ["Python basics", "NumPy"],
            "proficiency_levels": {"Python": 0.7},
            "learning_goals": ["Build neural networks"],
        }

        project_constraints = {
            "available_hours": 4,
            "skill_level": "intermediate",
            "primary_skills": ["Python", "NumPy"],
        }

        project = await agent.create_skill_project(user_context, project_constraints)

        assert project.title == "Build a Neural Net"
        assert len(project.phases) > 0

    def test_drill_lifecycle(self, mock_llm_service):
        """Test starting and progressing through a drill."""
        agent = DrillSergeantAgent(llm_service=mock_llm_service)
        user_id = uuid4()

        # Create a simple drill manually
        from src.modules.agents.drill_sergeant import TargetedDrill, DrillExercise

        drill = TargetedDrill(
            id=uuid4(),
            title="Test Drill",
            target_skill="Testing",
            rationale="Test",
            exercises=[
                DrillExercise(
                    exercise_number=1,
                    type="flashcard",
                    difficulty=1,
                    prompt="What is 2+2?",
                    correct_answer="4",
                    common_mistakes=["5"],
                    feedback_if_wrong="Try again",
                    feedback_if_correct="Correct!",
                ),
                DrillExercise(
                    exercise_number=2,
                    type="flashcard",
                    difficulty=2,
                    prompt="What is 3+3?",
                    correct_answer="6",
                    common_mistakes=["7"],
                    feedback_if_wrong="Try again",
                    feedback_if_correct="Correct!",
                ),
            ],
            progression_rule="2 correct",
            mastery_criteria="100%",
            follow_up_plan={},
            estimated_duration=5,
        )

        agent._drills[drill.id] = drill

        # Start drill
        first_exercise = agent.start_drill(user_id, drill.id)
        assert first_exercise is not None
        assert first_exercise.exercise_number == 1

        # Get next exercise
        next_exercise = agent.get_next_exercise(user_id)
        assert next_exercise is not None
        assert next_exercise.exercise_number == 2

        # No more exercises
        final = agent.get_next_exercise(user_id)
        assert final is None

    @pytest.mark.asyncio
    async def test_evaluate_exercise_answer(self, mock_llm_service):
        """Test exercise answer evaluation."""
        mock_llm_service.complete.return_value = LLMResponse(
            content='{"is_correct": true, "explanation": "Correct answer"}',
            model="claude-sonnet-4-20250514",
            usage={"input_tokens": 50, "output_tokens": 30},
        )

        agent = DrillSergeantAgent(llm_service=mock_llm_service)

        # Create and store a drill
        from src.modules.agents.drill_sergeant import TargetedDrill, DrillExercise

        drill = TargetedDrill(
            id=uuid4(),
            title="Test",
            target_skill="Test",
            rationale="Test",
            exercises=[
                DrillExercise(
                    exercise_number=1,
                    type="flashcard",
                    difficulty=1,
                    prompt="What is Python?",
                    correct_answer="A programming language",
                    common_mistakes=[],
                    feedback_if_wrong="Incorrect",
                    feedback_if_correct="Correct!",
                ),
            ],
            progression_rule="1 correct",
            mastery_criteria="100%",
            follow_up_plan={},
            estimated_duration=5,
        )

        agent._drills[drill.id] = drill

        is_correct, feedback, next_action = await agent.evaluate_exercise_answer(
            drill_id=drill.id,
            exercise_number=1,
            user_answer="A programming language",
        )

        assert is_correct is True


# Orchestrator Integration Tests


class TestOrchestratorWithNewAgents:
    """Test orchestrator integration with new agents."""

    @pytest.mark.asyncio
    async def test_routing_to_curriculum(self, mock_llm_service):
        """Test routing to curriculum agent."""
        from src.modules.agents.orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator(llm_service=mock_llm_service)

        # Verify curriculum agent is registered
        available = orchestrator.get_available_agents()
        assert AgentType.CURRICULUM in available

    @pytest.mark.asyncio
    async def test_routing_to_scout(self, mock_llm_service):
        """Test routing to scout agent."""
        from src.modules.agents.orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator(llm_service=mock_llm_service)

        available = orchestrator.get_available_agents()
        assert AgentType.SCOUT in available

    @pytest.mark.asyncio
    async def test_routing_to_drill_sergeant(self, mock_llm_service):
        """Test routing to drill sergeant agent."""
        from src.modules.agents.orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator(llm_service=mock_llm_service)

        available = orchestrator.get_available_agents()
        assert AgentType.DRILL_SERGEANT in available

    @pytest.mark.asyncio
    async def test_all_agents_registered(self, mock_llm_service):
        """Test that all 6 agents are registered."""
        from src.modules.agents.orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator(llm_service=mock_llm_service)

        available = orchestrator.get_available_agents()

        expected_agents = [
            AgentType.SOCRATIC,
            AgentType.COACH,
            AgentType.ASSESSMENT,
            AgentType.CURRICULUM,
            AgentType.SCOUT,
            AgentType.DRILL_SERGEANT,
        ]

        for agent_type in expected_agents:
            assert agent_type in available, f"{agent_type} not registered"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
