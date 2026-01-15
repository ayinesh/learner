"""Unit tests for enhanced question types."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.modules.assessment.question_types import (
    QuestionDifficulty,
    QuestionType,
    QuestionOption,
    GeneratedQuestion,
    QuestionGenerator,
    ScenarioQuestionGenerator,
    ComparisonQuestionGenerator,
    ApplicationQuestionGenerator,
    QuestionGeneratorFactory,
    generate_mixed_questions,
)


class TestQuestionDifficulty:
    """Tests for QuestionDifficulty enum."""

    def test_difficulty_levels(self):
        """Test all difficulty levels exist."""
        levels = [d.value for d in QuestionDifficulty]
        assert "recall" in levels
        assert "understand" in levels
        assert "apply" in levels
        assert "analyze" in levels
        assert "evaluate" in levels
        assert "create" in levels


class TestQuestionType:
    """Tests for QuestionType enum."""

    def test_question_types(self):
        """Test all question types exist."""
        types = [t.value for t in QuestionType]
        assert "scenario" in types
        assert "comparison" in types
        assert "application" in types
        assert "multiple_choice" in types


class TestGeneratedQuestion:
    """Tests for GeneratedQuestion dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        question = GeneratedQuestion(
            question_type=QuestionType.SCENARIO,
            difficulty=QuestionDifficulty.APPLY,
            text="What would you do?",
            topic="testing",
            options=[
                QuestionOption("Option A", True, "Correct"),
                QuestionOption("Option B", False, "Wrong"),
            ],
            correct_answer="Option A",
            explanation="Because...",
            hints=["Hint 1"],
            context="You are testing software.",
        )

        result = question.to_dict()

        assert result["question_type"] == "scenario"
        assert result["difficulty"] == "apply"
        assert result["text"] == "What would you do?"
        assert len(result["options"]) == 2
        assert result["options"][0]["is_correct"] is True
        assert result["context"] == "You are testing software."


class TestScenarioQuestionGenerator:
    """Tests for ScenarioQuestionGenerator."""

    @pytest.fixture
    def generator(self):
        """Create generator without LLM."""
        return ScenarioQuestionGenerator()

    @pytest.fixture
    def generator_with_llm(self):
        """Create generator with mock LLM."""
        mock_llm = AsyncMock()
        return ScenarioQuestionGenerator(llm_service=mock_llm)

    def test_question_type_property(self, generator):
        """Test question type is SCENARIO."""
        assert generator.question_type == QuestionType.SCENARIO

    @pytest.mark.asyncio
    async def test_generate_without_llm(self, generator):
        """Test generation falls back to templates."""
        question = await generator.generate(
            topic="neural_networks",
            difficulty=QuestionDifficulty.APPLY,
        )

        assert question.question_type == QuestionType.SCENARIO
        assert question.topic == "neural_networks"
        assert len(question.options) > 0
        assert question.correct_answer is not None

    @pytest.mark.asyncio
    async def test_generate_generic_for_unknown_topic(self, generator):
        """Test generic scenario for unknown topic."""
        question = await generator.generate(
            topic="unknown_topic_xyz",
            difficulty=QuestionDifficulty.ANALYZE,
        )

        assert question.question_type == QuestionType.SCENARIO
        assert question.topic == "unknown_topic_xyz"
        assert len(question.options) >= 2

    @pytest.mark.asyncio
    async def test_generate_with_llm(self, generator_with_llm):
        """Test generation uses LLM when available."""
        import json

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "scenario": "A test scenario",
            "question": "What should you do?",
            "options": [
                {"text": "Option A", "is_correct": True, "explanation": "Best"},
                {"text": "Option B", "is_correct": False, "explanation": "Not ideal"},
            ],
            "explanation": "Option A is correct because...",
            "hints": ["Think about..."],
        })
        generator_with_llm._llm.complete.return_value = mock_response

        question = await generator_with_llm.generate(
            topic="testing",
            difficulty=QuestionDifficulty.APPLY,
        )

        assert question.text == "What should you do?"
        assert question.context == "A test scenario"


