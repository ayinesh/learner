"""Integration tests for assessment flow."""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, patch
from sqlalchemy import text

from src.modules.auth import get_auth_service
from src.modules.assessment import get_assessment_service
from src.modules.llm.service import LLMResponse
from src.shared.database import get_db_session


@pytest.fixture
async def test_user():
    """Create a test user for assessment tests."""
    auth_service = get_auth_service()
    test_email = f"integration_assessment_{uuid4().hex[:8]}@example.com"

    # Clean up any existing test users (using parameterized queries to prevent SQL injection)
    async with get_db_session() as session:
        await session.execute(
            text("DELETE FROM users WHERE email = :email"),
            {"email": test_email}
        )
        await session.commit()

    result = await auth_service.register(test_email, "TestPassword123!")
    yield result.user_id

    # Cleanup (using parameterized queries to prevent SQL injection)
    async with get_db_session() as session:
        await session.execute(
            text("DELETE FROM quiz_attempts WHERE user_id = :user_id"),
            {"user_id": str(result.user_id)}
        )
        await session.execute(
            text("DELETE FROM quizzes WHERE user_id = :user_id"),
            {"user_id": str(result.user_id)}
        )
        await session.execute(
            text("DELETE FROM refresh_tokens WHERE user_id = :user_id"),
            {"user_id": str(result.user_id)}
        )
        await session.execute(
            text("DELETE FROM users WHERE id = :user_id"),
            {"user_id": str(result.user_id)}
        )
        await session.commit()


@pytest.fixture
def mock_llm_response():
    """Mock LLM response for quiz generation."""
    return LLMResponse(
        content='''[
            {
                "id": "q1",
                "type": "multiple_choice",
                "question": "What is Python?",
                "options": ["A programming language", "A snake", "A framework", "A database"],
                "correct_answer": "A programming language",
                "explanation": "Python is a high-level programming language.",
                "difficulty": 2
            },
            {
                "id": "q2",
                "type": "multiple_choice",
                "question": "What is async/await used for?",
                "options": ["Synchronous code", "Asynchronous code", "Database queries", "File I/O"],
                "correct_answer": "Asynchronous code",
                "explanation": "async/await is used for writing asynchronous code.",
                "difficulty": 3
            }
        ]''',
        model="claude-sonnet-4-20250514",
        usage={"input_tokens": 100, "output_tokens": 200},
    )


