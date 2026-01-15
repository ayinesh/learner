"""Test configuration and fixtures."""

import sys
from pathlib import Path

# Load environment variables before any imports that need them
from dotenv import load_dotenv
project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env")

# Ensure src is in path
sys.path.insert(0, str(project_root))

import pytest
from unittest.mock import AsyncMock, MagicMock


# Use session-scoped event loop to avoid "Event loop is closed" errors
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    import asyncio
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def reset_db_engine():
    """Reset database engine between tests to avoid connection pool issues."""
    yield
    # Reset the global engine after each test
    from src.shared import database
    if database._engine is not None:
        await database._engine.dispose()
        database._engine = None
        database._session_factory = None


@pytest.fixture
def mock_supabase():
    """Mock Supabase client."""
    client = MagicMock()
    client.auth = MagicMock()
    client.table = MagicMock(return_value=MagicMock())
    return client


@pytest.fixture
def mock_llm_service():
    """Mock LLM service."""
    service = AsyncMock()
    service.complete = AsyncMock(return_value=MagicMock(
        content="Test response",
        model="claude-sonnet-4-20250514",
        usage={"input_tokens": 10, "output_tokens": 20},
    ))
    return service


@pytest.fixture
def sample_user_id():
    """Sample user UUID."""
    from uuid import UUID
    return UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def sample_topic_id():
    """Sample topic UUID."""
    from uuid import UUID
    return UUID("87654321-4321-8765-4321-876543218765")
