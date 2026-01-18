"""Assessment Agent - Quiz generation and Feynman evaluation."""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from src.modules.agents.context_service import get_context_service
from src.modules.agents.interface import (
    AgentContext,
    AgentResponse,
    AgentType,
    BaseAgent,
    MenuOption,
)
from src.modules.agents.learning_context import OnboardingState
from src.modules.agents.context_builder import (
    ConversationContextBuilder,
    build_agent_system_prompt,
)
from src.modules.agents.handoff_generator import (
    create_action,
    create_discovery,
    create_handoff,
)
from src.modules.llm.service import LLMService, get_llm_service

logger = logging.getLogger(__name__)

# Conversational onboarding questions for the Assessment agent
# Asked one at a time when setting up quizzes
ASSESSMENT_ONBOARDING_QUESTIONS = [
    {
        "key": "quiz_topic",
        "question": "What topic should I quiz you on?",
        "context_field": "current_focus",
    },
    {
        "key": "question_count",
        "question": "How many questions would you like? (e.g., 3, 5, 10)",
        "context_field": "preferences.quiz_length",
    },
    {
        "key": "focus_area",
        "question": "Any specific areas of {topic} you'd like to focus on? (or say 'general' for a broad quiz)",
        "context_field": "preferences.quiz_focus",
    },
]


@dataclass
class QuizQuestion:
    """A single quiz question."""

    id: str
    type: str  # multiple_choice, short_answer, scenario, comparison
    question: str
    options: list[str] | None = None  # For multiple choice
    correct_answer: str = ""
    explanation: str = ""
    topic_id: str | None = None
    difficulty: int = 3  # 1-5
    is_review: bool = False


@dataclass
class Quiz:
    """A collection of quiz questions."""

    id: str
    questions: list[QuizQuestion]
    topic_ids: list[str]
    created_at: datetime = field(default_factory=datetime.utcnow)
    time_limit_minutes: int | None = None


@dataclass
class QuizResult:
    """Result of a completed quiz."""

    quiz_id: str
    user_id: UUID
    answers: dict[str, str]  # question_id -> user_answer
    scores: dict[str, bool]  # question_id -> is_correct
    total_correct: int
    total_questions: int
    score_percentage: float
    completed_at: datetime
    time_taken_seconds: int | None = None


@dataclass
class FeynmanEvaluation:
    """Evaluation of a Feynman dialogue."""

    topic: str
    scores: dict[str, float]  # completeness, accuracy, simplicity, overall
    gaps: list[str]
    inaccuracies: list[str]
    jargon_unexplained: list[str]
    strengths: list[str]
    suggestions: list[str]
    follow_up_topics: list[str]
    mastery_level: str  # novice, developing, proficient, advanced, expert


