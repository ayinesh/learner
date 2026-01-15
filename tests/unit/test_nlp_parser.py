"""Unit tests for NLP command parser."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.cli.nlp_parser import (
    CommandIntent,
    NLPCommandParser,
    get_nlp_parser,
)
from src.shared.exceptions import (
    CommandNotFoundError,
    NLPParseError,
    ValidationError,
)
from src.shared.models import SessionType


class TestInputSanitization:
    """Tests for input sanitization and security."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return NLPCommandParser()

    def test_empty_input_raises_error(self, parser):
        """Test that empty input raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            parser._sanitize_input("")
        assert "Please enter a command" in str(exc_info.value)

    def test_whitespace_only_raises_error(self, parser):
        """Test that whitespace-only input raises ValidationError."""
        with pytest.raises(ValidationError):
            parser._sanitize_input("   \t\n   ")

    def test_input_too_long_raises_error(self, parser):
        """Test that input exceeding max length raises ValidationError."""
        long_input = "a" * (parser.MAX_INPUT_LENGTH + 1)
        with pytest.raises(ValidationError) as exc_info:
            parser._sanitize_input(long_input)
        assert "too long" in str(exc_info.value)

    def test_max_length_input_passes(self, parser):
        """Test that input at max length passes."""
        valid_input = "a" * parser.MAX_INPUT_LENGTH
        result = parser._sanitize_input(valid_input)
        assert len(result) == parser.MAX_INPUT_LENGTH

    def test_whitespace_normalization(self, parser):
        """Test that multiple whitespace is normalized."""
        result = parser._sanitize_input("start   a    session")
        assert result == "start a session"

    def test_leading_trailing_whitespace_removed(self, parser):
        """Test that leading/trailing whitespace is removed."""
        result = parser._sanitize_input("  start a session  ")
        assert result == "start a session"

    @pytest.mark.parametrize("dangerous_input,pattern_name", [
        ("start; rm -rf /", "shell metacharacters"),
        ("start && whoami", "shell metacharacters"),
        ("start | cat /etc/passwd", "shell metacharacters"),
        ("start `whoami`", "shell metacharacters"),
        ("start $HOME", "shell metacharacters"),
        ("search ..\\..\\etc\\passwd", "path traversal"),
        ("search ../../../etc/passwd", "path traversal"),
        ("show -- drop table users", "SQL comment"),
        ("search ' OR '1'='1", "SQL injection"),
        ("search DROP TABLE users", "SQL injection"),
        ("start <script>alert(1)</script>", "script injection"),
        ("search javascript:alert(1)", "javascript injection"),
    ])
    def test_dangerous_patterns_blocked(self, parser, dangerous_input, pattern_name):
        """Test that dangerous patterns are blocked."""
        with pytest.raises(ValidationError) as exc_info:
            parser._sanitize_input(dangerous_input)
        assert "prohibited pattern" in str(exc_info.value).lower()

    def test_valid_input_passes(self, parser):
        """Test that valid inputs pass sanitization."""
        valid_inputs = [
            "start a session",
            "quiz me on Python",
            "show my stats",
            "search for machine learning papers",
            "explain transformers to me",
        ]
        for input_text in valid_inputs:
            result = parser._sanitize_input(input_text)
            assert result == input_text


class TestParameterValidation:
    """Tests for parameter validation methods."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return NLPCommandParser()

    def test_validate_minutes_valid(self, parser):
        """Test valid minutes values."""
        assert parser._validate_minutes(30) == 30
        assert parser._validate_minutes("45") == 45
        assert parser._validate_minutes(10) == 10
        assert parser._validate_minutes(180) == 180

    def test_validate_minutes_clamps_low(self, parser):
        """Test that low values are clamped to minimum."""
        assert parser._validate_minutes(5) == 10
        assert parser._validate_minutes(0) == 10
        assert parser._validate_minutes(-10) == 10

    def test_validate_minutes_clamps_high(self, parser):
        """Test that high values are clamped to maximum."""
        assert parser._validate_minutes(200) == 180
        assert parser._validate_minutes(500) == 180

    def test_validate_minutes_invalid_type(self, parser):
        """Test that invalid types return default."""
        assert parser._validate_minutes("invalid") == 30
        assert parser._validate_minutes(None) == 30
        assert parser._validate_minutes([]) == 30

    def test_validate_session_type_valid(self, parser):
        """Test valid session types."""
        assert parser._validate_session_type("regular") == SessionType.REGULAR
        assert parser._validate_session_type("drill") == SessionType.DRILL
        assert parser._validate_session_type("catchup") == SessionType.CATCHUP
        assert parser._validate_session_type("REGULAR") == SessionType.REGULAR

    def test_validate_session_type_invalid(self, parser):
        """Test that invalid session types return default."""
        assert parser._validate_session_type("invalid") == SessionType.REGULAR
        assert parser._validate_session_type(None) == SessionType.REGULAR
        assert parser._validate_session_type(123) == SessionType.REGULAR

    def test_validate_session_type_enum_passthrough(self, parser):
        """Test that SessionType enums pass through."""
        assert parser._validate_session_type(SessionType.DRILL) == SessionType.DRILL

    def test_validate_count_valid(self, parser):
        """Test valid count values."""
        assert parser._validate_count(5) == 5
        assert parser._validate_count("10") == 10
        assert parser._validate_count(1) == 1
        assert parser._validate_count(20) == 20

    def test_validate_count_clamps_low(self, parser):
        """Test that low values are clamped to minimum."""
        assert parser._validate_count(0) == 1
        assert parser._validate_count(-5) == 1

    def test_validate_count_clamps_high(self, parser):
        """Test that high values are clamped to maximum."""
        assert parser._validate_count(25) == 20
        assert parser._validate_count(100) == 20

    def test_validate_count_invalid_type(self, parser):
        """Test that invalid types return default."""
        assert parser._validate_count("invalid") == 5
        assert parser._validate_count(None) == 5


