"""Pytest configuration for MCP Client."""
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_mcp_client():
    """Create mock MCP client."""
    client = MagicMock()
    client.discover_tools = AsyncMock()
    client.invoke_tool = AsyncMock()
    client.check_server_health = AsyncMock(return_value=True)
    return client
