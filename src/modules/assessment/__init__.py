"""Assessment Module - Quizzes, Feynman dialogues, and gap identification.

Usage:
    # Recommended: Use service registry (respects feature flags)
    from src.modules.assessment import get_assessment_service
    service = get_assessment_service()

    # Direct access (bypasses feature flags)
    from src.modules.assessment import get_inmemory_assessment_service
    from src.modules.assessment import get_db_assessment_service
"""

from src.modules.assessment.interface import (
    FeynmanResponse,
    FeynmanResult,
    FeynmanSession,
    Gap,
    IAssessmentService,
    Question,
    QuestionType,
    Quiz,
    QuizResult,
    ReviewItem,
)
from src.modules.assessment.service import AssessmentService
from src.modules.assessment.service import get_assessment_service as get_inmemory_assessment_service
from src.modules.assessment.db_service import DatabaseAssessmentService, get_db_assessment_service
from src.modules.assessment.models import (
    QuizModel,
    QuizAttemptModel,
    FeynmanSessionModel,
    FeynmanResultModel,
)

# Registry-based service getter (recommended)
from src.shared.service_registry import get_assessment_service

__all__ = [
    # Interface types
    "FeynmanResponse",
    "FeynmanResult",
    "FeynmanSession",
    "Gap",
    "IAssessmentService",
    "Question",
    "QuestionType",
    "Quiz",
    "QuizResult",
    "ReviewItem",
    # Implementations
    "AssessmentService",
    "DatabaseAssessmentService",
    # Models
    "QuizModel",
    "QuizAttemptModel",
    "FeynmanSessionModel",
    "FeynmanResultModel",
    # Factory functions (recommended: get_assessment_service from registry)
    "get_assessment_service",  # Registry-based (respects feature flags)
    "get_inmemory_assessment_service",  # Direct in-memory access
    "get_db_assessment_service",  # Direct database access
]