class AssessmentAgent(BaseAgent):
    """Agent responsible for generating quizzes and evaluating Feynman dialogues.

    This agent creates retrieval practice questions calibrated to the user's
    proficiency level and evaluates their explanations using the Feynman Technique.
    """

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self._llm = llm_service or get_llm_service()

    @property
    def agent_type(self) -> AgentType:
        return AgentType.ASSESSMENT

    @property
    def system_prompt(self) -> str:
        template = self._llm.load_prompt_template("assessment/quiz_generation")
        return template.system

    async def respond(
        self,
        context: AgentContext,
        user_message: str,
    ) -> AgentResponse:
        """Generate assessment response based on context.

        Determines whether to generate a quiz, evaluate a response,
        or provide feedback.
        """
        action = context.additional_data.get("action", "quiz")

        # Check for ongoing onboarding
        context_service = get_context_service()
        onboarding = await context_service.get_onboarding_state(
            context.user_id, "assessment"
        )
        if onboarding and not onboarding.is_complete:
            return await self._handle_quiz_onboarding(context, user_message)

        if action == "generate_quiz":
            # Check if we need onboarding first
            if self._needs_quiz_onboarding(context):
                return await self._handle_quiz_onboarding(context, user_message)
            return await self._handle_quiz_generation(context)
        elif action == "evaluate_answer":
            return await self._handle_answer_evaluation(context, user_message)
        elif action == "evaluate_feynman":
            return await self._handle_feynman_evaluation(context)
        elif action == "provide_feedback":
            return await self._handle_feedback(context, user_message)
        else:
            # Default to quiz generation
            if self._needs_quiz_onboarding(context):
                return await self._handle_quiz_onboarding(context, user_message)
            return await self._handle_quiz_generation(context)

    async def generate_quiz(
        self,
        topics: list[str],
        proficiency_level: int,
        question_count: int = 5,
        new_count: int = 3,
        review_count: int = 2,
        recent_content: str = "",
    ) -> Quiz:
        """Generate a retrieval practice quiz.

        Args:
            topics: Topics to cover
            proficiency_level: User's proficiency (1-5)
            question_count: Total questions to generate
            new_count: Questions on new material
            review_count: Spaced repetition review questions
            recent_content: Summary of recently covered content

        Returns:
            Quiz with generated questions
        """
        template = self._llm.load_prompt_template("assessment/quiz_generation")

        system_prompt, user_prompt = template.format(
            question_count=question_count,
            topics=", ".join(topics),
            proficiency_level=proficiency_level,
            recent_content=recent_content or "General coverage of the topics",
            new_count=new_count,
            review_count=review_count,
        )

        response = await self._llm.complete(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.7,
        )

        # Parse quiz questions from JSON response
        questions = self._parse_quiz_questions(response.content)

        return Quiz(
            id=str(uuid4()),
            questions=questions,
            topic_ids=[],  # Would be populated from actual topic IDs
        )

    async def evaluate_quiz_answer(
        self,
        question: QuizQuestion,
        user_answer: str,
    ) -> tuple[bool, str]:
        """Evaluate a user's answer to a quiz question.

        Returns:
            (is_correct, feedback)
        """
        if question.type == "multiple_choice":
            # For multiple choice, compare directly
            is_correct = user_answer.strip().lower() == question.correct_answer.strip().lower()
            if is_correct:
                feedback = f"Correct! {question.explanation}"
            else:
                feedback = f"Not quite. The correct answer is: {question.correct_answer}. {question.explanation}"
            return is_correct, feedback

        # For other types, use LLM to evaluate
        eval_prompt = f"""
        Evaluate this answer to the question.

        Question: {question.question}
        Type: {question.type}
        Expected answer: {question.correct_answer}
        User's answer: {user_answer}

        Determine if the answer is correct (allowing for reasonable variations in wording).
        Provide brief, constructive feedback.

        Return as JSON:
        {{
            "is_correct": true/false,
            "feedback": "explanation of why correct/incorrect and what to learn"
        }}
        """

        response = await self._llm.complete(
            prompt=eval_prompt,
            system_prompt="You are a fair and helpful quiz evaluator. Be encouraging but honest.",
            temperature=0.3,
        )

        try:
            content = response.content.strip()
            if "```" in content:
                match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
                if match:
                    content = match.group(1)
            result = json.loads(content)
            return result.get("is_correct", False), result.get("feedback", "")
        except (json.JSONDecodeError, ValueError):
            # Fallback to simple comparison
            is_correct = user_answer.lower() in question.correct_answer.lower()
            return is_correct, question.explanation

    async def evaluate_feynman_dialogue(
        self,
        topic: str,
        dialogue_history: list[dict],
    ) -> FeynmanEvaluation:
        """Evaluate a completed Feynman technique dialogue.

        Args:
            topic: The topic being explained
            dialogue_history: List of conversation turns

        Returns:
            FeynmanEvaluation with scores and feedback
        """
        template = self._llm.load_prompt_template("assessment/feynman_evaluation")

        # Format dialogue history
        dialogue_str = "\n\n".join(
            f"**{turn.get('role', 'unknown').title()}**: {turn.get('content', '')}"
            for turn in dialogue_history
        )

        system_prompt, user_prompt = template.format(
            topic=topic,
            dialogue_history=dialogue_str,
        )

        response = await self._llm.complete(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
        )

        # Parse evaluation
        evaluation = self._parse_feynman_evaluation(response.content, topic)
        return evaluation

    async def generate_adaptive_questions(
        self,
        topic: str,
        current_performance: float,
        recent_errors: list[str],
        question_count: int = 3,
    ) -> list[QuizQuestion]:
        """Generate questions adapted to user's performance.

        If performance is low, generate easier questions.
        If high, generate more challenging ones.
        """
        template = self._llm.load_prompt_template("assessment/adaptive_difficulty")

        # Determine target difficulty
        if current_performance < 0.4:
            target_difficulty = 1
            focus = "foundational concepts"
        elif current_performance < 0.6:
            target_difficulty = 2
            focus = "basic application"
        elif current_performance < 0.8:
            target_difficulty = 3
            focus = "deeper understanding"
        else:
            target_difficulty = 4
            focus = "edge cases and nuances"

        system_prompt, user_prompt = template.format(
            topic=topic,
            target_difficulty=target_difficulty,
            focus_area=focus,
            recent_errors="\n".join(f"- {e}" for e in recent_errors) if recent_errors else "None noted",
            question_count=question_count,
            performance_level=f"{current_performance:.0%}",
        )

        response = await self._llm.complete(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.7,
        )

        return self._parse_quiz_questions(response.content)

    def _parse_quiz_questions(self, content: str) -> list[QuizQuestion]:
        """Parse quiz questions from LLM response."""
        try:
            # Extract JSON from response
            if "```" in content:
                match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
                if match:
                    content = match.group(1)

            questions_data = json.loads(content)

            if not isinstance(questions_data, list):
                questions_data = [questions_data]

            questions = []
            for q in questions_data:
                question = QuizQuestion(
                    id=q.get("id", str(uuid4())),
                    type=q.get("type", "multiple_choice"),
                    question=q.get("question", ""),
                    options=q.get("options"),
                    correct_answer=q.get("correct_answer", ""),
                    explanation=q.get("explanation", ""),
                    topic_id=q.get("topic_id"),
                    difficulty=q.get("difficulty", 3),
                    is_review=q.get("is_review", False),
                )
                if question.question:
                    questions.append(question)

            return questions

        except (json.JSONDecodeError, ValueError):
            # Return empty list if parsing fails
            return []

    def _parse_feynman_evaluation(
        self,
        content: str,
        topic: str,
    ) -> FeynmanEvaluation:
        """Parse Feynman evaluation from LLM response."""
        try:
            if "```" in content:
                match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
                if match:
                    content = match.group(1)

            data = json.loads(content)

            scores = data.get("scores", {})
            overall = scores.get("overall", 0.5)

            # Determine mastery level from overall score
            if overall >= 0.9:
                mastery = "expert"
            elif overall >= 0.8:
                mastery = "advanced"
            elif overall >= 0.7:
                mastery = "proficient"
            elif overall >= 0.5:
                mastery = "developing"
            else:
                mastery = "novice"

            return FeynmanEvaluation(
                topic=topic,
                scores=scores,
                gaps=data.get("gaps", []),
                inaccuracies=data.get("inaccuracies", []),
                jargon_unexplained=data.get("jargon_unexplained", []),
                strengths=data.get("strengths", []),
                suggestions=data.get("suggestions", []),
                follow_up_topics=data.get("follow_up_topics", []),
                mastery_level=mastery,
            )

        except (json.JSONDecodeError, ValueError):
            # Return default evaluation
            return FeynmanEvaluation(
                topic=topic,
                scores={"overall": 0.5},
                gaps=["Unable to parse detailed evaluation"],
                inaccuracies=[],
                jargon_unexplained=[],
                strengths=[],
                suggestions=["Try explaining again with more detail"],
                follow_up_topics=[],
                mastery_level="developing",
            )

    # ===================
    # Onboarding Flow Methods
    # ===================

    def _needs_quiz_onboarding(self, context: AgentContext) -> bool:
        """Check if user needs quiz setup conversation."""
        additional = context.additional_data
        # Skip onboarding if topics already provided
        if additional.get("topics"):
            return False
        # Check if learning context has a current focus
        learning_ctx = additional.get("learning_context")
        if learning_ctx and learning_ctx.current_focus:
            return False
        return True

    def _get_next_onboarding_question(
        self,
        onboarding: OnboardingState,
    ) -> dict | None:
        """Get the next unanswered onboarding question."""
        for q in ASSESSMENT_ONBOARDING_QUESTIONS:
            if not onboarding.is_question_answered(q["key"]):
                return q
        return None

    def _parse_question_count(self, count_str: str) -> int:
        """Parse question count from user input."""
        count_str = count_str.lower().strip()
        # Try to extract numbers
        import re
        numbers = re.findall(r"\d+", count_str)
        if numbers:
            count = int(numbers[0])
            return max(1, min(count, 20))  # Clamp to 1-20
        # Default to 5 questions
        return 5

    async def _process_onboarding_answer(
        self,
        user_id: UUID,
        question_key: str,
        answer: str,
        onboarding: OnboardingState,
    ) -> None:
        """Process and store an onboarding answer."""
        onboarding.record_answer(question_key, answer)

        context_service = get_context_service()

        if question_key == "quiz_topic":
            onboarding.topic = answer
            # Update current focus
            await context_service.update_current_focus(user_id, answer)
        elif question_key == "question_count":
            # Store preference
            count = self._parse_question_count(answer)
            await context_service.record_preference(user_id, "quiz_length", count)
        elif question_key == "focus_area":
            if answer.lower() not in ["general", "all", "everything", "broad"]:
                await context_service.record_preference(user_id, "quiz_focus", answer)

        # Save onboarding state
        await context_service.save_onboarding_state(user_id, onboarding)

    async def _handle_quiz_onboarding(
        self,
        context: AgentContext,
        user_message: str,
    ) -> AgentResponse:
        """Handle progressive quiz setup - one question at a time."""
        context_service = get_context_service()

        # Get or create onboarding state
        onboarding = await context_service.get_onboarding_state(
            context.user_id, "assessment"
        )

        if not onboarding:
            onboarding = OnboardingState(agent_type="assessment")

        # If this is a response to a previous question, process it
        if onboarding.current_question and not onboarding.is_complete:
            await self._process_onboarding_answer(
                context.user_id,
                onboarding.current_question,
                user_message,
                onboarding,
            )

        # Find next unanswered question
        next_q = self._get_next_onboarding_question(onboarding)

        if next_q is None:
            # Onboarding complete - generate the quiz
            onboarding.is_complete = True
            await context_service.save_onboarding_state(context.user_id, onboarding)

            # Build context from collected answers
            topic = onboarding.topic or "general"
            count_str = onboarding.answers_collected.get("question_count", "5")
            focus = onboarding.answers_collected.get("focus_area", "")

            # Update context with quiz parameters
            context.additional_data["topics"] = [topic]
            context.additional_data["question_count"] = self._parse_question_count(count_str)
            if focus and focus.lower() not in ["general", "all", "broad"]:
                context.additional_data["recent_content"] = f"Focus on: {focus}"

            # Clear onboarding state for next time
            await context_service.clear_onboarding_state(context.user_id, "assessment")

            # Now generate the quiz
            return await self._handle_quiz_generation(context)

        # Format the question (substitute topic if needed)
        topic = onboarding.topic or "this topic"
        question_text = next_q["question"].format(topic=topic)

        # Update state with current question
        onboarding.current_question = next_q["key"]
        await context_service.save_onboarding_state(context.user_id, onboarding)

        return AgentResponse(
            agent_type=self.agent_type,
            message=question_text,
            data={"onboarding_step": next_q["key"]},
        )

    async def _handle_quiz_generation(
        self,
        context: AgentContext,
    ) -> AgentResponse:
        """Handle quiz generation request."""
        additional = context.additional_data

        # Get shared learning context for personalized quiz generation
        learning_ctx = additional.get("learning_context")

        if learning_ctx:
            # Build topics from current focus and recent topics
            topics = []
            if learning_ctx.current_focus:
                topics.append(learning_ctx.current_focus)
            if learning_ctx.recent_topics:
                topics.extend(learning_ctx.recent_topics[:3])
            if not topics:
                topics = ["general"]

            # Determine proficiency level from shared context
            if learning_ctx.proficiency_levels and topics:
                main_topic = topics[0]
                proficiency_float = learning_ctx.proficiency_levels.get(main_topic, 0.5)
                # Convert 0-1 float to 1-5 scale
                proficiency = max(1, min(5, int(proficiency_float * 5) + 1))
            else:
                proficiency = additional.get("proficiency_level", 3)

            # Build recent content context from goal and focus
            recent_content = ""
            if learning_ctx.primary_goal:
                recent_content += f"Learning goal: {learning_ctx.primary_goal}. "
            if learning_ctx.current_focus:
                recent_content += f"Currently studying: {learning_ctx.current_focus}. "
            if learning_ctx.identified_gaps:
                recent_content += f"Areas needing work: {', '.join(learning_ctx.identified_gaps[:3])}."
        else:
            topics = additional.get("topics", ["general"])
            proficiency = additional.get("proficiency_level", 3)
            recent_content = additional.get("recent_content", "")

        count = additional.get("question_count", 5)

        quiz = await self.generate_quiz(
            topics=topics,
            proficiency_level=proficiency,
            question_count=count,
            recent_content=recent_content,
        )

        # Format first question for the user
        menu_options = None
        if quiz.questions:
            first_q = quiz.questions[0]
            message = f"Let's test your understanding!\n\n**Question 1/{len(quiz.questions)}**\n{first_q.question}"
            if first_q.options:
                # Format options with numbers (1, 2, 3, 4) instead of letters for easier selection
                message += "\n\n" + "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(first_q.options))
                # Create menu options for numeric answer selection
                menu_options = [
                    MenuOption(str(i+1), opt, AgentType.ASSESSMENT, f"answer_{i+1}")
                    for i, opt in enumerate(first_q.options)
                ]
        else:
            message = "I wasn't able to generate quiz questions. Let's try a different approach."

        return AgentResponse(
            agent_type=self.agent_type,
            message=message,
            data={
                "action": "quiz_started",
                "quiz_id": quiz.id,
                "quiz": {
                    "id": quiz.id,
                    "questions": [
                        {
                            "id": q.id,
                            "type": q.type,
                            "question": q.question,
                            "options": q.options,
                            "difficulty": q.difficulty,
                        }
                        for q in quiz.questions
                    ],
                    "total_questions": len(quiz.questions),
                },
                "current_question": 0,
            },
            menu_options=menu_options,
            suggested_next_agent=AgentType.ASSESSMENT,  # Stay in assessment during quiz
        )

    async def _handle_answer_evaluation(
        self,
        context: AgentContext,
        user_answer: str,
    ) -> AgentResponse:
        """Handle evaluating a quiz answer."""
        additional = context.additional_data
        question_data = additional.get("current_question_data", {})

        question = QuizQuestion(
            id=question_data.get("id", ""),
            type=question_data.get("type", "short_answer"),
            question=question_data.get("question", ""),
            options=question_data.get("options"),
            correct_answer=question_data.get("correct_answer", ""),
            explanation=question_data.get("explanation", ""),
        )

        is_correct, feedback = await self.evaluate_quiz_answer(question, user_answer)

        # Check if there are more questions
        current_idx = additional.get("current_question_index", 0)
        total_questions = additional.get("total_questions", 1)

        if current_idx + 1 < total_questions:
            message = f"{'✓ Correct!' if is_correct else '✗ Not quite.'} {feedback}\n\nReady for the next question?"
            end_quiz = False
        else:
            message = f"{'✓ Correct!' if is_correct else '✗ Not quite.'} {feedback}\n\nQuiz complete! Great effort."
            end_quiz = True

        # Calculate quiz results for handoff if quiz is complete
        handoff = None
        actions = None
        discoveries = None

        if end_quiz:
            # Gather quiz stats from context
            total_correct = additional.get("total_correct", 0) + (1 if is_correct else 0)
            quiz_topic = additional.get("quiz_topic", "general")
            weak_topics = additional.get("weak_topics", [])

            score = total_correct / total_questions if total_questions > 0 else 0

            # Determine next agent based on performance
            if score < 0.7 and weak_topics:
                suggested_next = AgentType.DRILL_SERGEANT
                suggested_steps = [f"Practice drills on: {', '.join(weak_topics[:3])}"]
            elif score >= 0.8:
                suggested_next = AgentType.CURRICULUM
                suggested_steps = ["Ready to advance to next topic"]
            else:
                suggested_next = AgentType.COACH
                suggested_steps = ["Review quiz results and plan next steps"]

            handoff = create_handoff(
                from_agent=self.agent_type,
                summary=f"Quiz completed: {total_correct}/{total_questions} ({score:.0%}). "
                        f"Topic: {quiz_topic}",
                outcomes={
                    "quiz_score": score,
                    "correct": total_correct,
                    "total": total_questions,
                    "topic": quiz_topic,
                },
                gaps_identified=weak_topics,
                proficiency_observations={quiz_topic: score},
                suggested_next_steps=suggested_steps,
                suggested_next_agent=suggested_next,
            )

            actions = [
                create_action(
                    self.agent_type,
                    "complete_quiz",
                    {
                        "topic": quiz_topic,
                        "score": score,
                        "correct": total_correct,
                        "total": total_questions,
                    },
                ),
            ]

            if weak_topics:
                discoveries = create_discovery(needs_support=weak_topics)

        return AgentResponse(
            agent_type=self.agent_type,
            message=message,
            data={
                "action": "answer_evaluated",
                "is_correct": is_correct,
                "feedback": feedback,
                "quiz_complete": end_quiz,
                "current_question_index": current_idx + 1,
            },
            end_conversation=end_quiz,
            # Stay in Assessment for next question, or go to Coach when done
            suggested_next_agent=AgentType.COACH if end_quiz else AgentType.ASSESSMENT,
            handoff_context=handoff,
            actions_taken=actions,
            discoveries=discoveries,
        )

    async def _handle_feynman_evaluation(
        self,
        context: AgentContext,
    ) -> AgentResponse:
        """Handle Feynman dialogue evaluation."""
        additional = context.additional_data
        topic = additional.get("topic", "the concept")
        dialogue = context.conversation_history

        evaluation = await self.evaluate_feynman_dialogue(topic, dialogue)

        # Format evaluation message
        scores = evaluation.scores
        message = f"""
**Feynman Evaluation for "{topic}"**

**Scores:**
- Completeness: {scores.get('completeness', 0):.0%}
- Accuracy: {scores.get('accuracy', 0):.0%}
- Simplicity: {scores.get('simplicity', 0):.0%}
- **Overall: {scores.get('overall', 0):.0%}**

**Mastery Level:** {evaluation.mastery_level.title()}

**Strengths:**
{chr(10).join(f"• {s}" for s in evaluation.strengths) if evaluation.strengths else "• Good effort!"}

**Areas to Improve:**
{chr(10).join(f"• {g}" for g in evaluation.gaps[:3]) if evaluation.gaps else "• Keep practicing!"}

**Suggested Next Steps:**
{chr(10).join(f"• {s}" for s in evaluation.suggestions[:2]) if evaluation.suggestions else "• Continue exploring this topic"}
"""

        # Calculate proficiency from overall score
        overall_score = scores.get("overall", 0.5)

        # Determine suggested next agent based on gaps
        if evaluation.gaps:
            suggested_next = AgentType.DRILL_SERGEANT
            suggested_steps = [f"Practice: {', '.join(evaluation.gaps[:3])}"]
        else:
            suggested_next = AgentType.COACH
            suggested_steps = evaluation.suggestions[:2] if evaluation.suggestions else ["Continue learning"]

        return AgentResponse(
            agent_type=self.agent_type,
            message=message.strip(),
            data={
                "action": "feynman_evaluated",
                "evaluation": {
                    "topic": evaluation.topic,
                    "scores": evaluation.scores,
                    "mastery_level": evaluation.mastery_level,
                    "gaps": evaluation.gaps,
                    "strengths": evaluation.strengths,
                    "suggestions": evaluation.suggestions,
                    "follow_up_topics": evaluation.follow_up_topics,
                },
            },
            suggested_next_agent=suggested_next,
            handoff_context=create_handoff(
                from_agent=self.agent_type,
                summary=f"Feynman evaluation completed for '{topic}'. "
                        f"Overall: {overall_score:.0%}. Mastery: {evaluation.mastery_level}",
                outcomes={
                    "completeness": scores.get("completeness", 0),
                    "accuracy": scores.get("accuracy", 0),
                    "simplicity": scores.get("simplicity", 0),
                    "overall": overall_score,
                    "mastery_level": evaluation.mastery_level,
                },
                gaps_identified=evaluation.gaps,
                proficiency_observations={topic: overall_score},
                topics_covered=[topic] + evaluation.follow_up_topics[:2],
                key_points=evaluation.strengths[:3],
                suggested_next_steps=suggested_steps,
                suggested_next_agent=suggested_next,
            ),
            actions_taken=[
                create_action(
                    self.agent_type,
                    "complete_feynman_evaluation",
                    {
                        "topic": topic,
                        "overall_score": overall_score,
                        "mastery_level": evaluation.mastery_level,
                        "gaps_count": len(evaluation.gaps),
                    },
                ),
            ],
            discoveries=create_discovery(
                needs_support=evaluation.gaps,
                strengths=evaluation.strengths,
            ) if evaluation.gaps or evaluation.strengths else None,
        )

    async def _handle_feedback(
        self,
        context: AgentContext,
        user_message: str,
    ) -> AgentResponse:
        """Handle providing general assessment feedback with conversation awareness."""
        # Use context builder for conversation history awareness
        ctx_builder = ConversationContextBuilder(context)

        # Build enhanced system prompt with what we know
        enhanced_system = build_agent_system_prompt(
            "You are a helpful assessment advisor. Be encouraging but honest. "
            "Provide specific and actionable feedback about their progress.",
            context,
        )

        # Build messages with full conversation history
        messages = ctx_builder.build_messages(user_message)

        response = await self._llm.complete_with_history(
            messages=messages,
            system_prompt=enhanced_system,
            temperature=0.7,
        )

        return AgentResponse(
            agent_type=self.agent_type,
            message=response.content,
            data={"action": "feedback_provided"},
        )


# Factory function
_assessment_agent: AssessmentAgent | None = None


def get_assessment_agent() -> AssessmentAgent:
    """Get Assessment agent singleton."""
    global _assessment_agent
    if _assessment_agent is None:
        _assessment_agent = AssessmentAgent()
    return _assessment_agent