class TestCommandRegistry:
    """Tests for command registry and builders."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return NLPCommandParser()

    def test_all_commands_registered(self, parser):
        """Test that all expected commands are in registry."""
        expected_commands = [
            "learn.start",
            "learn.status",
            "learn.end",
            "quiz.start",
            "explain.start",
            "stats.show",
            "profile.show",
            "content.search",
            "auth.logout",
            "auth.whoami",
        ]
        for cmd in expected_commands:
            assert cmd in parser._command_registry

    def test_get_available_intents(self, parser):
        """Test getting available intents."""
        intents = parser.get_available_intents()
        assert isinstance(intents, list)
        assert "learn.start" in intents
        assert "auth.logout" in intents

    def test_destructive_commands_defined(self, parser):
        """Test that destructive commands are properly defined."""
        assert "auth.logout" in parser.DESTRUCTIVE_COMMANDS
        assert "learn.end" in parser.DESTRUCTIVE_COMMANDS
        assert "learn.abandon" in parser.DESTRUCTIVE_COMMANDS
        # Non-destructive commands should not be in the set
        assert "learn.start" not in parser.DESTRUCTIVE_COMMANDS
        assert "stats.show" not in parser.DESTRUCTIVE_COMMANDS


class TestCommandBuilders:
    """Tests for individual command builders."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return NLPCommandParser()

    def test_build_learn_start_default(self, parser):
        """Test building learn.start with defaults."""
        intent = parser._build_learn_start("start a session", {})
        assert intent.command == "learn.start"
        assert intent.params["minutes"] == 30
        assert intent.params["type"] == "regular"
        assert "30 minutes" in intent.description
        assert not intent.needs_confirmation

    def test_build_learn_start_with_params(self, parser):
        """Test building learn.start with specific params."""
        intent = parser._build_learn_start(
            "start a 45 minute drill",
            {"minutes": 45, "type": "drill"}
        )
        assert intent.params["minutes"] == 45
        assert intent.params["type"] == "drill"
        assert "45 minutes" in intent.description
        assert "drill" in intent.description.lower()

    def test_build_learn_end_requires_confirmation(self, parser):
        """Test that learn.end requires confirmation."""
        intent = parser._build_learn_end("end my session", {})
        assert intent.command == "learn.end"
        assert intent.needs_confirmation is True

    def test_build_quiz_start_with_topic(self, parser):
        """Test building quiz.start with topic."""
        intent = parser._build_quiz_start(
            "quiz me on Python",
            {"topic": "Python", "count": 10}
        )
        assert intent.params["topic"] == "Python"
        assert intent.params["count"] == 10
        assert "Python" in intent.description

    def test_build_quiz_start_without_topic(self, parser):
        """Test building quiz.start without topic."""
        intent = parser._build_quiz_start("give me a quiz", {})
        assert intent.params["topic"] is None
        assert intent.params["count"] == 5

    def test_build_explain_extracts_topic(self, parser):
        """Test that explain.start extracts topic from input."""
        intent = parser._build_explain_start("explain transformers", {})
        assert intent.params["topic"] == "transformers"

    def test_build_content_search_extracts_query(self, parser):
        """Test that content.search extracts query from input."""
        intent = parser._build_content_search("search for machine learning", {})
        assert "machine learning" in intent.params["query"]

    def test_build_auth_logout_requires_confirmation(self, parser):
        """Test that auth.logout requires confirmation."""
        intent = parser._build_auth_logout("log out", {})
        assert intent.command == "auth.logout"
        assert intent.needs_confirmation is True

    def test_command_intent_has_execute_callable(self, parser):
        """Test that all intents have executable functions."""
        for cmd_name, builder in parser._command_registry.items():
            intent = builder("test input", {})
            assert callable(intent.execute), f"{cmd_name} missing execute callable"


