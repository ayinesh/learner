"""Assessment Service - Database-backed implementation."""

from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

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
from src.modules.assessment.models import (
    FeynmanResultModel,
    FeynmanSessionModel,
    QuizAttemptModel,
    QuizModel,
)
from src.modules.content.models import TopicModel, UserTopicProgressModel
from src.modules.llm.service import LLMService, get_llm_service
from src.shared.database import get_db_session


class DatabaseAssessmentService(IAssessmentService):
    """Database-backed assessment service.

    Handles quiz generation, Feynman dialogues, and gap identification.
    """

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self._llm = llm_service or get_llm_service()

    # --- Quiz methods ---

    async def generate_quiz(
        self,
        user_id: UUID,
        topic_ids: list[UUID] | None = None,
        question_count: int = 5,
        include_review: bool = True,
    ) -> Quiz:
        """Generate a quiz for the user."""
        async with get_db_session() as db:
            # Get topics to quiz on
            if topic_ids is None:
                # Auto-select from user's topics
                result = await db.execute(
                    select(UserTopicProgressModel).where(
                        UserTopicProgressModel.user_id == user_id
                    ).order_by(
                        UserTopicProgressModel.last_practiced.asc()
                    ).limit(3)
                )
                topic_ids = [row.topic_id for row in result.scalars().all()]

            if not topic_ids:
                # Use some default topics
                topic_ids = []

            # Generate questions using LLM
            questions = await self._generate_questions(db, topic_ids, question_count)

            # Create quiz record
            quiz = QuizModel(
                id=uuid4(),
                user_id=user_id,
                topic_ids=topic_ids,
                questions={
                    "questions": [
                        {
                            "id": str(q.id),
                            "type": q.type.value,
                            "question": q.question,
                            "options": q.options,
                            "correct_answer": q.correct_answer,
                            "explanation": q.explanation,
                            "topic_id": str(q.topic_id) if q.topic_id else None,
                            "difficulty": q.difficulty,
                        }
                        for q in questions
                    ]
                },
                is_spaced_repetition=include_review,
                created_at=datetime.utcnow(),
            )
            db.add(quiz)
            await db.flush()

            return Quiz(
                id=quiz.id,
                user_id=user_id,
                topic_ids=topic_ids,
                questions=questions,
                created_at=quiz.created_at,
                is_spaced_repetition=include_review,
            )

    async def evaluate_quiz(
        self,
        quiz_id: UUID,
        answers: list[dict],
        time_taken_seconds: int,
    ) -> QuizResult:
        """Evaluate quiz answers."""
        # Input validation for time values
        if time_taken_seconds < 0 or time_taken_seconds > 86400:
            raise ValueError("time_taken_seconds must be between 0 and 86400 (24 hours)")

        async with get_db_session() as db:
            result = await db.execute(
                select(QuizModel).where(QuizModel.id == quiz_id)
            )
            quiz = result.scalar_one_or_none()

            if quiz is None:
                raise ValueError(f"Quiz not found: {quiz_id}")

            # Evaluate each answer
            questions_data = quiz.questions.get("questions", [])
            answer_map = {str(a.get("question_id")): a.get("answer") for a in answers}

            correct_count = 0
            evaluated_answers = []
            gaps_identified: list[UUID] = []

            for q in questions_data:
                q_id = q.get("id")
                user_answer = answer_map.get(q_id, "")
                correct_answer = q.get("correct_answer", "")

                is_correct = await self._check_answer(
                    q.get("type", "short_answer"),
                    user_answer,
                    correct_answer,
                    q.get("question", ""),
                )

                if is_correct:
                    correct_count += 1
                else:
                    # Track gap
                    topic_id = q.get("topic_id")
                    if topic_id:
                        try:
                            gaps_identified.append(UUID(topic_id))
                        except ValueError:
                            pass

                evaluated_answers.append({
                    "question_id": q_id,
                    "user_answer": user_answer,
                    "correct": is_correct,
                    "correct_answer": correct_answer,
                    "feedback": q.get("explanation", ""),
                })

            score = correct_count / max(len(questions_data), 1)

            # Store attempt
            attempt = QuizAttemptModel(
                id=uuid4(),
                quiz_id=quiz_id,
                user_id=quiz.user_id,
                answers={"answers": evaluated_answers},
                score=score,
                time_taken_seconds=time_taken_seconds,
                gaps_identified=gaps_identified,
                attempted_at=datetime.utcnow(),
            )
            db.add(attempt)

            # Update topic progress
            for topic_id in quiz.topic_ids or []:
                await self._update_topic_progress(
                    db,
                    quiz.user_id,
                    topic_id,
                    score,
                )

            return QuizResult(
                quiz_id=quiz_id,
                score=score,
                correct_count=correct_count,
                total_count=len(questions_data),
                answers=evaluated_answers,
                time_taken_seconds=time_taken_seconds,
                gaps_identified=gaps_identified,
            )

    # --- Feynman dialogue methods ---

    async def start_feynman(self, user_id: UUID, topic_id: UUID) -> FeynmanSession:
        """Start a Feynman dialogue session."""
        async with get_db_session() as db:
            # Get topic name
            topic_result = await db.execute(
                select(TopicModel).where(TopicModel.id == topic_id)
            )
            topic = topic_result.scalar_one_or_none()
            topic_name = topic.name if topic else str(topic_id)[:8]

            # Create session
            session = FeynmanSessionModel(
                id=uuid4(),
                user_id=user_id,
                topic_id=topic_id,
                dialogue_history=[],
                status="active",
                started_at=datetime.utcnow(),
            )
            db.add(session)
            await db.flush()

            return FeynmanSession(
                id=session.id,
                user_id=user_id,
                topic_id=topic_id,
                topic_name=topic_name,
                dialogue_history=[],
                started_at=session.started_at,
            )

    async def continue_feynman(
        self,
        session_id: UUID,
        user_response: str,
    ) -> FeynmanResponse:
        """Continue Feynman dialogue with user's response."""
        async with get_db_session() as db:
            result = await db.execute(
                select(FeynmanSessionModel).where(
                    FeynmanSessionModel.id == session_id
                )
            )
            session = result.scalar_one_or_none()

            if session is None:
                raise ValueError(f"Session not found: {session_id}")

            # Get topic name
            topic_result = await db.execute(
                select(TopicModel).where(TopicModel.id == session.topic_id)
            )
            topic = topic_result.scalar_one_or_none()
            topic_name = topic.name if topic else str(session.topic_id)[:8]

            # Update dialogue history
            dialogue = session.dialogue_history or []
            dialogue.append({"role": "user", "content": user_response})

            # Generate Socratic response using LLM
            response = await self._generate_socratic_response(
                topic_name,
                dialogue,
            )

            # Add assistant response to history
            dialogue.append({"role": "assistant", "content": response.message})
            session.dialogue_history = dialogue

            if response.is_complete:
                session.status = "completed"
                session.completed_at = datetime.utcnow()

            return response

    async def evaluate_feynman(self, session_id: UUID) -> FeynmanResult:
        """Evaluate completed Feynman session."""
        async with get_db_session() as db:
            result = await db.execute(
                select(FeynmanSessionModel).where(
                    FeynmanSessionModel.id == session_id
                )
            )
            session = result.scalar_one_or_none()

            if session is None:
                raise ValueError(f"Session not found: {session_id}")

            # Get topic name
            topic_result = await db.execute(
                select(TopicModel).where(TopicModel.id == session.topic_id)
            )
            topic = topic_result.scalar_one_or_none()
            topic_name = topic.name if topic else str(session.topic_id)[:8]

            # Evaluate using LLM
            evaluation = await self._evaluate_explanation(
                topic_name,
                session.dialogue_history or [],
            )

            # Store result
            result_model = FeynmanResultModel(
                id=uuid4(),
                feynman_session_id=session_id,
                completeness_score=evaluation.completeness_score,
                accuracy_score=evaluation.accuracy_score,
                simplicity_score=evaluation.simplicity_score,
                overall_score=evaluation.overall_score,
                gaps=evaluation.gaps,
                strengths=evaluation.strengths,
                suggestions=evaluation.suggestions,
                evaluated_at=datetime.utcnow(),
            )
            db.add(result_model)

            # Update topic progress
            await self._update_topic_progress(
                db,
                session.user_id,
                session.topic_id,
                evaluation.overall_score,
            )

            return evaluation

    # --- Spaced repetition methods ---

    async def get_due_reviews(self, user_id: UUID, limit: int = 10) -> list[ReviewItem]:
        """Get items due for spaced repetition review."""
        async with get_db_session() as db:
            now = datetime.utcnow()

            result = await db.execute(
                select(UserTopicProgressModel).where(
                    and_(
                        UserTopicProgressModel.user_id == user_id,
                        UserTopicProgressModel.next_review <= now,
                    )
                ).order_by(
                    UserTopicProgressModel.next_review.asc()
                ).limit(limit)
            )
            progress_items = result.scalars().all()

            items: list[ReviewItem] = []
            for p in progress_items:
                # Get topic name
                topic_result = await db.execute(
                    select(TopicModel).where(TopicModel.id == p.topic_id)
                )
                topic = topic_result.scalar_one_or_none()
                topic_name = topic.name if topic else str(p.topic_id)[:8]

                items.append(ReviewItem(
                    topic_id=p.topic_id,
                    topic_name=topic_name,
                    last_reviewed=p.last_practiced or datetime.utcnow(),
                    next_review=p.next_review or datetime.utcnow(),
                    interval_days=p.interval_days,
                    ease_factor=p.ease_factor,
                    review_count=p.practice_count,
                ))

            return items

    async def update_review_schedule(
        self,
        user_id: UUID,
        topic_id: UUID,
        correct: bool,
        quality: int = 3,
    ) -> ReviewItem:
        """Update spaced repetition schedule after review using SM-2 algorithm."""
        async with get_db_session() as db:
            result = await db.execute(
                select(UserTopicProgressModel).where(
                    and_(
                        UserTopicProgressModel.user_id == user_id,
                        UserTopicProgressModel.topic_id == topic_id,
                    )
                )
            )
            progress = result.scalar_one_or_none()

            if progress is None:
                progress = UserTopicProgressModel(
                    id=uuid4(),
                    user_id=user_id,
                    topic_id=topic_id,
                )
                db.add(progress)

            # SM-2 algorithm
            if quality < 3:
                # Reset interval
                progress.interval_days = 1
            else:
                if progress.practice_count == 0:
                    progress.interval_days = 1
                elif progress.practice_count == 1:
                    progress.interval_days = 6
                else:
                    progress.interval_days = int(
                        progress.interval_days * progress.ease_factor
                    )

            # Update ease factor
            progress.ease_factor = max(
                1.3,
                progress.ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
            )

            progress.practice_count += 1
            progress.last_practiced = datetime.utcnow()
            progress.next_review = datetime.utcnow() + timedelta(days=progress.interval_days)

            # Update proficiency
            if correct:
                progress.proficiency_level = min(1.0, progress.proficiency_level + 0.1)
            else:
                progress.proficiency_level = max(0.0, progress.proficiency_level - 0.1)

            # Get topic name
            topic_result = await db.execute(
                select(TopicModel).where(TopicModel.id == topic_id)
            )
            topic = topic_result.scalar_one_or_none()
            topic_name = topic.name if topic else str(topic_id)[:8]

            return ReviewItem(
                topic_id=topic_id,
                topic_name=topic_name,
                last_reviewed=progress.last_practiced,
                next_review=progress.next_review,
                interval_days=progress.interval_days,
                ease_factor=progress.ease_factor,
                review_count=progress.practice_count,
            )

    async def identify_gaps(self, user_id: UUID) -> list[Gap]:
        """Identify knowledge gaps from recent assessments."""
        async with get_db_session() as db:
            # Get recent quiz attempts with low scores
            result = await db.execute(
                select(QuizAttemptModel).where(
                    and_(
                        QuizAttemptModel.user_id == user_id,
                        QuizAttemptModel.score < 0.7,
                    )
                ).order_by(
                    desc(QuizAttemptModel.attempted_at)
                ).limit(10)
            )
            attempts = result.scalars().all()

            # Collect gaps from attempts
            gap_topics: dict[UUID, float] = {}
            for attempt in attempts:
                for topic_id in (attempt.gaps_identified or []):
                    if topic_id in gap_topics:
                        gap_topics[topic_id] = max(gap_topics[topic_id], 1 - attempt.score)
                    else:
                        gap_topics[topic_id] = 1 - attempt.score

            # Get Feynman results with low scores
            feynman_result = await db.execute(
                select(FeynmanResultModel, FeynmanSessionModel).join(
                    FeynmanSessionModel,
                    FeynmanResultModel.feynman_session_id == FeynmanSessionModel.id
                ).where(
                    and_(
                        FeynmanSessionModel.user_id == user_id,
                        FeynmanResultModel.overall_score < 0.7,
                    )
                ).order_by(
                    desc(FeynmanResultModel.evaluated_at)
                ).limit(10)
            )

            for fr, fs in feynman_result.all():
                if fs.topic_id in gap_topics:
                    gap_topics[fs.topic_id] = max(gap_topics[fs.topic_id], 1 - fr.overall_score)
                else:
                    gap_topics[fs.topic_id] = 1 - fr.overall_score

            # Batch load all topic names in a single query (fixes N+1)
            topic_ids = list(gap_topics.keys())
            if topic_ids:
                topic_result = await db.execute(
                    select(TopicModel).where(TopicModel.id.in_(topic_ids))
                )
                topic_names = {t.id: t.name for t in topic_result.scalars().all()}
            else:
                topic_names = {}

            # Build gap list using pre-loaded topic names
            gaps: list[Gap] = []
            for topic_id, severity in sorted(gap_topics.items(), key=lambda x: -x[1]):
                topic_name = topic_names.get(topic_id, str(topic_id)[:8])

                gaps.append(Gap(
                    topic_id=topic_id,
                    topic_name=topic_name,
                    skill_component=None,
                    severity=severity,
                    identified_from="assessment",
                    identified_at=datetime.utcnow(),
                ))

            return gaps

    async def get_topic_proficiency(self, user_id: UUID, topic_id: UUID) -> float:
        """Get user's proficiency level for a topic."""
        async with get_db_session() as db:
            result = await db.execute(
                select(UserTopicProgressModel).where(
                    and_(
                        UserTopicProgressModel.user_id == user_id,
                        UserTopicProgressModel.topic_id == topic_id,
                    )
                )
            )
            progress = result.scalar_one_or_none()

            if progress is None:
                return 0.0

            return progress.proficiency_level

    async def get_topic_progress(self, user_id: UUID) -> dict[str, dict]:
        """Get topic progress for a user.

        Optimized to batch-load topic names to avoid N+1 queries.
        """
        async with get_db_session() as db:
            result = await db.execute(
                select(UserTopicProgressModel).where(
                    UserTopicProgressModel.user_id == user_id
                )
            )
            progress_items = result.scalars().all()

            if not progress_items:
                return {}

            # Batch load all topic names in a single query (fixes N+1)
            topic_ids = [p.topic_id for p in progress_items]
            topic_result = await db.execute(
                select(TopicModel).where(TopicModel.id.in_(topic_ids))
            )
            topic_names = {t.id: t.name for t in topic_result.scalars().all()}

            # Build progress dict using pre-loaded topic names
            progress: dict[str, dict] = {}
            for p in progress_items:
                topic_name = topic_names.get(p.topic_id, str(p.topic_id)[:8])

                progress[topic_name] = {
                    "mastery_level": p.proficiency_level,
                    "quiz_count": p.practice_count,
                    "last_quiz_date": p.last_practiced.strftime("%Y-%m-%d") if p.last_practiced else None,
                }

            return progress

    async def get_knowledge_gaps(self, user_id: UUID) -> list[dict]:
        """Get knowledge gaps for a user (CLI-friendly format)."""
        gaps = await self.identify_gaps(user_id)
        return [
            {
                "topic": g.topic_name,
                "severity": "high" if g.severity > 0.7 else "medium" if g.severity > 0.4 else "low",
                "last_attempt": g.identified_at.strftime("%Y-%m-%d"),
                "suggested_action": f"Review {g.topic_name} with quizzes and practice",
            }
            for g in gaps
        ]

    # --- Private methods ---

    async def _generate_questions(
        self,
        db: AsyncSession,
        topic_ids: list[UUID],
        count: int,
    ) -> list[Question]:
        """Generate quiz questions using LLM."""
        # Get topic names
        topic_names = []
        for topic_id in topic_ids:
            result = await db.execute(
                select(TopicModel).where(TopicModel.id == topic_id)
            )
            topic = result.scalar_one_or_none()
            if topic:
                topic_names.append(topic.name)
            else:
                topic_names.append(str(topic_id)[:8])

        if not topic_names:
            topic_names = ["general knowledge"]

        prompt = f"""Generate {count} quiz questions about: {', '.join(topic_names)}

For each question, provide:
1. The question
2. 4 multiple choice options (A, B, C, D)
3. The correct answer (A, B, C, or D)
4. A brief explanation

Format each question as:
QUESTION: [question text]
OPTIONS:
A) [option A]
B) [option B]
C) [option C]
D) [option D]
ANSWER: [A/B/C/D]
EXPLANATION: [brief explanation]
---"""

        try:
            response = await self._llm.complete(
                prompt=prompt,
                system_prompt="You create educational quiz questions. Make them clear and progressively difficult.",
                temperature=0.7,
                max_tokens=2000,
            )

            return self._parse_questions(response.content, topic_ids)
        except Exception:
            # Return default question on error
            return [
                Question(
                    id=uuid4(),
                    type=QuestionType.MULTIPLE_CHOICE,
                    question="What is the main purpose of learning?",
                    options=["To pass tests", "To gain knowledge", "To impress others", "To fill time"],
                    correct_answer="B",
                    explanation="Learning's primary purpose is knowledge acquisition.",
                    difficulty=1,
                )
            ]

    def _parse_questions(
        self,
        response: str,
        topic_ids: list[UUID],
    ) -> list[Question]:
        """Parse LLM response into Question objects."""
        questions: list[Question] = []
        blocks = response.split("---")

        for block in blocks:
            if "QUESTION:" not in block:
                continue

            try:
                lines = block.strip().split("\n")
                question_text = ""
                options = []
                correct_answer = ""
                explanation = ""

                in_options = False
                for line in lines:
                    line = line.strip()
                    if line.startswith("QUESTION:"):
                        question_text = line[9:].strip()
                    elif line.startswith("OPTIONS:"):
                        in_options = True
                    elif in_options and line.startswith(("A)", "B)", "C)", "D)")):
                        options.append(line)
                    elif line.startswith("ANSWER:"):
                        correct_answer = line[7:].strip()
                        in_options = False
                    elif line.startswith("EXPLANATION:"):
                        explanation = line[12:].strip()

                if question_text and options and correct_answer:
                    topic_id = topic_ids[len(questions) % len(topic_ids)] if topic_ids else None
                    questions.append(Question(
                        id=uuid4(),
                        type=QuestionType.MULTIPLE_CHOICE,
                        question=question_text,
                        options=options,
                        correct_answer=correct_answer,
                        explanation=explanation,
                        topic_id=topic_id,
                        difficulty=3,
                    ))
            except Exception:
                continue

        return questions

    async def _check_answer(
        self,
        question_type: str,
        user_answer: str,
        correct_answer: str,
        question: str,
    ) -> bool:
        """Check if an answer is correct."""
        if question_type == "multiple_choice":
            # Direct comparison for multiple choice
            return user_answer.strip().upper() == correct_answer.strip().upper()
        else:
            # Use LLM for short answer evaluation
            try:
                prompt = f"""Evaluate if this answer is correct:

Question: {question}
Correct Answer: {correct_answer}
User's Answer: {user_answer}

Is the user's answer correct? Reply with just "yes" or "no"."""

                response = await self._llm.complete(
                    prompt=prompt,
                    system_prompt="You evaluate quiz answers. Be fair but accurate.",
                    temperature=0.1,
                    max_tokens=10,
                )
                return "yes" in response.content.lower()
            except Exception:
                return user_answer.lower().strip() == correct_answer.lower().strip()

    async def _generate_socratic_response(
        self,
        topic: str,
        dialogue: list[dict],
    ) -> FeynmanResponse:
        """Generate a Socratic response for Feynman dialogue."""
        # Build conversation history
        conversation = "\n".join([
            f"{'User' if d['role'] == 'user' else 'Teacher'}: {d['content']}"
            for d in dialogue
        ])

        prompt = f"""You are a Socratic teacher helping a student explain "{topic}".

Conversation so far:
{conversation}

Based on the student's last response, do one of:
1. Ask a probing question to deepen their understanding
2. Point out any inaccuracies gently
3. Encourage them to elaborate on a point
4. If they've demonstrated good understanding, acknowledge it

Keep responses concise (2-3 sentences). If you think the explanation is complete and accurate, say "COMPLETE" at the end."""

        try:
            response = await self._llm.complete(
                prompt=prompt,
                system_prompt="You are a Socratic teacher. Guide understanding through questions.",
                temperature=0.6,
                max_tokens=200,
            )

            content = response.content.strip()
            is_complete = "COMPLETE" in content.upper()
            if is_complete:
                content = content.replace("COMPLETE", "").strip()

            return FeynmanResponse(
                message=content,
                is_complete=is_complete,
                gaps_so_far=[],
                probing_areas=[],
            )
        except Exception:
            return FeynmanResponse(
                message="Can you tell me more about that?",
                is_complete=False,
                gaps_so_far=[],
                probing_areas=[],
            )

    async def _evaluate_explanation(
        self,
        topic: str,
        dialogue: list[dict],
    ) -> FeynmanResult:
        """Evaluate a Feynman explanation."""
        # Extract user's explanations
        user_explanations = "\n".join([
            d["content"] for d in dialogue if d["role"] == "user"
        ])

        prompt = f"""Evaluate this explanation of "{topic}":

{user_explanations}

Score each from 0-1:
1. COMPLETENESS: Were all key aspects covered?
2. ACCURACY: Was the information correct?
3. SIMPLICITY: Was it explained accessibly?

Also list:
- GAPS: What was missing or incorrect?
- STRENGTHS: What was explained well?
- SUGGESTIONS: How could they improve?

Format:
COMPLETENESS: [0.0-1.0]
ACCURACY: [0.0-1.0]
SIMPLICITY: [0.0-1.0]
GAPS: [gap1], [gap2]
STRENGTHS: [strength1], [strength2]
SUGGESTIONS: [suggestion1], [suggestion2]"""

        try:
            response = await self._llm.complete(
                prompt=prompt,
                system_prompt="You evaluate explanations fairly and constructively.",
                temperature=0.3,
                max_tokens=400,
            )

            return self._parse_evaluation(response.content)
        except Exception:
            return FeynmanResult(
                session_id=uuid4(),
                completeness_score=0.5,
                accuracy_score=0.5,
                simplicity_score=0.5,
                overall_score=0.5,
                gaps=[],
                strengths=[],
                suggestions=["Keep practicing!"],
            )

    def _parse_evaluation(self, response: str) -> FeynmanResult:
        """Parse evaluation response."""
        completeness = 0.5
        accuracy = 0.5
        simplicity = 0.5
        gaps = []
        strengths = []
        suggestions = []

        for line in response.split("\n"):
            line = line.strip()
            if line.startswith("COMPLETENESS:"):
                try:
                    completeness = float(line.split(":")[1].strip())
                except ValueError:
                    pass
            elif line.startswith("ACCURACY:"):
                try:
                    accuracy = float(line.split(":")[1].strip())
                except ValueError:
                    pass
            elif line.startswith("SIMPLICITY:"):
                try:
                    simplicity = float(line.split(":")[1].strip())
                except ValueError:
                    pass
            elif line.startswith("GAPS:"):
                gaps = [g.strip() for g in line.split(":")[1].split(",") if g.strip()]
            elif line.startswith("STRENGTHS:"):
                strengths = [s.strip() for s in line.split(":")[1].split(",") if s.strip()]
            elif line.startswith("SUGGESTIONS:"):
                suggestions = [s.strip() for s in line.split(":")[1].split(",") if s.strip()]

        overall = (completeness * 0.4 + accuracy * 0.4 + simplicity * 0.2)

        return FeynmanResult(
            session_id=uuid4(),
            completeness_score=completeness,
            accuracy_score=accuracy,
            simplicity_score=simplicity,
            overall_score=overall,
            gaps=gaps,
            strengths=strengths,
            suggestions=suggestions,
        )

    async def _update_topic_progress(
        self,
        db: AsyncSession,
        user_id: UUID,
        topic_id: UUID,
        score: float,
    ) -> None:
        """Update topic progress after an assessment."""
        result = await db.execute(
            select(UserTopicProgressModel).where(
                and_(
                    UserTopicProgressModel.user_id == user_id,
                    UserTopicProgressModel.topic_id == topic_id,
                )
            )
        )
        progress = result.scalar_one_or_none()

        if progress is None:
            progress = UserTopicProgressModel(
                id=uuid4(),
                user_id=user_id,
                topic_id=topic_id,
            )
            db.add(progress)

        # Update proficiency based on score
        old_prof = progress.proficiency_level
        new_prof = (old_prof * 0.7) + (score * 0.3)  # Weighted average
        progress.proficiency_level = min(1.0, max(0.0, new_prof))

        progress.practice_count += 1
        progress.last_practiced = datetime.utcnow()

        # Update next review (simple SM-2)
        if score >= 0.8:
            progress.interval_days = int(progress.interval_days * progress.ease_factor)
        elif score < 0.6:
            progress.interval_days = 1

        progress.next_review = datetime.utcnow() + timedelta(days=progress.interval_days)


# Factory function
_db_assessment_service: DatabaseAssessmentService | None = None


def get_db_assessment_service() -> DatabaseAssessmentService:
    """Get database assessment service singleton."""
    global _db_assessment_service
    if _db_assessment_service is None:
        _db_assessment_service = DatabaseAssessmentService()
    return _db_assessment_service
