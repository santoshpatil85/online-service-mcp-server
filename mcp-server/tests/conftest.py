"""Pytest configuration and fixtures."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import Settings, AzureSettings, ServerSettings


@pytest.fixture(scope="session")
def event_loop() -> asyncio.AbstractEventLoop:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_settings() -> Settings:
    """Create mock settings."""
    return Settings(
        azure=AzureSettings(
            tenant_id="test-tenant",
            client_id="test-client",
            authority_host="https://login.microsoftonline.com",
        ),
        server=ServerSettings(
            host="127.0.0.1",
            port=8000,
            debug=True,
            log_level="DEBUG",
            backend_api_url="https://api.test.com",
            backend_api_timeout=10,
            readiness_check_backend=False,
        ),
    )


@pytest.fixture
def mock_rest_client() -> AsyncMock:
    """Create mock REST client."""
    return AsyncMock()


@pytest.fixture
def mock_azure_auth() -> MagicMock:
    """Create mock Azure auth."""
    with patch("src.auth.azure_identity.get_credential_manager") as mock:
        manager = MagicMock()
        manager.get_token = AsyncMock(return_value="test-token")
        manager.validate_authentication = AsyncMock(return_value=True)
        mock.return_value = manager
        yield mock
