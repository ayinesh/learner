"""Assessment API routes."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from src.api.dependencies import AssessmentServiceDep, CurrentUser
from src.api.schemas.assessments import (
    FeynmanDialogueResponse,
    FeynmanEvaluationResponse,
    FeynmanResponseRequest,
    FeynmanSessionResponse,
    FeynmanStatus,
    GapResponse,
    GapsListResponse,
    GenerateQuizRequest,
    QuestionResultResponse,
    QuestionType,
    QuizQuestionResponse,
    QuizResponse,
    QuizResultResponse,
    ReviewDueResponse,
    ReviewItemResponse,
    StartFeynmanRequest,
    SubmitQuizRequest,
)

router = APIRouter()


# Quiz Endpoints
@router.post(
    "/quiz/generate",
    response_model=QuizResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate quiz",
    description="Generate a quiz on specified topics.",
)
async def generate_quiz(
    request: GenerateQuizRequest,
    current_user: CurrentUser,
    assessment_service: AssessmentServiceDep,
) -> QuizResponse:
    """Generate a quiz.

    Args:
        request: Quiz parameters
        current_user: Currently authenticated user
        assessment_service: Assessment service instance

    Returns:
        Generated quiz
    """
    quiz = await assessment_service.generate_quiz(
        user_id=current_user.id,
        topic_ids=request.topic_ids,
        question_count=request.question_count,
        include_review=request.include_review_items,
        difficulty=request.difficulty,
    )

    return QuizResponse(
        id=quiz.id,
        questions=[
            QuizQuestionResponse(
                id=q.id,
                question_type=QuestionType(q.question_type.value),
                question_text=q.question_text,
                options=q.options,
                topic_id=q.topic_id,
                difficulty=q.difficulty,
            )
            for q in quiz.questions
        ],
        created_at=quiz.created_at,
        time_limit_seconds=quiz.time_limit_seconds,
    )


@router.post(
    "/quiz/{quiz_id}/submit",
    response_model=QuizResultResponse,
    summary="Submit quiz",
    description="Submit answers and get results.",
)
async def submit_quiz(
    quiz_id: UUID,
    request: SubmitQuizRequest,
    current_user: CurrentUser,
    assessment_service: AssessmentServiceDep,
) -> QuizResultResponse:
    """Submit quiz answers.

    Args:
        quiz_id: Quiz UUID
        request: Answers
        current_user: Currently authenticated user
        assessment_service: Assessment service instance

    Returns:
        Quiz results

    Raises:
        HTTPException: If quiz not found
    """
    # Convert string keys to UUIDs
    answers = {UUID(k): v for k, v in request.answers.items()}

    try:
        result = await assessment_service.evaluate_quiz(
            quiz_id=quiz_id,
            user_id=current_user.id,
            answers=answers,
            time_taken=request.time_taken_seconds,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    return QuizResultResponse(
        quiz_id=result.quiz_id,
        score=result.score,
        correct_count=result.correct_count,
        total_count=result.total_count,
        question_results=[
            QuestionResultResponse(
                question_id=qr.question_id,
                user_answer=qr.user_answer,
                correct_answer=qr.correct_answer,
                is_correct=qr.is_correct,
                explanation=qr.explanation,
            )
            for qr in result.question_results
        ],
        gaps_identified=result.gaps_identified,
        time_taken_seconds=result.time_taken,
    )


@router.get(
    "/quiz/{quiz_id}/result",
    response_model=QuizResultResponse,
    summary="Get quiz result",
    description="Get result for a completed quiz.",
)
async def get_quiz_result(
    quiz_id: UUID,
    current_user: CurrentUser,
    assessment_service: AssessmentServiceDep,
) -> QuizResultResponse:
    """Get quiz result.

    Args:
        quiz_id: Quiz UUID
        current_user: Currently authenticated user
        assessment_service: Assessment service instance

    Returns:
        Quiz result

    Raises:
        HTTPException: If quiz or result not found
    """
    result = await assessment_service.get_quiz_result(
        quiz_id=quiz_id,
        user_id=current_user.id,
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz result not found",
        )

    return QuizResultResponse(
        quiz_id=result.quiz_id,
        score=result.score,
        correct_count=result.correct_count,
        total_count=result.total_count,
        question_results=[
            QuestionResultResponse(
                question_id=qr.question_id,
                user_answer=qr.user_answer,
                correct_answer=qr.correct_answer,
                is_correct=qr.is_correct,
                explanation=qr.explanation,
            )
            for qr in result.question_results
        ],
        gaps_identified=result.gaps_identified,
        time_taken_seconds=result.time_taken,
    )


# Feynman Endpoints
@router.post(
    "/feynman/start",
    response_model=FeynmanSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start Feynman session",
    description="Start a Feynman dialogue for a topic.",
)
async def start_feynman(
    request: StartFeynmanRequest,
    current_user: CurrentUser,
    assessment_service: AssessmentServiceDep,
) -> FeynmanSessionResponse:
    """Start Feynman session.

    Args:
        request: Topic to explain
        current_user: Currently authenticated user
        assessment_service: Assessment service instance

    Returns:
        New Feynman session
    """
    session = await assessment_service.start_feynman_session(
        user_id=current_user.id,
        topic_id=request.topic_id,
    )

    return FeynmanSessionResponse(
        id=session.id,
        topic_id=session.topic_id,
        topic_name=session.topic_name,
        prompt=session.initial_prompt,
        status=FeynmanStatus.ACTIVE,
        dialogue_turn=0,
    )


@router.post(
    "/feynman/{session_id}/respond",
    response_model=FeynmanDialogueResponse,
    summary="Continue Feynman dialogue",
    description="Submit explanation and get response.",
)
async def respond_feynman(
    session_id: UUID,
    request: FeynmanResponseRequest,
    current_user: CurrentUser,
    assessment_service: AssessmentServiceDep,
) -> FeynmanDialogueResponse:
    """Continue Feynman dialogue.

    Args:
        session_id: Session UUID
        request: User's explanation
        current_user: Currently authenticated user
        assessment_service: Assessment service instance

    Returns:
        Dialogue response

    Raises:
        HTTPException: If session not found
    """
    try:
        response = await assessment_service.continue_feynman_dialogue(
            session_id=session_id,
            user_response=request.user_response,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    return FeynmanDialogueResponse(
        session_id=session_id,
        agent_response=response.agent_response,
        probing_questions=response.probing_questions,
        gaps_so_far=response.gaps_identified,
        dialogue_turn=response.dialogue_turn,
        is_complete=response.is_complete,
    )


@router.post(
    "/feynman/{session_id}/evaluate",
    response_model=FeynmanEvaluationResponse,
    summary="Evaluate Feynman session",
    description="Get final evaluation of the explanation.",
)
async def evaluate_feynman(
    session_id: UUID,
    current_user: CurrentUser,
    assessment_service: AssessmentServiceDep,
) -> FeynmanEvaluationResponse:
    """Evaluate Feynman session.

    Args:
        session_id: Session UUID
        current_user: Currently authenticated user
        assessment_service: Assessment service instance

    Returns:
        Evaluation results

    Raises:
        HTTPException: If session not found
    """
    try:
        evaluation = await assessment_service.evaluate_feynman_session(session_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    return FeynmanEvaluationResponse(
        session_id=session_id,
        completeness_score=evaluation.completeness_score,
        accuracy_score=evaluation.accuracy_score,
        simplicity_score=evaluation.simplicity_score,
        overall_score=evaluation.overall_score,
        gaps_identified=evaluation.gaps_identified,
        strengths_identified=evaluation.strengths_identified,
        feedback=evaluation.feedback,
    )


# Review Endpoints
@router.get(
    "/reviews/due",
    response_model=ReviewDueResponse,
    summary="Get due reviews",
    description="Get items due for spaced repetition review.",
)
async def get_due_reviews(
    current_user: CurrentUser,
    assessment_service: AssessmentServiceDep,
    limit: int = Query(default=10, ge=1, le=50),
) -> ReviewDueResponse:
    """Get due review items.

    Args:
        current_user: Currently authenticated user
        assessment_service: Assessment service instance
        limit: Maximum items

    Returns:
        Due review items
    """
    items = await assessment_service.get_due_reviews(
        user_id=current_user.id,
        limit=limit,
    )

    return ReviewDueResponse(
        items=[
            ReviewItemResponse(
                id=item.id,
                topic_id=item.topic_id,
                topic_name=item.topic_name,
                next_review=item.next_review,
                ease_factor=item.ease_factor,
                interval=item.interval,
                repetitions=item.repetitions,
            )
            for item in items
        ],
        total_due=len(items),
    )


# Gap Endpoints
@router.get(
    "/gaps",
    response_model=GapsListResponse,
    summary="Get knowledge gaps",
    description="Get identified knowledge gaps.",
)
async def get_gaps(
    current_user: CurrentUser,
    assessment_service: AssessmentServiceDep,
    limit: int = Query(default=20, ge=1, le=100),
) -> GapsListResponse:
    """Get identified knowledge gaps.

    Args:
        current_user: Currently authenticated user
        assessment_service: Assessment service instance
        limit: Maximum items

    Returns:
        Knowledge gaps
    """
    gaps = await assessment_service.get_gaps(
        user_id=current_user.id,
        limit=limit,
    )

    return GapsListResponse(
        gaps=[
            GapResponse(
                id=gap.id,
                topic_id=gap.topic_id,
                topic_name=gap.topic_name,
                description=gap.description,
                identified_at=gap.identified_at,
                severity=gap.severity,
                source=gap.source,
            )
            for gap in gaps
        ],
        total=len(gaps),
    )
