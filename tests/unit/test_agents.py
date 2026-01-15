"""Unit tests for agent implementations."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.modules.agents.interface import (
    AgentContext,
    AgentResponse,
    AgentType,
    ConversationState,
    MenuOption,
)
from src.modules.agents.socratic import SocraticAgent, DialogueState
from src.modules.agents.coach import CoachAgent
from src.modules.agents.assessment_agent import AssessmentAgent, QuizQuestion, Quiz
from src.modules.agents.orchestrator import AgentOrchestrator
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

    # Mock prompt template loading
    mock.load_prompt_template = MagicMock(return_value=PromptTemplate(
        name="test",
        system="Test system prompt",
        user="Test user prompt with {{topic}}",
        variables=["topic"],
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


# Socratic Agent Tests


class TestSocraticAgent:
    """Tests for SocraticAgent."""

    def test_agent_type(self, mock_llm_service):
        """Test that agent reports correct type."""
        agent = SocraticAgent(llm_service=mock_llm_service)
        assert agent.agent_type == AgentType.SOCRATIC

    def test_system_prompt(self, mock_llm_service):
        """Test system prompt loading."""
        agent = SocraticAgent(llm_service=mock_llm_service)
        prompt = agent.system_prompt
        assert prompt == "Test system prompt"
        mock_llm_service.load_prompt_template.assert_called_with("socratic/confused_student")

    @pytest.mark.asyncio
    async def test_start_dialogue(self, mock_llm_service):
        """Test starting a new Feynman dialogue."""
        agent = SocraticAgent(llm_service=mock_llm_service)

        opening = await agent.start_dialogue(
            topic="neural networks",
            user_context={},
        )

        assert opening == "Mock LLM response"
        mock_llm_service.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_probe_explanation(self, mock_llm_service):
        """Test probing user's explanation."""
        # Mock JSON response for gap identification
        mock_llm_service.complete.return_value = LLMResponse(
            content='["Gap 1", "Gap 2"]',
            model="claude-sonnet-4-20250514",
            usage={"input_tokens": 100, "output_tokens": 50},
        )

        agent = SocraticAgent(llm_service=mock_llm_service)

        response, gaps = await agent.probe_explanation(
            explanation="Neural networks are like brains...",
            dialogue_history=[],
            topic="neural networks",
        )

        assert response is not None
        assert isinstance(gaps, list)

    def test_begin_dialogue_creates_state(self, mock_llm_service):
        """Test that begin_dialogue creates dialogue state."""
        agent = SocraticAgent(llm_service=mock_llm_service)
        user_id = uuid4()
        session_id = uuid4()

        agent.begin_dialogue(user_id, session_id, "test topic")

        state = agent.get_dialogue_state(user_id, session_id)
        assert state is not None
        assert state.topic == "test topic"
        assert state.phase == "opening"
        assert state.turn_count == 0


# Coach Agent Tests


class TestCoachAgent:
    """Tests for CoachAgent."""

    def test_agent_type(self, mock_llm_service):
        """Test that agent reports correct type."""
        agent = CoachAgent(llm_service=mock_llm_service)
        assert agent.agent_type == AgentType.COACH

    @pytest.mark.asyncio
    async def test_generate_session_opening(self, mock_llm_service):
        """Test session opening generation."""
        agent = CoachAgent(llm_service=mock_llm_service)

        opening = await agent.generate_session_opening(
            user_id=uuid4(),
            session_context={
                "user_name": "Alice",
                "days_since_last": 1,
                "current_streak": 5,
                "available_minutes": 30,
            },
        )

        assert opening == "Mock LLM response"
        mock_llm_service.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_session_closing(self, mock_llm_service):
        """Test session closing generation."""
        agent = CoachAgent(llm_service=mock_llm_service)

        closing = await agent.generate_session_closing(
            session_summary={
                "session_minutes": 30,
                "topics_covered": ["topic1", "topic2"],
                "quiz_results": {"correct": 4, "total": 5},
            },
        )

        assert closing == "Mock LLM response"

    @pytest.mark.asyncio
    async def test_generate_recovery_plan(self, mock_llm_service):
        """Test recovery plan generation."""
        # Mock JSON response
        mock_llm_service.complete.return_value = LLMResponse(
            content='{"welcome_message": "Welcome back!", "encouragement": "Keep going!"}',
            model="claude-sonnet-4-20250514",
            usage={"input_tokens": 100, "output_tokens": 50},
        )

        agent = CoachAgent(llm_service=mock_llm_service)

        plan = await agent.generate_recovery_plan(
            recovery_context={
                "days_missed": 5,
                "previous_streak": 10,
                "available_minutes": 30,
            },
        )

        assert "welcome_message" in plan
        assert "encouragement" in plan


