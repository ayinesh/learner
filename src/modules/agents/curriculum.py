"""Curriculum Agent - Learning path planning and topic recommendations."""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from src.modules.agents.interface import (
    AgentContext,
    AgentResponse,
    AgentType,
    BaseAgent,
    ICurriculumAgent,
)
from src.modules.agents.learning_context import OnboardingState, SharedLearningContext
from src.modules.agents.context_service import get_context_service
from src.modules.agents.context_builder import (
    ConversationContextBuilder,
    build_agent_system_prompt,
)
from src.modules.llm.service import LLMService, get_llm_service


# Onboarding questions for curriculum agent - asked one at a time
CURRICULUM_ONBOARDING_QUESTIONS = [
    {
        "key": "motivation",
        "question": "What's driving your interest in {topic}? (career change, job enhancement, personal project, or academic?)",
        "context_field": "constraints.motivation",
    },
    {
        "key": "timeline",
        "question": "How much time can you dedicate weekly, and when do you want to reach your goal?",
        "context_field": "constraints.timeline",
    },
    {
        "key": "programming",
        "question": "What's your programming experience? (Python, other languages, or complete beginner?)",
        "context_field": "constraints.programming_background",
    },
    {
        "key": "math",
        "question": "How comfortable are you with math? (statistics, linear algebra, calculus - or beginner level?)",
        "context_field": "constraints.math_background",
    },
    {
        "key": "style",
        "question": "Last question - do you prefer hands-on projects, theory-first learning, or a mix of both?",
        "context_field": "preferences.learning_style",
    },
]


@dataclass
class LearningPath:
    """A structured learning path."""

    id: UUID
    title: str
    duration_weeks: int
    total_hours: float
    phases: list[dict]
    weekly_schedule: list[dict]
    success_criteria: list[str]
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TopicRecommendation:
    """A recommended next topic."""

    topic_id: UUID | str
    topic_title: str
    recommendation_type: str  # path_continuation, gap_recovery, review, skill_building, exploration
    rationale: str
    activity_type: str  # read, practice, quiz, feynman, project
    estimated_minutes: int
    difficulty_level: int
    goal_alignment: str
    session_structure: list[dict]
    alternative_topics: list[dict] = field(default_factory=list)


@dataclass
class UserLearningState:
    """Current learning state for a user."""

    user_id: UUID
    topic_proficiencies: dict[str, float]
    recent_topics: list[str]
    identified_gaps: list[str]
    review_items_due: list[str]
    recent_quiz_scores: list[float]
    last_feynman_score: float | None
    struggle_areas: list[str]
    strong_areas: list[str]
    current_phase: str
    planned_topics: list[str]
    user_goals: list[str]
    days_to_milestone: int


