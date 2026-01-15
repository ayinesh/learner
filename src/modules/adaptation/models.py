"""SQLAlchemy models for Adaptation module."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import Base
from src.shared.models import AdaptationType


class AdaptationEventModel(Base):
    """Adaptation event database model."""

    __tablename__ = "adaptation_events"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("uuid_generate_v4()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
    )
    adaptation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger_reason: Mapped[str] = mapped_column(Text, nullable=False)
    old_value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        server_default=text("NOW()"),
    )

    @property
    def adaptation_type_enum(self) -> AdaptationType:
        """Get adaptation type as enum."""
        return AdaptationType(self.adaptation_type)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "adaptation_type": self.adaptation_type,
            "trigger_reason": self.trigger_reason,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "created_at": self.created_at,
        }
