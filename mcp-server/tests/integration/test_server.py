"""Integration tests for MCP Server."""
import pytest


# Note: Integration tests for FastMCP HTTP transport server
# These tests require the server to be running on port 3333
# To run integration tests:
#   1. Start the server: python -m src.main
#   2. Run tests: pytest tests/integration/test_server.py -v

@pytest.mark.skip(reason="Requires server running on port 3333")
def test_server_health() -> None:
    """Test server health endpoint.
    
    This test demonstrates that the FastMCP HTTP transport
    server is running and responding to health checks.
    """
    import httpx
    
    with httpx.Client() as client:
        response = client.get("http://localhost:3333/health")
        assert response.status_code == 200


@pytest.mark.skip(reason="Requires server running on port 3333")
def test_tool_discovery() -> None:
    """Test tool discovery endpoint.
    
    This test demonstrates that the server exposes
    available MCP tools via the standard HTTP transport.
    """
    import httpx
    
    with httpx.Client() as client:
        response = client.get("http://localhost:3333/tools")
        assert response.status_code == 200
        data = response.json()
        assert "tools" in data

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
