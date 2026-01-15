"""Unit tests for Phase 2 database persistence functionality."""

import json
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from src.modules.agents.interface import AgentType, ConversationState
from src.shared.feature_flags import FeatureFlagManager, FeatureFlags


class TestConversationStateStore:
    """Tests for Redis-backed conversation state storage."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()
        redis.delete = AsyncMock(return_value=1)
        redis.exists = AsyncMock(return_value=0)
        redis.expire = AsyncMock(return_value=True)
        return redis

    @pytest.fixture
    def sample_state(self):
        """Create a sample conversation state."""
        user_id = uuid4()
        session_id = uuid4()
        now = datetime.utcnow()
        return ConversationState(
            user_id=user_id,
            session_id=session_id,
            current_agent=AgentType.COACH,
            history=[
                {
                    "role": "user",
                    "content": "Hello",
                    "agent_type": None,
                    "timestamp": now.isoformat(),
                }
            ],
            context={"topic": "test"},
            started_at=now,
            last_activity=now,
        )

    @pytest.fixture
    def state_store(self):
        """Create a fresh state store."""
        from src.modules.agents.state_store import ConversationStateStore
        return ConversationStateStore(ttl_seconds=3600)

    @pytest.mark.asyncio
    async def test_set_stores_state_in_redis(self, state_store, mock_redis, sample_state):
        """Test that set() stores state in Redis with correct key and TTL."""
        with patch("src.modules.agents.state_store.get_redis", return_value=mock_redis):
            await state_store.set(sample_state.user_id, sample_state)

            mock_redis.setex.assert_called_once()
            call_args = mock_redis.setex.call_args
            key = call_args[0][0]
            ttl = call_args[0][1]
            data = call_args[0][2]

            assert f"conversation:state:{sample_state.user_id}" == key
            assert ttl == 3600
            assert json.loads(data)["user_id"] == str(sample_state.user_id)

    @pytest.mark.asyncio
    async def test_get_returns_state_from_redis(self, state_store, mock_redis, sample_state):
        """Test that get() retrieves and deserializes state from Redis."""
        # Serialize the state as Redis would store it
        serialized = state_store._serialize(sample_state)
        mock_redis.get = AsyncMock(return_value=serialized)

        with patch("src.modules.agents.state_store.get_redis", return_value=mock_redis):
            result = await state_store.get(sample_state.user_id)

            assert result is not None
            assert result.user_id == sample_state.user_id
            assert result.current_agent == sample_state.current_agent
            assert len(result.history) == len(sample_state.history)

    @pytest.mark.asyncio
    async def test_get_returns_none_when_not_found(self, state_store, mock_redis):
        """Test that get() returns None when key doesn't exist."""
        mock_redis.get = AsyncMock(return_value=None)

        with patch("src.modules.agents.state_store.get_redis", return_value=mock_redis):
            result = await state_store.get(uuid4())
            assert result is None

    @pytest.mark.asyncio
    async def test_delete_removes_state(self, state_store, mock_redis, sample_state):
        """Test that delete() removes state from Redis."""
        with patch("src.modules.agents.state_store.get_redis", return_value=mock_redis):
            result = await state_store.delete(sample_state.user_id)

            assert result is True
            mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_exists_checks_key(self, state_store, mock_redis, sample_state):
        """Test that exists() correctly checks Redis for key."""
        mock_redis.exists = AsyncMock(return_value=1)

        with patch("src.modules.agents.state_store.get_redis", return_value=mock_redis):
            result = await state_store.exists(sample_state.user_id)
            assert result is True

    def test_serialize_handles_uuid_in_context(self, state_store, sample_state):
        """Test that serialization handles UUIDs in context."""
        topic_id = uuid4()
        sample_state.context["topic_id"] = topic_id

        serialized = state_store._serialize(sample_state)
        data = json.loads(serialized)

        assert data["context"]["topic_id"] == str(topic_id)

    def test_serialize_handles_datetime_in_context(self, state_store, sample_state):
        """Test that serialization handles datetimes in context."""
        now = datetime.utcnow()
        sample_state.context["last_update"] = now

        serialized = state_store._serialize(sample_state)
        data = json.loads(serialized)

        assert data["context"]["last_update"] == now.isoformat()

    def test_deserialize_recreates_state(self, state_store, sample_state):
        """Test that deserialize recreates the original state."""
        serialized = state_store._serialize(sample_state)
        result = state_store._deserialize(serialized)

        assert result.user_id == sample_state.user_id
        assert result.session_id == sample_state.session_id
        assert result.current_agent == sample_state.current_agent
        assert result.history == sample_state.history


