"""Shared Learning Context - Provides unified context across all agents.

This module defines the SharedLearningContext that enables agents to work
together toward a user's learning goals. When a user tells Coach "I want
to learn ML" and later asks Curriculum about math, Curriculum will know
that math is a prerequisite for the ML goal.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass
class LearningPathStage:
    """A stage in the user's learning path."""

    topic: str
    status: str = "not_started"  # "not_started", "in_progress", "completed"
    progress: float = 0.0  # 0.0 to 1.0
    milestone: str | None = None
    parent_goal: str | None = None  # Links back to primary goal


@dataclass
class SharedLearningContext:
    """Shared context accessible by all agents.

    This context is persisted in the database and passed to every agent,
    ensuring they all have awareness of:
    - The user's primary learning goal
    - What they're currently focusing on
    - Their learning path and progress
    - Discovered preferences and constraints

    Example flow:
    1. User tells Coach: "I want to learn machine learning"
    2. Context updated: primary_goal = "machine learning"
    3. Coach suggests: Math -> Python -> ML fundamentals
    4. Context updated: learning_path = [{topic: "math", ...}, ...]
    5. User asks Curriculum: "Let's start with math"
    6. Context updated: current_focus = "math foundations"
    7. Curriculum knows math is step 1 toward ML goal (not standalone)
    """

    user_id: UUID

    # Primary learning goal extracted from conversations
    # e.g., "become an ML expert", "learn Python for data science"
    primary_goal: str | None = None

    # Current focus area within the goal
    # e.g., "math foundations", "linear algebra", "Python basics"
    current_focus: str | None = None

    # Learning path stages with progress tracking
    learning_path: list[LearningPathStage] = field(default_factory=list)

    # User preferences discovered from conversation
    # e.g., {"learning_style": "hands-on", "pace": "moderate", "explanation_depth": "detailed"}
    preferences: dict[str, Any] = field(default_factory=dict)

    # Recent topics discussed (for continuity)
    recent_topics: list[str] = field(default_factory=list)

    # Knowledge gaps identified by agents
    identified_gaps: list[str] = field(default_factory=list)

    # User's stated constraints
    # e.g., {"time_per_day_minutes": 30, "deadline": "3 months", "background": "beginner"}
    constraints: dict[str, Any] = field(default_factory=dict)

    # Proficiency levels by topic (0.0 to 1.0)
    proficiency_levels: dict[str, float] = field(default_factory=dict)

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def get_current_stage(self) -> LearningPathStage | None:
        """Get the current in-progress stage of the learning path."""
        for stage in self.learning_path:
            if stage.status == "in_progress":
                return stage
        return None

    def get_next_stage(self) -> LearningPathStage | None:
        """Get the next not-started stage in the learning path."""
        for stage in self.learning_path:
            if stage.status == "not_started":
                return stage
        return None

    def add_topic_to_recent(self, topic: str, max_recent: int = 10) -> None:
        """Add a topic to recent topics, maintaining max size."""
        if topic in self.recent_topics:
            self.recent_topics.remove(topic)
        self.recent_topics.insert(0, topic)
        self.recent_topics = self.recent_topics[:max_recent]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "user_id": str(self.user_id),
            "primary_goal": self.primary_goal,
            "current_focus": self.current_focus,
            "learning_path": [
                {
                    "topic": stage.topic,
                    "status": stage.status,
                    "progress": stage.progress,
                    "milestone": stage.milestone,
                    "parent_goal": stage.parent_goal,
                }
                for stage in self.learning_path
            ],
            "preferences": self.preferences,
            "recent_topics": self.recent_topics,
            "identified_gaps": self.identified_gaps,
            "constraints": self.constraints,
            "proficiency_levels": self.proficiency_levels,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SharedLearningContext":
        """Create from dictionary."""
        learning_path = [
            LearningPathStage(
                topic=stage["topic"],
                status=stage.get("status", "not_started"),
                progress=stage.get("progress", 0.0),
                milestone=stage.get("milestone"),
                parent_goal=stage.get("parent_goal"),
            )
            for stage in data.get("learning_path", [])
        ]

        return cls(
            user_id=UUID(data["user_id"]) if isinstance(data["user_id"], str) else data["user_id"],
            primary_goal=data.get("primary_goal"),
            current_focus=data.get("current_focus"),
            learning_path=learning_path,
            preferences=data.get("preferences", {}),
            recent_topics=data.get("recent_topics", []),
            identified_gaps=data.get("identified_gaps", []),
            constraints=data.get("constraints", {}),
            proficiency_levels=data.get("proficiency_levels", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.utcnow(),
        )


@dataclass
class ContextUpdate:
    """A single context update to be applied.

    Used by the ContextExtractor to communicate discovered updates
    back to the orchestrator.
    """

    field: str  # Field name: "primary_goal", "current_focus", etc.
    value: Any  # The new value
    confidence: float  # 0.0 to 1.0 - how confident the extraction is
    source: str  # "user_stated", "inferred", "agent_determined"
    reason: str = ""  # Why this update was extracted


@dataclass
class OnboardingState:
    """Tracks conversational onboarding progress for agents.

    When an agent needs to gather information (e.g., Curriculum needs to know
    goals, timeline, background before creating a learning path), this state
    tracks which questions have been asked and answered.

    This enables a natural conversational flow where agents ask one question
    at a time instead of overwhelming users with many questions at once.
    """

    # Which agent's onboarding this is for
    agent_type: str = "curriculum"

    # Whether onboarding for this agent is complete
    is_complete: bool = False

    # Current question being asked (key from ONBOARDING_QUESTIONS)
    current_question: str | None = None

    # Answers collected so far: {"goal": "career change", "timeline": "6 months", ...}
    answers_collected: dict[str, str] = field(default_factory=dict)

    # The topic being discussed (e.g., "machine learning")
    topic: str | None = None

    # Timestamp when onboarding started
    started_at: datetime = field(default_factory=datetime.utcnow)

    def is_question_answered(self, question_key: str) -> bool:
        """Check if a specific question has been answered."""
        return question_key in self.answers_collected

    def record_answer(self, question_key: str, answer: str) -> None:
        """Record an answer to a question."""
        self.answers_collected[question_key] = answer

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "agent_type": self.agent_type,
            "is_complete": self.is_complete,
            "current_question": self.current_question,
            "answers_collected": self.answers_collected,
            "topic": self.topic,
            "started_at": self.started_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OnboardingState":
        """Create from dictionary."""
        return cls(
            agent_type=data.get("agent_type", "curriculum"),
            is_complete=data.get("is_complete", False),
            current_question=data.get("current_question"),
            answers_collected=data.get("answers_collected", {}),
            topic=data.get("topic"),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else datetime.utcnow(),
        )
