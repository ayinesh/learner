"""SQLAlchemy models for user profiles and learning patterns."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Enum, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP, UUID as PostgreSQL_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import Base
from src.shared.models import SourceType


class UserProfileModel(Base):
    """User profile model for learning preferences.

    Maps to the 'user_profiles' table in the database schema.
    Represents a user's learning profile, background, and preferences.
    """

    __tablename__ = "user_profiles"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PostgreSQL_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=func.uuid_generate_v4(),
    )

    # Foreign key to users table
    user_id: Mapped[UUID] = mapped_column(
        PostgreSQL_UUID(as_uuid=True),
        unique=True,
        nullable=False,
        index=True,
    )

    # Profile fields
    background: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    goals: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        default=list,
        server_default="{}",
    )

    time_budget_minutes: Mapped[int] = mapped_column(
        Integer,
        default=30,
        server_default="30",
    )

    preferred_sources: Mapped[list[str]] = mapped_column(
        ARRAY(Enum(
            SourceType,
            name="source_type",
            create_type=False,  # Don't create the enum, it already exists
            values_callable=lambda e: [member.value for member in e],  # Use lowercase values
        )),
        default=list,
        server_default="{}",
    )

    timezone: Mapped[str] = mapped_column(
        Text,
        default="UTC",
        server_default="UTC",
    )

    onboarding_completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<UserProfile(id={self.id}, user_id={self.user_id}, onboarding_completed={self.onboarding_completed})>"


class UserSourceConfigModel(Base):
    """User content source configuration model.

    Maps to the 'user_source_configs' table in the database schema.
    Stores configuration for each content source a user has enabled.
    """

    __tablename__ = "user_source_configs"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PostgreSQL_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=func.uuid_generate_v4(),
    )

    # Foreign key to users table
    user_id: Mapped[UUID] = mapped_column(
        PostgreSQL_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # Source configuration
    source_type: Mapped[str] = mapped_column(
        Enum(
            SourceType,
            name="source_type",
            create_type=False,  # Don't create the enum, it already exists
            values_callable=lambda e: [member.value for member in e],  # Use lowercase values
        ),
        nullable=False,
    )

    config: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        server_default="{}",
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<UserSourceConfig(id={self.id}, user_id={self.user_id}, source={self.source_type}, enabled={self.enabled})>"


# Note: UserLearningPatternModel is defined in src/modules/session/models.py
# to avoid circular imports and duplicate table definitions.
# Import it from there if needed:
# from src.modules.session.models import UserLearningPatternModel