class TestOrchestratorPersistence:
    """Tests for orchestrator state persistence with feature flags."""

    @pytest.fixture(autouse=True)
    def reset_singletons(self):
        """Reset singletons before each test."""
        FeatureFlagManager._instance = None
        yield

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM service."""
        llm = MagicMock()
        llm.complete = AsyncMock(return_value=MagicMock(content="COACH"))
        return llm

    @pytest.fixture
    def mock_agents(self):
        """Create mock agents."""
        agents = {}
        for agent_type in AgentType:
            agent = MagicMock()
            agent.agent_type = agent_type
            agent.respond = AsyncMock(return_value=MagicMock(
                message="Test response",
                agent_type=agent_type,
                timestamp=datetime.utcnow(),
                end_conversation=False,
                suggested_next_agent=None,
            ))
            agents[agent_type] = agent
        return agents

    @pytest.mark.asyncio
    async def test_get_state_uses_redis_when_flag_enabled(self, mock_llm):
        """Test that get_conversation_state uses Redis when FF enabled."""
        with patch.dict(os.environ, {"FF_USE_DATABASE_PERSISTENCE": "true"}):
            FeatureFlagManager._instance = None

            from src.modules.agents.orchestrator import AgentOrchestrator

            orchestrator = AgentOrchestrator(llm_service=mock_llm)

            mock_store = AsyncMock()
            mock_store.get = AsyncMock(return_value=None)

            with patch.object(orchestrator, "_get_state_store", return_value=mock_store):
                result = await orchestrator.get_conversation_state(uuid4())

                mock_store.get.assert_called_once()
                assert result is None

    @pytest.mark.asyncio
    async def test_get_state_uses_memory_when_flag_disabled(self, mock_llm):
        """Test that get_conversation_state uses in-memory when FF disabled."""
        with patch.dict(os.environ, {"FF_USE_DATABASE_PERSISTENCE": "false"}):
            FeatureFlagManager._instance = None

            from src.modules.agents.orchestrator import AgentOrchestrator

            orchestrator = AgentOrchestrator(llm_service=mock_llm)
            user_id = uuid4()

            # Pre-populate in-memory state
            now = datetime.utcnow()
            state = ConversationState(
                user_id=user_id,
                session_id=None,
                current_agent=AgentType.COACH,
                history=[],
                context={},
                started_at=now,
                last_activity=now,
            )
            orchestrator._conversation_states[user_id] = state

            result = await orchestrator.get_conversation_state(user_id)

            assert result is not None
            assert result.user_id == user_id

    @pytest.mark.asyncio
    async def test_save_state_writes_to_both_when_flag_enabled(self, mock_llm):
        """Test that save writes to both in-memory and Redis when FF enabled."""
        with patch.dict(os.environ, {"FF_USE_DATABASE_PERSISTENCE": "true"}):
            FeatureFlagManager._instance = None

            from src.modules.agents.orchestrator import AgentOrchestrator

            orchestrator = AgentOrchestrator(llm_service=mock_llm)

            mock_store = AsyncMock()
            mock_store.set = AsyncMock()

            now = datetime.utcnow()
            user_id = uuid4()
            state = ConversationState(
                user_id=user_id,
                session_id=None,
                current_agent=AgentType.COACH,
                history=[],
                context={},
                started_at=now,
                last_activity=now,
            )

            with patch.object(orchestrator, "_get_state_store", return_value=mock_store):
                await orchestrator._save_conversation_state(user_id, state)

                # Check in-memory
                assert user_id in orchestrator._conversation_states

                # Check Redis
                mock_store.set.assert_called_once_with(user_id, state)

    @pytest.mark.asyncio
    async def test_fallback_to_memory_on_redis_error(self, mock_llm):
        """Test fallback to in-memory when Redis fails."""
        with patch.dict(os.environ, {"FF_USE_DATABASE_PERSISTENCE": "true"}):
            FeatureFlagManager._instance = None

            from src.modules.agents.orchestrator import AgentOrchestrator

            orchestrator = AgentOrchestrator(llm_service=mock_llm)

            mock_store = AsyncMock()
            mock_store.get = AsyncMock(side_effect=Exception("Redis connection failed"))

            user_id = uuid4()

            # Pre-populate in-memory as fallback
            now = datetime.utcnow()
            state = ConversationState(
                user_id=user_id,
                session_id=None,
                current_agent=AgentType.COACH,
                history=[],
                context={},
                started_at=now,
                last_activity=now,
            )
            orchestrator._conversation_states[user_id] = state

            with patch.object(orchestrator, "_get_state_store", return_value=mock_store):
                result = await orchestrator.get_conversation_state(user_id)

                # Should fallback to in-memory
                assert result is not None
                assert result.user_id == user_id

    @pytest.mark.asyncio
    async def test_reset_conversation_clears_both_stores(self, mock_llm):
        """Test that reset clears both in-memory and Redis."""
        with patch.dict(os.environ, {"FF_USE_DATABASE_PERSISTENCE": "true"}):
            FeatureFlagManager._instance = None

            from src.modules.agents.orchestrator import AgentOrchestrator

            orchestrator = AgentOrchestrator(llm_service=mock_llm)

            mock_store = AsyncMock()
            mock_store.delete = AsyncMock()

            user_id = uuid4()

            # Pre-populate in-memory
            now = datetime.utcnow()
            orchestrator._conversation_states[user_id] = ConversationState(
                user_id=user_id,
                session_id=None,
                current_agent=AgentType.COACH,
                history=[],
                context={},
                started_at=now,
                last_activity=now,
            )

            with patch.object(orchestrator, "_get_state_store", return_value=mock_store):
                await orchestrator.reset_conversation(user_id)

                # Check both cleared
                assert user_id not in orchestrator._conversation_states
                mock_store.delete.assert_called_once_with(user_id)


class TestClassifyIntent:
    """Tests for the exposed classify_intent method."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM service."""
        llm = MagicMock()
        llm.complete = AsyncMock(return_value=MagicMock(content="COACH"))
        return llm

    @pytest.fixture(autouse=True)
    def reset_singletons(self):
        """Reset singletons."""
        FeatureFlagManager._instance = None
        with patch.dict(os.environ, {"FF_USE_DATABASE_PERSISTENCE": "false"}):
            yield

    @pytest.mark.asyncio
    async def test_classify_intent_returns_coach_for_motivation(self, mock_llm):
        """Test that motivation-related messages route to coach."""
        mock_llm.complete = AsyncMock(return_value=MagicMock(content="COACH"))

        from src.modules.agents.orchestrator import AgentOrchestrator
        orchestrator = AgentOrchestrator(llm_service=mock_llm)

        result = await orchestrator.classify_intent("I'm feeling motivated today!")
        assert result == AgentType.COACH

    @pytest.mark.asyncio
    async def test_classify_intent_returns_socratic_for_explain(self, mock_llm):
        """Test that explain requests route to Socratic agent."""
        mock_llm.complete = AsyncMock(return_value=MagicMock(content="SOCRATIC"))

        from src.modules.agents.orchestrator import AgentOrchestrator
        orchestrator = AgentOrchestrator(llm_service=mock_llm)

        result = await orchestrator.classify_intent("Explain recursion to me")
        assert result == AgentType.SOCRATIC

    @pytest.mark.asyncio
    async def test_classify_intent_returns_assessment_for_quiz(self, mock_llm):
        """Test that quiz requests route to assessment agent."""
        mock_llm.complete = AsyncMock(return_value=MagicMock(content="ASSESSMENT"))

        from src.modules.agents.orchestrator import AgentOrchestrator
        orchestrator = AgentOrchestrator(llm_service=mock_llm)

        result = await orchestrator.classify_intent("Quiz me on Python")
        assert result == AgentType.ASSESSMENT

    @pytest.mark.asyncio
    async def test_classify_intent_with_state_context(self, mock_llm):
        """Test that classify_intent uses state for context."""
        mock_llm.complete = AsyncMock(return_value=MagicMock(content="DRILL_SERGEANT"))

        from src.modules.agents.orchestrator import AgentOrchestrator
        orchestrator = AgentOrchestrator(llm_service=mock_llm)

        now = datetime.utcnow()
        state = ConversationState(
            user_id=uuid4(),
            session_id=None,
            current_agent=AgentType.COACH,
            history=[
                {"role": "user", "content": "I want practice", "agent_type": None, "timestamp": now.isoformat()}
            ],
            context={},
            started_at=now,
            last_activity=now,
        )

        result = await orchestrator.classify_intent("Give me exercises", state)
        assert result == AgentType.DRILL_SERGEANT


