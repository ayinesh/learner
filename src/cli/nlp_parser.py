"""NLP Command Parser - Natural language to CLI command translation.

This module provides secure natural language parsing for CLI commands,
translating user intent into executable command functions.

Security measures:
- Input sanitization with max length and pattern blocking
- Static command registry (no dynamic eval/exec)
- Confirmation required for destructive actions
- Prompt injection protection via strict LLM prompts
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from src.shared.exceptions import (
    AmbiguousCommandError,
    CommandNotFoundError,
    NLPParseError,
    ValidationError,
)
from src.shared.models import SessionType

logger = logging.getLogger(__name__)


@dataclass
class CommandIntent:
    """Parsed command intent with execution details.

    Attributes:
        command: Canonical command identifier (e.g., "learn.start")
        description: Human-readable description of what will happen
        params: Validated parameters extracted from natural language
        needs_confirmation: Whether user must confirm before execution
        command_signature: Equivalent CLI command string
        execute: Callable that performs the actual command
    """
    command: str
    description: str
    params: dict[str, Any]
    needs_confirmation: bool
    command_signature: str
    execute: Callable[[], dict[str, Any]]


@dataclass
class CommandResult:
    """Result from executing a command."""
    success: bool = True
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)


class NLPCommandParser:
    """Parses natural language into structured command intents.

    This parser translates free-form user input into executable CLI
    commands using LLM-based intent classification and a static
    command registry.

    Security:
        - Input length limited to MAX_INPUT_LENGTH
        - Dangerous patterns (shell injection, SQL, etc.) blocked
        - Only commands in the static registry can execute
        - Destructive commands require confirmation
    """

    MAX_INPUT_LENGTH = 500
    MIN_CONFIDENCE = 0.5
    CONFIRMATION_THRESHOLD = 0.8

    # Commands that modify state or are irreversible
    DESTRUCTIVE_COMMANDS = frozenset({
        "auth.logout",
        "learn.end",
        "learn.abandon",
    })

    # Dangerous input patterns to block
    DANGEROUS_PATTERNS = [
        (r'[;&|`$]', "shell metacharacters"),
        (r'\.\.[\\/]', "path traversal"),
        (r'--\s', "SQL comment"),
        (r"'\s*OR\s*'", "SQL injection"),
        (r'DROP\s+TABLE', "SQL injection"),
        (r'<script', "script injection"),
        (r'javascript:', "javascript injection"),
        (r'\x00', "null byte injection"),
    ]

    def __init__(self) -> None:
        """Initialize the NLP command parser."""
        self._llm = None  # Lazy loaded
        self._command_registry = self._build_command_registry()

    def _get_llm(self):
        """Get LLM service (lazy load)."""
        if self._llm is None:
            from src.modules.llm.service import get_llm_service
            self._llm = get_llm_service()
        return self._llm

    async def parse_command(
        self,
        user_input: str,
        is_authenticated: bool = False,
    ) -> CommandIntent:
        """Parse natural language into an executable command intent.

        Args:
            user_input: Natural language command from user
            is_authenticated: Whether user is currently logged in

        Returns:
            CommandIntent with executable function and metadata

        Raises:
            ValidationError: Input fails security validation
            NLPParseError: Cannot parse user intent
            CommandNotFoundError: No matching command found
            AmbiguousCommandError: Multiple possible interpretations
        """
        # Step 1: Sanitize input
        sanitized = self._sanitize_input(user_input)

        # Step 2: Classify intent using LLM
        intent_type, confidence, params = await self._classify_intent(
            sanitized, is_authenticated
        )

        logger.info(
            f"NLP classified: intent={intent_type}, confidence={confidence:.2f}",
            extra={"user_input": sanitized[:50], "params": params}
        )

        # Step 3: Validate intent exists
        if intent_type not in self._command_registry:
            raise CommandNotFoundError(
                user_input,
                suggestion="Try 'learner chat examples' to see available commands"
            )

        # Step 4: Build command intent
        builder = self._command_registry[intent_type]
        intent = builder(sanitized, params)

        # Step 5: Determine if confirmation needed
        intent.needs_confirmation = (
            intent.command in self.DESTRUCTIVE_COMMANDS or
            confidence < self.CONFIRMATION_THRESHOLD
        )

        return intent

    def _sanitize_input(self, user_input: str) -> str:
        """Validate and sanitize user input for security.

        Args:
            user_input: Raw user input

        Returns:
            Sanitized input string

        Raises:
            ValidationError: If input fails security checks
        """
        # Check for empty input
        if not user_input or not user_input.strip():
            raise ValidationError("input", "Please enter a command")

        user_input = user_input.strip()

        # Check length
        if len(user_input) > self.MAX_INPUT_LENGTH:
            raise ValidationError(
                "input",
                f"Command too long (max {self.MAX_INPUT_LENGTH} characters)"
            )

        # Check for dangerous patterns
        for pattern, name in self.DANGEROUS_PATTERNS:
            if re.search(pattern, user_input, re.IGNORECASE):
                logger.warning(
                    f"Blocked dangerous input pattern: {name}",
                    extra={"pattern": pattern}
                )
                raise ValidationError(
                    "input",
                    f"Input contains prohibited pattern: {name}"
                )

        # Normalize whitespace
        user_input = " ".join(user_input.split())

        return user_input

    async def _classify_intent(
        self,
        user_input: str,
        is_authenticated: bool,
    ) -> tuple[str, float, dict[str, Any]]:
        """Classify user intent using LLM.

        Args:
            user_input: Sanitized user input
            is_authenticated: Whether user is authenticated

        Returns:
            Tuple of (intent_type, confidence, extracted_params)

        Raises:
            NLPParseError: If classification fails
        """
        available_commands = self._get_available_commands(is_authenticated)

        prompt = f"""Classify this user command and extract parameters.

