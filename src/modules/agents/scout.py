"""Scout Agent - Content discovery, relevance scoring, and summarization."""

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
)
from src.modules.agents.context_builder import (
    ConversationContextBuilder,
    build_agent_system_prompt,
)
from src.modules.agents.handoff_generator import (
    create_action,
    create_discovery,
    create_handoff,
)
from src.modules.llm.service import LLMService, get_llm_service


@dataclass
class ContentItem:
    """A piece of content to evaluate."""

    id: UUID
    title: str
    source: str
    content_type: str  # tutorial, conceptual, research, tool, opinion, news
    summary: str
    topics: list[str]
    difficulty: str  # beginner, intermediate, advanced
    length_minutes: int
    full_text: str | None = None
    url: str | None = None


@dataclass
class RelevanceEvaluation:
    """Evaluation of content relevance."""

    content_id: UUID
    relevance_score: float  # 0-1
    timing_assessment: str  # too_early, perfect_timing, review, advanced, tangential
    recommended_action: str  # read_now, save_for_later, skim, skip, archive
    rationale: str
    goal_alignment: dict
    prerequisite_check: dict
    practical_value: dict
    when_to_consume: str
    estimated_time: int
    key_takeaways: list[str]
    evaluated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ContentSummary:
    """Summarized content for learning."""

    content_id: UUID
    headline: str
    core_insight: str
    key_concepts: list[dict]
    practical_application: dict
    prerequisites: dict
    technical_details: dict
    connections: dict
    full_summary: str
    follow_up_questions: list[str]
    time_saved: int
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class UserContentProfile:
    """User's content preferences and context."""

    user_id: UUID
    goals: list[str]
    current_phase: str
    current_topics: list[str]
    proficiency_levels: dict[str, float]
    identified_gaps: list[str]
    interests: list[str]
    available_time_weekly: int  # minutes
    backlog_size: int
    upcoming_milestones: list[str]
    priority_topics: list[str]


