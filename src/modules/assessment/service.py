"""Assessment Service - Quiz generation, Feynman dialogues, and spaced repetition.

This service provides:
- Quiz generation with multiple question types (scenario, comparison, application)
- Feynman dialogue sessions for deep understanding
- Spaced repetition scheduling using SM-2 algorithm
- Knowledge gap identification from assessment results
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from src.modules.assessment.interface import (
    FeynmanResponse,
    FeynmanResult,
    FeynmanSession,
    Gap,
    IAssessmentService,
    Question,
    QuestionType,
    Quiz,
    QuizResult,
    ReviewItem,
)
from src.modules.assessment.question_types import (
    QuestionDifficulty,
    QuestionType as EnhancedQuestionType,
    QuestionGeneratorFactory,
    GeneratedQuestion,
    generate_mixed_questions,
)
from src.modules.agents.socratic import SocraticAgent, get_socratic_agent
from src.modules.agents.assessment_agent import (
    AssessmentAgent,
    get_assessment_agent,
    FeynmanEvaluation,
)
from src.modules.llm.service import LLMService, get_llm_service
from src.shared.feature_flags import FeatureFlags, get_feature_flags


class AssessmentService(IAssessmentService):
    """Service for managing assessments, quizzes, and Feynman dialogues.

    This service coordinates between the assessment agent for quiz generation
    and the Socratic agent for Feynman dialogues. It also handles spaced
    repetition scheduling and gap identification.

    Enhanced question types (scenario, comparison, application) are available
    when the ENABLE_ENHANCED_QUESTIONS feature flag is enabled.
    """

    def __init__(
        self,
        llm_service: LLMService | None = None,
        assessment_agent: AssessmentAgent | None = None,
        socratic_agent: SocraticAgent | None = None,
    ) -> None:
        self._llm = llm_service or get_llm_service()
        self._assessment_agent = assessment_agent or get_assessment_agent()
        self._socratic_agent = socratic_agent or get_socratic_agent()
        self._flags = get_feature_flags()

        # In-memory storage (in production, use database)
        self._quizzes: dict[UUID, Quiz] = {}
        self._feynman_sessions: dict[UUID, FeynmanSession] = {}
        self._quiz_results: dict[UUID, list[QuizResult]] = {}
        self._feynman_results: dict[UUID, list[FeynmanResult]] = {}
        self._review_schedules: dict[tuple[UUID, UUID], ReviewItem] = {}  # (user_id, topic_id) -> ReviewItem
        self._topic_names: dict[UUID, str] = {}  # topic_id -> name cache

    # Quiz Methods

    async def generate_quiz(
        self,
        user_id: UUID,
        topic_ids: list[UUID] | None = None,
        question_count: int = 5,
        include_review: bool = True,
    ) -> Quiz:
        """Generate a quiz for the user."""
        # Get topic names (in production, fetch from content service)
        topics = []
        if topic_ids:
            for tid in topic_ids:
                name = self._topic_names.get(tid, f"Topic {str(tid)[:8]}")
                topics.append(name)
        else:
            topics = ["general learning concepts"]

        # Determine how many questions for new vs review
        review_count = 0
        if include_review:
            due_reviews = await self.get_due_reviews(user_id, limit=question_count // 2)
            review_count = min(len(due_reviews), question_count // 2)

        new_count = question_count - review_count

        # Get user proficiency (in production, fetch from user service)
        proficiency_level = 3  # Default mid-level

        # Generate quiz using assessment agent
        agent_quiz = await self._assessment_agent.generate_quiz(
            topics=topics,
            proficiency_level=proficiency_level,
            question_count=question_count,
            new_count=new_count,
            review_count=review_count,
        )

        # Convert to interface types
        questions = []
        for q in agent_quiz.questions:
            question = Question(
                id=UUID(q.id) if len(q.id) == 36 else uuid4(),
                type=QuestionType(q.type) if q.type in QuestionType.__members__.values() else QuestionType.MULTIPLE_CHOICE,
                question=q.question,
                options=q.options,
                correct_answer=q.correct_answer,
                explanation=q.explanation,
                topic_id=UUID(q.topic_id) if q.topic_id and len(q.topic_id) == 36 else None,
                difficulty=q.difficulty,
            )
            questions.append(question)

        quiz = Quiz(
            id=uuid4(),
            user_id=user_id,
            topic_ids=topic_ids or [],
            questions=questions,
            is_spaced_repetition=review_count > 0,
        )

        # Store quiz
        self._quizzes[quiz.id] = quiz

        return quiz

    async def generate_enhanced_quiz(
        self,
        user_id: UUID,
        topic: str,
        question_count: int = 5,
        difficulty: str = "apply",
        include_scenarios: bool = True,
        include_comparisons: bool = True,
    ) -> Quiz:
        """Generate a quiz with enhanced question types.

        This method generates quizzes using the enhanced question generators
        (scenario, comparison, application) for deeper learning assessment.

        Args:
            user_id: The user taking the quiz.
            topic: The topic to generate questions about.
            question_count: Number of questions to generate.
            difficulty: Difficulty level (recall, understand, apply, analyze, evaluate, create).
            include_scenarios: Whether to include scenario-based questions.
            include_comparisons: Whether to include comparison questions.

        Returns:
            A Quiz with enhanced question types.
        """
        # Check feature flag
        if not self._flags.is_enabled(FeatureFlags.ENABLE_ENHANCED_QUESTIONS):
            # Fall back to standard quiz generation
            return await self.generate_quiz(user_id, question_count=question_count)

        # Map difficulty string to enum
        difficulty_map = {
            "recall": QuestionDifficulty.RECALL,
            "understand": QuestionDifficulty.UNDERSTAND,
            "apply": QuestionDifficulty.APPLY,
            "analyze": QuestionDifficulty.ANALYZE,
            "evaluate": QuestionDifficulty.EVALUATE,
            "create": QuestionDifficulty.CREATE,
        }
        diff_level = difficulty_map.get(difficulty.lower(), QuestionDifficulty.APPLY)

        # Generate mixed questions using enhanced generators
        generated_questions = await generate_mixed_questions(
            topic=topic,
            count=question_count,
            difficulty=diff_level,
            llm_service=self._llm if self._flags.is_enabled(FeatureFlags.ENABLE_NLP_COMMANDS) else None,
        )

        # Convert to interface Question format
        questions = []
        for gq in generated_questions:
            question = self._convert_generated_question(gq)
            questions.append(question)

        quiz = Quiz(
            id=uuid4(),
            user_id=user_id,
            topic_ids=[],  # Enhanced quizzes use string topics
            questions=questions,
            is_spaced_repetition=False,
        )

        self._quizzes[quiz.id] = quiz
        return quiz

    async def generate_scenario_question(
        self,
        topic: str,
        difficulty: str = "apply",
    ) -> Question:
        """Generate a single scenario-based question.

        Scenario questions present a realistic situation and ask the learner
        to apply their knowledge to solve a problem.

        Args:
            topic: The topic for the scenario.
            difficulty: Difficulty level.

        Returns:
            A scenario-based Question.
        """
        difficulty_map = {
            "recall": QuestionDifficulty.RECALL,
            "understand": QuestionDifficulty.UNDERSTAND,
            "apply": QuestionDifficulty.APPLY,
            "analyze": QuestionDifficulty.ANALYZE,
            "evaluate": QuestionDifficulty.EVALUATE,
            "create": QuestionDifficulty.CREATE,
        }
        diff_level = difficulty_map.get(difficulty.lower(), QuestionDifficulty.APPLY)

        generator = QuestionGeneratorFactory.create(
            EnhancedQuestionType.SCENARIO,
            llm_service=self._llm if self._flags.is_enabled(FeatureFlags.ENABLE_NLP_COMMANDS) else None,
        )

        generated = await generator.generate(topic, diff_level)
        return self._convert_generated_question(generated)

    async def generate_comparison_question(
        self,
        topic: str,
        difficulty: str = "analyze",
    ) -> Question:
        """Generate a comparison question.

        Comparison questions ask learners to identify similarities, differences,
        or trade-offs between related concepts.

        Args:
            topic: The topic for comparison.
            difficulty: Difficulty level.

        Returns:
            A comparison Question.
        """
        difficulty_map = {
            "recall": QuestionDifficulty.RECALL,
            "understand": QuestionDifficulty.UNDERSTAND,
            "apply": QuestionDifficulty.APPLY,
            "analyze": QuestionDifficulty.ANALYZE,
            "evaluate": QuestionDifficulty.EVALUATE,
            "create": QuestionDifficulty.CREATE,
        }
        diff_level = difficulty_map.get(difficulty.lower(), QuestionDifficulty.ANALYZE)

        generator = QuestionGeneratorFactory.create(
            EnhancedQuestionType.COMPARISON,
            llm_service=self._llm if self._flags.is_enabled(FeatureFlags.ENABLE_NLP_COMMANDS) else None,
        )

        generated = await generator.generate(topic, diff_level)
        return self._convert_generated_question(generated)

    def _convert_generated_question(self, gq: GeneratedQuestion) -> Question:
        """Convert a GeneratedQuestion to the interface Question type."""
        # Map enhanced question type to interface question type
        type_map = {
            EnhancedQuestionType.SCENARIO: QuestionType.SCENARIO,
            EnhancedQuestionType.COMPARISON: QuestionType.COMPARISON,
            EnhancedQuestionType.APPLICATION: QuestionType.SHORT_ANSWER,
            EnhancedQuestionType.MULTIPLE_CHOICE: QuestionType.MULTIPLE_CHOICE,
        }

        q_type = type_map.get(gq.question_type, QuestionType.MULTIPLE_CHOICE)

        # Build the question text with context if available
        question_text = gq.text
        if gq.context:
            question_text = f"{gq.context}\n\n{gq.text}"

        # Convert options
        options = [opt.text for opt in gq.options] if gq.options else None

        return Question(
            id=uuid4(),
            type=q_type,
            question=question_text,
            options=options,
            correct_answer=gq.correct_answer,
            explanation=gq.explanation,
            topic_id=None,  # Enhanced questions use string topics
            difficulty=gq.difficulty.value,
        )

    async def evaluate_quiz(
        self,
        quiz_id: UUID,
        answers: list[dict],
        time_taken_seconds: int,
    ) -> QuizResult:
        """Evaluate quiz answers."""
        quiz = self._quizzes.get(quiz_id)
        if quiz is None:
            raise ValueError(f"Quiz {quiz_id} not found")

        # Map answers by question ID
        answer_map = {a["question_id"]: a["answer"] for a in answers}

        evaluated_answers = []
        correct_count = 0
        gaps_identified = []

        for question in quiz.questions:
            user_answer = answer_map.get(str(question.id), "")

            # Evaluate answer
            is_correct, feedback = await self._assessment_agent.evaluate_quiz_answer(
                question=self._question_to_agent_format(question),
                user_answer=user_answer,
            )

            if is_correct:
                correct_count += 1
            elif question.topic_id and question.topic_id not in gaps_identified:
                gaps_identified.append(question.topic_id)

            evaluated_answers.append({
                "question_id": str(question.id),
                "user_answer": user_answer,
                "correct": is_correct,
                "feedback": feedback,
                "correct_answer": question.correct_answer,
            })

            # Update spaced repetition schedule
            if question.topic_id:
                await self.update_review_schedule(
                    user_id=quiz.user_id,
                    topic_id=question.topic_id,
                    correct=is_correct,
                    quality=4 if is_correct else 2,
                )

        result = QuizResult(
            quiz_id=quiz_id,
            score=correct_count / len(quiz.questions) if quiz.questions else 0,
            correct_count=correct_count,
            total_count=len(quiz.questions),
            answers=evaluated_answers,
            time_taken_seconds=time_taken_seconds,
            gaps_identified=gaps_identified,
        )

        # Store result
        if quiz.user_id not in self._quiz_results:
            self._quiz_results[quiz.user_id] = []
        self._quiz_results[quiz.user_id].append(result)

        return result

    # Feynman Dialogue Methods

    async def start_feynman(self, user_id: UUID, topic_id: UUID) -> FeynmanSession:
        """Start a Feynman dialogue session."""
        topic_name = self._topic_names.get(topic_id, "the concept")

        # Initialize dialogue with Socratic agent
        self._socratic_agent.begin_dialogue(user_id, None, topic_name)

        # Get opening message
        opening = await self._socratic_agent.start_dialogue(
            topic=topic_name,
            user_context={},
        )

        session = FeynmanSession(
            id=uuid4(),
            user_id=user_id,
            topic_id=topic_id,
            topic_name=topic_name,
            dialogue_history=[
                {"role": "assistant", "content": opening}
            ],
        )

        self._feynman_sessions[session.id] = session
        return session

    async def continue_feynman(
        self,
        session_id: UUID,
        user_response: str,
    ) -> FeynmanResponse:
        """Continue Feynman dialogue with user's response."""
        session = self._feynman_sessions.get(session_id)
        if session is None:
            raise ValueError(f"Feynman session {session_id} not found")

        # Add user response to history
        session.dialogue_history.append({
            "role": "user",
            "content": user_response,
        })

        # Get Socratic agent response
        response_text, gaps = await self._socratic_agent.probe_explanation(
            explanation=user_response,
            dialogue_history=session.dialogue_history,
            topic=session.topic_name,
        )

        # Add assistant response to history
        session.dialogue_history.append({
            "role": "assistant",
            "content": response_text,
        })

        # Check if dialogue should conclude (after ~8 turns)
        turn_count = len([h for h in session.dialogue_history if h["role"] == "user"])
        is_complete = turn_count >= 8

        return FeynmanResponse(
            message=response_text,
            is_complete=is_complete,
            gaps_so_far=gaps,
            probing_areas=[],  # Could extract from response
        )

    async def evaluate_feynman(self, session_id: UUID) -> FeynmanResult:
        """Evaluate completed Feynman session."""
        session = self._feynman_sessions.get(session_id)
        if session is None:
            raise ValueError(f"Feynman session {session_id} not found")

        # Use assessment agent to evaluate the dialogue
        evaluation = await self._assessment_agent.evaluate_feynman_dialogue(
            topic=session.topic_name,
            dialogue_history=session.dialogue_history,
        )

        result = FeynmanResult(
            session_id=session_id,
            completeness_score=evaluation.scores.get("completeness", 0.5),
            accuracy_score=evaluation.scores.get("accuracy", 0.5),
            simplicity_score=evaluation.scores.get("simplicity", 0.5),
            overall_score=evaluation.scores.get("overall", 0.5),
            gaps=evaluation.gaps,
            strengths=evaluation.strengths,
            suggestions=evaluation.suggestions,
        )

        # Store result
        if session.user_id not in self._feynman_results:
            self._feynman_results[session.user_id] = []
        self._feynman_results[session.user_id].append(result)

        # Update spaced repetition based on performance
        await self.update_review_schedule(
            user_id=session.user_id,
            topic_id=session.topic_id,
            correct=result.overall_score >= 0.7,
            quality=int(result.overall_score * 5),
        )

        return result

    # Spaced Repetition Methods

    async def get_due_reviews(self, user_id: UUID, limit: int = 10) -> list[ReviewItem]:
        """Get items due for spaced repetition review."""
        now = datetime.utcnow()
        due_items = []

        for (uid, tid), item in self._review_schedules.items():
            if uid == user_id and item.next_review <= now:
                due_items.append(item)

        # Sort by how overdue they are
        due_items.sort(key=lambda x: x.next_review)

        return due_items[:limit]

    async def update_review_schedule(
        self,
        user_id: UUID,
        topic_id: UUID,
        correct: bool,
        quality: int = 3,
    ) -> ReviewItem:
        """Update spaced repetition schedule after review.

        Uses SM-2 algorithm for spaced repetition scheduling.
        """
        key = (user_id, topic_id)
        now = datetime.utcnow()

        if key in self._review_schedules:
            item = self._review_schedules[key]
        else:
            # Create new review item
            item = ReviewItem(
                topic_id=topic_id,
                topic_name=self._topic_names.get(topic_id, f"Topic {str(topic_id)[:8]}"),
                last_reviewed=now,
                next_review=now + timedelta(days=1),
                interval_days=1,
                ease_factor=2.5,
                review_count=0,
            )

        # Update using SM-2 algorithm
        item.last_reviewed = now
        item.review_count += 1

        # Adjust ease factor based on quality (0-5)
        item.ease_factor = max(
            1.3,
            item.ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        )

        if correct and quality >= 3:
            # Calculate new interval
            if item.review_count == 1:
                item.interval_days = 1
            elif item.review_count == 2:
                item.interval_days = 6
            else:
                item.interval_days = int(item.interval_days * item.ease_factor)
        else:
            # Reset interval on failure
            item.interval_days = 1

        item.next_review = now + timedelta(days=item.interval_days)

        self._review_schedules[key] = item
        return item

    # Gap Identification

    async def identify_gaps(self, user_id: UUID) -> list[Gap]:
        """Identify knowledge gaps from recent assessments."""
        gaps = []

        # Analyze quiz results
        quiz_results = self._quiz_results.get(user_id, [])
        for result in quiz_results[-10:]:  # Last 10 quizzes
            for topic_id in result.gaps_identified:
                gap = Gap(
                    topic_id=topic_id,
                    topic_name=self._topic_names.get(topic_id, "Unknown"),
                    skill_component=None,
                    severity=1 - result.score,  # Higher severity for lower scores
                    identified_from="quiz",
                    identified_at=result.attempted_at,
                )
                gaps.append(gap)

        # Analyze Feynman results
        feynman_results = self._feynman_results.get(user_id, [])
        for result in feynman_results[-5:]:  # Last 5 Feynman sessions
            session = next(
                (s for s in self._feynman_sessions.values() if s.id == result.session_id),
                None
            )
            if session:
                for gap_desc in result.gaps:
                    gap = Gap(
                        topic_id=session.topic_id,
                        topic_name=session.topic_name,
                        skill_component=gap_desc,
                        severity=1 - result.overall_score,
                        identified_from="feynman",
                        identified_at=result.evaluated_at,
                    )
                    gaps.append(gap)

        # Sort by severity
        gaps.sort(key=lambda x: x.severity, reverse=True)

        # Deduplicate by topic
        seen_topics = set()
        unique_gaps = []
        for gap in gaps:
            if gap.topic_id not in seen_topics:
                seen_topics.add(gap.topic_id)
                unique_gaps.append(gap)

        return unique_gaps

    async def get_topic_proficiency(self, user_id: UUID, topic_id: UUID) -> float:
        """Get user's proficiency level for a topic."""
        # Calculate from quiz results
        quiz_scores = []
        for result in self._quiz_results.get(user_id, []):
            quiz = self._quizzes.get(result.quiz_id)
            if quiz and topic_id in quiz.topic_ids:
                quiz_scores.append(result.score)

        # Calculate from Feynman results
        feynman_scores = []
        for result in self._feynman_results.get(user_id, []):
            session = next(
                (s for s in self._feynman_sessions.values() if s.id == result.session_id),
                None
            )
            if session and session.topic_id == topic_id:
                feynman_scores.append(result.overall_score)

        # Combine scores with Feynman weighted higher
        all_scores = quiz_scores + [s * 1.2 for s in feynman_scores]  # Feynman bonus

        if not all_scores:
            return 0.0

        # Use exponential moving average (recent scores weighted higher)
        weights = [0.5 ** i for i in range(len(all_scores))]
        weighted_sum = sum(s * w for s, w in zip(reversed(all_scores), weights))
        weight_total = sum(weights)

        return min(1.0, weighted_sum / weight_total)

    # Helper methods

    def _question_to_agent_format(self, question: Question) -> Any:
        """Convert interface Question to agent format."""
        from src.modules.agents.assessment_agent import QuizQuestion as AgentQuestion

        return AgentQuestion(
            id=str(question.id),
            type=question.type.value,
            question=question.question,
            options=question.options,
            correct_answer=question.correct_answer or "",
            explanation=question.explanation or "",
            topic_id=str(question.topic_id) if question.topic_id else None,
            difficulty=question.difficulty,
        )

    def register_topic(self, topic_id: UUID, topic_name: str) -> None:
        """Register a topic name for use in assessments."""
        self._topic_names[topic_id] = topic_name

    def get_quiz(self, quiz_id: UUID) -> Quiz | None:
        """Get a quiz by ID."""
        return self._quizzes.get(quiz_id)

    def get_feynman_session(self, session_id: UUID) -> FeynmanSession | None:
        """Get a Feynman session by ID."""
        return self._feynman_sessions.get(session_id)


# Factory function
_assessment_service: AssessmentService | None = None


def get_assessment_service() -> AssessmentService:
    """Get assessment service singleton."""
    global _assessment_service
    if _assessment_service is None:
        _assessment_service = AssessmentService()
    return _assessment_service