class TestDatabaseContentServiceAdapters:
    """Tests for content service adapter registration."""

    @pytest.fixture(autouse=True)
    def reset_singletons(self):
        """Reset singletons."""
        FeatureFlagManager._instance = None
        yield

    def test_all_adapters_registered(self):
        """Test that all 6 content adapters are registered."""
        # Mock all adapters to avoid actual initialization
        with patch("src.modules.content.db_service.get_arxiv_adapter") as mock_arxiv, \
             patch("src.modules.content.db_service.get_rss_adapter") as mock_rss, \
             patch("src.modules.content.db_service.get_youtube_adapter") as mock_youtube, \
             patch("src.modules.content.db_service.get_github_adapter") as mock_github, \
             patch("src.modules.content.db_service.get_reddit_adapter") as mock_reddit, \
             patch("src.modules.content.db_service.get_twitter_adapter") as mock_twitter, \
             patch("src.modules.content.db_service.get_llm_service"):

            mock_arxiv.return_value = MagicMock()
            mock_rss.return_value = MagicMock()
            mock_youtube.return_value = MagicMock()
            mock_github.return_value = MagicMock()
            mock_reddit.return_value = MagicMock()
            mock_twitter.return_value = MagicMock()

            from src.modules.content.db_service import DatabaseContentService
            from src.shared.models import SourceType

            service = DatabaseContentService()

            # Check all source types have adapters
            assert SourceType.ARXIV in service._adapters
            assert SourceType.BLOG in service._adapters
            assert SourceType.NEWSLETTER in service._adapters
            assert SourceType.YOUTUBE in service._adapters
            assert SourceType.GITHUB in service._adapters
            assert SourceType.REDDIT in service._adapters
            assert SourceType.TWITTER in service._adapters

    def test_rss_adapter_shared_for_blog_and_newsletter(self):
        """Test that RSS adapter is shared for BLOG and NEWSLETTER types."""
        with patch("src.modules.content.db_service.get_arxiv_adapter"), \
             patch("src.modules.content.db_service.get_rss_adapter") as mock_rss, \
             patch("src.modules.content.db_service.get_youtube_adapter"), \
             patch("src.modules.content.db_service.get_github_adapter"), \
             patch("src.modules.content.db_service.get_reddit_adapter"), \
             patch("src.modules.content.db_service.get_twitter_adapter"), \
             patch("src.modules.content.db_service.get_llm_service"):

            rss_adapter = MagicMock()
            mock_rss.return_value = rss_adapter

            from src.modules.content.db_service import DatabaseContentService
            from src.shared.models import SourceType

            service = DatabaseContentService()

            # Both BLOG and NEWSLETTER should use the same RSS adapter
            assert service._adapters[SourceType.BLOG] is service._adapters[SourceType.NEWSLETTER]


