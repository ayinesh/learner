"""Assessment Module - Quizzes, Feynman dialogues, and gap identification."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Protocol
from uuid import UUID


class QuestionType(str, Enum):
    """Types of quiz questions."""

    MULTIPLE_CHOICE = "multiple_choice"
    SHORT_ANSWER = "short_answer"
    SCENARIO = "scenario"
    COMPARISON = "comparison"


@dataclass
class Question:
    """A quiz question."""

    id: UUID
    type: QuestionType
    question: str
    options: list[str] | None = None  # For multiple choice
    correct_answer: str | None = None
    explanation: str | None = None
    topic_id: UUID | None = None
    difficulty: int = 3  # 1-5


@dataclass
class Quiz:
    """A generated quiz."""

    id: UUID
    user_id: UUID
    topic_ids: list[UUID]
    questions: list[Question]
    created_at: datetime = field(default_factory=datetime.utcnow)
    is_spaced_repetition: bool = False  # True if this is a review quiz


@dataclass
class QuizResult:
    """Result of a quiz attempt."""

    quiz_id: UUID
    score: float  # 0-1
    correct_count: int
    total_count: int
    answers: list[dict]  # [{question_id, user_answer, correct, feedback}]
    time_taken_seconds: int
    gaps_identified: list[UUID]  # Topic IDs where user struggled
    attempted_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FeynmanSession:
    """An active Feynman dialogue session."""

    id: UUID
    user_id: UUID
    topic_id: UUID
    topic_name: str
    dialogue_history: list[dict]  # [{role: "user"|"assistant", content: str}]
    started_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FeynmanResponse:
    """Response from the Socratic agent during Feynman dialogue."""

    message: str
    is_complete: bool  # True if dialogue has reached conclusion
    gaps_so_far: list[str]  # Gaps identified during dialogue
    probing_areas: list[str]  # Areas the agent wants to explore more


@dataclass
class FeynmanResult:
    """Final evaluation of a Feynman session."""

    session_id: UUID
    completeness_score: float  # 0-1: Were all key aspects covered?
    accuracy_score: float  # 0-1: Was information correct?
    simplicity_score: float  # 0-1: Was it accessible to layperson?
    overall_score: float  # Weighted combination
    gaps: list[str]  # Specific gaps identified
    strengths: list[str]  # What user did well
    suggestions: list[str]  # How to improve
    evaluated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Gap:
    """An identified knowledge gap."""

    topic_id: UUID
    topic_name: str
    skill_component: str | None  # Specific sub-skill if applicable
    severity: float  # 0-1, how significant is this gap
    identified_from: str  # "quiz" or "feynman"
    identified_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ReviewItem:
    """An item due for spaced repetition review."""

    topic_id: UUID
    topic_name: str
    last_reviewed: datetime
    next_review: datetime
    interval_days: int
    ease_factor: float
    review_count: int


class IAssessmentService(Protocol):
    """Interface for assessment service.

    Handles quiz generation, Feynman dialogues, and gap identification.
    """

    # Quiz methods

    async def generate_quiz(
        self,
        user_id: UUID,
        topic_ids: list[UUID] | None = None,
        question_count: int = 5,
        include_review: bool = True,
    ) -> Quiz:
        """Generate a quiz for the user.

        Args:
            user_id: User to generate quiz for
            topic_ids: Specific topics to cover (or None for auto-select)
            question_count: Number of questions
            include_review: Include spaced repetition review items

        Returns:
            Generated Quiz
        """
        ...

    async def evaluate_quiz(
        self,
        quiz_id: UUID,
        answers: list[dict],  # [{question_id, answer}]
        time_taken_seconds: int,
    ) -> QuizResult:
        """Evaluate quiz answers.

        Args:
            quiz_id: Quiz being answered
            answers: User's answers
            time_taken_seconds: Time spent on quiz

        Returns:
            QuizResult with score and feedback
        """
        ...

    # Feynman dialogue methods

    async def start_feynman(self, user_id: UUID, topic_id: UUID) -> FeynmanSession:
        """Start a Feynman dialogue session.

        Args:
            user_id: User starting the session
            topic_id: Topic to explain

        Returns:
            New FeynmanSession with initial prompt
        """
        ...

    async def continue_feynman(
        self,
        session_id: UUID,
        user_response: str,
    ) -> FeynmanResponse:
        """Continue Feynman dialogue with user's response.

        Args:
            session_id: Active session
            user_response: User's explanation/response

        Returns:
            FeynmanResponse with next question or completion
        """
        ...

    async def evaluate_feynman(self, session_id: UUID) -> FeynmanResult:
        """Evaluate completed Feynman session.

        Args:
            session_id: Session to evaluate

        Returns:
            FeynmanResult with scores and feedback
        """
        ...

    # Spaced repetition methods

    async def get_due_reviews(self, user_id: UUID, limit: int = 10) -> list[ReviewItem]:
        """Get items due for spaced repetition review.

        Args:
            user_id: User to get reviews for
            limit: Maximum items

        Returns:
            List of ReviewItems due for review
        """
        ...

    async def update_review_schedule(
        self,
        user_id: UUID,
        topic_id: UUID,
        correct: bool,
        quality: int = 3,  # 0-5 quality of recall
    ) -> ReviewItem:
        """Update spaced repetition schedule after review.

        Args:
            user_id: User
            topic_id: Topic reviewed
            correct: Whether recall was correct
            quality: Quality of recall (0-5)

        Returns:
            Updated ReviewItem with new schedule
        """
        ...

    # Gap identification

    async def identify_gaps(self, user_id: UUID) -> list[Gap]:
        """Identify knowledge gaps from recent assessments.

        Args:
            user_id: User to analyze

        Returns:
            List of identified Gaps sorted by severity
        """
        ...

    async def get_topic_proficiency(self, user_id: UUID, topic_id: UUID) -> float:
        """Get user's proficiency level for a topic.

        Args:
            user_id: User
            topic_id: Topic

        Returns:
            Proficiency score 0-1
        """
        ...