class ScoutAgent(BaseAgent):
    """Agent responsible for content discovery, evaluation, and summarization.

    The Scout filters the overwhelming volume of learning content to surface
    only what matters for a specific learner at their current stage. It
    evaluates relevance, timing, and practical value.
    """

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self._llm = llm_service or get_llm_service()
        self._evaluations: dict[UUID, RelevanceEvaluation] = {}
        self._summaries: dict[UUID, ContentSummary] = {}
        self._user_reading_lists: dict[UUID, list[UUID]] = {}  # user_id -> content_ids

    @property
    def agent_type(self) -> AgentType:
        return AgentType.SCOUT

    @property
    def system_prompt(self) -> str:
        template = self._llm.load_prompt_template("scout/content_relevance")
        return template.system

    async def respond(
        self,
        context: AgentContext,
        user_message: str,
    ) -> AgentResponse:
        """Generate scout-related response based on context."""
        action = context.additional_data.get("action", "evaluate")

        if action == "evaluate_content":
            return await self._handle_content_evaluation(context)
        elif action == "summarize_content":
            return await self._handle_summarization(context)
        elif action == "get_recommendations":
            return await self._handle_recommendations(context)
        elif action == "manage_reading_list":
            return await self._handle_reading_list(context)
        else:
            return await self._handle_general(context, user_message)

    async def evaluate_content(
        self,
        content: ContentItem,
        user_profile: UserContentProfile,
    ) -> RelevanceEvaluation:
        """Evaluate content relevance for a specific user.

        Args:
            content: Content to evaluate
            user_profile: User's learning context

        Returns:
            RelevanceEvaluation with scores and recommendations
        """
        template = self._llm.load_prompt_template("scout/content_relevance")

        # Format proficiencies
        proficiency_str = "\n".join(
            f"- {topic}: {level:.0%}"
            for topic, level in user_profile.proficiency_levels.items()
        ) or "No proficiency data"

        system_prompt, user_prompt = template.format(
            content_title=content.title,
            content_source=content.source,
            content_type=content.content_type,
            content_summary=content.summary,
            content_topics=", ".join(content.topics),
            content_difficulty=content.difficulty,
            content_length=f"{content.length_minutes} minutes",
            user_goals=", ".join(user_profile.goals),
            current_phase=user_profile.current_phase,
            current_topics=", ".join(user_profile.current_topics),
            user_proficiency=proficiency_str,
            user_gaps=", ".join(user_profile.identified_gaps) or "None identified",
            user_interests=", ".join(user_profile.interests),
            available_time=user_profile.available_time_weekly,
            backlog_size=user_profile.backlog_size,
            upcoming_milestones=", ".join(user_profile.upcoming_milestones) or "None",
            priority_topics=", ".join(user_profile.priority_topics),
        )

        response = await self._llm.complete(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.4,
        )

        eval_data = self._parse_evaluation(response.content)

        evaluation = RelevanceEvaluation(
            content_id=content.id,
            relevance_score=eval_data.get("relevance_score", 0.5),
            timing_assessment=eval_data.get("timing_assessment", "tangential"),
            recommended_action=eval_data.get("recommended_action", "skip"),
            rationale=eval_data.get("rationale", ""),
            goal_alignment=eval_data.get("goal_alignment", {}),
            prerequisite_check=eval_data.get("prerequisite_check", {}),
            practical_value=eval_data.get("practical_value", {}),
            when_to_consume=eval_data.get("when_to_consume", "later"),
            estimated_time=eval_data.get("estimated_time_investment", content.length_minutes),
            key_takeaways=eval_data.get("key_takeaways", []),
        )

        self._evaluations[content.id] = evaluation
        return evaluation

    async def summarize_content(
        self,
        content: ContentItem,
        user_context: dict,
    ) -> ContentSummary:
        """Create a learning-optimized summary of content.

        Args:
            content: Content to summarize
            user_context: User's learning context

        Returns:
            ContentSummary with key insights and takeaways
        """
        template = self._llm.load_prompt_template("scout/content_summarization")

        system_prompt, user_prompt = template.format(
            content_title=content.title,
            content_source=content.source,
            content_type=content.content_type,
            content_text=content.full_text or content.summary,
            user_level=user_context.get("level", "intermediate"),
            user_background=user_context.get("background", "General technical"),
            user_goals=", ".join(user_context.get("goals", [])),
            target_length=user_context.get("target_length", 200),
            focus_areas=", ".join(user_context.get("focus_areas", [])) or "General",
            include_code="yes" if user_context.get("include_code", True) else "no",
        )

        response = await self._llm.complete(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.5,
        )

        summary_data = self._parse_summary(response.content)

        summary = ContentSummary(
            content_id=content.id,
            headline=summary_data.get("headline", content.title),
            core_insight=summary_data.get("core_insight", content.summary),
            key_concepts=summary_data.get("key_concepts", []),
            practical_application=summary_data.get("practical_application", {}),
            prerequisites=summary_data.get("prerequisites", {}),
            technical_details=summary_data.get("technical_details", {}),
            connections=summary_data.get("connections", {}),
            full_summary=summary_data.get("full_summary", content.summary),
            follow_up_questions=summary_data.get("follow_up_questions", []),
            time_saved=summary_data.get("time_saved", 0),
        )

        self._summaries[content.id] = summary
        return summary

    async def batch_evaluate(
        self,
        contents: list[ContentItem],
        user_profile: UserContentProfile,
    ) -> list[RelevanceEvaluation]:
        """Evaluate multiple content items for relevance.

        Args:
            contents: List of content to evaluate
            user_profile: User's learning context

        Returns:
            List of evaluations sorted by relevance
        """
        evaluations = []
        for content in contents:
            evaluation = await self.evaluate_content(content, user_profile)
            evaluations.append(evaluation)

        # Sort by relevance score
        evaluations.sort(key=lambda e: e.relevance_score, reverse=True)
        return evaluations

    async def get_reading_recommendations(
        self,
        user_id: UUID,
        user_profile: UserContentProfile,
        available_time: int,
    ) -> list[dict]:
        """Get personalized reading recommendations.

        Args:
            user_id: User to recommend for
            user_profile: User's learning context
            available_time: Time available in minutes

        Returns:
            List of recommended content with rationale
        """
        # Get user's reading list
        reading_list = self._user_reading_lists.get(user_id, [])

        recommendations = []
        time_allocated = 0

        for content_id in reading_list:
            if time_allocated >= available_time:
                break

            evaluation = self._evaluations.get(content_id)
            if evaluation and evaluation.recommended_action in ["read_now", "skim"]:
                recommendations.append({
                    "content_id": str(content_id),
                    "action": evaluation.recommended_action,
                    "rationale": evaluation.rationale,
                    "estimated_time": evaluation.estimated_time,
                    "key_takeaways": evaluation.key_takeaways[:3],
                })
                time_allocated += evaluation.estimated_time

        return recommendations

    def add_to_reading_list(
        self,
        user_id: UUID,
        content_id: UUID,
    ) -> None:
        """Add content to user's reading list."""
        if user_id not in self._user_reading_lists:
            self._user_reading_lists[user_id] = []
        if content_id not in self._user_reading_lists[user_id]:
            self._user_reading_lists[user_id].append(content_id)

    def remove_from_reading_list(
        self,
        user_id: UUID,
        content_id: UUID,
    ) -> None:
        """Remove content from user's reading list."""
        if user_id in self._user_reading_lists:
            if content_id in self._user_reading_lists[user_id]:
                self._user_reading_lists[user_id].remove(content_id)

    def _parse_evaluation(self, content: str) -> dict:
        """Parse evaluation from LLM response."""
        try:
            if "```" in content:
                match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
                if match:
                    content = match.group(1)
            return json.loads(content)
        except (json.JSONDecodeError, ValueError):
            return {
                "relevance_score": 0.5,
                "timing_assessment": "tangential",
                "recommended_action": "save_for_later",
                "rationale": "Unable to evaluate fully",
            }

    def _parse_summary(self, content: str) -> dict:
        """Parse summary from LLM response."""
        try:
            if "```" in content:
                match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
                if match:
                    content = match.group(1)
            return json.loads(content)
        except (json.JSONDecodeError, ValueError):
            return {
                "headline": "Summary unavailable",
                "core_insight": "Unable to generate summary",
                "full_summary": content[:500],
            }

    async def _handle_content_evaluation(
        self,
        context: AgentContext,
    ) -> AgentResponse:
        """Handle content evaluation request."""
        content_data = context.additional_data.get("content", {})

        content = ContentItem(
            id=uuid4(),
            title=content_data.get("title", "Unknown"),
            source=content_data.get("source", "Unknown"),
            content_type=content_data.get("type", "conceptual"),
            summary=content_data.get("summary", ""),
            topics=content_data.get("topics", []),
            difficulty=content_data.get("difficulty", "intermediate"),
            length_minutes=content_data.get("length_minutes", 10),
        )

        # Get shared learning context for enriched user profile
        learning_ctx = context.additional_data.get("learning_context")

        # Build user profile from shared context + additional_data
        if learning_ctx:
            goals = [learning_ctx.primary_goal] if learning_ctx.primary_goal else []
            current_phase = "focused" if learning_ctx.current_focus else "learning"
            current_topics = [learning_ctx.current_focus] if learning_ctx.current_focus else []
            current_topics.extend(learning_ctx.recent_topics[:3] if learning_ctx.recent_topics else [])
            proficiency_levels = learning_ctx.proficiency_levels or {}
            identified_gaps = learning_ctx.identified_gaps or []
            constraints = learning_ctx.constraints or {}
            available_time = constraints.get("time_per_day", 30) * 7  # weekly
        else:
            goals = context.additional_data.get("goals", [])
            current_phase = context.additional_data.get("current_phase", "learning")
            current_topics = context.additional_data.get("current_topics", [])
            proficiency_levels = context.additional_data.get("proficiency_levels", {})
            identified_gaps = context.additional_data.get("identified_gaps", [])
            available_time = context.additional_data.get("available_time", 120)

        user_profile = UserContentProfile(
            user_id=context.user_id,
            goals=goals,
            current_phase=current_phase,
            current_topics=current_topics,
            proficiency_levels=proficiency_levels,
            identified_gaps=identified_gaps,
            interests=context.additional_data.get("interests", []),
            available_time_weekly=available_time,
            backlog_size=context.additional_data.get("backlog_size", 0),
            upcoming_milestones=context.additional_data.get("milestones", []),
            priority_topics=context.additional_data.get("priority_topics", []),
        )

        evaluation = await self.evaluate_content(content, user_profile)

        # Format response
        action_emoji = {
            "read_now": "📖",
            "save_for_later": "📌",
            "skim": "👀",
            "skip": "⏭️",
            "archive": "📦",
        }

        message = f"""**Content Evaluation: {content.title}**

**Relevance Score:** {evaluation.relevance_score:.0%}
**Recommendation:** {action_emoji.get(evaluation.recommended_action, '📄')} {evaluation.recommended_action.replace('_', ' ').title()}
**Timing:** {evaluation.timing_assessment.replace('_', ' ').title()}

**Why:** {evaluation.rationale}

**Key Takeaways:**
{chr(10).join(f"• {t}" for t in evaluation.key_takeaways[:3]) if evaluation.key_takeaways else "• To be discovered"}

**Estimated Time:** {evaluation.estimated_time} minutes"""

        # Determine suggested next agent based on action
        if evaluation.recommended_action == "read_now":
            suggested_next = AgentType.SOCRATIC  # Test understanding after reading
            suggested_steps = ["Read the content", "Then explain it back using Feynman technique"]
        elif evaluation.recommended_action == "skip":
            suggested_next = AgentType.SCOUT  # Find different content
            suggested_steps = ["Find alternative content"]
        else:
            suggested_next = AgentType.COACH
            suggested_steps = ["Continue learning session"]

        return AgentResponse(
            agent_type=self.agent_type,
            message=message,
            data={
                "action": "content_evaluated",
                "evaluation": {
                    "content_id": str(content.id),
                    "relevance_score": evaluation.relevance_score,
                    "recommended_action": evaluation.recommended_action,
                    "timing": evaluation.timing_assessment,
                },
            },
            handoff_context=create_handoff(
                from_agent=self.agent_type,
                summary=f"Evaluated content '{content.title}': {evaluation.relevance_score:.0%} relevant. "
                        f"Action: {evaluation.recommended_action.replace('_', ' ')}",
                outcomes={
                    "content_title": content.title,
                    "relevance_score": evaluation.relevance_score,
                    "recommended_action": evaluation.recommended_action,
                    "timing": evaluation.timing_assessment,
                },
                key_points=evaluation.key_takeaways[:3],
                topics_covered=content.topics[:3] if content.topics else [],
                suggested_next_steps=suggested_steps,
                suggested_next_agent=suggested_next,
            ),
            actions_taken=[
                create_action(
                    self.agent_type,
                    "evaluate_content",
                    {
                        "content_title": content.title,
                        "relevance_score": evaluation.relevance_score,
                        "action": evaluation.recommended_action,
                    },
                ),
            ],
        )

    async def _handle_summarization(
        self,
        context: AgentContext,
    ) -> AgentResponse:
        """Handle content summarization request."""
        content_data = context.additional_data.get("content", {})

        content = ContentItem(
            id=uuid4(),
            title=content_data.get("title", "Unknown"),
            source=content_data.get("source", "Unknown"),
            content_type=content_data.get("type", "conceptual"),
            summary=content_data.get("summary", ""),
            topics=content_data.get("topics", []),
            difficulty=content_data.get("difficulty", "intermediate"),
            length_minutes=content_data.get("length_minutes", 10),
            full_text=content_data.get("full_text"),
        )

        user_context = {
            "level": context.additional_data.get("user_level", "intermediate"),
            "background": context.additional_data.get("background", "Technical"),
            "goals": context.additional_data.get("goals", []),
            "target_length": context.additional_data.get("target_length", 200),
            "focus_areas": context.additional_data.get("focus_areas", []),
            "include_code": context.additional_data.get("include_code", True),
        }

        summary = await self.summarize_content(content, user_context)

        # Format response
        concepts_str = "\n".join(
            f"• **{c.get('concept', 'Concept')}**: {c.get('explanation', '')}"
            for c in summary.key_concepts[:3]
        ) if summary.key_concepts else "• See full content"

        message = f"""**{summary.headline}**

{summary.core_insight}

**Key Concepts:**
{concepts_str}

**Practical Application:** {summary.practical_application.get('how_to_apply', 'Apply as needed')}

**Follow-up Questions:**
{chr(10).join(f"• {q}" for q in summary.follow_up_questions[:2]) if summary.follow_up_questions else "• What else would you like to know?"}

*Time saved: ~{summary.time_saved} minutes*"""

        return AgentResponse(
            agent_type=self.agent_type,
            message=message,
            data={
                "action": "content_summarized",
                "summary": {
                    "content_id": str(content.id),
                    "headline": summary.headline,
                    "key_concepts": [c.get("concept") for c in summary.key_concepts],
                },
            },
        )

    async def _handle_recommendations(
        self,
        context: AgentContext,
    ) -> AgentResponse:
        """Handle reading recommendations request."""
        available_time = context.additional_data.get("available_time", 30)

        # Get shared learning context for enriched recommendations
        learning_ctx = context.additional_data.get("learning_context")

        if learning_ctx:
            goals = [learning_ctx.primary_goal] if learning_ctx.primary_goal else []
            current_phase = "focused" if learning_ctx.current_focus else "learning"
            current_topics = [learning_ctx.current_focus] if learning_ctx.current_focus else []
            current_topics.extend(learning_ctx.recent_topics[:3] if learning_ctx.recent_topics else [])
            proficiency_levels = learning_ctx.proficiency_levels or {}
            identified_gaps = learning_ctx.identified_gaps or []
            # Extract priority topics from learning path
            priority_topics = [
                stage.get("topic", "") for stage in (learning_ctx.learning_path or [])[:3]
                if stage.get("status") != "completed"
            ]
        else:
            goals = context.additional_data.get("goals", [])
            current_phase = context.additional_data.get("current_phase", "learning")
            current_topics = []
            proficiency_levels = {}
            identified_gaps = []
            priority_topics = []

        user_profile = UserContentProfile(
            user_id=context.user_id,
            goals=goals,
            current_phase=current_phase,
            current_topics=current_topics,
            proficiency_levels=proficiency_levels,
            identified_gaps=identified_gaps,
            interests=[],
            available_time_weekly=120,
            backlog_size=0,
            upcoming_milestones=[],
            priority_topics=priority_topics,
        )

        recommendations = await self.get_reading_recommendations(
            context.user_id,
            user_profile,
            available_time,
        )

        if recommendations:
            rec_str = "\n".join(
                f"• **{r.get('action', 'Read').title()}**: {r.get('rationale', 'Recommended')} ({r.get('estimated_time', '?')} min)"
                for r in recommendations[:5]
            )
            message = f"**Reading Recommendations** ({available_time} min available):\n\n{rec_str}"
        else:
            message = "No reading recommendations at this time. Would you like me to evaluate some content for you?"

        return AgentResponse(
            agent_type=self.agent_type,
            message=message,
            data={
                "action": "recommendations_provided",
                "recommendations": recommendations,
            },
        )

    async def _handle_reading_list(
        self,
        context: AgentContext,
    ) -> AgentResponse:
        """Handle reading list management."""
        list_action = context.additional_data.get("list_action", "view")
        content_id = context.additional_data.get("content_id")

        if list_action == "add" and content_id:
            self.add_to_reading_list(context.user_id, UUID(content_id))
            message = "Added to your reading list!"
        elif list_action == "remove" and content_id:
            self.remove_from_reading_list(context.user_id, UUID(content_id))
            message = "Removed from your reading list."
        else:
            reading_list = self._user_reading_lists.get(context.user_id, [])
            if reading_list:
                message = f"Your reading list has {len(reading_list)} items."
            else:
                message = "Your reading list is empty. I can help you discover relevant content!"

        return AgentResponse(
            agent_type=self.agent_type,
            message=message,
            data={"action": "reading_list_updated"},
        )

    async def _handle_general(
        self,
        context: AgentContext,
        user_message: str,
    ) -> AgentResponse:
        """Handle general scout queries with conversation awareness."""
        # Use context builder for conversation history awareness
        ctx_builder = ConversationContextBuilder(context)

        # Build enhanced system prompt with what we know
        enhanced_system = build_agent_system_prompt(self.system_prompt, context)

        # Build messages with full conversation history
        messages = ctx_builder.build_messages(user_message)

        response = await self._llm.complete_with_history(
            messages=messages,
            system_prompt=enhanced_system,
            temperature=0.7,
        )

        return AgentResponse(
            agent_type=self.agent_type,
            message=response.content,
            data={"action": "general_help"},
        )

    def get_evaluation(self, content_id: UUID) -> RelevanceEvaluation | None:
        """Get stored evaluation for content."""
        return self._evaluations.get(content_id)

    def get_summary(self, content_id: UUID) -> ContentSummary | None:
        """Get stored summary for content."""
        return self._summaries.get(content_id)


# Factory function
_scout_agent: ScoutAgent | None = None


def get_scout_agent() -> ScoutAgent:
    """Get Scout agent singleton."""
    global _scout_agent
    if _scout_agent is None:
        _scout_agent = ScoutAgent()
    return _scout_agent
