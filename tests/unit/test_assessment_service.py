"""Unit tests for AssessmentService."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.modules.assessment.interface import (
    Question,
    QuestionType,
    Quiz,
    QuizResult,
    FeynmanSession,
    FeynmanResult,
    Gap,
    ReviewItem,
)
from src.modules.assessment.service import AssessmentService
from src.modules.llm.service import LLMResponse, PromptTemplate


@pytest.fixture
def mock_llm_service():
    """Create a mock LLM service."""
    mock = MagicMock()

    async def mock_complete(*args, **kwargs):
        return LLMResponse(
            content="Mock LLM response",
            model="claude-sonnet-4-20250514",
            usage={"input_tokens": 100, "output_tokens": 50},
        )

    mock.complete = AsyncMock(side_effect=mock_complete)
    mock.complete_with_history = AsyncMock(side_effect=mock_complete)
    mock.load_prompt_template = MagicMock(return_value=PromptTemplate(
        name="test",
        system="Test system prompt",
        user="Test user prompt",
        variables=[],
    ))

    return mock


@pytest.fixture
def mock_assessment_agent(mock_llm_service):
    """Create a mock assessment agent."""
    from src.modules.agents.assessment_agent import AssessmentAgent, Quiz as AgentQuiz, QuizQuestion

    agent = MagicMock(spec=AssessmentAgent)

    # Mock generate_quiz
    async def mock_generate_quiz(*args, **kwargs):
        return AgentQuiz(
            id="quiz-123",
            questions=[
                QuizQuestion(
                    id="q1",
                    type="multiple_choice",
                    question="What is ML?",
                    options=["A", "B", "C", "D"],
                    correct_answer="A",
                    explanation="ML is...",
                    difficulty=3,
                )
            ],
            topic_ids=[],
        )

    agent.generate_quiz = AsyncMock(side_effect=mock_generate_quiz)

    # Mock evaluate_quiz_answer
    async def mock_evaluate(*args, **kwargs):
        return (True, "Correct!")

    agent.evaluate_quiz_answer = AsyncMock(side_effect=mock_evaluate)

    # Mock evaluate_feynman_dialogue
    from src.modules.agents.assessment_agent import FeynmanEvaluation

    async def mock_evaluate_feynman(*args, **kwargs):
        return FeynmanEvaluation(
            topic="test topic",
            scores={"completeness": 0.8, "accuracy": 0.9, "simplicity": 0.7, "overall": 0.8},
            gaps=["Minor gap"],
            inaccuracies=[],
            jargon_unexplained=[],
            strengths=["Good explanation"],
            suggestions=["Add examples"],
            follow_up_topics=[],
            mastery_level="advanced",
        )

    agent.evaluate_feynman_dialogue = AsyncMock(side_effect=mock_evaluate_feynman)

    return agent


@pytest.fixture
def mock_socratic_agent(mock_llm_service):
    """Create a mock Socratic agent."""
    from src.modules.agents.socratic import SocraticAgent

    agent = MagicMock(spec=SocraticAgent)

    agent.begin_dialogue = MagicMock()

    async def mock_start(*args, **kwargs):
        return "Please explain the concept to me."

    agent.start_dialogue = AsyncMock(side_effect=mock_start)

    async def mock_probe(*args, **kwargs):
        return ("Interesting, but can you explain more?", ["gap1"])

    agent.probe_explanation = AsyncMock(side_effect=mock_probe)

    return agent


@pytest.fixture
def assessment_service(mock_llm_service, mock_assessment_agent, mock_socratic_agent):
    """Create assessment service with mocks."""
    return AssessmentService(
        llm_service=mock_llm_service,
        assessment_agent=mock_assessment_agent,
        socratic_agent=mock_socratic_agent,
    )


class TestQuizGeneration:
    """Tests for quiz generation."""

    @pytest.mark.asyncio
    async def test_generate_quiz_basic(self, assessment_service):
        """Test basic quiz generation."""
        user_id = uuid4()
        topic_ids = [uuid4()]

        quiz = await assessment_service.generate_quiz(
            user_id=user_id,
            topic_ids=topic_ids,
            question_count=5,
        )

        assert quiz.id is not None
        assert quiz.user_id == user_id
        assert len(quiz.questions) > 0

    @pytest.mark.asyncio
    async def test_generate_quiz_without_topics(self, assessment_service):
        """Test quiz generation without specific topics."""
        user_id = uuid4()

        quiz = await assessment_service.generate_quiz(
            user_id=user_id,
            question_count=5,
        )

        assert quiz.id is not None

    @pytest.mark.asyncio
    async def test_quiz_stored(self, assessment_service):
        """Test that generated quiz is stored."""
        user_id = uuid4()

        quiz = await assessment_service.generate_quiz(
            user_id=user_id,
            question_count=5,
        )

        stored = assessment_service.get_quiz(quiz.id)
        assert stored is not None
        assert stored.id == quiz.id


class TestQuizEvaluation:
    """Tests for quiz evaluation."""

    @pytest.mark.asyncio
    async def test_evaluate_quiz(self, assessment_service):
        """Test quiz evaluation."""
        user_id = uuid4()

        # Generate quiz
        quiz = await assessment_service.generate_quiz(
            user_id=user_id,
            question_count=1,
        )

        # Evaluate answers
        result = await assessment_service.evaluate_quiz(
            quiz_id=quiz.id,
            answers=[{"question_id": str(quiz.questions[0].id), "answer": "A"}],
            time_taken_seconds=60,
        )

        assert result.quiz_id == quiz.id
        assert result.total_count == 1
        assert 0 <= result.score <= 1

    @pytest.mark.asyncio
    async def test_evaluate_quiz_not_found(self, assessment_service):
        """Test evaluating non-existent quiz."""
        with pytest.raises(ValueError, match="not found"):
            await assessment_service.evaluate_quiz(
                quiz_id=uuid4(),
                answers=[],
                time_taken_seconds=60,
            )


class TestFeynmanDialogue:
    """Tests for Feynman dialogue functionality."""

    @pytest.mark.asyncio
    async def test_start_feynman(self, assessment_service):
        """Test starting Feynman session."""
        user_id = uuid4()
        topic_id = uuid4()

        session = await assessment_service.start_feynman(
            user_id=user_id,
            topic_id=topic_id,
        )

        assert session.id is not None
        assert session.user_id == user_id
        assert session.topic_id == topic_id
        assert len(session.dialogue_history) == 1
        assert session.dialogue_history[0]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_continue_feynman(self, assessment_service):
        """Test continuing Feynman dialogue."""
        user_id = uuid4()
        topic_id = uuid4()

        # Start session
        session = await assessment_service.start_feynman(
            user_id=user_id,
            topic_id=topic_id,
        )

        # Continue with response
        response = await assessment_service.continue_feynman(
            session_id=session.id,
            user_response="Let me explain...",
        )

        assert response.message is not None
        assert isinstance(response.gaps_so_far, list)

    @pytest.mark.asyncio
    async def test_continue_feynman_not_found(self, assessment_service):
        """Test continuing non-existent session."""
        with pytest.raises(ValueError, match="not found"):
            await assessment_service.continue_feynman(
                session_id=uuid4(),
                user_response="test",
            )

    @pytest.mark.asyncio
    async def test_evaluate_feynman(self, assessment_service):
        """Test Feynman session evaluation."""
        user_id = uuid4()
        topic_id = uuid4()

        # Start and continue session
        session = await assessment_service.start_feynman(
            user_id=user_id,
            topic_id=topic_id,
        )

        await assessment_service.continue_feynman(
            session_id=session.id,
            user_response="Neural networks are...",
        )

        # Evaluate
        result = await assessment_service.evaluate_feynman(session_id=session.id)

        assert result.session_id == session.id
        assert 0 <= result.overall_score <= 1
        assert isinstance(result.gaps, list)
        assert isinstance(result.strengths, list)


class TestSpacedRepetition:
    """Tests for spaced repetition functionality."""

    @pytest.mark.asyncio
    async def test_get_due_reviews_empty(self, assessment_service):
        """Test getting due reviews when none exist."""
        user_id = uuid4()

        reviews = await assessment_service.get_due_reviews(user_id)

        assert reviews == []

    @pytest.mark.asyncio
    async def test_update_review_schedule_new(self, assessment_service):
        """Test creating new review schedule."""
        user_id = uuid4()
        topic_id = uuid4()

        item = await assessment_service.update_review_schedule(
            user_id=user_id,
            topic_id=topic_id,
            correct=True,
            quality=4,
        )

        assert item.topic_id == topic_id
        assert item.review_count == 1
        assert item.interval_days >= 1

    @pytest.mark.asyncio
    async def test_update_review_schedule_incorrect(self, assessment_service):
        """Test review schedule after incorrect answer."""
        user_id = uuid4()
        topic_id = uuid4()

        # First review (correct)
        await assessment_service.update_review_schedule(
            user_id=user_id,
            topic_id=topic_id,
            correct=True,
            quality=4,
        )

        # Second review (incorrect)
        item = await assessment_service.update_review_schedule(
            user_id=user_id,
            topic_id=topic_id,
            correct=False,
            quality=1,
        )

        # Interval should reset to 1
        assert item.interval_days == 1

    @pytest.mark.asyncio
    async def test_due_reviews_after_update(self, assessment_service):
        """Test that reviews become due after schedule update."""
        user_id = uuid4()
        topic_id = uuid4()

        # Register topic name
        assessment_service.register_topic(topic_id, "Test Topic")

        # Create review with past due date (by manipulating the returned item)
        item = await assessment_service.update_review_schedule(
            user_id=user_id,
            topic_id=topic_id,
            correct=True,
            quality=4,
        )

        # Manually set to past due for testing
        item.next_review = datetime.utcnow() - timedelta(days=1)

        # Get due reviews
        reviews = await assessment_service.get_due_reviews(user_id)

        assert len(reviews) == 1
        assert reviews[0].topic_id == topic_id


class TestGapIdentification:
    """Tests for gap identification."""

    @pytest.mark.asyncio
    async def test_identify_gaps_no_data(self, assessment_service):
        """Test gap identification with no assessment data."""
        user_id = uuid4()

        gaps = await assessment_service.identify_gaps(user_id)

        assert gaps == []

    @pytest.mark.asyncio
    async def test_identify_gaps_from_quiz(self, assessment_service, mock_assessment_agent):
        """Test gap identification from quiz results."""
        user_id = uuid4()
        topic_id = uuid4()

        # Mock a quiz result with gaps
        quiz_result = QuizResult(
            quiz_id=uuid4(),
            score=0.5,
            correct_count=1,
            total_count=2,
            answers=[],
            time_taken_seconds=60,
            gaps_identified=[topic_id],
        )

        assessment_service._quiz_results[user_id] = [quiz_result]

        gaps = await assessment_service.identify_gaps(user_id)

        assert len(gaps) > 0
        assert gaps[0].topic_id == topic_id
        assert gaps[0].identified_from == "quiz"


class TestTopicProficiency:
    """Tests for topic proficiency calculation."""

    @pytest.mark.asyncio
    async def test_get_proficiency_no_data(self, assessment_service):
        """Test proficiency with no data."""
        user_id = uuid4()
        topic_id = uuid4()

        proficiency = await assessment_service.get_topic_proficiency(user_id, topic_id)

        assert proficiency == 0.0

    @pytest.mark.asyncio
    async def test_topic_registration(self, assessment_service):
        """Test topic registration."""
        topic_id = uuid4()
        topic_name = "Test Topic"

        assessment_service.register_topic(topic_id, topic_name)

        assert assessment_service._topic_names[topic_id] == topic_name


class TestHelperMethods:
    """Tests for helper methods."""

    def test_get_quiz_not_found(self, assessment_service):
        """Test getting non-existent quiz."""
        result = assessment_service.get_quiz(uuid4())
        assert result is None

    def test_get_feynman_session_not_found(self, assessment_service):
        """Test getting non-existent Feynman session."""
        result = assessment_service.get_feynman_session(uuid4())
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
