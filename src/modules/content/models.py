"""SQLAlchemy models for Content module."""

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
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
from src.shared.models import SourceType


class ContentModel(Base):
    """Content database model."""

    __tablename__ = "content"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("uuid_generate_v4()"),
    )
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    raw_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processed_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    embedding = mapped_column(Vector(1536), nullable=True)
    topics: Mapped[List[UUID]] = mapped_column(
        ARRAY(PGUUID(as_uuid=True)),
        default=list,
        server_default="{}",
    )
    difficulty_level: Mapped[int] = mapped_column(Integer, default=3)
    importance_score: Mapped[float] = mapped_column(Float, default=0.5)
    author: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        server_default=text("NOW()"),
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    interactions: Mapped[List["UserContentInteractionModel"]] = relationship(
        back_populates="content",
        cascade="all, delete-orphan",
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "title": self.title,
            "raw_content": self.raw_content,
            "processed_content": self.processed_content,
            "summary": self.summary,
            "topics": self.topics or [],
            "difficulty_level": self.difficulty_level,
            "importance_score": self.importance_score,
            "author": self.author,
            "published_at": self.published_at,
            "created_at": self.created_at,
            "processed_at": self.processed_at,
        }


class UserContentInteractionModel(Base):
    """User content interaction database model."""

    __tablename__ = "user_content_interactions"

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
    content_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("content.id", ondelete="CASCADE"),
        nullable=False,
    )
    presented_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        server_default=text("NOW()"),
    )
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    time_spent_seconds: Mapped[int] = mapped_column(Integer, default=0)
    relevance_feedback: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    content: Mapped["ContentModel"] = relationship(back_populates="interactions")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "content_id": self.content_id,
            "presented_at": self.presented_at,
            "completed": self.completed,
            "time_spent_seconds": self.time_spent_seconds,
            "relevance_feedback": self.relevance_feedback,
            "notes": self.notes,
        }


class TopicModel(Base):
    """Topic database model."""

    __tablename__ = "topics"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("uuid_generate_v4()"),
    )
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prerequisites: Mapped[List[UUID]] = mapped_column(
        ARRAY(PGUUID(as_uuid=True)),
        default=list,
        server_default="{}",
    )
    difficulty_level: Mapped[int] = mapped_column(Integer, default=3)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        server_default=text("NOW()"),
    )

    # Relationships
    skill_components: Mapped[List["SkillComponentModel"]] = relationship(
        back_populates="topic",
        cascade="all, delete-orphan",
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "prerequisites": self.prerequisites or [],
            "difficulty_level": self.difficulty_level,
            "created_at": self.created_at,
        }


class SkillComponentModel(Base):
    """Skill component database model."""

    __tablename__ = "skill_components"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("uuid_generate_v4()"),
    )
    topic_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        server_default=text("NOW()"),
    )

    # Relationships
    topic: Mapped["TopicModel"] = relationship(back_populates="skill_components")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "topic_id": self.topic_id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at,
        }


class UserTopicProgressModel(Base):
    """User topic progress database model."""

    __tablename__ = "user_topic_progress"

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
    topic_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
    )
    proficiency_level: Mapped[float] = mapped_column(Float, default=0.0)
    last_practiced: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    next_review: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    practice_count: Mapped[int] = mapped_column(Integer, default=0)
    interleaving_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    ease_factor: Mapped[float] = mapped_column(Float, default=2.5)
    interval_days: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        server_default=text("NOW()"),
    )
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
            "topic_id": self.topic_id,
            "proficiency_level": self.proficiency_level,
            "last_practiced": self.last_practiced,
            "next_review": self.next_review,
            "practice_count": self.practice_count,
            "interleaving_eligible": self.interleaving_eligible,
            "ease_factor": self.ease_factor,
            "interval_days": self.interval_days,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