# Assessment Agent Tests


class TestAssessmentAgent:
    """Tests for AssessmentAgent."""

    def test_agent_type(self, mock_llm_service):
        """Test that agent reports correct type."""
        agent = AssessmentAgent(llm_service=mock_llm_service)
        assert agent.agent_type == AgentType.ASSESSMENT

    @pytest.mark.asyncio
    async def test_generate_quiz(self, mock_llm_service):
        """Test quiz generation."""
        # Mock JSON response with quiz questions
        mock_llm_service.complete.return_value = LLMResponse(
            content='''[
                {
                    "id": "q1",
                    "type": "multiple_choice",
                    "question": "What is ML?",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": "A",
                    "explanation": "Because...",
                    "difficulty": 3
                }
            ]''',
            model="claude-sonnet-4-20250514",
            usage={"input_tokens": 100, "output_tokens": 200},
        )

        agent = AssessmentAgent(llm_service=mock_llm_service)

        quiz = await agent.generate_quiz(
            topics=["machine learning"],
            proficiency_level=3,
            question_count=5,
        )

        assert quiz.id is not None
        assert len(quiz.questions) > 0

    @pytest.mark.asyncio
    async def test_evaluate_quiz_answer_multiple_choice(self, mock_llm_service):
        """Test evaluating multiple choice answer."""
        agent = AssessmentAgent(llm_service=mock_llm_service)

        question = QuizQuestion(
            id="q1",
            type="multiple_choice",
            question="What is 2+2?",
            options=["3", "4", "5", "6"],
            correct_answer="4",
            explanation="Basic arithmetic",
        )

        is_correct, feedback = await agent.evaluate_quiz_answer(question, "4")

        assert is_correct is True
        assert "Correct" in feedback

    @pytest.mark.asyncio
    async def test_evaluate_feynman_dialogue(self, mock_llm_service):
        """Test Feynman dialogue evaluation."""
        # Mock JSON evaluation response
        mock_llm_service.complete.return_value = LLMResponse(
            content='''{
                "scores": {
                    "completeness": 0.8,
                    "accuracy": 0.9,
                    "simplicity": 0.7,
                    "overall": 0.8
                },
                "gaps": ["Minor gap"],
                "strengths": ["Clear explanation"],
                "suggestions": ["Add examples"],
                "inaccuracies": [],
                "jargon_unexplained": [],
                "follow_up_topics": []
            }''',
            model="claude-sonnet-4-20250514",
            usage={"input_tokens": 100, "output_tokens": 200},
        )

        agent = AssessmentAgent(llm_service=mock_llm_service)

        evaluation = await agent.evaluate_feynman_dialogue(
            topic="neural networks",
            dialogue_history=[
                {"role": "assistant", "content": "Explain neural networks"},
                {"role": "user", "content": "They are like brains..."},
            ],
        )

        assert evaluation.scores["overall"] == 0.8
        assert evaluation.mastery_level == "advanced"


# Orchestrator Tests


