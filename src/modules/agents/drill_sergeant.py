"""Drill Sergeant Agent - Targeted practice and skill-building projects."""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from src.modules.agents.context_service import get_context_service
from src.modules.agents.interface import (
    AgentContext,
    AgentResponse,
    AgentType,
    BaseAgent,
)
from src.modules.agents.learning_context import OnboardingState
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

logger = logging.getLogger(__name__)

# Conversational onboarding questions for the Drill Sergeant
# Asked one at a time when creating practice sessions
DRILL_ONBOARDING_QUESTIONS = [
    {
        "key": "practice_topic",
        "question": "What topic would you like to practice?",
        "context_field": "current_focus",
    },
    {
        "key": "time_available",
        "question": "How much time do you have right now? (e.g., 5 min, 15 min, 30 min)",
        "context_field": "constraints.available_minutes",
    },
    {
        "key": "weak_areas",
        "question": "Any specific areas of {topic} that feel weak or confusing?",
        "context_field": "identified_gaps",
    },
]


@dataclass
class DrillExercise:
    """A single drill exercise."""

    exercise_number: int
    type: str  # flashcard, explain, scenario, code, compare
    difficulty: int  # 1-5
    prompt: str
    correct_answer: str
    common_mistakes: list[str]
    feedback_if_wrong: str
    feedback_if_correct: str
    time_limit_seconds: int | None = None


@dataclass
class TargetedDrill:
    """A targeted practice drill."""

    id: UUID
    title: str
    target_skill: str
    rationale: str
    exercises: list[DrillExercise]
    progression_rule: str
    mastery_criteria: str
    follow_up_plan: dict
    estimated_duration: int
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DrillResult:
    """Result of a completed drill."""

    drill_id: UUID
    user_id: UUID
    exercises_completed: int
    exercises_correct: int
    time_taken_seconds: int
    mastery_achieved: bool
    weak_points: list[str]
    completed_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ProjectPhase:
    """A phase of a skill-building project."""

    phase: int
    title: str
    estimated_hours: float
    objectives: list[str]
    tasks: list[dict]
    common_pitfalls: list[str]
    checkpoint_validation: str


@dataclass
class SkillProject:
    """A skill-building project."""

    id: UUID
    title: str
    difficulty_level: str
    estimated_hours: float
    skills_practiced: list[str]
    overview: dict
    requirements: dict
    phases: list[ProjectPhase]
    resources: dict
    checkpoints: list[dict]
    extensions: list[dict]
    reflection_questions: list[str]
    next_steps: str
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class WeaknessAnalysis:
    """Analysis of a user's weakness."""

    topic_name: str
    specific_gap: str
    gap_source: str  # quiz, feynman, both
    severity: float  # 0-1
    evidence: str
    current_proficiency: float
    related_proficiency: dict[str, float]
    recent_mistakes: list[str]
    error_pattern: str