class TestIntentClassification:
    """Tests for LLM-based intent classification."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return NLPCommandParser()

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM service."""
        llm = AsyncMock()
        return llm

    @pytest.mark.asyncio
    async def test_classify_intent_success(self, parser, mock_llm):
        """Test successful intent classification."""
        mock_llm.complete = AsyncMock(return_value=MagicMock(
            content='{"intent": "learn.start", "confidence": 0.95, "params": {"minutes": 30}}'
        ))
        parser._llm = mock_llm

        intent, confidence, params = await parser._classify_intent(
            "start a 30 minute session",
            is_authenticated=True
        )

        assert intent == "learn.start"
        assert confidence == 0.95
        assert params["minutes"] == 30

    @pytest.mark.asyncio
    async def test_classify_intent_low_confidence_rejected(self, parser, mock_llm):
        """Test that low confidence results are rejected."""
        mock_llm.complete = AsyncMock(return_value=MagicMock(
            content='{"intent": "learn.start", "confidence": 0.3, "params": {}}'
        ))
        parser._llm = mock_llm

        with pytest.raises(NLPParseError):
            await parser._classify_intent("maybe start?", is_authenticated=True)

    @pytest.mark.asyncio
    async def test_classify_intent_handles_markdown_blocks(self, parser, mock_llm):
        """Test that markdown code blocks are handled."""
        mock_llm.complete = AsyncMock(return_value=MagicMock(
            content='```json\n{"intent": "learn.start", "confidence": 0.9, "params": {}}\n```'
        ))
        parser._llm = mock_llm

        intent, confidence, params = await parser._classify_intent(
            "start a session",
            is_authenticated=True
        )

        assert intent == "learn.start"

    @pytest.mark.asyncio
    async def test_classify_intent_invalid_json_raises_error(self, parser, mock_llm):
        """Test that invalid JSON raises NLPParseError."""
        mock_llm.complete = AsyncMock(return_value=MagicMock(
            content='not valid json'
        ))
        parser._llm = mock_llm

        with pytest.raises(NLPParseError):
            await parser._classify_intent("start", is_authenticated=True)

    @pytest.mark.asyncio
    async def test_classify_intent_clamps_confidence(self, parser, mock_llm):
        """Test that confidence is clamped to 0-1 range."""
        mock_llm.complete = AsyncMock(return_value=MagicMock(
            content='{"intent": "learn.start", "confidence": 1.5, "params": {}}'
        ))
        parser._llm = mock_llm

        intent, confidence, params = await parser._classify_intent(
            "start",
            is_authenticated=True
        )

        assert confidence == 1.0


