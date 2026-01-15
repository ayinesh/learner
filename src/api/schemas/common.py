"""Common API response schemas."""

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class SuccessResponse(BaseModel):
    """Generic success response."""

    success: bool = True
    message: str = "Operation completed successfully"


class ErrorResponse(BaseModel):
    """Structured error response."""

    success: bool = False
    error: dict[str, Any] = Field(
        ...,
        description="Error details",
        examples=[{
            "code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": {},
        }],
    )
    request_id: str = Field(
        ...,
        description="Unique request identifier for debugging",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Error timestamp",
    )


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response."""

    items: list[T] = Field(
        ...,
        description="List of items",
    )
    total: int = Field(
        ...,
        description="Total number of items",
    )
    page: int = Field(
        default=1,
        description="Current page number",
    )
    page_size: int = Field(
        default=10,
        description="Items per page",
    )
    has_more: bool = Field(
        ...,
        description="Whether more pages exist",
    )

    @classmethod
    def create(
        cls,
        items: list[T],
        total: int,
        page: int = 1,
        page_size: int = 10,
    ) -> "PaginatedResponse[T]":
        """Create paginated response from items.

        Args:
            items: List of items for current page
            total: Total count of all items
            page: Current page number
            page_size: Items per page

        Returns:
            PaginatedResponse instance
        """
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_more=(page * page_size) < total,
        )


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str = Field(
        ...,
        description="Response message",
    )