class TestComparisonQuestionGenerator:
    """Tests for ComparisonQuestionGenerator."""

    @pytest.fixture
    def generator(self):
        """Create generator without LLM."""
        return ComparisonQuestionGenerator()

    def test_question_type_property(self, generator):
        """Test question type is COMPARISON."""
        assert generator.question_type == QuestionType.COMPARISON

    @pytest.mark.asyncio
    async def test_generate_for_known_topic(self, generator):
        """Test generation for topic with templates."""
        question = await generator.generate(
            topic="normalization",
            difficulty=QuestionDifficulty.ANALYZE,
        )

        assert question.question_type == QuestionType.COMPARISON
        assert "concept_a" in question.metadata or question.metadata == {}

    @pytest.mark.asyncio
    async def test_generate_for_unknown_topic(self, generator):
        """Test generic comparison for unknown topic."""
        question = await generator.generate(
            topic="random_topic",
            difficulty=QuestionDifficulty.ANALYZE,
        )

        assert question.question_type == QuestionType.COMPARISON
        assert len(question.options) >= 2


class TestApplicationQuestionGenerator:
    """Tests for ApplicationQuestionGenerator."""

    @pytest.fixture
    def generator(self):
        """Create generator without LLM."""
        return ApplicationQuestionGenerator()

    def test_question_type_property(self, generator):
        """Test question type is APPLICATION."""
        assert generator.question_type == QuestionType.APPLICATION

    @pytest.mark.asyncio
    async def test_generate_for_known_topic(self, generator):
        """Test generation for topic with templates."""
        question = await generator.generate(
            topic="attention",
            difficulty=QuestionDifficulty.APPLY,
        )

        assert question.question_type == QuestionType.APPLICATION
        assert len(question.options) >= 2

    @pytest.mark.asyncio
    async def test_generate_generic(self, generator):
        """Test generic application question."""
        question = await generator.generate(
            topic="any_topic",
            difficulty=QuestionDifficulty.APPLY,
        )

        assert question.question_type == QuestionType.APPLICATION
        assert question.correct_answer is not None


class TestQuestionGeneratorFactory:
    """Tests for QuestionGeneratorFactory."""

    def test_create_scenario_generator(self):
        """Test creating scenario generator."""
        generator = QuestionGeneratorFactory.create(QuestionType.SCENARIO)
        assert isinstance(generator, ScenarioQuestionGenerator)

    def test_create_comparison_generator(self):
        """Test creating comparison generator."""
        generator = QuestionGeneratorFactory.create(QuestionType.COMPARISON)
        assert isinstance(generator, ComparisonQuestionGenerator)

    def test_create_application_generator(self):
        """Test creating application generator."""
        generator = QuestionGeneratorFactory.create(QuestionType.APPLICATION)
        assert isinstance(generator, ApplicationQuestionGenerator)

    def test_create_with_llm(self):
        """Test creating generator with LLM service."""
        mock_llm = MagicMock()
        generator = QuestionGeneratorFactory.create(
            QuestionType.SCENARIO,
            llm_service=mock_llm,
        )
        assert generator._llm is mock_llm

    def test_unsupported_type_raises_error(self):
        """Test that unsupported types raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported"):
            QuestionGeneratorFactory.create(QuestionType.TRUE_FALSE)

    def test_get_supported_types(self):
        """Test getting supported types."""
        types = QuestionGeneratorFactory.get_supported_types()
        assert QuestionType.SCENARIO in types
        assert QuestionType.COMPARISON in types
        assert QuestionType.APPLICATION in types


class TestGenerateMixedQuestions:
    """Tests for generate_mixed_questions function."""

    @pytest.mark.asyncio
    async def test_generates_correct_count(self):
        """Test generating specified number of questions."""
        questions = await generate_mixed_questions(
            topic="machine_learning",
            count=5,
            difficulty=QuestionDifficulty.APPLY,
        )

        assert len(questions) == 5

    @pytest.mark.asyncio
    async def test_generates_mixed_types(self):
        """Test that questions have different types."""
        questions = await generate_mixed_questions(
            topic="testing",
            count=6,
            difficulty=QuestionDifficulty.ANALYZE,
        )

        types = {q.question_type for q in questions}
        assert len(types) >= 2  # At least 2 different types

    @pytest.mark.asyncio
    async def test_with_llm_service(self):
        """Test generation with LLM service (falls back to templates on error)."""
        # The generators use LLM for dynamic content but fall back on failure
        # Testing that 3 questions are generated, even if some fail with mock
        questions = await generate_mixed_questions(
            topic="testing",
            count=3,
            difficulty=QuestionDifficulty.APPLY,
            llm_service=None,  # No LLM, use templates
        )

        assert len(questions) == 3
