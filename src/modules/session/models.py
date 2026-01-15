"""SQLAlchemy models for Session module."""

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
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.database import Base
from src.shared.models import ActivityType, SessionStatus, SessionType


class SessionModel(Base):
    """Session database model."""

    __tablename__ = "sessions"

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
    session_type: Mapped[str] = mapped_column(
        String(50),
        default="regular",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="planned",
    )
    planned_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_duration_minutes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        server_default=text("NOW()"),
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    activities: Mapped[List["SessionActivityModel"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="SessionActivityModel.started_at",
    )

    @property
    def session_type_enum(self) -> SessionType:
        """Get session type as enum."""
        return SessionType(self.session_type)

    @property
    def status_enum(self) -> SessionStatus:
        """Get status as enum."""
        return SessionStatus(self.status)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "session_type": self.session_type,
            "status": self.status,
            "planned_duration_minutes": self.planned_duration_minutes,
            "actual_duration_minutes": self.actual_duration_minutes,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
        }

    def to_schema(self) -> "SessionSchema":
        """Convert to Pydantic schema."""
        from src.modules.session.schemas import SessionSchema

        return SessionSchema(
            id=self.id,
            user_id=self.user_id,
            session_type=SessionType(self.session_type),
            status=SessionStatus(self.status),
            planned_duration_minutes=self.planned_duration_minutes,
            actual_duration_minutes=self.actual_duration_minutes,
            started_at=self.started_at,
            ended_at=self.ended_at,
        )


class SessionActivityModel(Base):
    """Session activity database model."""

    __tablename__ = "session_activities"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("uuid_generate_v4()"),
    )
    session_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    activity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    topic_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="SET NULL"),
        nullable=True,
    )
    content_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("content.id", ondelete="SET NULL"),
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        server_default=text("NOW()"),
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    performance_data: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        server_default="{}",
    )

    # Relationships
    session: Mapped["SessionModel"] = relationship(back_populates="activities")

    @property
    def activity_type_enum(self) -> ActivityType:
        """Get activity type as enum."""
        return ActivityType(self.activity_type)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "activity_type": self.activity_type,
            "topic_id": self.topic_id,
            "content_id": self.content_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "performance_data": self.performance_data or {},
        }

    def to_schema(self) -> "SessionActivitySchema":
        """Convert to Pydantic schema."""
        from src.modules.session.schemas import SessionActivitySchema

        return SessionActivitySchema(
            id=self.id,
            session_id=self.session_id,
            activity_type=ActivityType(self.activity_type),
            topic_id=self.topic_id,
            content_id=self.content_id,
            started_at=self.started_at,
            ended_at=self.ended_at,
            performance_data=self.performance_data or {},
        )


class UserLearningPatternModel(Base):
    """User learning pattern database model."""

    __tablename__ = "user_learning_patterns"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("uuid_generate_v4()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    avg_session_duration: Mapped[float] = mapped_column(Float, default=0.0)
    preferred_time_of_day: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    completion_rate: Mapped[float] = mapped_column(Float, default=0.0)
    quiz_accuracy_trend: Mapped[float] = mapped_column(Float, default=0.0)
    feynman_score_trend: Mapped[float] = mapped_column(Float, default=0.0)
    days_since_last_session: Mapped[int] = mapped_column(Integer, default=0)
    total_sessions: Mapped[int] = mapped_column(Integer, default=0)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        server_default=text("NOW()"),
        onupdate=datetime.utcnow,
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "avg_session_duration": self.avg_session_duration,
            "preferred_time_of_day": self.preferred_time_of_day,
            "completion_rate": self.completion_rate,
            "quiz_accuracy_trend": self.quiz_accuracy_trend,
            "feynman_score_trend": self.feynman_score_trend,
            "days_since_last_session": self.days_since_last_session,
            "total_sessions": self.total_sessions,
            "current_streak": self.current_streak,
            "longest_streak": self.longest_streak,
            "updated_at": self.updated_at,
        }