class TestAssessmentFlow:
    """Test complete assessment flow."""

    @pytest.mark.asyncio
    async def test_quiz_generation_and_submission(self, test_user, mock_llm_response):
        """Test quiz generation -> answer submission -> scoring flow."""
        assessment_service = get_assessment_service()
        user_id = test_user

        # Mock the LLM service for quiz generation
        with patch('src.modules.llm.service.LLMService.complete', new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = mock_llm_response

            # Step 1: Generate a quiz
            quiz = await assessment_service.generate_quiz(
                user_id=user_id,
                topics=["Python basics"],
                question_count=2,
                proficiency_level=2
            )

            assert quiz is not None
            assert len(quiz.questions) == 2
            assert quiz.questions[0].question == "What is Python?"

            quiz_id = quiz.id

            # Step 2: Start quiz attempt
            attempt = await assessment_service.start_quiz_attempt(
                user_id=user_id,
                quiz_id=quiz_id
            )

            assert attempt is not None
            assert attempt.quiz_id == quiz_id
            assert attempt.user_id == user_id
            assert len(attempt.answers) == 0

            attempt_id = attempt.id

            # Step 3: Submit answers
            answers = [
                {"question_id": "q1", "answer": "A programming language"},
                {"question_id": "q2", "answer": "Asynchronous code"}
            ]

            result = await assessment_service.submit_quiz_answers(
                user_id=user_id,
                attempt_id=attempt_id,
                answers=answers
            )

            assert result is not None
            assert result.score > 0
            assert len(result.answers) == 2
            assert all(a.is_correct for a in result.answers)

    @pytest.mark.asyncio
    async def test_partial_quiz_answers(self, test_user, mock_llm_response):
        """Test submitting partial quiz answers."""
        assessment_service = get_assessment_service()
        user_id = test_user

        with patch('src.modules.llm.service.LLMService.complete', new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = mock_llm_response

            # Generate quiz
            quiz = await assessment_service.generate_quiz(
                user_id=user_id,
                topics=["Python"],
                question_count=2,
                proficiency_level=2
            )

            # Start attempt
            attempt = await assessment_service.start_quiz_attempt(
                user_id=user_id,
                quiz_id=quiz.id
            )

            # Submit only one answer
            answers = [
                {"question_id": "q1", "answer": "A programming language"}
            ]

            result = await assessment_service.submit_quiz_answers(
                user_id=user_id,
                attempt_id=attempt.id,
                answers=answers
            )

            assert result is not None
            assert len(result.answers) == 1
            assert result.score <= 50  # Only answered half

    @pytest.mark.asyncio
    async def test_wrong_answers_scoring(self, test_user, mock_llm_response):
        """Test scoring with wrong answers."""
        assessment_service = get_assessment_service()
        user_id = test_user

        with patch('src.modules.llm.service.LLMService.complete', new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = mock_llm_response

            # Generate quiz
            quiz = await assessment_service.generate_quiz(
                user_id=user_id,
                topics=["Python"],
                question_count=2,
                proficiency_level=2
            )

            # Start attempt
            attempt = await assessment_service.start_quiz_attempt(
                user_id=user_id,
                quiz_id=quiz.id
            )

            # Submit wrong answers
            answers = [
                {"question_id": "q1", "answer": "A snake"},
                {"question_id": "q2", "answer": "Synchronous code"}
            ]

            result = await assessment_service.submit_quiz_answers(
                user_id=user_id,
                attempt_id=attempt.id,
                answers=answers
            )

            assert result is not None
            assert result.score == 0
            assert all(not a.is_correct for a in result.answers)

    @pytest.mark.asyncio
    async def test_quiz_history(self, test_user, mock_llm_response):
        """Test retrieving quiz history."""
        assessment_service = get_assessment_service()
        user_id = test_user

        with patch('src.modules.llm.service.LLMService.complete', new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = mock_llm_response

            # Generate and complete multiple quizzes
            for i in range(3):
                quiz = await assessment_service.generate_quiz(
                    user_id=user_id,
                    topics=["Python"],
                    question_count=2,
                    proficiency_level=2
                )

                attempt = await assessment_service.start_quiz_attempt(
                    user_id=user_id,
                    quiz_id=quiz.id
                )

                answers = [
                    {"question_id": "q1", "answer": "A programming language"},
                    {"question_id": "q2", "answer": "Asynchronous code"}
                ]

                await assessment_service.submit_quiz_answers(
                    user_id=user_id,
                    attempt_id=attempt.id,
                    answers=answers
                )

            # Get history
            history = await assessment_service.get_quiz_history(user_id, limit=10)

            assert len(history) >= 3
            # Most recent first
            assert all(h.score == 100 for h in history)

    @pytest.mark.asyncio
    async def test_feynman_dialogue_evaluation(self, test_user):
        """Test Feynman technique dialogue evaluation."""
        assessment_service = get_assessment_service()
        user_id = test_user

        # Mock evaluation response
        eval_response = LLMResponse(
            content='''{
                "scores": {
                    "completeness": 0.8,
                    "accuracy": 0.9,
                    "simplicity": 0.7,
                    "overall": 0.8
                },
                "gaps": ["Could explain activation functions better"],
                "strengths": ["Clear analogy to biological neurons"],
                "suggestions": ["Add concrete examples"],
                "inaccuracies": [],
                "jargon_unexplained": [],
                "follow_up_topics": ["Backpropagation", "Gradient descent"]
            }''',
            model="claude-sonnet-4-20250514",
            usage={"input_tokens": 150, "output_tokens": 100},
        )

        with patch('src.modules.llm.service.LLMService.complete', new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = eval_response

            # Evaluate dialogue
            dialogue_history = [
                {"role": "assistant", "content": "Explain neural networks to me"},
                {"role": "user", "content": "Neural networks are like brains made of math..."},
                {"role": "assistant", "content": "How do they learn?"},
                {"role": "user", "content": "They adjust weights based on errors..."}
            ]

            evaluation = await assessment_service.evaluate_feynman_dialogue(
                user_id=user_id,
                topic="neural networks",
                dialogue_history=dialogue_history
            )

            assert evaluation is not None
            assert evaluation.scores["overall"] == 0.8
            assert evaluation.mastery_level == "advanced"
            assert len(evaluation.gaps) > 0
            assert len(evaluation.strengths) > 0

    @pytest.mark.asyncio
    async def test_get_recommendations(self, test_user, mock_llm_response):
        """Test getting study recommendations based on quiz performance."""
        assessment_service = get_assessment_service()
        user_id = test_user

        with patch('src.modules.llm.service.LLMService.complete', new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = mock_llm_response

            # Take a quiz with some wrong answers
            quiz = await assessment_service.generate_quiz(
                user_id=user_id,
                topics=["Python"],
                question_count=2,
                proficiency_level=2
            )

            attempt = await assessment_service.start_quiz_attempt(
                user_id=user_id,
                quiz_id=quiz.id
            )

            answers = [
                {"question_id": "q1", "answer": "A snake"},  # Wrong
                {"question_id": "q2", "answer": "Asynchronous code"}  # Correct
            ]

            await assessment_service.submit_quiz_answers(
                user_id=user_id,
                attempt_id=attempt.id,
                answers=answers
            )

            # Get recommendations
            recommendations = await assessment_service.get_study_recommendations(user_id)

            assert recommendations is not None
            assert "weak_topics" in recommendations or "focus_areas" in recommendations


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
