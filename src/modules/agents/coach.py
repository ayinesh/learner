"""Coach Agent - Learning motivation and session management."""

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from src.modules.agents.context_service import get_context_service
from src.modules.agents.interface import (
    AgentContext,
    AgentResponse,
    AgentType,
    BaseAgent,
    ICoachAgent,
    MenuOption,
)
from src.modules.agents.learning_context import OnboardingState
from src.modules.llm.service import LLMService, get_llm_service

logger = logging.getLogger(__name__)

# Conversational onboarding questions for the Coach agent
# Asked one at a time when setting goals
COACH_ONBOARDING_QUESTIONS = [
    {
        "key": "learning_topic",
        "question": "What would you like to learn?",
        "context_field": "primary_goal",
    },
    {
        "key": "motivation",
        "question": "That's a great choice! Why is learning {topic} important to you?",
        "context_field": "constraints.motivation",
    },
    {
        "key": "success_criteria",
        "question": "How will you know when you've succeeded? What does mastery of {topic} look like for you?",
        "context_field": "constraints.success_criteria",
    },
]


@dataclass
class SessionContext:
    """Context for a learning session."""

    user_name: str
    days_since_last: int
    current_streak: int
    longest_streak: int
    available_minutes: int
    session_type: str
    topics_preview: list[str]
    has_reviews: bool
    last_quiz_score: float | None
    last_feynman_score: float | None


@dataclass
class SessionSummary:
    """Summary of a completed session."""

    session_minutes: int
    topics_covered: list[str]
    activities_completed: list[str]
    quiz_results: dict[str, Any]
    feynman_score: float | None
    challenges: list[str]
    breakthroughs: list[str]
    topics_mastered: list[str]
    skills_practiced: list[str]
    goal_progress: float
    current_streak: int
    total_sessions: int
    next_session_time: str | None
    review_items_count: int
    next_topic: str | None
    upcoming_milestone: str | None


@dataclass
class RecoveryContext:
    """Context for recovery after missed sessions."""

    days_missed: int
    previous_streak: int
    longest_previous_gap: int
    last_session_topic: str
    topics_before_gap: list[str]
    last_quiz_score: float | None
    last_feynman_score: float | None
    proficiency_before_gap: dict[str, float]
    gap_reason: str | None
    available_minutes: int
    next_milestone: str
    days_to_milestone: int
    current_phase: str
    phase_progress: float
    planned_topics: list[str]


