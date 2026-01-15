"""API schemas package."""

from src.api.schemas.common import (
    ErrorResponse,
    SuccessResponse,
    PaginatedResponse,
)
from src.api.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserResponse,
    AuthResponse,
)
from src.api.schemas.users import (
    UserProfileResponse,
    UpdateProfileRequest,
    OnboardingRequest,
    LearningPatternResponse,
    UpdateTimeBudgetRequest,
    SourceConfigRequest,
    SourceConfigResponse,
)
from src.api.schemas.sessions import (
    StartSessionRequest,
    SessionResponse,
    SessionPlanResponse,
    RecordActivityRequest,
    SessionSummaryResponse,
    SessionHistoryResponse,
    StreakInfoResponse,
)
from src.api.schemas.content import (
    ContentFeedRequest,
    ContentResponse,
    ContentFeedbackRequest,
    ContentSearchRequest,
    ContentSearchResponse,
)
from src.api.schemas.assessments import (
    GenerateQuizRequest,
    QuizResponse,
    QuizQuestionResponse,
    SubmitQuizRequest,
    QuizResultResponse,
    StartFeynmanRequest,
    FeynmanSessionResponse,
    FeynmanResponseRequest,
    FeynmanDialogueResponse,
    FeynmanEvaluationResponse,
    ReviewItemResponse,
    GapResponse,
)

__all__ = [
    # Common
    "ErrorResponse",
    "SuccessResponse",
    "PaginatedResponse",
    # Auth
    "RegisterRequest",
    "LoginRequest",
    "RefreshTokenRequest",
    "TokenResponse",
    "UserResponse",
    "AuthResponse",
    # Users
    "UserProfileResponse",
    "UpdateProfileRequest",
    "OnboardingRequest",
    "LearningPatternResponse",
    "UpdateTimeBudgetRequest",
    "SourceConfigRequest",
    "SourceConfigResponse",
    # Sessions
    "StartSessionRequest",
    "SessionResponse",
    "SessionPlanResponse",
    "RecordActivityRequest",
    "SessionSummaryResponse",
    "SessionHistoryResponse",
    "StreakInfoResponse",
    # Content
    "ContentFeedRequest",
    "ContentResponse",
    "ContentFeedbackRequest",
    "ContentSearchRequest",
    "ContentSearchResponse",
    # Assessments
    "GenerateQuizRequest",
    "QuizResponse",
    "QuizQuestionResponse",
    "SubmitQuizRequest",
    "QuizResultResponse",
    "StartFeynmanRequest",
    "FeynmanSessionResponse",
    "FeynmanResponseRequest",
    "FeynmanDialogueResponse",
    "FeynmanEvaluationResponse",
    "ReviewItemResponse",
    "GapResponse",
]