class TestAgentOrchestrator:
    """Tests for AgentOrchestrator."""

    @pytest.fixture
    def mock_agents(self, mock_llm_service):
        """Create mock agents."""
        return {
            "socratic": SocraticAgent(llm_service=mock_llm_service),
            "coach": CoachAgent(llm_service=mock_llm_service),
            "assessment": AssessmentAgent(llm_service=mock_llm_service),
        }

    def test_initialization(self, mock_llm_service, mock_agents):
        """Test orchestrator initialization."""
        orchestrator = AgentOrchestrator(
            llm_service=mock_llm_service,
            socratic_agent=mock_agents["socratic"],
            coach_agent=mock_agents["coach"],
            assessment_agent=mock_agents["assessment"],
        )

        available = orchestrator.get_available_agents()
        assert AgentType.SOCRATIC in available
        assert AgentType.COACH in available
        assert AgentType.ASSESSMENT in available

    @pytest.mark.asyncio
    async def test_route_message_new_conversation(self, mock_llm_service, mock_agents):
        """Test routing message in new conversation."""
        orchestrator = AgentOrchestrator(
            llm_service=mock_llm_service,
            socratic_agent=mock_agents["socratic"],
            coach_agent=mock_agents["coach"],
            assessment_agent=mock_agents["assessment"],
        )

        user_id = uuid4()
        response = await orchestrator.route_message(
            user_id=user_id,
            message="Hello, I want to learn",
        )

        assert response is not None
        assert isinstance(response, AgentResponse)

        # Should have created conversation state
        state = await orchestrator.get_conversation_state(user_id)
        assert state is not None

    @pytest.mark.asyncio
    async def test_force_agent(self, mock_llm_service, mock_agents):
        """Test forcing specific agent."""
        orchestrator = AgentOrchestrator(
            llm_service=mock_llm_service,
            socratic_agent=mock_agents["socratic"],
            coach_agent=mock_agents["coach"],
            assessment_agent=mock_agents["assessment"],
        )

        user_id = uuid4()
        response = await orchestrator.force_agent(
            user_id=user_id,
            agent_type=AgentType.ASSESSMENT,
            message="Give me a quiz",
        )

        assert response.agent_type == AgentType.ASSESSMENT

    @pytest.mark.asyncio
    async def test_reset_conversation(self, mock_llm_service, mock_agents):
        """Test resetting conversation state."""
        orchestrator = AgentOrchestrator(
            llm_service=mock_llm_service,
            socratic_agent=mock_agents["socratic"],
            coach_agent=mock_agents["coach"],
            assessment_agent=mock_agents["assessment"],
        )

        user_id = uuid4()

        # Create conversation
        await orchestrator.route_message(user_id=user_id, message="Hello")

        # Verify state exists
        state = await orchestrator.get_conversation_state(user_id)
        assert state is not None

        # Reset
        await orchestrator.reset_conversation(user_id)

        # Verify state is gone
        state = await orchestrator.get_conversation_state(user_id)
        assert state is None

    @pytest.mark.asyncio
    async def test_start_feynman_dialogue(self, mock_llm_service, mock_agents):
        """Test starting Feynman dialogue through orchestrator."""
        orchestrator = AgentOrchestrator(
            llm_service=mock_llm_service,
            socratic_agent=mock_agents["socratic"],
            coach_agent=mock_agents["coach"],
            assessment_agent=mock_agents["assessment"],
        )

        user_id = uuid4()
        response = await orchestrator.start_feynman_dialogue(
            user_id=user_id,
            topic="machine learning",
        )

        assert response.agent_type == AgentType.SOCRATIC

        # Check conversation state
        state = await orchestrator.get_conversation_state(user_id)
        assert state is not None
        assert state.current_agent == AgentType.SOCRATIC
        assert state.context.get("feynman_topic") == "machine learning"

    @pytest.mark.asyncio
    async def test_start_quiz(self, mock_llm_service, mock_agents):
        """Test starting quiz through orchestrator."""
        # Mock quiz generation response
        mock_llm_service.complete.return_value = LLMResponse(
            content='[{"id": "q1", "type": "multiple_choice", "question": "Test?", "options": ["A", "B"], "correct_answer": "A", "explanation": "...", "difficulty": 3}]',
            model="claude-sonnet-4-20250514",
            usage={"input_tokens": 100, "output_tokens": 100},
        )

        orchestrator = AgentOrchestrator(
            llm_service=mock_llm_service,
            socratic_agent=mock_agents["socratic"],
            coach_agent=mock_agents["coach"],
            assessment_agent=mock_agents["assessment"],
        )

        user_id = uuid4()
        response = await orchestrator.start_quiz(
            user_id=user_id,
            topics=["python basics"],
            question_count=5,
        )

        assert response.agent_type == AgentType.ASSESSMENT

        # Check conversation state
        state = await orchestrator.get_conversation_state(user_id)
        assert state is not None
        assert state.current_agent == AgentType.ASSESSMENT


# Integration-style tests