class DrillSergeantAgent(BaseAgent):
    """Agent that designs targeted practice drills and skill-building projects.

    The Drill Sergeant zeros in on weaknesses and creates deliberate practice
    to close knowledge gaps. It doesn't waste time on what learners already
    know - it focuses on turning weaknesses into strengths.
    """

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self._llm = llm_service or get_llm_service()
        self._drills: dict[UUID, TargetedDrill] = {}
        self._projects: dict[UUID, SkillProject] = {}
        self._drill_results: dict[UUID, list[DrillResult]] = {}  # user_id -> results
        self._active_drills: dict[UUID, tuple[UUID, int]] = {}  # user_id -> (drill_id, current_exercise)

    @property
    def agent_type(self) -> AgentType:
        return AgentType.DRILL_SERGEANT

    @property
    def system_prompt(self) -> str:
        template = self._llm.load_prompt_template("drill_sergeant/targeted_practice")
        return template.system

    async def respond(
        self,
        context: AgentContext,
        user_message: str,
    ) -> AgentResponse:
        """Generate drill sergeant response based on context."""
        action = context.additional_data.get("action", "create_drill")

        # Check for ongoing onboarding
        context_service = get_context_service()
        onboarding = await context_service.get_onboarding_state(
            context.user_id, "drill_sergeant"
        )
        if onboarding and not onboarding.is_complete:
            return await self._handle_drill_onboarding(context, user_message)

        if action == "create_drill":
            # Check if we need onboarding first
            if self._needs_drill_onboarding(context):
                return await self._handle_drill_onboarding(context, user_message)
            return await self._handle_drill_creation(context)
        elif action == "create_project":
            return await self._handle_project_creation(context)
        elif action == "answer_exercise":
            return await self._handle_exercise_answer(context, user_message)
        elif action == "check_progress":
            return await self._handle_progress_check(context)
        else:
            return await self._handle_general(context, user_message)

    async def create_targeted_drill(
        self,
        weakness: WeaknessAnalysis,
        available_minutes: int = 15,
        energy_level: str = "medium",
        learning_style: str = "active",
    ) -> TargetedDrill:
        """Create a targeted practice drill for a specific weakness.

        Args:
            weakness: Analysis of the weakness to address
            available_minutes: Time available for the drill
            energy_level: User's current energy level
            learning_style: User's preferred learning style

        Returns:
            TargetedDrill with exercises to close the gap
        """
        template = self._llm.load_prompt_template("drill_sergeant/targeted_practice")

        # Format related proficiencies
        related_str = "\n".join(
            f"- {topic}: {level:.0%}"
            for topic, level in weakness.related_proficiency.items()
        ) or "No related data"

        system_prompt, user_prompt = template.format(
            topic_name=weakness.topic_name,
            specific_gap=weakness.specific_gap,
            gap_source=weakness.gap_source,
            severity=f"{weakness.severity:.0%}",
            evidence=weakness.evidence,
            current_proficiency=f"{weakness.current_proficiency:.0%}",
            related_proficiency=related_str,
            recent_mistakes=", ".join(weakness.recent_mistakes) or "None recorded",
            error_pattern=weakness.error_pattern or "No clear pattern",
            available_minutes=available_minutes,
            energy_level=energy_level,
            previous_attempts="0",
            learning_style=learning_style,
            target_proficiency="80%",
            mastery_threshold="3 correct in a row",
        )

        response = await self._llm.complete(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.6,
        )

        drill_data = self._parse_drill(response.content)

        # Convert to structured format
        exercises = []
        for ex in drill_data.get("exercises", []):
            exercise = DrillExercise(
                exercise_number=ex.get("exercise_number", len(exercises) + 1),
                type=ex.get("type", "explain"),
                difficulty=ex.get("difficulty", 3),
                prompt=ex.get("prompt", ""),
                correct_answer=ex.get("correct_answer", ""),
                common_mistakes=ex.get("common_mistakes", []),
                feedback_if_wrong=ex.get("feedback_if_wrong", "Try again!"),
                feedback_if_correct=ex.get("feedback_if_correct", "Correct!"),
                time_limit_seconds=ex.get("time_limit_seconds"),
            )
            if exercise.prompt:
                exercises.append(exercise)

        drill = TargetedDrill(
            id=uuid4(),
            title=drill_data.get("drill_title", f"Practice: {weakness.topic_name}"),
            target_skill=drill_data.get("target_skill", weakness.specific_gap),
            rationale=drill_data.get("rationale", ""),
            exercises=exercises,
            progression_rule=drill_data.get("progression_rule", "3 correct in a row"),
            mastery_criteria=drill_data.get("mastery_criteria", "80% accuracy"),
            follow_up_plan=drill_data.get("follow_up_plan", {}),
            estimated_duration=drill_data.get("estimated_duration", available_minutes),
        )

        self._drills[drill.id] = drill
        return drill

    async def create_skill_project(
        self,
        user_context: dict,
        project_constraints: dict,
    ) -> SkillProject:
        """Create a skill-building project.

        Args:
            user_context: User's learning context
            project_constraints: Time, skill level, preferences

        Returns:
            SkillProject with phases and checkpoints
        """
        template = self._llm.load_prompt_template("drill_sergeant/skill_building_project")

        # Format proficiency levels
        proficiency_str = "\n".join(
            f"- {topic}: {level:.0%}"
            for topic, level in user_context.get("proficiency_levels", {}).items()
        ) or "No proficiency data"

        system_prompt, user_prompt = template.format(
            recent_topics=", ".join(user_context.get("recent_topics", [])),
            proficiency_levels=proficiency_str,
            knowledge_gaps=", ".join(user_context.get("knowledge_gaps", [])) or "None identified",
            learning_goals=", ".join(user_context.get("learning_goals", [])),
            available_hours=project_constraints.get("available_hours", 4),
            skill_level=project_constraints.get("skill_level", "intermediate"),
            project_type_preference=project_constraints.get("project_type", "implementation"),
            available_resources=project_constraints.get("resources", "Standard development environment"),
            primary_skills=", ".join(project_constraints.get("primary_skills", [])),
            supporting_skills=", ".join(project_constraints.get("supporting_skills", [])) or "N/A",
            integration_goals=project_constraints.get("integration_goals", "Apply recent learning"),
            previous_projects=", ".join(user_context.get("previous_projects", [])) or "None",
            current_phase=user_context.get("current_phase", "Learning"),
            next_milestone=user_context.get("next_milestone", "Continue progress"),
        )

        response = await self._llm.complete(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.7,
        )

        project_data = self._parse_project(response.content)

        # Convert phases
        phases = []
        for p in project_data.get("phases", []):
            phase = ProjectPhase(
                phase=p.get("phase", len(phases) + 1),
                title=p.get("title", f"Phase {len(phases) + 1}"),
                estimated_hours=p.get("estimated_hours", 1),
                objectives=p.get("objectives", []),
                tasks=p.get("tasks", []),
                common_pitfalls=p.get("common_pitfalls", []),
                checkpoint_validation=p.get("checkpoint_validation", ""),
            )
            phases.append(phase)

        project = SkillProject(
            id=uuid4(),
            title=project_data.get("project_title", "Skill Building Project"),
            difficulty_level=project_data.get("difficulty_level", "intermediate"),
            estimated_hours=project_data.get("estimated_hours", 4),
            skills_practiced=project_data.get("skills_practiced", []),
            overview=project_data.get("overview", {}),
            requirements=project_data.get("requirements", {}),
            phases=phases,
            resources=project_data.get("resources", {}),
            checkpoints=project_data.get("checkpoints", []),
            extensions=project_data.get("extensions", []),
            reflection_questions=project_data.get("reflection_questions", []),
            next_steps=project_data.get("next_steps", ""),
        )

        self._projects[project.id] = project
        return project

    async def evaluate_exercise_answer(
        self,
        drill_id: UUID,
        exercise_number: int,
        user_answer: str,
    ) -> tuple[bool, str, str]:
        """Evaluate user's answer to a drill exercise.

        Returns:
            (is_correct, feedback, next_action)
        """
        drill = self._drills.get(drill_id)
        if not drill:
            return False, "Drill not found", "restart"

        # Find the exercise
        exercise = None
        for ex in drill.exercises:
            if ex.exercise_number == exercise_number:
                exercise = ex
                break

        if not exercise:
            return False, "Exercise not found", "restart"

        # Use LLM to evaluate answer
        eval_prompt = f"""
        Evaluate this drill answer.

        Exercise Type: {exercise.type}
        Prompt: {exercise.prompt}
        Expected Answer: {exercise.correct_answer}
        User's Answer: {user_answer}
        Common Mistakes: {exercise.common_mistakes}

        Determine if the answer is correct (allowing for reasonable variations).
        Return JSON:
        {{
            "is_correct": true/false,
            "explanation": "why correct or incorrect",
            "specific_issue": "if wrong, what specifically was wrong"
        }}
        """

        response = await self._llm.complete(
            prompt=eval_prompt,
            system_prompt="You are evaluating a drill answer. Be fair but strict.",
            temperature=0.2,
        )

        try:
            content = response.content.strip()
            if "```" in content:
                match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
                if match:
                    content = match.group(1)
            result = json.loads(content)

            is_correct = result.get("is_correct", False)
            if is_correct:
                feedback = exercise.feedback_if_correct
                next_action = "next"
            else:
                feedback = f"{exercise.feedback_if_wrong}\n{result.get('explanation', '')}"
                next_action = "retry"

            return is_correct, feedback, next_action

        except (json.JSONDecodeError, ValueError):
            # Simple comparison fallback
            is_correct = user_answer.lower().strip() in exercise.correct_answer.lower()
            feedback = exercise.feedback_if_correct if is_correct else exercise.feedback_if_wrong
            return is_correct, feedback, "next" if is_correct else "retry"

    def start_drill(self, user_id: UUID, drill_id: UUID) -> DrillExercise | None:
        """Start a drill for a user, returning the first exercise."""
        drill = self._drills.get(drill_id)
        if not drill or not drill.exercises:
            return None

        self._active_drills[user_id] = (drill_id, 0)
        return drill.exercises[0]

    def get_next_exercise(self, user_id: UUID) -> DrillExercise | None:
        """Get the next exercise in the user's active drill."""
        if user_id not in self._active_drills:
            return None

        drill_id, current_idx = self._active_drills[user_id]
        drill = self._drills.get(drill_id)

        if not drill:
            return None

        next_idx = current_idx + 1
        if next_idx >= len(drill.exercises):
            return None  # Drill complete

        self._active_drills[user_id] = (drill_id, next_idx)
        return drill.exercises[next_idx]

    def _parse_drill(self, content: str) -> dict:
        """Parse drill from LLM response."""
        try:
            if "```" in content:
                match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
                if match:
                    content = match.group(1)
            return json.loads(content)
        except (json.JSONDecodeError, ValueError):
            return {
                "drill_title": "Practice Drill",
                "target_skill": "General",
                "exercises": [],
            }

    def _parse_project(self, content: str) -> dict:
        """Parse project from LLM response."""
        try:
            if "```" in content:
                match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
                if match:
                    content = match.group(1)
            return json.loads(content)
        except (json.JSONDecodeError, ValueError):
            return {
                "project_title": "Skill Building Project",
                "phases": [],
            }

    # ===================
    # Onboarding Flow Methods
    # ===================

    def _needs_drill_onboarding(self, context: AgentContext) -> bool:
        """Check if user needs drill setup conversation."""
        additional = context.additional_data
        # Need onboarding if no topic specified and no active drill
        if context.user_id in self._active_drills:
            return False
        # Skip onboarding if topic is already provided
        if additional.get("topic_name"):
            return False
        return True

    def _get_next_onboarding_question(
        self,
        onboarding: OnboardingState,
    ) -> dict | None:
        """Get the next unanswered onboarding question."""
        for q in DRILL_ONBOARDING_QUESTIONS:
            if not onboarding.is_question_answered(q["key"]):
                return q
        return None

    def _parse_time_to_minutes(self, time_str: str) -> int:
        """Parse time string to minutes."""
        time_str = time_str.lower().strip()
        # Try to extract numbers
        import re
        numbers = re.findall(r"\d+", time_str)
        if numbers:
            mins = int(numbers[0])
            # If they said "hour" or "hr", multiply
            if "hour" in time_str or "hr" in time_str:
                mins *= 60
            return mins
        # Default to 15 minutes
        return 15

    async def _process_onboarding_answer(
        self,
        user_id: UUID,
        question_key: str,
        answer: str,
        onboarding: OnboardingState,
    ) -> None:
        """Process and store an onboarding answer."""
        onboarding.record_answer(question_key, answer)

        context_service = get_context_service()

        if question_key == "practice_topic":
            onboarding.topic = answer
            # Update current focus in learning context
            await context_service.update_current_focus(user_id, answer)
        elif question_key == "time_available":
            # Parse and store time
            minutes = self._parse_time_to_minutes(answer)
            context = await context_service.get_context(user_id)
            constraints = context.constraints.copy()
            constraints["available_minutes"] = minutes
            await context_service.update_context(user_id, {"constraints": constraints})
        elif question_key == "weak_areas":
            # Record as identified gap if specified
            if answer.lower() not in ["no", "none", "not sure", "nothing specific"]:
                await context_service.record_gap(user_id, answer)

        # Save onboarding state
        await context_service.save_onboarding_state(user_id, onboarding)

    async def _handle_drill_onboarding(
        self,
        context: AgentContext,
        user_message: str,
    ) -> AgentResponse:
        """Handle progressive drill setup - one question at a time."""
        context_service = get_context_service()

        # Get or create onboarding state
        onboarding = await context_service.get_onboarding_state(
            context.user_id, "drill_sergeant"
        )

        if not onboarding:
            onboarding = OnboardingState(agent_type="drill_sergeant")

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
            # Onboarding complete - create the drill
            onboarding.is_complete = True
            await context_service.save_onboarding_state(context.user_id, onboarding)

            # Build context from collected answers
            topic = onboarding.topic or "general"
            time_str = onboarding.answers_collected.get("time_available", "15 min")
            weak_areas = onboarding.answers_collected.get("weak_areas", "")

            # Update context with drill parameters
            context.additional_data["topic_name"] = topic
            context.additional_data["available_minutes"] = self._parse_time_to_minutes(time_str)
            if weak_areas and weak_areas.lower() not in ["no", "none", "not sure"]:
                context.additional_data["specific_gap"] = weak_areas

            # Clear onboarding state for next time
            await context_service.clear_onboarding_state(context.user_id, "drill_sergeant")

            # Now create the drill
            return await self._handle_drill_creation(context)

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

    async def _handle_drill_creation(
        self,
        context: AgentContext,
    ) -> AgentResponse:
        """Handle drill creation request."""
        additional = context.additional_data

        # Get shared learning context for enriched weakness analysis
        learning_ctx = additional.get("learning_context")

        # Build weakness analysis from shared context + additional_data
        if learning_ctx:
            # Use identified gaps from shared context if no specific gap provided
            identified_gaps = learning_ctx.identified_gaps or []
            topic_name = additional.get("topic_name") or (
                learning_ctx.current_focus or
                (identified_gaps[0] if identified_gaps else "General")
            )
            specific_gap = additional.get("specific_gap") or (
                identified_gaps[0] if identified_gaps else "Understanding"
            )
            proficiency_levels = learning_ctx.proficiency_levels or {}
            current_proficiency = proficiency_levels.get(topic_name, 0.5)
            # Get related proficiencies from shared context
            related_proficiency = {
                k: v for k, v in proficiency_levels.items()
                if k != topic_name
            }
        else:
            topic_name = additional.get("topic_name", "General")
            specific_gap = additional.get("specific_gap", "Understanding")
            current_proficiency = additional.get("current_proficiency", 0.5)
            related_proficiency = additional.get("related_proficiency", {})

        weakness = WeaknessAnalysis(
            topic_name=topic_name,
            specific_gap=specific_gap,
            gap_source=additional.get("gap_source", "quiz"),
            severity=additional.get("severity", 0.5),
            evidence=additional.get("evidence", "Recent assessment"),
            current_proficiency=current_proficiency,
            related_proficiency=related_proficiency,
            recent_mistakes=additional.get("recent_mistakes", []),
            error_pattern=additional.get("error_pattern", ""),
        )

        drill = await self.create_targeted_drill(
            weakness=weakness,
            available_minutes=additional.get("available_minutes", 15),
            energy_level=additional.get("energy_level", "medium"),
        )

        # Start the drill
        first_exercise = self.start_drill(context.user_id, drill.id)

        if first_exercise:
            message = f"""**Drill: {drill.title}**

*Target: {drill.target_skill}*
*{len(drill.exercises)} exercises • ~{drill.estimated_duration} min*

{drill.rationale}

---

**Exercise 1/{len(drill.exercises)}** (Difficulty: {'⭐' * first_exercise.difficulty})

{first_exercise.prompt}"""

            if first_exercise.time_limit_seconds:
                message += f"\n\n*Time limit: {first_exercise.time_limit_seconds} seconds*"

        else:
            message = "Unable to create drill. Please try again."

        return AgentResponse(
            agent_type=self.agent_type,
            message=message,
            data={
                "action": "drill_started",
                "drill_id": str(drill.id),
                "total_exercises": len(drill.exercises),
                "current_exercise": 1,
            },
        )

    async def _handle_project_creation(
        self,
        context: AgentContext,
    ) -> AgentResponse:
        """Handle project creation request."""
        additional = context.additional_data

        # Get shared learning context for enriched project creation
        learning_ctx = additional.get("learning_context")

        if learning_ctx:
            user_context = {
                "recent_topics": learning_ctx.recent_topics or [],
                "proficiency_levels": learning_ctx.proficiency_levels or {},
                "knowledge_gaps": learning_ctx.identified_gaps or [],
                "learning_goals": [learning_ctx.primary_goal] if learning_ctx.primary_goal else [],
                "previous_projects": additional.get("previous_projects", []),
                "current_phase": learning_ctx.current_focus or "Learning",
                "next_milestone": self._get_next_milestone(learning_ctx),
            }
        else:
            user_context = {
                "recent_topics": additional.get("recent_topics", []),
                "proficiency_levels": additional.get("proficiency_levels", {}),
                "knowledge_gaps": additional.get("knowledge_gaps", []),
                "learning_goals": additional.get("learning_goals", []),
                "previous_projects": additional.get("previous_projects", []),
                "current_phase": additional.get("current_phase", "Learning"),
                "next_milestone": additional.get("next_milestone", "Continue"),
            }

        project_constraints = {
            "available_hours": additional.get("available_hours", 4),
            "skill_level": additional.get("skill_level", "intermediate"),
            "project_type": additional.get("project_type", "implementation"),
            "resources": additional.get("resources", "Standard tools"),
            "primary_skills": additional.get("primary_skills", []),
            "supporting_skills": additional.get("supporting_skills", []),
            "integration_goals": additional.get("integration_goals", ""),
        }

        project = await self.create_skill_project(user_context, project_constraints)

        # Format project overview
        phases_preview = "\n".join(
            f"  {p.phase}. {p.title} ({p.estimated_hours}h)"
            for p in project.phases[:3]
        )

        message = f"""**Project: {project.title}**

*{project.difficulty_level.title()} • {project.estimated_hours} hours*

**Overview:**
{project.overview.get('context', '')}

**Objective:** {project.overview.get('objective', '')}

**Phases:**
{phases_preview}

**Skills You'll Practice:**
{chr(10).join(f"• {s}" for s in project.skills_practiced[:5])}

Ready to start? I'll guide you through each phase with checkpoints along the way."""

        return AgentResponse(
            agent_type=self.agent_type,
            message=message,
            data={
                "action": "project_created",
                "project_id": str(project.id),
                "project": {
                    "title": project.title,
                    "phases": len(project.phases),
                    "estimated_hours": project.estimated_hours,
                },
            },
            suggested_next_agent=AgentType.COACH,
        )

    async def _handle_exercise_answer(
        self,
        context: AgentContext,
        user_answer: str,
    ) -> AgentResponse:
        """Handle user's answer to a drill exercise."""
        if context.user_id not in self._active_drills:
            return AgentResponse(
                agent_type=self.agent_type,
                message="No active drill. Would you like to start one?",
                data={"action": "no_drill"},
            )

        drill_id, current_idx = self._active_drills[context.user_id]
        drill = self._drills.get(drill_id)

        if not drill:
            return AgentResponse(
                agent_type=self.agent_type,
                message="Drill not found. Starting a new one...",
                data={"action": "drill_not_found"},
            )

        current_exercise = drill.exercises[current_idx]
        is_correct, feedback, next_action = await self.evaluate_exercise_answer(
            drill_id=drill_id,
            exercise_number=current_exercise.exercise_number,
            user_answer=user_answer,
        )

        if is_correct:
            # Move to next exercise
            next_exercise = self.get_next_exercise(context.user_id)

            if next_exercise:
                message = f"""✓ **Correct!** {feedback}

---

**Exercise {next_exercise.exercise_number}/{len(drill.exercises)}** (Difficulty: {'⭐' * next_exercise.difficulty})

{next_exercise.prompt}"""

                return AgentResponse(
                    agent_type=self.agent_type,
                    message=message,
                    data={
                        "action": "exercise_correct",
                        "current_exercise": next_exercise.exercise_number,
                    },
                )
            else:
                # Drill complete - calculate results
                exercises_completed = len(drill.exercises)
                exercises_correct = context.additional_data.get("correct_count", exercises_completed)
                score = exercises_correct / exercises_completed if exercises_completed > 0 else 0
                weak_points = context.additional_data.get("weak_points", [])

                del self._active_drills[context.user_id]
                message = f"""✓ **Correct!** {feedback}

---

**Drill Complete!**

You've completed all {exercises_completed} exercises in "{drill.title}".

{drill.follow_up_plan.get('integration_practice', 'Keep practicing this skill in real contexts!')}"""

                # Determine next agent based on performance
                if score >= 0.8:
                    suggested_next = AgentType.ASSESSMENT  # Ready for quiz
                    suggested_steps = ["Test knowledge with a quiz", "Move to next topic"]
                elif weak_points:
                    suggested_next = AgentType.DRILL_SERGEANT  # More practice
                    suggested_steps = [f"Practice more on: {', '.join(weak_points[:3])}"]
                else:
                    suggested_next = AgentType.COACH
                    suggested_steps = ["Review session progress"]

                return AgentResponse(
                    agent_type=self.agent_type,
                    message=message,
                    data={
                        "action": "drill_complete",
                        "drill_id": str(drill_id),
                    },
                    suggested_next_agent=suggested_next,
                    handoff_context=create_handoff(
                        from_agent=self.agent_type,
                        summary=f"Completed drill '{drill.title}': {exercises_correct}/{exercises_completed} ({score:.0%})",
                        outcomes={
                            "drill_score": score,
                            "correct": exercises_correct,
                            "total": exercises_completed,
                            "target_skill": drill.target_skill,
                        },
                        gaps_identified=weak_points,
                        proficiency_observations={drill.target_skill: score},
                        topics_covered=[drill.target_skill],
                        suggested_next_steps=suggested_steps,
                        suggested_next_agent=suggested_next,
                    ),
                    actions_taken=[
                        create_action(
                            self.agent_type,
                            "complete_drill",
                            {
                                "drill_title": drill.title,
                                "target_skill": drill.target_skill,
                                "score": score,
                                "exercises_completed": exercises_completed,
                            },
                        ),
                    ],
                    discoveries=create_discovery(
                        needs_support=weak_points,
                        approach_results=[
                            {
                                "approach": "targeted drill practice",
                                "worked": score >= 0.7,
                                "topic": drill.target_skill,
                                "discovered_by": self.agent_type.value,
                            }
                        ],
                    ) if weak_points or score >= 0.7 else None,
                )
        else:
            # Wrong answer - retry
            message = f"""✗ **Not quite.** {feedback}

The expected answer was: {current_exercise.correct_answer}

**Try again or type 'skip' to move on:**

{current_exercise.prompt}"""

            return AgentResponse(
                agent_type=self.agent_type,
                message=message,
                data={
                    "action": "exercise_incorrect",
                    "current_exercise": current_exercise.exercise_number,
                },
            )

    async def _handle_progress_check(
        self,
        context: AgentContext,
    ) -> AgentResponse:
        """Handle progress check request."""
        results = self._drill_results.get(context.user_id, [])

        if results:
            recent = results[-5:]
            total_exercises = sum(r.exercises_completed for r in recent)
            total_correct = sum(r.exercises_correct for r in recent)
            accuracy = total_correct / total_exercises if total_exercises > 0 else 0

            message = f"""**Your Drill Progress**

Recent drills: {len(recent)}
Total exercises: {total_exercises}
Accuracy: {accuracy:.0%}

{'Keep up the good work!' if accuracy >= 0.7 else "Keep practicing - you're improving!"}"""
        else:
            message = "No drill history yet. Ready to start your first targeted practice session?"

        return AgentResponse(
            agent_type=self.agent_type,
            message=message,
            data={"action": "progress_checked"},
        )

    async def _handle_general(
        self,
        context: AgentContext,
        user_message: str,
    ) -> AgentResponse:
        """Handle general drill sergeant queries."""
        message_lower = user_message.lower()

        if any(kw in message_lower for kw in ["project", "build", "hands-on"]):
            context.additional_data["action"] = "create_project"
            return await self._handle_project_creation(context)
        elif any(kw in message_lower for kw in ["drill", "practice", "exercise"]):
            context.additional_data["action"] = "create_drill"
            return await self._handle_drill_creation(context)
        else:
            # Use context builder for conversation history awareness
            ctx_builder = ConversationContextBuilder(context)

            # Build enhanced system prompt with drill sergeant instructions
            drill_instructions = """
            Be direct and no-nonsense (drill sergeant style).
            Focus on their weaknesses and what will help them reach their goal.
            Don't repeat questions that have already been answered.
            """
            enhanced_system = build_agent_system_prompt(
                f"{self.system_prompt}\n\n{drill_instructions}",
                context,
            )

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

    def get_drill(self, drill_id: UUID) -> TargetedDrill | None:
        """Get a drill by ID."""
        return self._drills.get(drill_id)

    def get_project(self, project_id: UUID) -> SkillProject | None:
        """Get a project by ID."""
        return self._projects.get(project_id)

    def _get_next_milestone(self, learning_ctx) -> str:
        """Extract next milestone from learning context."""
        if not learning_ctx or not learning_ctx.learning_path:
            return "Continue progress"

        # Find the first incomplete stage in learning path
        for stage in learning_ctx.learning_path:
            if isinstance(stage, dict) and stage.get("status") != "completed":
                return f"Complete: {stage.get('topic', 'current topic')}"

        return "All milestones complete"


# Factory function
_drill_sergeant_agent: DrillSergeantAgent | None = None


def get_drill_sergeant_agent() -> DrillSergeantAgent:
    """Get Drill Sergeant agent singleton."""
    global _drill_sergeant_agent
    if _drill_sergeant_agent is None:
        _drill_sergeant_agent = DrillSergeantAgent()
    return _drill_sergeant_agent