User input: "{user_input}"

Available commands:
{available_commands}

Respond in this EXACT JSON format only, no other text:
{{
    "intent": "command.subcommand",
    "confidence": 0.95,
    "params": {{"param_name": "value"}}
}}

Parameter extraction rules:
- For time/duration: extract as "minutes" (integer)
- For session type: extract as "type" (regular/drill/catchup)
- For topics: extract as "topic" (string)
- For question count: extract as "count" (integer, default 5)
- For search queries: extract as "query" (string)

Examples:
- "start a 30 minute session" -> {{"intent": "learn.start", "confidence": 0.98, "params": {{"minutes": 30}}}}
- "quiz me on transformers" -> {{"intent": "quiz.start", "confidence": 0.92, "params": {{"topic": "transformers", "count": 5}}}}
- "show my stats" -> {{"intent": "stats.show", "confidence": 0.95, "params": {{}}}}
- "log out" -> {{"intent": "auth.logout", "confidence": 0.99, "params": {{}}}}

If the command doesn't match any available command, use:
{{"intent": "unknown", "confidence": 0.0, "params": {{}}}}"""

        try:
            llm = self._get_llm()
            response = await llm.complete(
                prompt=prompt,
                system_prompt=(
                    "You are a command classifier for a learning CLI. "
                    "Respond ONLY with valid JSON, no explanation or other text. "
                    "Be strict about matching commands to the available list."
                ),
                temperature=0.1,
                max_tokens=150,
            )

            # Parse JSON response
            content = response.content.strip()

            # Handle potential markdown code blocks
            if content.startswith("```"):
                content = re.sub(r'^```(?:json)?\s*', '', content)
                content = re.sub(r'\s*```$', '', content)

            result = json.loads(content)

            intent = result.get("intent", "unknown")
            confidence = float(result.get("confidence", 0.0))
            params = result.get("params", {})

            # Validate confidence range
            confidence = max(0.0, min(1.0, confidence))

            # Reject low confidence
            if confidence < self.MIN_CONFIDENCE:
                raise NLPParseError(
                    user_input,
                    "I'm not sure what you want to do. Please try rephrasing."
                )

            return intent, confidence, params

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}")
            raise NLPParseError(
                user_input,
                "Could not understand the command. Please try rephrasing."
            )
        except Exception as e:
            logger.error(f"Intent classification failed: {e}")
            raise NLPParseError(
                user_input,
                f"Failed to process command: {e}"
            )

    def _get_available_commands(self, is_authenticated: bool) -> str:
        """Get formatted list of available commands.

        Args:
            is_authenticated: Whether to include auth-required commands

        Returns:
            Formatted string of available commands
        """
        commands = [
            ("learn.start", "Start a learning session", "minutes, type"),
            ("learn.status", "Check current session status", ""),
            ("learn.end", "End the current session", ""),
            ("quiz.start", "Start a quiz", "topic, count"),
            ("explain.start", "Start Feynman explanation", "topic"),
            ("stats.show", "Show learning progress/stats", ""),
            ("profile.show", "Show user profile", ""),
            ("content.search", "Search for learning content", "query"),
        ]

        if is_authenticated:
            commands.extend([
                ("auth.logout", "Log out", ""),
                ("auth.whoami", "Show current user", ""),
            ])
        else:
            commands.append(
                ("auth.login", "Log in (not via NLP)", "")
            )

        lines = []
        for cmd, desc, params in commands:
            param_str = f" (params: {params})" if params else ""
            lines.append(f"- {cmd}: {desc}{param_str}")

        return "\n".join(lines)

    def _build_command_registry(self) -> dict[str, Callable]:
        """Build the intent to command builder mapping.

        Returns:
            Dictionary mapping intent strings to builder functions
        """
        return {
            "learn.start": self._build_learn_start,
            "learn.status": self._build_learn_status,
            "learn.end": self._build_learn_end,
            "quiz.start": self._build_quiz_start,
            "explain.start": self._build_explain_start,
            "stats.show": self._build_stats_show,
            "profile.show": self._build_profile_show,
            "content.search": self._build_content_search,
            "auth.logout": self._build_auth_logout,
            "auth.whoami": self._build_auth_whoami,
        }

    # =========================================================================
    # Command Builders
    # =========================================================================

    def _build_learn_start(
        self,
        user_input: str,
        params: dict[str, Any],
    ) -> CommandIntent:
        """Build intent for starting a learning session."""
        minutes = self._validate_minutes(params.get("minutes", 30))
        session_type = self._validate_session_type(params.get("type", "regular"))

        def execute() -> dict[str, Any]:
            from src.cli.commands.learn import start
            # Call the actual command - it handles its own output
            start(minutes=minutes, session_type=session_type.value)
            return {"message": f"Started {session_type.value} session for {minutes} minutes"}

        return CommandIntent(
            command="learn.start",
            description=f"Start a {session_type.value} learning session for {minutes} minutes",
            params={"minutes": minutes, "type": session_type.value},
            needs_confirmation=False,
            command_signature=f"learner learn start --time {minutes} --type {session_type.value}",
            execute=execute,
        )

    def _build_learn_status(
        self,
        user_input: str,
        params: dict[str, Any],
    ) -> CommandIntent:
        """Build intent for checking session status."""
        def execute() -> dict[str, Any]:
            from src.cli.commands.learn import status
            status()
            return {"message": "Session status displayed"}

        return CommandIntent(
            command="learn.status",
            description="Check your current learning session status",
            params={},
            needs_confirmation=False,
            command_signature="learner learn status",
            execute=execute,
        )

    def _build_learn_end(
        self,
        user_input: str,
        params: dict[str, Any],
    ) -> CommandIntent:
        """Build intent for ending a session."""
        def execute() -> dict[str, Any]:
            from src.cli.commands.learn import end
            end()
            return {"message": "Session ended"}

        return CommandIntent(
            command="learn.end",
            description="End your current learning session",
            params={},
            needs_confirmation=True,  # Always confirm ending
            command_signature="learner learn end",
            execute=execute,
        )

    def _build_quiz_start(
        self,
        user_input: str,
        params: dict[str, Any],
    ) -> CommandIntent:
        """Build intent for starting a quiz."""
        topic = params.get("topic")
        count = self._validate_count(params.get("count", 5))

        def execute() -> dict[str, Any]:
            from src.cli.main import quick_quiz
            quick_quiz(topic=topic, count=count)
            return {"message": f"Quiz started" + (f" on {topic}" if topic else "")}

        topic_desc = f" on '{topic}'" if topic else ""
        return CommandIntent(
            command="quiz.start",
            description=f"Start a {count}-question quiz{topic_desc}",
            params={"topic": topic, "count": count},
            needs_confirmation=False,
            command_signature=f"learner quiz --topic '{topic or ''}' --count {count}".replace("--topic ''", "").strip(),
            execute=execute,
        )

    def _build_explain_start(
        self,
        user_input: str,
        params: dict[str, Any],
    ) -> CommandIntent:
        """Build intent for starting Feynman explanation."""
        topic = params.get("topic", "")

        # Try to extract topic from input if not in params
        if not topic:
            # Common patterns
            patterns = [
                r"explain\s+(.+)",
                r"teach\s+me\s+(?:about\s+)?(.+)",
                r"what\s+is\s+(.+)",
            ]
            for pattern in patterns:
                match = re.search(pattern, user_input, re.IGNORECASE)
                if match:
                    topic = match.group(1).strip()
                    break

        if not topic:
            topic = "the topic"

        def execute() -> dict[str, Any]:
            from src.cli.main import quick_explain
            quick_explain(topic=topic)
            return {"message": f"Started Feynman dialogue on '{topic}'"}

        return CommandIntent(
            command="explain.start",
            description=f"Start a Feynman explanation dialogue on '{topic}'",
            params={"topic": topic},
            needs_confirmation=False,
            command_signature=f"learner explain '{topic}'",
            execute=execute,
        )

    def _build_stats_show(
        self,
        user_input: str,
        params: dict[str, Any],
    ) -> CommandIntent:
        """Build intent for showing stats."""
        def execute() -> dict[str, Any]:
            from src.cli.commands.stats import progress
            progress()
            return {"message": "Stats displayed"}

        return CommandIntent(
            command="stats.show",
            description="Show your learning progress and statistics",
            params={},
            needs_confirmation=False,
            command_signature="learner stats progress",
            execute=execute,
        )

    def _build_profile_show(
        self,
        user_input: str,
        params: dict[str, Any],
    ) -> CommandIntent:
        """Build intent for showing profile."""
        def execute() -> dict[str, Any]:
            from src.cli.commands.profile import show
            show()
            return {"message": "Profile displayed"}

        return CommandIntent(
            command="profile.show",
            description="Show your user profile",
            params={},
            needs_confirmation=False,
            command_signature="learner profile show",
            execute=execute,
        )

    def _build_content_search(
        self,
        user_input: str,
        params: dict[str, Any],
    ) -> CommandIntent:
        """Build intent for content search."""
        query = params.get("query", "")

        # Extract query from input if not in params
        if not query:
            patterns = [
                r"search\s+(?:for\s+)?(.+)",
                r"find\s+(.+)",
                r"look\s+(?:for\s+)?(.+)",
            ]
            for pattern in patterns:
                match = re.search(pattern, user_input, re.IGNORECASE)
                if match:
                    query = match.group(1).strip()
                    break

        if not query:
            query = "learning content"

        def execute() -> dict[str, Any]:
            from src.cli.commands.content import search
            search(query=query)
            return {"message": f"Searched for '{query}'"}

        return CommandIntent(
            command="content.search",
            description=f"Search for content about '{query}'",
            params={"query": query},
            needs_confirmation=False,
            command_signature=f"learner content search '{query}'",
            execute=execute,
        )

    def _build_auth_logout(
        self,
        user_input: str,
        params: dict[str, Any],
    ) -> CommandIntent:
        """Build intent for logout."""
        def execute() -> dict[str, Any]:
            from src.cli.commands.auth import logout
            logout()
            return {"message": "Logged out successfully"}

        return CommandIntent(
            command="auth.logout",
            description="Log out of your account",
            params={},
            needs_confirmation=True,  # Always confirm logout
            command_signature="learner auth logout",
            execute=execute,
        )

    def _build_auth_whoami(
        self,
        user_input: str,
        params: dict[str, Any],
    ) -> CommandIntent:
        """Build intent for whoami."""
        def execute() -> dict[str, Any]:
            from src.cli.commands.auth import whoami
            whoami()
            return {"message": "User info displayed"}

        return CommandIntent(
            command="auth.whoami",
            description="Show your current user information",
            params={},
            needs_confirmation=False,
            command_signature="learner auth whoami",
            execute=execute,
        )

    # =========================================================================
    # Parameter Validators
    # =========================================================================

    def _validate_minutes(self, minutes: Any) -> int:
        """Validate and normalize session minutes.

        Args:
            minutes: Raw minutes value from params

        Returns:
            Validated minutes (clamped to 10-180)
        """
        try:
            minutes = int(minutes)
        except (ValueError, TypeError):
            minutes = 30  # Default

        # Clamp to valid range
        return max(10, min(180, minutes))

    def _validate_session_type(self, stype: Any) -> SessionType:
        """Validate and normalize session type.

        Args:
            stype: Raw session type from params

        Returns:
            Valid SessionType enum value
        """
        if isinstance(stype, SessionType):
            return stype

        try:
            return SessionType(str(stype).lower())
        except ValueError:
            return SessionType.REGULAR

    def _validate_count(self, count: Any) -> int:
        """Validate and normalize question count.

        Args:
            count: Raw count value from params

        Returns:
            Validated count (clamped to 1-20)
        """
        try:
            count = int(count)
        except (ValueError, TypeError):
            count = 5  # Default

        return max(1, min(20, count))

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def get_suggestion(self, failed_input: str) -> str:
        """Get a helpful suggestion for a failed parse.

        Args:
            failed_input: The input that failed to parse

        Returns:
            Helpful suggestion string
        """
        suggestions = [
            "Try 'learner chat examples' to see what I can do.",
            "You can say things like:",
            "  - 'start a 30 minute session'",
            "  - 'quiz me on Python'",
            "  - 'show my stats'",
        ]
        return "\n".join(suggestions)

    def get_available_intents(self) -> list[str]:
        """Get list of available command intents.

        Returns:
            List of intent strings
        """
        return list(self._command_registry.keys())


# Factory function
_parser: NLPCommandParser | None = None


def get_nlp_parser() -> NLPCommandParser:
    """Get the NLP parser singleton.

    Returns:
        Shared NLPCommandParser instance
    """
    global _parser
    if _parser is None:
        _parser = NLPCommandParser()
    return _parser