class TestAgentIntegration:
    """Integration tests for agent interactions."""

    @pytest.mark.asyncio
    async def test_full_feynman_flow(self, mock_llm_service):
        """Test complete Feynman dialogue flow."""
        # Set up orchestrator with real agents
        socratic = SocraticAgent(llm_service=mock_llm_service)
        coach = CoachAgent(llm_service=mock_llm_service)
        assessment = AssessmentAgent(llm_service=mock_llm_service)

        orchestrator = AgentOrchestrator(
            llm_service=mock_llm_service,
            socratic_agent=socratic,
            coach_agent=coach,
            assessment_agent=assessment,
        )

        user_id = uuid4()

        # Start dialogue
        response1 = await orchestrator.start_feynman_dialogue(
            user_id=user_id,
            topic="neural networks",
        )
        assert response1.agent_type == AgentType.SOCRATIC

        # Continue with explanation
        response2 = await orchestrator.route_message(
            user_id=user_id,
            message="Neural networks are computational models inspired by biological brains...",
        )
        assert response2.agent_type == AgentType.SOCRATIC

    @pytest.mark.asyncio
    async def test_agent_transition(self, mock_llm_service):
        """Test transitioning between agents."""
        socratic = SocraticAgent(llm_service=mock_llm_service)
        coach = CoachAgent(llm_service=mock_llm_service)
        assessment = AssessmentAgent(llm_service=mock_llm_service)

        orchestrator = AgentOrchestrator(
            llm_service=mock_llm_service,
            socratic_agent=socratic,
            coach_agent=coach,
            assessment_agent=assessment,
        )

        user_id = uuid4()

        # Start with coach
        response1 = await orchestrator.force_agent(
            user_id=user_id,
            agent_type=AgentType.COACH,
            message="Hello",
        )
        assert response1.agent_type == AgentType.COACH

        # Transition to assessment
        response2 = await orchestrator.transition_to(
            user_id=user_id,
            agent_type=AgentType.ASSESSMENT,
            transition_message="Let's test your knowledge",
        )
        assert response2.agent_type == AgentType.ASSESSMENT


class TestMenuOptionRouting:
    """Tests for menu option routing in orchestrator."""

    @pytest.fixture
    def orchestrator_with_agents(self, mock_llm_service):
        """Create orchestrator with all agents."""
        socratic = SocraticAgent(llm_service=mock_llm_service)
        coach = CoachAgent(llm_service=mock_llm_service)
        assessment = AssessmentAgent(llm_service=mock_llm_service)

        return AgentOrchestrator(
            llm_service=mock_llm_service,
            socratic_agent=socratic,
            coach_agent=coach,
            assessment_agent=assessment,
        )

    @pytest.mark.asyncio
    async def test_numeric_input_routes_to_menu_option(self, orchestrator_with_agents):
        """Test that numeric input '1' routes to agent specified in menu_options."""
        orchestrator = orchestrator_with_agents
        user_id = uuid4()

        # Create initial state with menu options
        state = ConversationState(
            user_id=user_id,
            session_id=uuid4(),
            current_agent=AgentType.COACH,
            history=[],
            context={
                "menu_options": {
                    "1": {"agent": AgentType.CURRICULUM, "action": "learn", "label": "Learn"},
                    "2": {"agent": AgentType.ASSESSMENT, "action": "quiz", "label": "Quiz"},
                }
            },
            started_at=datetime.utcnow(),
            last_activity=datetime.utcnow(),
        )

        # Manually save state to orchestrator
        await orchestrator._save_conversation_state(user_id, state)

        # Call _determine_agent with "1"
        result = await orchestrator._determine_agent(state, "1")

        assert result == AgentType.CURRICULUM
        # Menu options should be cleared after selection
        assert "menu_options" not in state.context

    @pytest.mark.asyncio
    async def test_ambiguous_input_uses_pending_suggestion(self, orchestrator_with_agents):
        """Test that ambiguous input 'ok' uses pending_next_agent."""
        orchestrator = orchestrator_with_agents
        user_id = uuid4()

        # Create state with pending_next_agent but no menu options
        state = ConversationState(
            user_id=user_id,
            session_id=uuid4(),
            current_agent=AgentType.COACH,
            history=[],
            context={
                "pending_next_agent": AgentType.SCOUT,
            },
            started_at=datetime.utcnow(),
            last_activity=datetime.utcnow(),
        )

        await orchestrator._save_conversation_state(user_id, state)

        # "ok" is ambiguous, should use pending suggestion
        result = await orchestrator._determine_agent(state, "ok")

        assert result == AgentType.SCOUT
        # Pending should be cleared after use
        assert "pending_next_agent" not in state.context

    @pytest.mark.asyncio
    async def test_explicit_keyword_overrides_menu(self, orchestrator_with_agents):
        """Test that explicit keyword 'quiz' overrides menu options."""
        orchestrator = orchestrator_with_agents
        user_id = uuid4()

        # Create state with menu options that would route to CURRICULUM
        state = ConversationState(
            user_id=user_id,
            session_id=uuid4(),
            current_agent=AgentType.COACH,
            history=[],
            context={
                "menu_options": {
                    "1": {"agent": AgentType.CURRICULUM, "action": "learn", "label": "Learn"},
                },
                "pending_next_agent": AgentType.CURRICULUM,
            },
            started_at=datetime.utcnow(),
            last_activity=datetime.utcnow(),
        )

        await orchestrator._save_conversation_state(user_id, state)

        # "quiz" is an explicit keyword, should override menu/pending
        result = await orchestrator._determine_agent(state, "quiz")

        assert result == AgentType.ASSESSMENT
        # Menu and pending should be cleared for explicit inputs
        assert "menu_options" not in state.context
        assert "pending_next_agent" not in state.context

    def test_is_ambiguous_input(self, orchestrator_with_agents):
        """Test the ambiguous input detection helper."""
        orchestrator = orchestrator_with_agents

        # Numeric inputs are ambiguous
        assert orchestrator._is_ambiguous_input("1") is True
        assert orchestrator._is_ambiguous_input("2") is True
        assert orchestrator._is_ambiguous_input("123") is True

        # Short affirmative responses are ambiguous
        assert orchestrator._is_ambiguous_input("ok") is True
        assert orchestrator._is_ambiguous_input("yes") is True
        assert orchestrator._is_ambiguous_input("no") is True
        assert orchestrator._is_ambiguous_input("y") is True
        assert orchestrator._is_ambiguous_input("sure") is True

        # Regular messages are not ambiguous
        assert orchestrator._is_ambiguous_input("I want to learn about ML") is False
        assert orchestrator._is_ambiguous_input("explain neural networks") is False
        assert orchestrator._is_ambiguous_input("give me a quiz") is False

    @pytest.mark.asyncio
    async def test_menu_option_stores_selected_action(self, orchestrator_with_agents):
        """Test that selecting a menu option stores the action in context."""
        orchestrator = orchestrator_with_agents
        user_id = uuid4()

        state = ConversationState(
            user_id=user_id,
            session_id=uuid4(),
            current_agent=AgentType.COACH,
            history=[],
            context={
                "menu_options": {
                    "1": {"agent": AgentType.CURRICULUM, "action": "generate_path", "label": "Build path"},
                }
            },
            started_at=datetime.utcnow(),
            last_activity=datetime.utcnow(),
        )

        await orchestrator._save_conversation_state(user_id, state)

        # Select option 1
        result = await orchestrator._determine_agent(state, "1")

        assert result == AgentType.CURRICULUM
        # Action should be stored for the target agent
        assert state.context.get("selected_action") == "generate_path"


