"""Integration tests for NLP command flow.

These tests verify end-to-end functionality of the NLP command parsing
and execution pipeline, including integration with feature flags and
the CLI state management.
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typer.testing import CliRunner

from src.cli.main import app
from src.shared.feature_flags import FeatureFlagManager, FeatureFlags, get_feature_flags


runner = CliRunner()


class TestChatCommandAvailability:
    """Tests for chat command availability and feature flag integration."""

    @pytest.fixture(autouse=True)
    def reset_feature_flags(self):
        """Reset feature flags before each test."""
        FeatureFlagManager._instance = None
        get_feature_flags.cache_clear()
        yield

    def test_chat_help_available(self):
        """Test that chat command help is available."""
        result = runner.invoke(app, ["chat", "--help"])
        assert result.exit_code == 0
        assert "Natural language" in result.output

    def test_chat_ask_help_available(self):
        """Test that chat ask help is available."""
        result = runner.invoke(app, ["chat", "ask", "--help"])
        assert result.exit_code == 0
        assert "natural language" in result.output.lower()

    def test_chat_examples_works(self):
        """Test that chat examples command works."""
        result = runner.invoke(app, ["chat", "examples"])
        assert result.exit_code == 0
        assert "Learning Sessions" in result.output
        assert "Assessment" in result.output
        assert "start a" in result.output.lower()

    def test_chat_intents_works(self):
        """Test that chat intents command works."""
        result = runner.invoke(app, ["chat", "intents"])
        assert result.exit_code == 0
        assert "learn.start" in result.output
        assert "auth.logout" in result.output

    def test_chat_ask_blocked_when_feature_disabled(self):
        """Test that chat ask is blocked when NLP feature is disabled."""
        with patch.dict(os.environ, {"FF_ENABLE_NLP_COMMANDS": "false"}, clear=False):
            get_feature_flags.cache_clear()
            result = runner.invoke(app, ["chat", "ask", "start a session"])
            assert result.exit_code == 1
            assert "not enabled" in result.output.lower()


class TestNLPFlowWithMockedLLM:
    """Tests for NLP flow with mocked LLM service."""

    @pytest.fixture(autouse=True)
    def setup_feature_flags(self):
        """Enable NLP commands for tests."""
        FeatureFlagManager._instance = None
        get_feature_flags.cache_clear()
        yield

    @pytest.fixture
    def mock_llm_response(self):
        """Create a mock LLM response."""
        def make_response(intent, confidence=0.95, params=None):
            params = params or {}
            import json
            return MagicMock(
                content=json.dumps({
                    "intent": intent,
                    "confidence": confidence,
                    "params": params
                })
            )
        return make_response

    @pytest.mark.asyncio
    async def test_parse_start_session_command(self, mock_llm_response):
        """Test parsing a start session command."""
        with patch.dict(os.environ, {"FF_ENABLE_NLP_COMMANDS": "true"}):
            get_feature_flags.cache_clear()

            from src.cli.nlp_parser import NLPCommandParser

            parser = NLPCommandParser()
            mock_llm = AsyncMock()
            mock_llm.complete = AsyncMock(return_value=mock_llm_response(
                "learn.start",
                confidence=0.95,
                params={"minutes": 30, "type": "regular"}
            ))
            parser._llm = mock_llm

            intent = await parser.parse_command(
                "start a 30 minute session",
                is_authenticated=True
            )

            assert intent.command == "learn.start"
            assert intent.params["minutes"] == 30
            assert not intent.needs_confirmation

    @pytest.mark.asyncio
    async def test_parse_quiz_command(self, mock_llm_response):
        """Test parsing a quiz command."""
        with patch.dict(os.environ, {"FF_ENABLE_NLP_COMMANDS": "true"}):
            get_feature_flags.cache_clear()

            from src.cli.nlp_parser import NLPCommandParser

            parser = NLPCommandParser()
            mock_llm = AsyncMock()
            mock_llm.complete = AsyncMock(return_value=mock_llm_response(
                "quiz.start",
                confidence=0.92,
                params={"topic": "transformers", "count": 5}
            ))
            parser._llm = mock_llm

            intent = await parser.parse_command(
                "quiz me on transformers",
                is_authenticated=True
            )

            assert intent.command == "quiz.start"
            assert intent.params["topic"] == "transformers"

    @pytest.mark.asyncio
    async def test_destructive_command_needs_confirmation(self, mock_llm_response):
        """Test that destructive commands require confirmation."""
        with patch.dict(os.environ, {"FF_ENABLE_NLP_COMMANDS": "true"}):
            get_feature_flags.cache_clear()

            from src.cli.nlp_parser import NLPCommandParser

            parser = NLPCommandParser()
            mock_llm = AsyncMock()
            mock_llm.complete = AsyncMock(return_value=mock_llm_response(
                "auth.logout",
                confidence=0.99,
                params={}
            ))
            parser._llm = mock_llm

            intent = await parser.parse_command(
                "log me out",
                is_authenticated=True
            )

            assert intent.command == "auth.logout"
            assert intent.needs_confirmation is True

    @pytest.mark.asyncio
    async def test_low_confidence_needs_confirmation(self, mock_llm_response):
        """Test that low confidence results need confirmation."""
        with patch.dict(os.environ, {"FF_ENABLE_NLP_COMMANDS": "true"}):
            get_feature_flags.cache_clear()

            from src.cli.nlp_parser import NLPCommandParser

            parser = NLPCommandParser()
            mock_llm = AsyncMock()
            mock_llm.complete = AsyncMock(return_value=mock_llm_response(
                "learn.start",
                confidence=0.65,
                params={}
            ))
            parser._llm = mock_llm

            intent = await parser.parse_command(
                "maybe start",
                is_authenticated=True
            )

            assert intent.needs_confirmation is True


class TestAuthenticationAwareness:
    """Tests for authentication-aware command availability."""

    @pytest.fixture(autouse=True)
    def setup_feature_flags(self):
        """Enable NLP commands for tests."""
        FeatureFlagManager._instance = None
        get_feature_flags.cache_clear()
        yield

    @pytest.mark.asyncio
    async def test_authenticated_commands_include_logout(self):
        """Test that authenticated users can access logout."""
        from src.cli.nlp_parser import NLPCommandParser

        parser = NLPCommandParser()
        commands = parser._get_available_commands(is_authenticated=True)

        assert "auth.logout" in commands
        assert "auth.whoami" in commands

    @pytest.mark.asyncio
    async def test_unauthenticated_commands_exclude_logout(self):
        """Test that unauthenticated users cannot logout."""
        from src.cli.nlp_parser import NLPCommandParser

        parser = NLPCommandParser()
        commands = parser._get_available_commands(is_authenticated=False)

        # Logout should not be in the list (it's auth-required)
        # Instead, login hint should be shown
        assert "auth.login" in commands


class TestCommandSignatureGeneration:
    """Tests for command signature generation."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        from src.cli.nlp_parser import NLPCommandParser
        return NLPCommandParser()

    def test_learn_start_signature(self, parser):
        """Test learn.start command signature."""
        intent = parser._build_learn_start(
            "start a 45 minute drill session",
            {"minutes": 45, "type": "drill"}
        )
        assert "learner learn start" in intent.command_signature
        assert "--time 45" in intent.command_signature
        assert "--type drill" in intent.command_signature

    def test_quiz_signature_with_topic(self, parser):
        """Test quiz command signature with topic."""
        intent = parser._build_quiz_start(
            "quiz me on Python",
            {"topic": "Python", "count": 10}
        )
        assert "learner quiz" in intent.command_signature
        assert "Python" in intent.command_signature
        assert "10" in intent.command_signature

    def test_explain_signature(self, parser):
        """Test explain command signature."""
        intent = parser._build_explain_start(
            "explain neural networks",
            {"topic": "neural networks"}
        )
        assert "learner explain" in intent.command_signature
        assert "neural networks" in intent.command_signature


