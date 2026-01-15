"""Content API routes."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from src.api.dependencies import ContentServiceDep, CurrentUser
from src.api.schemas.content import (
    ContentDetailResponse,
    ContentFeedbackRequest,
    ContentFeedResponse,
    ContentResponse,
    ContentSearchRequest,
    ContentSearchResponse,
    IngestContentRequest,
    IngestContentResponse,
)
from src.api.schemas.common import SuccessResponse
from src.shared.models import SourceType

router = APIRouter()


@router.get(
    "/feed",
    response_model=ContentFeedResponse,
    summary="Get content feed",
    description="Get personalized content recommendations.",
)
async def get_content_feed(
    current_user: CurrentUser,
    content_service: ContentServiceDep,
    limit: int = Query(default=10, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    min_relevance: float = Query(default=0.0, ge=0.0, le=1.0),
) -> ContentFeedResponse:
    """Get personalized content feed.

    Args:
        current_user: Currently authenticated user
        content_service: Content service instance
        limit: Maximum items
        offset: Pagination offset
        min_relevance: Minimum relevance score

    Returns:
        Content feed
    """
    # Get relevant content from service
    all_content = await content_service.get_relevant_content(
        user_id=current_user.id,
        limit=limit + offset,  # Get extra for offset
        min_relevance=min_relevance,
    )

    # Apply offset and limit
    items = all_content[offset:offset + limit]

    # Convert to response
    content_items = [
        ContentResponse(
            id=content.id,
            title=content.title,
            summary=content.summary,
            source_type=content.source_type,
            source_url=content.source_url,
            topics=content.topics,
            difficulty_level=content.difficulty_level,
            relevance_score=content.relevance_score,
            importance_score=0.0,  # Not exposed in Content interface
            created_at=content.created_at,
        )
        for content in items
    ]

    return ContentFeedResponse(
        items=content_items,
        total=len(all_content),
        has_more=offset + limit < len(all_content),
    )


@router.get(
    "/search",
    response_model=ContentSearchResponse,
    summary="Search content",
    description="Search content by query.",
)
async def search_content(
    current_user: CurrentUser,
    content_service: ContentServiceDep,
    query: str = Query(..., min_length=2, max_length=200),
    limit: int = Query(default=10, ge=1, le=50),
) -> ContentSearchResponse:
    """Search content.

    Args:
        current_user: Currently authenticated user
        content_service: Content service instance
        query: Search query
        limit: Maximum results

    Returns:
        Search results
    """
    results = await content_service.search_content(
        query=query,
        user_id=current_user.id,
        limit=limit,
    )

    content_items = [
        ContentResponse(
            id=content.id,
            title=content.title,
            summary=content.summary,
            source_type=content.source_type,
            source_url=content.source_url,
            topics=content.topics,
            difficulty_level=content.difficulty_level,
            relevance_score=content.relevance_score,
            importance_score=0.0,  # Not exposed in Content interface
            created_at=content.created_at,
        )
        for content in results
    ]

    return ContentSearchResponse(
        items=content_items,
        total=len(content_items),
        query=query,
    )


@router.get(
    "/{content_id}",
    response_model=ContentDetailResponse,
    summary="Get content details",
    description="Get detailed content by ID.",
)
async def get_content(
    content_id: UUID,
    current_user: CurrentUser,
    content_service: ContentServiceDep,
) -> ContentDetailResponse:
    """Get content by ID.

    Args:
        content_id: Content UUID
        current_user: Currently authenticated user
        content_service: Content service instance

    Returns:
        Content details

    Raises:
        HTTPException: If content not found
    """
    # Search for the specific content
    # Note: In production, this would be a direct DB lookup
    all_content = await content_service.get_relevant_content(
        user_id=current_user.id,
        limit=100,
        min_relevance=0.0,
    )

    content = next((c for c in all_content if c.id == content_id), None)

    if content is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found",
        )

    # Mark as seen
    await content_service.mark_content_seen(content_id, current_user.id)

    return ContentDetailResponse(
        id=content.id,
        title=content.title,
        summary=content.summary,
        source_type=content.source_type,
        source_url=content.source_url,
        topics=content.topics,
        difficulty_level=content.difficulty_level,
        relevance_score=content.relevance_score,
        importance_score=0.0,
        created_at=content.created_at,
        raw_content=content.content,  # Content interface uses 'content' field
        processed_content=content.content,
        authors=None,
        published_at=None,
    )


@router.post(
    "/{content_id}/feedback",
    response_model=SuccessResponse,
    summary="Submit feedback",
    description="Submit feedback on content relevance.",
)
async def submit_feedback(
    content_id: UUID,
    request: ContentFeedbackRequest,
    current_user: CurrentUser,
    content_service: ContentServiceDep,
) -> SuccessResponse:
    """Submit content feedback.

    Args:
        content_id: Content UUID
        request: Feedback data
        current_user: Currently authenticated user
        content_service: Content service instance

    Returns:
        Success response
    """
    await content_service.record_feedback(
        content_id=content_id,
        user_id=current_user.id,
        relevance_rating=request.relevance_rating,
        notes=request.notes,
    )

    return SuccessResponse(message="Feedback recorded")


@router.get(
    "/topics/{topic_id}",
    response_model=ContentFeedResponse,
    summary="Get content by topic",
    description="Get content filtered by topic.",
)
async def get_content_by_topic(
    topic_id: UUID,
    current_user: CurrentUser,
    content_service: ContentServiceDep,
    limit: int = Query(default=10, ge=1, le=50),
) -> ContentFeedResponse:
    """Get content by topic.

    Args:
        topic_id: Topic UUID
        current_user: Currently authenticated user
        content_service: Content service instance
        limit: Maximum items

    Returns:
        Content for topic
    """
    content_list = await content_service.get_content_by_topic(
        topic_id=topic_id,
        user_id=current_user.id,
        limit=limit,
    )

    content_items = [
        ContentResponse(
            id=content.id,
            title=content.title,
            summary=content.summary,
            source_type=content.source_type,
            source_url=content.source_url,
            topics=content.topics,
            difficulty_level=content.difficulty_level,
            relevance_score=content.relevance_score,
            importance_score=0.0,
            created_at=content.created_at,
        )
        for content in content_list
    ]

    return ContentFeedResponse(
        items=content_items,
        total=len(content_items),
        has_more=False,
    )


@router.post(
    "/ingest",
    response_model=IngestContentResponse,
    summary="Ingest content (Admin)",
    description="Trigger content ingestion from a source.",
)
async def ingest_content(
    request: IngestContentRequest,
    current_user: CurrentUser,
    content_service: ContentServiceDep,
) -> IngestContentResponse:
    """Trigger content ingestion.

    Args:
        request: Ingestion parameters
        current_user: Currently authenticated user (should be admin)
        content_service: Content service instance

    Returns:
        Ingestion results
    """
    try:
        items = await content_service.ingest_from_source(
            source_type=request.source_type,
            config=request.config,
            limit=request.limit,
        )

        return IngestContentResponse(
            success=True,
            items_ingested=len(items),
            errors=[],
        )

    except Exception as e:
        return IngestContentResponse(
            success=False,
            items_ingested=0,
            errors=[str(e)],
        )