class TestMenuOptionDataclass:
    """Tests for the MenuOption dataclass."""

    def test_menu_option_creation(self):
        """Test creating a MenuOption."""
        option = MenuOption(
            number="1",
            label="Learn about ML",
            agent=AgentType.CURRICULUM,
            action="learn_concepts",
        )

        assert option.number == "1"
        assert option.label == "Learn about ML"
        assert option.agent == AgentType.CURRICULUM
        assert option.action == "learn_concepts"

    def test_menu_option_without_action(self):
        """Test creating MenuOption without action (optional field)."""
        option = MenuOption(
            number="2",
            label="Take a quiz",
            agent=AgentType.ASSESSMENT,
        )

        assert option.number == "2"
        assert option.agent == AgentType.ASSESSMENT
        assert option.action is None


class TestCurriculumAgentOnboarding:
    """Tests for CurriculumAgent onboarding flow - prevents regression of repeated onboarding bug."""

    @pytest.fixture
    def curriculum_agent(self, mock_llm_service):
        """Create curriculum agent with mock LLM."""
        from src.modules.agents.curriculum import CurriculumAgent
        return CurriculumAgent(llm_service=mock_llm_service)

    def test_needs_onboarding_returns_false_when_complete(self, curriculum_agent):
        """Test that _needs_onboarding returns False when onboarding is already complete.

        This is the critical fix for the bug where users were repeatedly asked
        for background info even after completing onboarding.
        """
        from src.modules.agents.learning_context import OnboardingState, SharedLearningContext

        # Create learning context with minimal info (would normally trigger onboarding)
        learning_ctx = SharedLearningContext(
            user_id=uuid4(),
            primary_goal="Machine Learning",
        )

        # Create completed onboarding state - this should prevent re-onboarding
        onboarding = OnboardingState(
            agent_type="curriculum",
            is_complete=True,
            answers_collected={
                "motivation": "career",
                "timeline": "6 months",
                "programming": "beginner",
                "math": "algebra",
                "style": "hands-on",
            },
        )

        # CRITICAL: Should return False because onboarding is already complete
        result = curriculum_agent._needs_onboarding(learning_ctx, onboarding)
        assert result is False, "Completed onboarding should prevent re-onboarding"

    def test_needs_onboarding_checks_all_constraint_fields(self, curriculum_agent):
        """Test that _needs_onboarding checks all constraint fields, not just timeline/motivation.

        Bug: Original code only checked for 'timeline' or 'motivation' in constraints,
        but onboarding also collects 'programming_background' and 'math_background'.
        """
        from src.modules.agents.learning_context import SharedLearningContext

        # Create context with programming_background but no timeline/motivation
        # This was incorrectly returning True (needs onboarding) before the fix
        learning_ctx = SharedLearningContext(
            user_id=uuid4(),
            primary_goal="ML",
            constraints={"programming_background": "beginner"},
            preferences={"learning_style": "hands-on"},
        )

        # Should return False because we have goal + constraint + preference
        result = curriculum_agent._needs_onboarding(learning_ctx, None)
        assert result is False, "programming_background should count as a valid constraint"

    def test_needs_onboarding_checks_math_background(self, curriculum_agent):
        """Test that math_background is also recognized as a valid constraint."""
        from src.modules.agents.learning_context import SharedLearningContext

        learning_ctx = SharedLearningContext(
            user_id=uuid4(),
            primary_goal="ML",
            constraints={"math_background": "algebra"},
            preferences={"learning_style": "theory-first"},
        )

        result = curriculum_agent._needs_onboarding(learning_ctx, None)
        assert result is False, "math_background should count as a valid constraint"

    def test_needs_onboarding_returns_true_when_missing_info(self, curriculum_agent):
        """Test that _needs_onboarding returns True when key info is missing."""
        from src.modules.agents.learning_context import SharedLearningContext

        # No constraints, no preferences - should need onboarding
        learning_ctx = SharedLearningContext(
            user_id=uuid4(),
            primary_goal="ML",
        )

        result = curriculum_agent._needs_onboarding(learning_ctx, None)
        assert result is True, "Missing constraints/preferences should require onboarding"

    def test_is_continuation_message_detects_affirmations(self, curriculum_agent):
        """Test that continuation messages are properly detected."""
        # These should all be detected as continuation messages
        assert curriculum_agent._is_continuation_message("ok") is True
        assert curriculum_agent._is_continuation_message("yes") is True
        assert curriculum_agent._is_continuation_message("let's go") is True
        assert curriculum_agent._is_continuation_message("let's start") is True
        assert curriculum_agent._is_continuation_message("let's get started") is True
        assert curriculum_agent._is_continuation_message("ok lets get started then") is True
        assert curriculum_agent._is_continuation_message("no lets get started") is True
        assert curriculum_agent._is_continuation_message("ready") is True
        assert curriculum_agent._is_continuation_message("proceed") is True
        assert curriculum_agent._is_continuation_message("sounds good") is True

    def test_is_continuation_message_rejects_topics(self, curriculum_agent):
        """Test that actual topics are not detected as continuation messages."""
        # These should NOT be detected as continuation messages
        assert curriculum_agent._is_continuation_message("Machine Learning") is False
        assert curriculum_agent._is_continuation_message("I want to learn Python") is False
        assert curriculum_agent._is_continuation_message("Core concepts") is False
        assert curriculum_agent._is_continuation_message("theory first") is False

    def test_needs_onboarding_with_learning_path(self, curriculum_agent):
        """Test that having a learning path prevents re-onboarding."""
        from src.modules.agents.learning_context import SharedLearningContext, LearningPathStage

        learning_ctx = SharedLearningContext(
            user_id=uuid4(),
            primary_goal="ML",
            learning_path=[
                LearningPathStage(
                    topic="Foundations",
                    status="in_progress",
                    progress=0.5,
                    milestone="Understand basics",
                )
            ],
        )

        result = curriculum_agent._needs_onboarding(learning_ctx, None)
        assert result is False, "Having a learning path should prevent re-onboarding"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
