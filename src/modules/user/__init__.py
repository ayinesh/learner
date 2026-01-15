"""User module - Profile and preferences management."""

from src.modules.user.interface import (
    IUserService,
    OnboardingData,
    UserLearningPattern,
    UserProfile,
)
from src.modules.user.models import (
    UserProfileModel,
    UserSourceConfigModel,
)
# UserLearningPatternModel is defined in session module to avoid duplicate table definitions
from src.modules.session.models import UserLearningPatternModel
from src.modules.user.schemas import (
    AddSourceRequest,
    CompleteOnboardingRequest,
    CreateProfileRequest,
    PatternSuccessResponse,
    ProfileSuccessResponse,
    RemoveSourceRequest,
    SourceConfigResponse,
    SourceConfigSchema,
    SourceSuccessResponse,
    UpdateProfileRequest,
    UpdateTimeBudgetRequest,
    UserErrorResponse,
    UserLearningPatternSchema,
    UserProfileSchema,
)
from src.modules.user.service import UserService, get_user_service

__all__ = [
    # Interface
    "IUserService",
    "UserProfile",
    "UserLearningPattern",
    "OnboardingData",
    # Service
    "UserService",
    "get_user_service",
    # Models
    "UserProfileModel",
    "UserSourceConfigModel",
    "UserLearningPatternModel",
    # Schemas
    "CreateProfileRequest",
    "UpdateProfileRequest",
    "CompleteOnboardingRequest",
    "UpdateTimeBudgetRequest",
    "AddSourceRequest",
    "RemoveSourceRequest",
    "UserProfileSchema",
    "UserLearningPatternSchema",
    "SourceConfigSchema",
    "ProfileSuccessResponse",
    "PatternSuccessResponse",
    "SourceSuccessResponse",
    "SourceConfigResponse",
    "UserErrorResponse",
]