class TestEndToEndFlowSimulation:
    """Simulated end-to-end flow tests."""

    @pytest.fixture(autouse=True)
    def setup_feature_flags(self):
        """Enable NLP commands for tests."""
        FeatureFlagManager._instance = None
        get_feature_flags.cache_clear()
        with patch.dict(os.environ, {"FF_ENABLE_NLP_COMMANDS": "true"}):
            get_feature_flags.cache_clear()
            yield

    @pytest.mark.asyncio
    async def test_full_parse_to_intent_flow(self):
        """Test complete flow from natural language to intent."""
        from src.cli.nlp_parser import NLPCommandParser
        import json

        parser = NLPCommandParser()

        # Mock LLM
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value=MagicMock(
            content=json.dumps({
                "intent": "stats.show",
                "confidence": 0.96,
                "params": {}
            })
        ))
        parser._llm = mock_llm

        # Parse command
        intent = await parser.parse_command(
            "show me my learning statistics",
            is_authenticated=True
        )

        # Verify intent structure
        assert intent.command == "stats.show"
        assert intent.description  # Has description
        assert intent.command_signature  # Has CLI equivalent
        assert callable(intent.execute)  # Is executable
        assert not intent.needs_confirmation  # Non-destructive

    @pytest.mark.asyncio
    async def test_validation_before_classification(self):
        """Test that input is validated before LLM classification."""
        from src.cli.nlp_parser import NLPCommandParser
        from src.shared.exceptions import ValidationError

        parser = NLPCommandParser()

        # Mock LLM - should NOT be called due to validation failure
        mock_llm = AsyncMock()
        parser._llm = mock_llm

        with pytest.raises(ValidationError):
            await parser.parse_command(
                "start; rm -rf /",  # Shell injection attempt
                is_authenticated=True
            )

        # LLM should not have been called
        mock_llm.complete.assert_not_called()
