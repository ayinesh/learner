"""Test configuration and fixtures."""

import pytest
from unittest.mock import AsyncMock, MagicMock


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
