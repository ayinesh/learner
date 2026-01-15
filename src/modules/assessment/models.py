"""SQLAlchemy models for Assessment module."""

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.database import Base


class QuizModel(Base):
    """Quiz database model."""

    __tablename__ = "quizzes"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("uuid_generate_v4()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    topic_ids: Mapped[List[UUID]] = mapped_column(
        ARRAY(PGUUID(as_uuid=True)),
        nullable=False,
    )
    questions: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_spaced_repetition: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        server_default=text("NOW()"),
    )

    # Relationships
    attempts: Mapped[List["QuizAttemptModel"]] = relationship(
        back_populates="quiz",
        cascade="all, delete-orphan",
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "topic_ids": self.topic_ids or [],
            "questions": self.questions,
            "is_spaced_repetition": self.is_spaced_repetition,
            "created_at": self.created_at,
        }


class QuizAttemptModel(Base):
    """Quiz attempt database model."""

    __tablename__ = "quiz_attempts"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("uuid_generate_v4()"),
    )
    quiz_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    answers: Mapped[dict] = mapped_column(JSONB, nullable=False)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    time_taken_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    gaps_identified: Mapped[List[UUID]] = mapped_column(
        ARRAY(PGUUID(as_uuid=True)),
        default=list,
        server_default="{}",
    )
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        server_default=text("NOW()"),
    )

    # Relationships
    quiz: Mapped["QuizModel"] = relationship(back_populates="attempts")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "quiz_id": self.quiz_id,
            "user_id": self.user_id,
            "answers": self.answers,
            "score": self.score,
            "time_taken_seconds": self.time_taken_seconds,
            "gaps_identified": self.gaps_identified or [],
            "attempted_at": self.attempted_at,
        }


class FeynmanSessionModel(Base):
    """Feynman session database model."""

    __tablename__ = "feynman_sessions"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("uuid_generate_v4()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    topic_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
    )
    dialogue_history: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        server_default="[]",
    )
    status: Mapped[str] = mapped_column(Text, default="active")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        server_default=text("NOW()"),
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    results: Mapped[List["FeynmanResultModel"]] = relationship(
        back_populates="feynman_session",
        cascade="all, delete-orphan",
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "topic_id": self.topic_id,
            "dialogue_history": self.dialogue_history or [],
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


class FeynmanResultModel(Base):
    """Feynman result database model."""

    __tablename__ = "feynman_results"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("uuid_generate_v4()"),
    )
    feynman_session_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("feynman_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    completeness_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    accuracy_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    simplicity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    overall_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gaps: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    strengths: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    suggestions: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        server_default=text("NOW()"),
    )

    # Relationships
    feynman_session: Mapped["FeynmanSessionModel"] = relationship(
        back_populates="results"
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "feynman_session_id": self.feynman_session_id,
            "completeness_score": self.completeness_score,
            "accuracy_score": self.accuracy_score,
            "simplicity_score": self.simplicity_score,
            "overall_score": self.overall_score,
            "gaps": self.gaps or [],
            "strengths": self.strengths or [],
            "suggestions": self.suggestions or [],
            "evaluated_at": self.evaluated_at,
        }