class CoachAgent(BaseAgent, ICoachAgent):
    """Agent responsible for learning motivation and session management.

    The coach provides personalized session openings, closings, and recovery
    plans to keep learners motivated and on track.
    """

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self._llm = llm_service or get_llm_service()

    @property
    def agent_type(self) -> AgentType:
        return AgentType.COACH

    @property
    def system_prompt(self) -> str:
        template = self._llm.load_prompt_template("coach/session_opening")
        return template.system

    async def respond(
        self,
        context: AgentContext,
        user_message: str,
    ) -> AgentResponse:
        """Generate a coaching response based on context.

        Determines what type of coaching is needed based on the user's
        situation and generates appropriate support.
        """
        # Analyze user message and context to determine coaching action
        action = await self._determine_coaching_action(context, user_message)

        if action == "session_opening":
            return await self._handle_session_opening(context)
        elif action == "session_closing":
            return await self._handle_session_closing(context)
        elif action == "recovery":
            return await self._handle_recovery(context)
        elif action == "goal_setting":
            return await self._handle_goal_onboarding(context, user_message)
        elif action == "motivation":
            return await self._handle_motivation(context, user_message)
        else:
            # General coaching response
            return await self._handle_general(context, user_message)

    async def generate_session_opening(
        self,
        user_id: UUID,
        session_context: dict,
    ) -> str:
        """Generate a personalized session opening message."""
        template = self._llm.load_prompt_template("coach/session_opening")

        # Build context from dict
        ctx = SessionContext(
            user_name=session_context.get("user_name", "there"),
            days_since_last=session_context.get("days_since_last", 0),
            current_streak=session_context.get("current_streak", 0),
            longest_streak=session_context.get("longest_streak", 0),
            available_minutes=session_context.get("available_minutes", 30),
            session_type=session_context.get("session_type", "learning"),
            topics_preview=session_context.get("topics_preview", []),
            has_reviews=session_context.get("has_reviews", False),
            last_quiz_score=session_context.get("last_quiz_score"),
            last_feynman_score=session_context.get("last_feynman_score"),
        )

        system_prompt, user_prompt = template.format(
            user_name=ctx.user_name,
            days_since_last=ctx.days_since_last,
            current_streak=ctx.current_streak,
            longest_streak=ctx.longest_streak,
            available_minutes=ctx.available_minutes,
            session_type=ctx.session_type,
            topics_preview=", ".join(ctx.topics_preview) if ctx.topics_preview else "continuing your learning path",
            has_reviews="yes" if ctx.has_reviews else "no",
            last_quiz_score=f"{ctx.last_quiz_score:.0%}" if ctx.last_quiz_score else "N/A",
            last_feynman_score=f"{ctx.last_feynman_score:.1f}/10" if ctx.last_feynman_score else "N/A",
        )

        response = await self._llm.complete(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.7,
        )

        return response.content

    async def generate_session_closing(
        self,
        session_summary: dict,
    ) -> str:
        """Generate a personalized session closing message."""
        template = self._llm.load_prompt_template("coach/session_closing")

        # Build summary from dict
        summary = SessionSummary(
            session_minutes=session_summary.get("session_minutes", 0),
            topics_covered=session_summary.get("topics_covered", []),
            activities_completed=session_summary.get("activities_completed", []),
            quiz_results=session_summary.get("quiz_results", {}),
            feynman_score=session_summary.get("feynman_score"),
            challenges=session_summary.get("challenges", []),
            breakthroughs=session_summary.get("breakthroughs", []),
            topics_mastered=session_summary.get("topics_mastered", []),
            skills_practiced=session_summary.get("skills_practiced", []),
            goal_progress=session_summary.get("goal_progress", 0),
            current_streak=session_summary.get("current_streak", 0),
            total_sessions=session_summary.get("total_sessions", 0),
            next_session_time=session_summary.get("next_session_time"),
            review_items_count=session_summary.get("review_items_count", 0),
            next_topic=session_summary.get("next_topic"),
            upcoming_milestone=session_summary.get("upcoming_milestone"),
        )

        # Format quiz results
        quiz_str = "No quizzes taken"
        if summary.quiz_results:
            correct = summary.quiz_results.get("correct", 0)
            total = summary.quiz_results.get("total", 0)
            if total > 0:
                quiz_str = f"{correct}/{total} correct ({correct/total:.0%})"

        system_prompt, user_prompt = template.format(
            session_minutes=summary.session_minutes,
            topics_covered=", ".join(summary.topics_covered) if summary.topics_covered else "general learning",
            activities_completed=", ".join(summary.activities_completed) if summary.activities_completed else "learning activities",
            quiz_results=quiz_str,
            feynman_score=f"{summary.feynman_score:.1f}/10" if summary.feynman_score else "N/A",
            challenges=", ".join(summary.challenges) if summary.challenges else "none noted",
            breakthroughs=", ".join(summary.breakthroughs) if summary.breakthroughs else "steady progress",
            topics_mastered=", ".join(summary.topics_mastered) if summary.topics_mastered else "none this session",
            skills_practiced=", ".join(summary.skills_practiced) if summary.skills_practiced else "various skills",
            goal_progress=f"{summary.goal_progress:.0%}",
            current_streak=summary.current_streak,
            total_sessions=summary.total_sessions,
            next_session_time=summary.next_session_time or "not scheduled",
            review_items_count=summary.review_items_count,
            next_topic=summary.next_topic or "to be determined",
            upcoming_milestone=summary.upcoming_milestone or "continuing progress",
        )

        response = await self._llm.complete(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.7,
        )

        return response.content

    async def generate_recovery_message(
        self,
        days_missed: int,
        recovery_plan: dict,
    ) -> str:
        """Generate a message for returning after missed days."""
        # Generate a friendly recovery message based on the plan
        welcome = recovery_plan.get("welcome_message", "Welcome back!")
        encouragement = recovery_plan.get("encouragement", "Let's get back on track.")

        immediate_action = recovery_plan.get("recovery_plan", {}).get("immediate_action", "")

        # Combine into a natural message
        message_parts = [welcome]
        if immediate_action:
            message_parts.append(f"Let's start with: {immediate_action}")
        message_parts.append(encouragement)

        return " ".join(message_parts)

    async def generate_recovery_plan(
        self,
        recovery_context: dict,
    ) -> dict[str, Any]:
        """Generate a comprehensive recovery plan for returning users."""
        template = self._llm.load_prompt_template("coach/recovery_plan")

        # Build context
        ctx = RecoveryContext(
            days_missed=recovery_context.get("days_missed", 1),
            previous_streak=recovery_context.get("previous_streak", 0),
            longest_previous_gap=recovery_context.get("longest_previous_gap", 0),
            last_session_topic=recovery_context.get("last_session_topic", "previous topic"),
            topics_before_gap=recovery_context.get("topics_before_gap", []),
            last_quiz_score=recovery_context.get("last_quiz_score"),
            last_feynman_score=recovery_context.get("last_feynman_score"),
            proficiency_before_gap=recovery_context.get("proficiency_before_gap", {}),
            gap_reason=recovery_context.get("gap_reason"),
            available_minutes=recovery_context.get("available_minutes", 30),
            next_milestone=recovery_context.get("next_milestone", "next goal"),
            days_to_milestone=recovery_context.get("days_to_milestone", 30),
            current_phase=recovery_context.get("current_phase", "learning"),
            phase_progress=recovery_context.get("phase_progress", 0),
            planned_topics=recovery_context.get("planned_topics", []),
        )

        # Format proficiency levels
        proficiency_str = "\n".join(
            f"- {topic}: {level:.0%}"
            for topic, level in ctx.proficiency_before_gap.items()
        ) or "No proficiency data"

        system_prompt, user_prompt = template.format(
            days_missed=ctx.days_missed,
            previous_streak=ctx.previous_streak,
            longest_previous_gap=ctx.longest_previous_gap,
            last_session_topic=ctx.last_session_topic,
            topics_before_gap=", ".join(ctx.topics_before_gap) if ctx.topics_before_gap else "various topics",
            last_quiz_score=f"{ctx.last_quiz_score:.0%}" if ctx.last_quiz_score else "N/A",
            last_feynman_score=f"{ctx.last_feynman_score:.1f}/10" if ctx.last_feynman_score else "N/A",
            proficiency_before_gap=proficiency_str,
            gap_reason=ctx.gap_reason or "not specified",
            available_minutes=ctx.available_minutes,
            next_milestone=ctx.next_milestone,
            days_to_milestone=ctx.days_to_milestone,
            current_phase=ctx.current_phase,
            phase_progress=f"{ctx.phase_progress:.0%}",
            planned_topics=", ".join(ctx.planned_topics) if ctx.planned_topics else "continuing learning path",
        )

        response = await self._llm.complete(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.5,
        )

        # Parse JSON response
        try:
            content = response.content.strip()
            if "```" in content:
                match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
                if match:
                    content = match.group(1)
            return json.loads(content)
        except (json.JSONDecodeError, ValueError):
            # Return a default plan
            return {
                "welcome_message": "Welcome back! Let's pick up where we left off.",
                "retention_assessment": {
                    "expected_retention": "medium",
                    "concerns": [],
                    "reasoning": "Based on the time away",
                },
                "recovery_plan": {
                    "immediate_action": "Quick review quiz",
                    "review_session": {
                        "needed": ctx.days_missed > 3,
                        "duration_minutes": min(15, ctx.available_minutes),
                        "topics_to_review": ctx.topics_before_gap[:3],
                        "format": "quiz",
                    },
                    "adjustment_period": {
                        "sessions": 1 if ctx.days_missed <= 7 else 2,
                        "difficulty_adjustment": "easier" if ctx.days_missed > 7 else "same",
                        "pace_adjustment": "slower" if ctx.days_missed > 14 else "same",
                    },
                },
                "today_session_plan": [
                    {
                        "activity": "Quick review",
                        "duration_minutes": 10,
                        "purpose": "Rebuild confidence",
                    }
                ],
                "timeline_impact": {
                    "milestone_still_achievable": ctx.days_missed <= 7,
                    "new_target_date": None,
                    "explanation": "Minor adjustment needed" if ctx.days_missed > 7 else "On track",
                },
                "encouragement": "Every expert was once a beginner who kept coming back. Let's continue!",
            }

    # ===================
    # Onboarding Flow Methods
    # ===================

    def _needs_goal_setting(self, learning_ctx) -> bool:
        """Check if user needs goal-setting conversation."""
        if not learning_ctx:
            return True
        # Need goal setting if no primary goal is set
        return learning_ctx.primary_goal is None

    def _get_next_onboarding_question(
        self,
        onboarding: OnboardingState,
    ) -> dict | None:
        """Get the next unanswered onboarding question."""
        for q in COACH_ONBOARDING_QUESTIONS:
            if not onboarding.is_question_answered(q["key"]):
                return q
        return None

    async def _process_onboarding_answer(
        self,
        user_id: UUID,
        question_key: str,
        answer: str,
        onboarding: OnboardingState,
    ) -> None:
        """Process and store an onboarding answer."""
        onboarding.record_answer(question_key, answer)

        # Get context service
        context_service = get_context_service()

        # Update learning context based on question type
        if question_key == "learning_topic":
            # Set as primary goal
            await context_service.set_primary_goal(user_id, answer)
            onboarding.topic = answer
        elif question_key == "motivation":
            # Store motivation in constraints
            context = await context_service.get_context(user_id)
            constraints = context.constraints.copy()
            constraints["motivation"] = answer
            await context_service.update_context(user_id, {"constraints": constraints})
        elif question_key == "success_criteria":
            # Store success criteria in constraints
            context = await context_service.get_context(user_id)
            constraints = context.constraints.copy()
            constraints["success_criteria"] = answer
            await context_service.update_context(user_id, {"constraints": constraints})

        # Save updated onboarding state
        await context_service.save_onboarding_state(user_id, onboarding)

    async def _handle_goal_onboarding(
        self,
        context: AgentContext,
        user_message: str,
    ) -> AgentResponse:
        """Handle progressive goal-setting flow - one question at a time."""
        context_service = get_context_service()

        # Get or create onboarding state
        onboarding = await context_service.get_onboarding_state(
            context.user_id, "coach"
        )

        if not onboarding:
            onboarding = OnboardingState(agent_type="coach")

        # If this is a response to a previous question, process it
        if onboarding.current_question and not onboarding.is_complete:
            await self._process_onboarding_answer(
                context.user_id,
                onboarding.current_question,
                user_message,
                onboarding,
            )

        # Find next unanswered question
        next_q = self._get_next_onboarding_question(onboarding)

        if next_q is None:
            # Onboarding complete - provide encouraging summary
            onboarding.is_complete = True
            await context_service.save_onboarding_state(context.user_id, onboarding)

            topic = onboarding.topic or "your goal"
            motivation = onboarding.answers_collected.get("motivation", "")
            success = onboarding.answers_collected.get("success_criteria", "")

            message = f"""I've recorded your learning goal!

**Topic:** {topic}
**Why:** {motivation}
**Success looks like:** {success}

You're all set! I'll help keep you motivated and on track. Would you like to:

1. **Build a learning path** - Get a personalized curriculum
2. **Start with practice** - Hands-on exercises right away
3. **Learn some concepts** - Read about the fundamentals first"""

            return AgentResponse(
                agent_type=self.agent_type,
                message=message,
                data={
                    "action": "goal_set",
                    "onboarding_complete": True,
                    "topic": topic,
                },
                suggested_next_agent=AgentType.CURRICULUM,
                menu_options=[
                    MenuOption("1", "Build a learning path", AgentType.CURRICULUM, "generate_path"),
                    MenuOption("2", "Start with practice", AgentType.DRILL_SERGEANT, "start_practice"),
                    MenuOption("3", "Learn some concepts", AgentType.SCOUT, "find_content"),
                ],
            )

        # Format the question (substitute topic if needed)
        topic = onboarding.topic or "this topic"
        question_text = next_q["question"].format(topic=topic)

        # Update state with current question
        onboarding.current_question = next_q["key"]
        await context_service.save_onboarding_state(context.user_id, onboarding)

        return AgentResponse(
            agent_type=self.agent_type,
            message=question_text,
            data={"onboarding_step": next_q["key"]},
        )

    async def _determine_coaching_action(
        self,
        context: AgentContext,
        user_message: str,
    ) -> str:
        """Determine what type of coaching action is needed."""
        # Check for explicit indicators
        additional = context.additional_data

        if additional.get("action") == "session_opening":
            return "session_opening"
        if additional.get("action") == "session_closing":
            return "session_closing"
        if additional.get("action") == "recovery":
            return "recovery"

        # Check if user needs goal-setting conversation
        learning_ctx = additional.get("learning_context")
        if self._needs_goal_setting(learning_ctx):
            return "goal_setting"

        # Check for ongoing goal-setting onboarding
        context_service = get_context_service()
        onboarding = await context_service.get_onboarding_state(
            context.user_id, "coach"
        )
        if onboarding and not onboarding.is_complete:
            return "goal_setting"

        # Check for days since last session
        days_since = additional.get("days_since_last_session", 0)
        if days_since > 3:
            return "recovery"

        # Check for motivation keywords
        motivation_keywords = [
            "struggling", "hard", "difficult", "frustrated",
            "can't", "give up", "tired", "overwhelmed",
        ]
        if any(kw in user_message.lower() for kw in motivation_keywords):
            return "motivation"

        return "general"

    async def _handle_session_opening(
        self,
        context: AgentContext,
    ) -> AgentResponse:
        """Handle session opening."""
        opening = await self.generate_session_opening(
            user_id=context.user_id,
            session_context=context.additional_data,
        )

        return AgentResponse(
            agent_type=self.agent_type,
            message=opening,
            data={"action": "session_opened"},
            suggested_next_agent=AgentType.CURRICULUM,
        )

    async def _handle_session_closing(
        self,
        context: AgentContext,
    ) -> AgentResponse:
        """Handle session closing."""
        closing = await self.generate_session_closing(
            session_summary=context.additional_data,
        )

        return AgentResponse(
            agent_type=self.agent_type,
            message=closing,
            data={"action": "session_closed"},
            end_conversation=True,
        )

    async def _handle_recovery(
        self,
        context: AgentContext,
    ) -> AgentResponse:
        """Handle recovery after missed sessions."""
        plan = await self.generate_recovery_plan(
            recovery_context=context.additional_data,
        )

        message = await self.generate_recovery_message(
            days_missed=context.additional_data.get("days_missed", 1),
            recovery_plan=plan,
        )

        return AgentResponse(
            agent_type=self.agent_type,
            message=message,
            data={
                "action": "recovery_planned",
                "recovery_plan": plan,
            },
            suggested_next_agent=AgentType.ASSESSMENT,
        )

    async def _handle_motivation(
        self,
        context: AgentContext,
        user_message: str,
    ) -> AgentResponse:
        """Handle motivation and encouragement with shared context awareness."""
        # Get shared learning context for personalized motivation
        learning_ctx = context.additional_data.get("learning_context")
        primary_goal = learning_ctx.primary_goal if learning_ctx else None
        current_focus = learning_ctx.current_focus if learning_ctx else None

        prompt = f"""
        The user is expressing difficulty or frustration with their learning:
        "{user_message}"

        User context:
        - Primary learning goal: {primary_goal or "Not set yet"}
        - Current focus area: {current_focus or "Not set yet"}
        - Current streak: {context.current_progress.get("streak", 0)} days
        - Recent progress: {context.current_progress.get("recent_progress", "unknown")}

        Generate a supportive, encouraging response that:
        1. Acknowledges their feelings
        2. Normalizes the struggle (learning is hard)
        3. Connects to their stated goal if they have one ("{primary_goal or 'their learning journey'}")
        4. Offers a concrete small step forward related to their current focus
        5. Reminds them of their progress

        Keep it brief (3-4 sentences) and genuine, not saccharine.
        """

        response = await self._llm.complete(
            prompt=prompt,
            system_prompt="You are a supportive learning coach. Be warm but not over-the-top.",
            temperature=0.7,
        )

        return AgentResponse(
            agent_type=self.agent_type,
            message=response.content,
            data={"action": "motivation_provided"},
        )

    async def _handle_general(
        self,
        context: AgentContext,
        user_message: str,
    ) -> AgentResponse:
        """Handle general coaching interactions with shared context awareness."""
        # Get shared learning context for personalized coaching
        learning_ctx = context.additional_data.get("learning_context")
        primary_goal = learning_ctx.primary_goal if learning_ctx else None
        current_focus = learning_ctx.current_focus if learning_ctx else None

        prompt = f"""
        The user says: "{user_message}"

        You are their learning coach. Respond helpfully based on:
        - Their primary goal: {primary_goal or "Not set yet - help them define one!"}
        - Current focus area: {current_focus or "Not set yet"}
        - Current streak: {context.current_progress.get("streak", 0)} days
        - Learning path: {context.current_progress.get("learning_path", [])}

        Important: If they mention a topic or goal, acknowledge it in the context of their overall learning journey.
        If they say "I want to learn X", recognize this as their goal.
        Be brief, supportive, and action-oriented.

        If offering choices, format them as numbered options like:
        1. **First option** - brief description
        2. **Second option** - brief description
        3. **Third option** - brief description
        """

        response = await self._llm.complete(
            prompt=prompt,
            system_prompt="You are a supportive learning coach. Keep responses brief and helpful.",
            temperature=0.7,
        )

        # Parse the response to detect numbered options and create menu_options
        menu_options = self._parse_numbered_options(response.content)

        return AgentResponse(
            agent_type=self.agent_type,
            message=response.content,
            data={"action": "general_coaching"},
            menu_options=menu_options if menu_options else None,
            # Default to CURRICULUM for learning-related general responses
            suggested_next_agent=AgentType.CURRICULUM if menu_options else None,
        )

    def _parse_numbered_options(self, message: str) -> list[MenuOption] | None:
        """Parse numbered options from an LLM response and create MenuOption list.

        Detects patterns like:
        1. **Option text** - description
        1. Option text
        """
        import re

        options = []

        for line in message.split("\n"):
            line = line.strip()
            if not line:
                continue

            # More flexible pattern to handle various LLM output formats:
            # - Handles leading/trailing whitespace (via strip above)
            # - Handles 0-2 asterisks for bold formatting
            # - Handles various dash types (hyphen, en-dash, em-dash) or colon as separator
            # - Makes description optional
            match = re.match(r'^(\d)\.\s+\*{0,2}(.+?)\*{0,2}(?:\s*[-–—:]\s*(.+))?$', line)
            if match:
                number = match.group(1)
                label = match.group(2).strip().replace("**", "").replace("*", "")
                # Map common keywords to agents
                agent = self._infer_agent_from_label(label)
                options.append(MenuOption(number, label, agent))
                logger.debug(f"Parsed menu option: {number} -> {label} -> {agent}")

        # Only return if we found 2-4 valid options
        if 2 <= len(options) <= 4:
            logger.debug(f"Successfully parsed {len(options)} menu options")
            return options

        logger.debug(f"Menu parsing found {len(options)} options (need 2-4), returning None")
        return None

    def _infer_agent_from_label(self, label: str) -> AgentType:
        """Infer the target agent from an option label."""
        label_lower = label.lower()

        if any(kw in label_lower for kw in ["learn", "understand", "concept", "what is", "ml is", "basics"]):
            return AgentType.CURRICULUM
        if any(kw in label_lower for kw in ["quiz", "test", "assess", "check"]):
            return AgentType.ASSESSMENT
        if any(kw in label_lower for kw in ["practice", "project", "hands-on", "exercise", "drill"]):
            return AgentType.DRILL_SERGEANT
        if any(kw in label_lower for kw in ["read", "article", "content", "material", "resource"]):
            return AgentType.SCOUT
        if any(kw in label_lower for kw in ["plan", "path", "curriculum", "schedule", "roadmap"]):
            return AgentType.CURRICULUM
        if any(kw in label_lower for kw in ["explain", "feynman", "teach"]):
            return AgentType.SOCRATIC
        if any(kw in label_lower for kw in ["setup", "environment", "install"]):
            return AgentType.SCOUT

        # Default to curriculum for learning-related options
        return AgentType.CURRICULUM


# Factory function
_coach_agent: CoachAgent | None = None


def get_coach_agent() -> CoachAgent:
    """Get Coach agent singleton."""
    global _coach_agent
    if _coach_agent is None:
        _coach_agent = CoachAgent()
    return _coach_agent