class TestParseCommand:
    """Tests for the main parse_command method."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return NLPCommandParser()

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM service."""
        llm = AsyncMock()
        return llm

    @pytest.mark.asyncio
    async def test_parse_command_success(self, parser, mock_llm):
        """Test successful command parsing."""
        mock_llm.complete = AsyncMock(return_value=MagicMock(
            content='{"intent": "learn.start", "confidence": 0.95, "params": {"minutes": 30}}'
        ))
        parser._llm = mock_llm

        intent = await parser.parse_command(
            "start a 30 minute session",
            is_authenticated=True
        )

        assert isinstance(intent, CommandIntent)
        assert intent.command == "learn.start"
        assert intent.params["minutes"] == 30

    @pytest.mark.asyncio
    async def test_parse_command_unknown_intent_raises_error(self, parser, mock_llm):
        """Test that unknown intents raise CommandNotFoundError."""
        mock_llm.complete = AsyncMock(return_value=MagicMock(
            content='{"intent": "unknown.command", "confidence": 0.9, "params": {}}'
        ))
        parser._llm = mock_llm

        with pytest.raises(CommandNotFoundError):
            await parser.parse_command("do something weird", is_authenticated=True)

    @pytest.mark.asyncio
    async def test_parse_command_needs_confirmation_for_destructive(self, parser, mock_llm):
        """Test that destructive commands need confirmation."""
        mock_llm.complete = AsyncMock(return_value=MagicMock(
            content='{"intent": "auth.logout", "confidence": 0.99, "params": {}}'
        ))
        parser._llm = mock_llm

        intent = await parser.parse_command("log me out", is_authenticated=True)

        assert intent.needs_confirmation is True

    @pytest.mark.asyncio
    async def test_parse_command_needs_confirmation_for_low_confidence(self, parser, mock_llm):
        """Test that low confidence commands need confirmation."""
        mock_llm.complete = AsyncMock(return_value=MagicMock(
            content='{"intent": "learn.start", "confidence": 0.6, "params": {}}'
        ))
        parser._llm = mock_llm

        intent = await parser.parse_command("maybe start", is_authenticated=True)

        assert intent.needs_confirmation is True

    @pytest.mark.asyncio
    async def test_parse_command_sanitizes_input(self, parser, mock_llm):
        """Test that input is sanitized before classification."""
        with pytest.raises(ValidationError):
            await parser.parse_command("start; rm -rf /", is_authenticated=True)

        # LLM should not have been called
        mock_llm.complete.assert_not_called()


class TestAvailableCommands:
    """Tests for available commands list."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return NLPCommandParser()

    def test_authenticated_includes_auth_commands(self, parser):
        """Test that authenticated users see auth commands."""
        commands = parser._get_available_commands(is_authenticated=True)
        assert "auth.logout" in commands
        assert "auth.whoami" in commands

    def test_unauthenticated_shows_login_hint(self, parser):
        """Test that unauthenticated users see login hint."""
        commands = parser._get_available_commands(is_authenticated=False)
        assert "auth.login" in commands

    def test_learning_commands_always_available(self, parser):
        """Test that learning commands are always available."""
        for is_auth in [True, False]:
            commands = parser._get_available_commands(is_authenticated=is_auth)
            assert "learn.start" in commands
            assert "quiz.start" in commands
            assert "stats.show" in commands


class TestHelperMethods:
    """Tests for helper methods."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return NLPCommandParser()

    def test_get_suggestion_includes_examples(self, parser):
        """Test that get_suggestion includes helpful examples."""
        suggestion = parser.get_suggestion("bad input")
        assert "learner chat examples" in suggestion
        assert "session" in suggestion.lower()


class TestSingleton:
    """Tests for singleton behavior."""

    def test_get_nlp_parser_returns_same_instance(self):
        """Test that get_nlp_parser returns the same instance."""
        # Reset singleton
        import src.cli.nlp_parser as module
        module._parser = None

        parser1 = get_nlp_parser()
        parser2 = get_nlp_parser()
        assert parser1 is parser2