class CurriculumAgent(BaseAgent, ICurriculumAgent):
    """Agent responsible for planning learning paths and recommending topics.

    This agent creates personalized learning curricula based on user goals,
    background, and constraints. It applies principles from Ultralearning
    and Learning How to Learn to optimize the learning sequence.
    """

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self._llm = llm_service or get_llm_service()
        self._learning_paths: dict[UUID, LearningPath] = {}
        self._user_paths: dict[UUID, UUID] = {}  # user_id -> path_id

    @property
    def agent_type(self) -> AgentType:
        return AgentType.CURRICULUM

    @property
    def system_prompt(self) -> str:
        template = self._llm.load_prompt_template("curriculum/learning_path")
        return template.system

    async def respond(
        self,
        context: AgentContext,
        user_message: str,
    ) -> AgentResponse:
        """Generate curriculum-related response based on context."""
        action = context.additional_data.get("action", "recommend")

        if action == "generate_path":
            return await self._handle_path_generation(context)
        elif action == "recommend_topic":
            return await self._handle_topic_recommendation(context)
        elif action == "review_progress":
            return await self._handle_progress_review(context)
        else:
            # Analyze message to determine intent
            return await self._handle_general(context, user_message)

    async def generate_learning_path(
        self,
        user_id: UUID,
        goals: list[str],
        time_horizon_days: int = 30,
    ) -> dict:
        """Generate a personalized learning path.

        Args:
            user_id: User to generate path for
            goals: User's learning goals
            time_horizon_days: How many days to plan for

        Returns:
            Learning path with phases, topics, and schedule
        """
        template = self._llm.load_prompt_template("curriculum/learning_path")

        # Calculate weeks from days
        duration_weeks = max(1, time_horizon_days // 7)

        # Default values for optional context
        system_prompt, user_prompt = template.format(
            background="General technical background",
            goals=", ".join(goals),
            hours_per_week=5,
            duration_weeks=duration_weeks,
            learning_preferences="Active learning with practice",
            prior_knowledge="To be assessed",
            session_minutes=30,
            content_preferences="Interactive content, videos, hands-on projects",
            specific_interests=", ".join(goals),
            motivation="Career development and personal growth",
            target_outcome="Practical proficiency in " + ", ".join(goals),
            deadline=f"{time_horizon_days} days from now",
        )

        response = await self._llm.complete(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.7,
        )

        # Parse response
        path_data = self._parse_learning_path(response.content)

        # Create and store path
        path = LearningPath(
            id=uuid4(),
            title=path_data.get("title", "Learning Path"),
            duration_weeks=path_data.get("duration_weeks", duration_weeks),
            total_hours=path_data.get("total_hours", duration_weeks * 5),
            phases=path_data.get("phases", []),
            weekly_schedule=path_data.get("weekly_schedule", []),
            success_criteria=path_data.get("success_criteria", []),
        )

        self._learning_paths[path.id] = path
        self._user_paths[user_id] = path.id

        return path_data

    async def recommend_next_topic(self, user_id: UUID) -> dict:
        """Recommend the next topic to learn.

        Args:
            user_id: User to recommend for

        Returns:
            Topic recommendation with rationale
        """
        # Get user's learning state (in production, fetch from services)
        state = self._get_user_learning_state(user_id)

        template = self._llm.load_prompt_template("curriculum/next_topic")

        # Format proficiencies
        proficiency_str = "\n".join(
            f"- {topic}: {level:.0%}"
            for topic, level in state.topic_proficiencies.items()
        ) or "No proficiency data yet"

        # Format quiz scores
        quiz_scores_str = ", ".join(
            f"{score:.0%}" for score in state.recent_quiz_scores
        ) or "No recent quizzes"

        system_prompt, user_prompt = template.format(
            user_id=str(user_id),
            session_minutes=30,
            energy_level="medium",
            topic_proficiencies=proficiency_str,
            recent_topics=", ".join(state.recent_topics) or "None",
            identified_gaps=", ".join(state.identified_gaps) or "None identified",
            review_items_due=", ".join(state.review_items_due) or "None due",
            recent_quiz_scores=quiz_scores_str,
            last_feynman_score=f"{state.last_feynman_score:.1f}/10" if state.last_feynman_score else "N/A",
            struggle_areas=", ".join(state.struggle_areas) or "None noted",
            strong_areas=", ".join(state.strong_areas) or "None noted",
            current_phase=state.current_phase,
            planned_topics=", ".join(state.planned_topics) or "To be determined",
            user_goals=", ".join(state.user_goals) or "General learning",
            days_to_milestone=state.days_to_milestone,
            days_since_last=1,
            time_of_day="afternoon",
            session_type_preference="balanced",
        )

        response = await self._llm.complete(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.6,
        )

        return self._parse_recommendation(response.content)

    async def generate_learning_path_detailed(
        self,
        user_id: UUID,
        profile: dict,
    ) -> dict:
        """Generate a detailed learning path with full user profile.

        Args:
            user_id: User to generate path for
            profile: Detailed user profile with background, goals, constraints

        Returns:
            Comprehensive learning path
        """
        template = self._llm.load_prompt_template("curriculum/learning_path")

        system_prompt, user_prompt = template.format(
            background=profile.get("background", "General background"),
            goals=", ".join(profile.get("goals", [])),
            hours_per_week=profile.get("hours_per_week", 5),
            duration_weeks=profile.get("duration_weeks", 4),
            learning_preferences=profile.get("learning_preferences", "Active learning"),
            prior_knowledge=profile.get("prior_knowledge", "To be assessed"),
            session_minutes=profile.get("session_minutes", 30),
            content_preferences=profile.get("content_preferences", "Mixed"),
            specific_interests=profile.get("specific_interests", ""),
            motivation=profile.get("motivation", "Personal growth"),
            target_outcome=profile.get("target_outcome", "Practical proficiency"),
            deadline=profile.get("deadline", "Flexible"),
        )

        response = await self._llm.complete(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.7,
        )

        path_data = self._parse_learning_path(response.content)

        # Store path
        path = LearningPath(
            id=uuid4(),
            title=path_data.get("title", "Learning Path"),
            duration_weeks=path_data.get("duration_weeks", 4),
            total_hours=path_data.get("total_hours", 20),
            phases=path_data.get("phases", []),
            weekly_schedule=path_data.get("weekly_schedule", []),
            success_criteria=path_data.get("success_criteria", []),
        )

        self._learning_paths[path.id] = path
        self._user_paths[user_id] = path.id

        return path_data

    async def recommend_with_context(
        self,
        user_id: UUID,
        state: UserLearningState,
        session_context: dict,
    ) -> TopicRecommendation:
        """Recommend next topic with full context.

        Args:
            user_id: User to recommend for
            state: Current learning state
            session_context: Current session context (time, energy, etc.)

        Returns:
            TopicRecommendation with detailed guidance
        """
        template = self._llm.load_prompt_template("curriculum/next_topic")

        # Format proficiencies
        proficiency_str = "\n".join(
            f"- {topic}: {level:.0%}"
            for topic, level in state.topic_proficiencies.items()
        ) or "No proficiency data yet"

        quiz_scores_str = ", ".join(
            f"{score:.0%}" for score in state.recent_quiz_scores
        ) or "No recent quizzes"

        system_prompt, user_prompt = template.format(
            user_id=str(user_id),
            session_minutes=session_context.get("session_minutes", 30),
            energy_level=session_context.get("energy_level", "medium"),
            topic_proficiencies=proficiency_str,
            recent_topics=", ".join(state.recent_topics) or "None",
            identified_gaps=", ".join(state.identified_gaps) or "None",
            review_items_due=", ".join(state.review_items_due) or "None",
            recent_quiz_scores=quiz_scores_str,
            last_feynman_score=f"{state.last_feynman_score:.1f}/10" if state.last_feynman_score else "N/A",
            struggle_areas=", ".join(state.struggle_areas) or "None",
            strong_areas=", ".join(state.strong_areas) or "None",
            current_phase=state.current_phase,
            planned_topics=", ".join(state.planned_topics) or "To be determined",
            user_goals=", ".join(state.user_goals) or "General learning",
            days_to_milestone=state.days_to_milestone,
            days_since_last=session_context.get("days_since_last", 1),
            time_of_day=session_context.get("time_of_day", "afternoon"),
            session_type_preference=session_context.get("session_type", "balanced"),
        )

        response = await self._llm.complete(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.6,
        )

        rec_data = self._parse_recommendation(response.content)

        return TopicRecommendation(
            topic_id=rec_data.get("recommended_topic_id", str(uuid4())),
            topic_title=rec_data.get("topic_title", "Next Topic"),
            recommendation_type=rec_data.get("recommendation_type", "path_continuation"),
            rationale=rec_data.get("rationale", ""),
            activity_type=rec_data.get("activity_type", "read"),
            estimated_minutes=rec_data.get("estimated_minutes", 30),
            difficulty_level=rec_data.get("difficulty_level", 3),
            goal_alignment=rec_data.get("goal_alignment", ""),
            session_structure=rec_data.get("session_structure", []),
            alternative_topics=rec_data.get("alternative_topics", []),
        )

    def _parse_learning_path(self, content: str) -> dict:
        """Parse learning path from LLM response."""
        try:
            if "```" in content:
                match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
                if match:
                    content = match.group(1)
            return json.loads(content)
        except (json.JSONDecodeError, ValueError):
            return {
                "title": "Learning Path",
                "duration_weeks": 4,
                "total_hours": 20,
                "phases": [],
                "weekly_schedule": [],
                "success_criteria": [],
            }

    def _parse_recommendation(self, content: str) -> dict:
        """Parse topic recommendation from LLM response."""
        try:
            if "```" in content:
                match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
                if match:
                    content = match.group(1)
            return json.loads(content)
        except (json.JSONDecodeError, ValueError):
            return {
                "recommended_topic_id": str(uuid4()),
                "topic_title": "Continue Learning",
                "recommendation_type": "path_continuation",
                "rationale": "Continue with the current learning path",
                "activity_type": "read",
                "estimated_minutes": 30,
                "difficulty_level": 3,
                "goal_alignment": "Advancing toward your goals",
                "session_structure": [],
            }

    def _get_user_learning_state(
        self,
        user_id: UUID,
        context: AgentContext | None = None,
    ) -> UserLearningState:
        """Get user learning state from shared context.

        Uses SharedLearningContext from the orchestrator to ensure
        all agents have consistent view of user's goals and progress.

        Args:
            user_id: User's UUID
            context: AgentContext containing shared learning context

        Returns:
            UserLearningState populated from shared context
        """
        # Try to get learning context from AgentContext
        learning_ctx = None
        if context and context.additional_data:
            learning_ctx = context.additional_data.get("learning_context")

        if learning_ctx:
            # Use shared context data
            return UserLearningState(
                user_id=user_id,
                topic_proficiencies=learning_ctx.proficiency_levels or {},
                recent_topics=learning_ctx.recent_topics or [],
                identified_gaps=learning_ctx.identified_gaps or [],
                review_items_due=[],  # From spaced repetition system
                recent_quiz_scores=[],  # From assessment history
                last_feynman_score=None,
                struggle_areas=learning_ctx.identified_gaps or [],
                strong_areas=[
                    topic for topic, level in (learning_ctx.proficiency_levels or {}).items()
                    if level >= 0.7
                ],
                current_phase=learning_ctx.current_focus or "Getting Started",
                planned_topics=[
                    stage.topic for stage in (learning_ctx.learning_path or [])
                    if stage.status != "completed"
                ],
                user_goals=[learning_ctx.primary_goal] if learning_ctx.primary_goal else ["Learn effectively"],
                days_to_milestone=learning_ctx.constraints.get("deadline_days", 30) if learning_ctx.constraints else 30,
            )

        # Fallback to defaults if no context available
        return UserLearningState(
            user_id=user_id,
            topic_proficiencies={},
            recent_topics=[],
            identified_gaps=[],
            review_items_due=[],
            recent_quiz_scores=[],
            last_feynman_score=None,
            struggle_areas=[],
            strong_areas=[],
            current_phase="Getting Started",
            planned_topics=[],
            user_goals=["Learn effectively"],
            days_to_milestone=30,
        )

    async def _handle_path_generation(
        self,
        context: AgentContext,
    ) -> AgentResponse:
        """Handle learning path generation request."""
        # Get goals from shared learning context first, then fall back to additional_data
        learning_ctx = context.additional_data.get("learning_context")
        if learning_ctx and learning_ctx.primary_goal:
            goals = [learning_ctx.primary_goal]
        else:
            goals = context.additional_data.get("goals", ["General learning"])

        time_horizon = context.additional_data.get("time_horizon_days", 30)

        path = await self.generate_learning_path(
            user_id=context.user_id,
            goals=goals,
            time_horizon_days=time_horizon,
        )

        # Format response message
        phases_summary = "\n".join(
            f"  {i+1}. {p.get('title', 'Phase')}: {p.get('milestone', 'Complete phase goals')}"
            for i, p in enumerate(path.get("phases", [])[:3])
        )

        message = f"""I've created a personalized learning path for you!

**{path.get('title', 'Your Learning Path')}**
Duration: {path.get('duration_weeks', 4)} weeks ({path.get('total_hours', 20)} hours total)

**Phases:**
{phases_summary}

Ready to start? I'll guide you through each phase with quizzes and practice along the way."""

        return AgentResponse(
            agent_type=self.agent_type,
            message=message,
            data={
                "action": "path_generated",
                "learning_path": path,
            },
            suggested_next_agent=AgentType.COACH,
        )

    async def _handle_topic_recommendation(
        self,
        context: AgentContext,
    ) -> AgentResponse:
        """Handle topic recommendation request."""
        recommendation = await self.recommend_next_topic(context.user_id)

        # Format response
        message = f"""**Recommended Next Topic:** {recommendation.get('topic_title', 'Next Topic')}

**Why now:** {recommendation.get('rationale', 'This is the next step in your learning path.')}

**Activity:** {recommendation.get('activity_type', 'Study').title()} ({recommendation.get('estimated_minutes', 30)} minutes)

**How it helps:** {recommendation.get('goal_alignment', 'Moves you toward your goals')}

Ready to start?"""

        return AgentResponse(
            agent_type=self.agent_type,
            message=message,
            data={
                "action": "topic_recommended",
                "recommendation": recommendation,
            },
        )

    async def _handle_progress_review(
        self,
        context: AgentContext,
    ) -> AgentResponse:
        """Handle progress review request."""
        state = self._get_user_learning_state(context.user_id, context)

        # Use context builder for conversation awareness
        ctx_builder = ConversationContextBuilder(context)

        # Build progress summary prompt with history context
        progress_info = f"""
        Summarize the user's learning progress:
        - Current phase: {state.current_phase}
        - Strong areas: {state.strong_areas}
        - Areas to improve: {state.struggle_areas}
        - Days to milestone: {state.days_to_milestone}

        Provide a brief, encouraging summary with 1-2 actionable suggestions.
        """

        # Include conversation history for continuity
        messages = ctx_builder.build_messages(progress_info)
        enhanced_system = build_agent_system_prompt(
            "You are a supportive learning coach reviewing progress.",
            context,
        )

        response = await self._llm.complete_with_history(
            messages=messages,
            system_prompt=enhanced_system,
            temperature=0.7,
        )

        return AgentResponse(
            agent_type=self.agent_type,
            message=response.content,
            data={"action": "progress_reviewed"},
        )

    async def _handle_general(
        self,
        context: AgentContext,
        user_message: str,
    ) -> AgentResponse:
        """Handle general curriculum-related queries."""
        # Get shared learning context
        learning_ctx = context.additional_data.get("learning_context")

        # Get onboarding state FIRST so we can check completion status
        context_service = get_context_service()
        onboarding = await context_service.get_onboarding_state(
            context.user_id, "curriculum"
        )

        # Check if this looks like a topic/goal statement that needs onboarding
        message_lower = user_message.lower()
        is_topic_statement = (
            len(user_message.split()) <= 5 and  # Short message
            not any(kw in message_lower for kw in ["plan", "path", "next", "progress", "how", "what", "?"])
        )

        # CRITICAL FIX: Check if this is a continuation message (like "ok lets get started")
        # If so, don't treat it as a new topic that needs onboarding
        is_continuation = self._is_continuation_message(user_message)

        # Check if onboarding is needed - pass onboarding state for completion check
        needs_onboarding = self._needs_onboarding(learning_ctx, onboarding)

        # If it's a topic statement (like "Machine learning"), check for onboarding
        # But skip if it's a continuation message and onboarding is already complete
        if (is_topic_statement or needs_onboarding) and not (is_continuation and onboarding and onboarding.is_complete):
            # If onboarding is in progress, continue it
            if onboarding and not onboarding.is_complete:
                return await self._handle_onboarding(context, user_message, learning_ctx)

            # If no onboarding and this looks like a new topic, start onboarding
            # CRITICAL FIX: Don't restart onboarding for continuation messages
            if is_topic_statement and needs_onboarding and not is_continuation:
                # Set the topic as primary goal first
                if learning_ctx:
                    await context_service.set_primary_goal(context.user_id, user_message)
                    # Refresh context
                    learning_ctx = await context_service.get_context(context.user_id)

                return await self._handle_onboarding(context, user_message, learning_ctx)

        # Determine intent for non-onboarding queries
        if any(kw in message_lower for kw in ["plan", "path", "curriculum", "schedule"]):
            # Check if we need to gather info first - pass onboarding state
            if self._needs_onboarding(learning_ctx, onboarding):
                return await self._handle_onboarding(context, user_message, learning_ctx)
            return await self._handle_path_generation(context)
        elif any(kw in message_lower for kw in ["next", "what should", "recommend"]):
            return await self._handle_topic_recommendation(context)
        elif any(kw in message_lower for kw in ["progress", "how am i", "status"]):
            return await self._handle_progress_review(context)
        else:
            # Use ConversationContextBuilder for context-aware LLM calls
            ctx_builder = ConversationContextBuilder(context)

            # Build enhanced system prompt with what we already know
            enhanced_system = build_agent_system_prompt(self.system_prompt, context)

            # Build messages with conversation history
            messages = ctx_builder.build_messages(user_message)

            # Use complete_with_history for multi-turn awareness
            response = await self._llm.complete_with_history(
                messages=messages,
                system_prompt=enhanced_system,
                temperature=0.7,
            )

            return AgentResponse(
                agent_type=self.agent_type,
                message=response.content,
                data={"action": "general_guidance"},
            )

    def get_user_path(self, user_id: UUID) -> LearningPath | None:
        """Get user's current learning path."""
        path_id = self._user_paths.get(user_id)
        if path_id:
            return self._learning_paths.get(path_id)
        return None

    # ===================
    # Conversational Onboarding Flow
    # ===================

    def _needs_onboarding(
        self,
        learning_ctx: SharedLearningContext | None,
        onboarding_state: OnboardingState | None = None,
    ) -> bool:
        """Check if user needs onboarding before generating a curriculum.

        Onboarding is needed when we don't have enough info to create a path
        AND onboarding hasn't already been completed.

        Args:
            learning_ctx: The shared learning context with user data
            onboarding_state: The onboarding state tracking completion status

        Returns:
            True if onboarding is needed, False otherwise
        """
        # CRITICAL FIX: If onboarding was already completed, don't restart it
        if onboarding_state and onboarding_state.is_complete:
            return False

        if not learning_ctx:
            return True

        # If we have a complete learning path already, no need
        # Reduced threshold from 3 to 1 - any learning path means onboarding is done
        if learning_ctx.learning_path and len(learning_ctx.learning_path) >= 1:
            return False

        # Check if we have minimum required info
        has_goal = bool(learning_ctx.primary_goal)

        # FIXED: Check ALL relevant constraint fields, not just timeline/motivation
        constraints = learning_ctx.constraints or {}
        has_constraints = bool(
            constraints.get("timeline") or
            constraints.get("motivation") or
            constraints.get("programming_background") or
            constraints.get("math_background")
        )

        has_preferences = bool(learning_ctx.preferences.get("learning_style"))

        # Need onboarding if missing key info
        return not (has_goal and has_constraints and has_preferences)

    def _is_continuation_message(self, message: str) -> bool:
        """Check if message is a continuation/affirmation rather than a new topic.

        Continuation messages indicate the user wants to proceed with the current
        flow rather than start something new.

        Args:
            message: The user's message

        Returns:
            True if this is a continuation message, False if it's a potential new topic
        """
        message_lower = message.lower().strip()

        # Common continuation/affirmation patterns
        continuation_patterns = [
            "ok", "okay", "yes", "yeah", "yep", "sure", "go ahead",
            "let's go", "lets go", "let's start", "lets start",
            "let's get started", "lets get started",
            "let's begin", "lets begin", "start", "begin",
            "ready", "i'm ready", "im ready",
            "continue", "proceed", "next",
            "sounds good", "perfect", "great", "good",
            "do it", "go for it", "let's do it", "lets do it",
            "no lets get started", "no let's get started",
            "ok lets get started then", "ok let's get started then",
        ]

        # Check exact match or prefix match
        if message_lower in continuation_patterns:
            return True

        # Check if starts with common affirmation prefixes
        affirmation_prefixes = ["ok ", "yes ", "sure ", "no "]
        if any(message_lower.startswith(p) for p in affirmation_prefixes):
            # Check if what follows is also a continuation pattern
            for prefix in affirmation_prefixes:
                if message_lower.startswith(prefix):
                    remainder = message_lower[len(prefix):].strip()
                    if remainder in continuation_patterns or remainder.startswith("let"):
                        return True

        return False

    async def _handle_onboarding(
        self,
        context: AgentContext,
        user_message: str,
        learning_ctx: SharedLearningContext,
    ) -> AgentResponse:
        """Handle progressive onboarding flow - one question at a time.

        This creates a natural conversation where we ask one question,
        wait for the answer, then ask the next question.
        """
        context_service = get_context_service()

        # Get or create onboarding state
        onboarding = await context_service.get_onboarding_state(
            context.user_id, "curriculum"
        )

        if onboarding is None:
            # First time - start onboarding
            onboarding = OnboardingState(
                agent_type="curriculum",
                topic=learning_ctx.primary_goal or user_message,
            )

        # If there's a current question, process the user's answer
        if onboarding.current_question:
            await self._process_onboarding_answer(
                context.user_id,
                onboarding.current_question,
                user_message,
                learning_ctx,
            )
            onboarding.record_answer(onboarding.current_question, user_message)

        # Find the next unanswered question
        next_question = self._get_next_onboarding_question(onboarding)

        if next_question is None:
            # All questions answered - complete onboarding
            onboarding.is_complete = True
            await context_service.save_onboarding_state(context.user_id, onboarding)

            # Now generate the learning path with all collected info
            return await self._handle_path_generation(context)

        # Ask the next question
        topic = onboarding.topic or learning_ctx.primary_goal or "this topic"
        question_text = next_question["question"].format(topic=topic)

        # Add a brief acknowledgment if this isn't the first question
        if onboarding.current_question:
            acknowledgments = [
                "Got it!",
                "Thanks for sharing that!",
                "Perfect!",
                "Great, that helps!",
            ]
            import random
            ack = random.choice(acknowledgments)
            question_text = f"{ack} {question_text}"

        # Update state with next question
        onboarding.current_question = next_question["key"]
        await context_service.save_onboarding_state(context.user_id, onboarding)

        return AgentResponse(
            agent_type=self.agent_type,
            message=question_text,
            data={
                "onboarding_step": next_question["key"],
                "onboarding_progress": len(onboarding.answers_collected) + 1,
                "onboarding_total": len(CURRICULUM_ONBOARDING_QUESTIONS),
            },
        )

    def _get_next_onboarding_question(
        self,
        onboarding: OnboardingState,
    ) -> dict | None:
        """Get the next unanswered question in the onboarding flow."""
        for question in CURRICULUM_ONBOARDING_QUESTIONS:
            if not onboarding.is_question_answered(question["key"]):
                return question
        return None

    async def _process_onboarding_answer(
        self,
        user_id: UUID,
        question_key: str,
        answer: str,
        learning_ctx: SharedLearningContext,
    ) -> None:
        """Process and store an onboarding answer in the learning context."""
        context_service = get_context_service()

        # Find the question to get the context field
        question = next(
            (q for q in CURRICULUM_ONBOARDING_QUESTIONS if q["key"] == question_key),
            None
        )
        if not question:
            return

        context_field = question["context_field"]

        # Parse the field path (e.g., "constraints.motivation")
        if "." in context_field:
            parent, key = context_field.split(".", 1)

            if parent == "constraints":
                constraints = learning_ctx.constraints.copy()
                constraints[key] = answer
                await context_service.update_context(user_id, {"constraints": constraints})

            elif parent == "preferences":
                preferences = learning_ctx.preferences.copy()
                preferences[key] = answer
                await context_service.update_context(user_id, {"preferences": preferences})


# Factory function
_curriculum_agent: CurriculumAgent | None = None


def get_curriculum_agent() -> CurriculumAgent:
    """Get Curriculum agent singleton."""
    global _curriculum_agent
    if _curriculum_agent is None:
        _curriculum_agent = CurriculumAgent()
    return _curriculum_agent