class TestDatabaseHealthCheck:
    """Tests for database health check functionality."""

    @pytest.mark.asyncio
    async def test_check_db_health_success(self):
        """Test successful database health check."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        mock_engine = MagicMock()
        mock_engine.begin = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(return_value=None)
        ))

        with patch("src.shared.database.get_engine", return_value=mock_engine):
            from src.shared.database import check_db_health

            result = await check_db_health(max_retries=1, retry_delay=0)
            assert result is True

    @pytest.mark.asyncio
    async def test_check_db_health_failure_with_retries(self):
        """Test database health check with retries on failure."""
        mock_engine = MagicMock()
        mock_engine.begin = MagicMock(side_effect=Exception("Connection failed"))

        with patch("src.shared.database.get_engine", return_value=mock_engine):
            from src.shared.database import check_db_health

            result = await check_db_health(max_retries=2, retry_delay=0.01)
            assert result is False

    @pytest.mark.asyncio
    async def test_check_redis_health_success(self):
        """Test successful Redis health check."""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()

        with patch("src.shared.database.get_redis", return_value=mock_redis):
            from src.shared.database import check_redis_health

            result = await check_redis_health(max_retries=1, retry_delay=0)
            assert result is True

    @pytest.mark.asyncio
    async def test_check_redis_health_failure_with_retries(self):
        """Test Redis health check with retries on failure."""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(side_effect=Exception("Connection failed"))

        with patch("src.shared.database.get_redis", return_value=mock_redis):
            from src.shared.database import check_redis_health

            result = await check_redis_health(max_retries=2, retry_delay=0.01)
            assert result is False

    @pytest.mark.asyncio
    async def test_get_health_status_returns_all_components(self):
        """Test that get_health_status returns status for all components."""
        with patch("src.shared.database.check_db_health", return_value=True), \
             patch("src.shared.database.check_redis_health", return_value=True):

            from src.shared.database import get_health_status

            status = await get_health_status()

            assert "database" in status
            assert "redis" in status
            assert "overall" in status
            assert status["database"]["healthy"] is True
            assert status["redis"]["healthy"] is True
            assert status["overall"] is True

    @pytest.mark.asyncio
    async def test_get_health_status_overall_false_if_any_unhealthy(self):
        """Test that overall is False if any component is unhealthy."""
        with patch("src.shared.database.check_db_health", return_value=True), \
             patch("src.shared.database.check_redis_health", return_value=False):

            from src.shared.database import get_health_status

            status = await get_health_status()

            assert status["database"]["healthy"] is True
            assert status["redis"]["healthy"] is False
            assert status["overall"] is False


class TestStartupShutdown:
    """Tests for startup and shutdown lifecycle functions."""

    @pytest.mark.asyncio
    async def test_startup_raises_on_db_failure(self):
        """Test that startup raises RuntimeError on DB connection failure."""
        with patch("src.shared.database.check_db_health", return_value=False):
            from src.shared.database import startup

            with pytest.raises(RuntimeError, match="Failed to connect to database"):
                await startup()

    @pytest.mark.asyncio
    async def test_startup_raises_on_redis_failure(self):
        """Test that startup raises RuntimeError on Redis connection failure."""
        with patch("src.shared.database.check_db_health", return_value=True), \
             patch("src.shared.database.check_redis_health", return_value=False):

            from src.shared.database import startup

            with pytest.raises(RuntimeError, match="Failed to connect to Redis"):
                await startup()

    @pytest.mark.asyncio
    async def test_startup_succeeds_when_all_healthy(self):
        """Test that startup succeeds when all connections are healthy."""
        with patch("src.shared.database.check_db_health", return_value=True), \
             patch("src.shared.database.check_redis_health", return_value=True):

            from src.shared.database import startup

            # Should not raise
            await startup()

    @pytest.mark.asyncio
    async def test_shutdown_closes_all_connections(self):
        """Test that shutdown closes both DB and Redis connections."""
        with patch("src.shared.database.close_db") as mock_close_db, \
             patch("src.shared.database.close_redis") as mock_close_redis:

            from src.shared.database import shutdown

            await shutdown()

            mock_close_db.assert_called_once()
            mock_close_redis.assert_called_once()
