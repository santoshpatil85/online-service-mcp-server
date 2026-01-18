"""Integration tests for MCP Server health probes."""
import pytest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from src.main import app


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    return TestClient(app)


def test_liveness_probe(client: TestClient) -> None:
    """Test liveness probe endpoint."""
    response = client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert data["service_version"] == "1.0.0"
    assert "timestamp" in data


def test_readiness_probe_success(client: TestClient) -> None:
    """Test readiness probe when all checks pass."""
    with patch("src.main.validate_azure_auth", new_callable=AsyncMock, return_value=True):
        with patch("src.main.get_rest_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.health_check = AsyncMock(return_value=True)
            mock_get_client.return_value = mock_client
            
            response = client.get("/health/ready")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ready"
            assert data["dependencies"]["azure_auth"] == "healthy"


def test_readiness_probe_auth_failure(client: TestClient) -> None:
    """Test readiness probe when Azure auth fails."""
    with patch("src.main.validate_azure_auth", new_callable=AsyncMock, return_value=False):
        response = client.get("/health/ready")
        assert response.status_code == 503


def test_health_endpoint(client: TestClient) -> None:
    """Test simple health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_root_endpoint(client: TestClient) -> None:
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "mcp-server"
    assert data["version"] == "1.0.0"
    assert data["status"] == "operational"
