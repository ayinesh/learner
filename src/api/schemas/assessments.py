"""Assessment API schemas."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class QuestionType(str, Enum):
    """Quiz question types."""

    MULTIPLE_CHOICE = "multiple_choice"
    SHORT_ANSWER = "short_answer"
    SCENARIO = "scenario"
    COMPARISON = "comparison"


class FeynmanStatus(str, Enum):
    """Feynman session status."""

    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


# Quiz Schemas
class GenerateQuizRequest(BaseModel):
    """Quiz generation request."""

    topic_ids: list[UUID] = Field(
        ...,
        min_length=1,
        description="Topics to generate quiz for",
    )
    question_count: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of questions (1-20)",
    )
    include_review_items: bool = Field(
        default=True,
        description="Include spaced repetition items",
    )
    difficulty: int | None = Field(
        default=None,
        ge=1,
        le=5,
        description="Target difficulty level (1-5)",
    )


class QuizQuestionResponse(BaseModel):
    """Quiz question response."""

    id: UUID = Field(
        ...,
        description="Question unique identifier",
    )
    question_type: QuestionType = Field(
        ...,
        description="Type of question",
    )
    question_text: str = Field(
        ...,
        description="The question text",
    )
    options: list[str] | None = Field(
        default=None,
        description="Options for multiple choice",
    )
    topic_id: UUID = Field(
        ...,
        description="Related topic ID",
    )
    difficulty: int = Field(
        ...,
        ge=1,
        le=5,
        description="Question difficulty",
    )


class QuizResponse(BaseModel):
    """Generated quiz response."""

    id: UUID = Field(
        ...,
        description="Quiz unique identifier",
    )
    questions: list[QuizQuestionResponse] = Field(
        ...,
        description="Quiz questions",
    )
    created_at: datetime = Field(
        ...,
        description="Quiz creation timestamp",
    )
    time_limit_seconds: int | None = Field(
        default=None,
        description="Optional time limit",
    )


class SubmitQuizRequest(BaseModel):
    """Quiz submission request."""

    answers: dict[str, str] = Field(
        ...,
        description="Question ID to answer mapping",
    )
    time_taken_seconds: int = Field(
        ...,
        ge=0,
        description="Time taken to complete quiz",
    )


class QuestionResultResponse(BaseModel):
    """Individual question result."""

    question_id: UUID = Field(
        ...,
        description="Question identifier",
    )
    user_answer: str = Field(
        ...,
        description="User's answer",
    )
    correct_answer: str = Field(
        ...,
        description="Correct answer",
    )
    is_correct: bool = Field(
        ...,
        description="Whether answer was correct",
    )
    explanation: str | None = Field(
        default=None,
        description="Explanation of correct answer",
    )


class QuizResultResponse(BaseModel):
    """Quiz result response."""

    quiz_id: UUID = Field(
        ...,
        description="Quiz identifier",
    )
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall score (0-1)",
    )
    correct_count: int = Field(
        ...,
        description="Number of correct answers",
    )
    total_count: int = Field(
        ...,
        description="Total questions",
    )
    question_results: list[QuestionResultResponse] = Field(
        ...,
        description="Individual question results",
    )
    gaps_identified: list[str] = Field(
        default_factory=list,
        description="Knowledge gaps identified",
    )
    time_taken_seconds: int = Field(
        ...,
        description="Time taken",
    )


# Feynman Schemas
class StartFeynmanRequest(BaseModel):
    """Start Feynman session request."""

    topic_id: UUID = Field(
        ...,
        description="Topic to explain",
    )


class FeynmanSessionResponse(BaseModel):
    """Feynman session response."""

    id: UUID = Field(
        ...,
        description="Session unique identifier",
    )
    topic_id: UUID = Field(
        ...,
        description="Topic being explained",
    )
    topic_name: str = Field(
        ...,
        description="Topic name",
    )
    prompt: str = Field(
        ...,
        description="Initial prompt for explanation",
    )
    status: FeynmanStatus = Field(
        ...,
        description="Session status",
    )
    dialogue_turn: int = Field(
        default=0,
        description="Current dialogue turn",
    )


class FeynmanResponseRequest(BaseModel):
    """User response in Feynman dialogue."""

    user_response: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="User's explanation",
    )


class FeynmanDialogueResponse(BaseModel):
    """Feynman dialogue response."""

    session_id: UUID = Field(
        ...,
        description="Session identifier",
    )
    agent_response: str = Field(
        ...,
        description="Socratic agent's response",
    )
    probing_questions: list[str] = Field(
        default_factory=list,
        description="Follow-up probing questions",
    )
    gaps_so_far: list[str] = Field(
        default_factory=list,
        description="Gaps identified so far",
    )
    dialogue_turn: int = Field(
        ...,
        description="Current dialogue turn",
    )
    is_complete: bool = Field(
        ...,
        description="Whether dialogue should end",
    )


class FeynmanEvaluationResponse(BaseModel):
    """Feynman session evaluation response."""

    session_id: UUID = Field(
        ...,
        description="Session identifier",
    )
    completeness_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="How complete the explanation was",
    )
    accuracy_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="How accurate the explanation was",
    )
    simplicity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="How simple/clear the explanation was",
    )
    overall_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall Feynman score",
    )
    gaps_identified: list[str] = Field(
        default_factory=list,
        description="Knowledge gaps identified",
    )
    strengths_identified: list[str] = Field(
        default_factory=list,
        description="Strengths in explanation",
    )
    feedback: str = Field(
        ...,
        description="Detailed feedback",
    )


# Spaced Repetition Schemas
class ReviewItemResponse(BaseModel):
    """Spaced repetition review item."""

    id: UUID = Field(
        ...,
        description="Item unique identifier",
    )
    topic_id: UUID = Field(
        ...,
        description="Related topic",
    )
    topic_name: str = Field(
        ...,
        description="Topic name",
    )
    next_review: datetime = Field(
        ...,
        description="Next review timestamp",
    )
    ease_factor: float = Field(
        ...,
        description="SM-2 ease factor",
    )
    interval: int = Field(
        ...,
        description="Current interval in days",
    )
    repetitions: int = Field(
        ...,
        description="Number of successful reviews",
    )


class ReviewDueResponse(BaseModel):
    """Due review items response."""

    items: list[ReviewItemResponse] = Field(
        ...,
        description="Items due for review",
    )
    total_due: int = Field(
        ...,
        description="Total items due",
    )


class GapResponse(BaseModel):
    """Knowledge gap response."""

    id: UUID = Field(
        ...,
        description="Gap unique identifier",
    )
    topic_id: UUID = Field(
        ...,
        description="Related topic",
    )
    topic_name: str = Field(
        ...,
        description="Topic name",
    )
    description: str = Field(
        ...,
        description="Gap description",
    )
    identified_at: datetime = Field(
        ...,
        description="When gap was identified",
    )
    severity: str = Field(
        ...,
        description="Gap severity (low/medium/high)",
    )
    source: str = Field(
        ...,
        description="How gap was identified (quiz/feynman)",
    )


class GapsListResponse(BaseModel):
    """List of knowledge gaps."""

    gaps: list[GapResponse] = Field(
        ...,
        description="Knowledge gaps",
    )
    total: int = Field(
        ...,
        description="Total gaps",
    )
