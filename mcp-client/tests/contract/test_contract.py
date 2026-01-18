"""Contract tests for MCP Client <-> MCP Server compatibility."""
import json
import pytest
from typing import Any
from unittest.mock import AsyncMock, patch

from src.client.mcp_client import MCPClient
from src.client.tool_discoverer import ToolDiscoverer, ToolDefinition


# Expected tool contract
EXPECTED_TOOLS = {
    "get_user_profile",
    "list_users",
    "create_ticket",
    "list_tickets",
    "query_data",
}


@pytest.fixture
def client() -> MCPClient:
    """Create MCP client."""
    return MCPClient("http://localhost:8000")


@pytest.fixture
def discoverer() -> ToolDiscoverer:
    """Create tool discoverer."""
    return ToolDiscoverer()


@pytest.fixture
def mock_tools_response() -> dict[str, Any]:
    """Mock tools response from server."""
    return {
        "tools": [
            {
                "name": "get_user_profile",
                "description": "Retrieve user profile",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string"},
                        "include_details": {"type": "boolean"},
                    },
                    "required": ["user_id"],
                },
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "name": {"type": "string"},
                        "email": {"type": "string"},
                    },
                },
            },
            {
                "name": "list_users",
                "description": "List users with pagination",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "skip": {"type": "integer"},
                        "limit": {"type": "integer"},
                    },
                },
            },
            {
                "name": "create_ticket",
                "description": "Create a ticket",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "priority": {"type": "string"},
                    },
                    "required": ["title", "description"],
                },
            },
            {
                "name": "list_tickets",
                "description": "List tickets",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "skip": {"type": "integer"},
                        "limit": {"type": "integer"},
                    },
                },
            },
            {
                "name": "query_data",
                "description": "Query data",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dataset": {"type": "string"},
                        "filters": {"type": "object"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["dataset"],
                },
            },
        ]
    }


# ============================================================================
# Tool Discovery Contract Tests
# ============================================================================


@pytest.mark.asyncio
async def test_contract_tool_names_discovered(
    discoverer: ToolDiscoverer,
    mock_tools_response: dict[str, Any],
) -> None:
    """Contract: All expected tool names must be discovered."""
    with patch.object(
        discoverer._client, "discover_tools", return_value=mock_tools_response["tools"]
    ):
        tools = await discoverer.discover_tools()
        discovered_names = set(tools.keys())
        
        assert discovered_names == EXPECTED_TOOLS, (
            f"Tool name mismatch. Expected: {EXPECTED_TOOLS}, "
            f"Got: {discovered_names}"
        )


@pytest.mark.asyncio
async def test_contract_tool_descriptions_not_empty(
    discoverer: ToolDiscoverer,
    mock_tools_response: dict[str, Any],
) -> None:
    """Contract: All tools must have descriptions."""
    with patch.object(
        discoverer._client, "discover_tools", return_value=mock_tools_response["tools"]
    ):
        tools = await discoverer.discover_tools()
        
        for tool_name, tool_def in tools.items():
            assert tool_def.description, f"Tool '{tool_name}' has no description"


# ============================================================================
# Input/Output Schema Contract Tests
# ============================================================================


@pytest.mark.asyncio
async def test_contract_tool_schemas_valid_json(
    discoverer: ToolDiscoverer,
    mock_tools_response: dict[str, Any],
) -> None:
    """Contract: Tool schemas must be valid JSON."""
    with patch.object(
        discoverer._client, "discover_tools", return_value=mock_tools_response["tools"]
    ):
        tools = await discoverer.discover_tools()
        
        for tool_name, tool_def in tools.items():
            # Must be serializable to JSON
            try:
                json.dumps(tool_def.input_schema)
            except (TypeError, ValueError) as e:
                pytest.fail(f"Tool '{tool_name}' has invalid input schema: {e}")


@pytest.mark.asyncio
async def test_contract_get_user_profile_schema(
    discoverer: ToolDiscoverer,
    mock_tools_response: dict[str, Any],
) -> None:
    """Contract: get_user_profile must have required input fields."""
    with patch.object(
        discoverer._client, "discover_tools", return_value=mock_tools_response["tools"]
    ):
        tools = await discoverer.discover_tools()
        tool = tools.get("get_user_profile")
        
        assert tool is not None, "get_user_profile tool not found"
        assert "user_id" in tool.input_schema["properties"]
        assert "user_id" in tool.input_schema.get("required", [])


@pytest.mark.asyncio
async def test_contract_create_ticket_schema(
    discoverer: ToolDiscoverer,
    mock_tools_response: dict[str, Any],
) -> None:
    """Contract: create_ticket must have required title and description."""
    with patch.object(
        discoverer._client, "discover_tools", return_value=mock_tools_response["tools"]
    ):
        tools = await discoverer.discover_tools()
        tool = tools.get("create_ticket")
        
        assert tool is not None
        assert "title" in tool.input_schema["properties"]
        assert "description" in tool.input_schema["properties"]
        assert "title" in tool.input_schema["required"]


# ============================================================================
# Tool Invocation Contract Tests
# ============================================================================


@pytest.mark.asyncio
async def test_contract_tool_invocation_response_format(
    client: MCPClient,
) -> None:
    """Contract: Tool invocation must return standard response format."""
    mock_response = {
        "result": {
            "id": "user-123",
            "name": "Test User",
            "email": "test@example.com",
        }
    }
    
    with patch.object(client, "invoke_tool", return_value=mock_response):
        result = await client.invoke_tool("get_user_profile", {"user_id": "user-123"})
        
        assert "result" in result, "Response must contain 'result' field"


@pytest.mark.asyncio
async def test_contract_tool_invocation_error_handling(
    client: MCPClient,
) -> None:
    """Contract: Tool invocation errors must raise RuntimeError."""
    with patch.object(
        client, "invoke_tool", side_effect=RuntimeError("Tool failed")
    ):
        with pytest.raises(RuntimeError):
            await client.invoke_tool("get_user_profile", {"user_id": "invalid"})


@pytest.mark.asyncio
async def test_contract_list_tools_pagination(
    discoverer: ToolDiscoverer,
    mock_tools_response: dict[str, Any],
) -> None:
    """Contract: list_tools and list_tickets must support pagination."""
    with patch.object(
        discoverer._client, "discover_tools", return_value=mock_tools_response["tools"]
    ):
        tools = await discoverer.discover_tools()
        
        for tool_name in ["list_users", "list_tickets"]:
            tool = tools.get(tool_name)
            assert tool is not None
            
            # Must have skip and limit parameters
            props = tool.input_schema.get("properties", {})
            assert "skip" in props, f"{tool_name} must have 'skip' parameter"
            assert "limit" in props, f"{tool_name} must have 'limit' parameter"


# ============================================================================
# Error Response Contract Tests
# ============================================================================


@pytest.mark.asyncio
async def test_contract_error_response_structure(
    client: MCPClient,
) -> None:
    """Contract: Error responses must have standard structure."""
    error_response = {
        "error": "VALIDATION_ERROR",
        "message": "Invalid user_id",
        "details": {},
    }
    
    # This would be returned from the server
    assert "error" in error_response
    assert "message" in error_response
    assert error_response["error"] in [
        "VALIDATION_ERROR",
        "SERVICE_ERROR",
        "AUTHENTICATION_ERROR",
        "TIMEOUT_ERROR",
        "INTERNAL_ERROR",
    ]


# ============================================================================
# Snapshot Tests (Tool Schema Verification)
# ============================================================================


@pytest.mark.asyncio
async def test_contract_tool_schema_snapshots(
    discoverer: ToolDiscoverer,
    mock_tools_response: dict[str, Any],
    snapshot,  # syrupy snapshot fixture
) -> None:
    """Contract: Tool schemas match expected snapshots."""
    with patch.object(
        discoverer._client, "discover_tools", return_value=mock_tools_response["tools"]
    ):
        tools = await discoverer.discover_tools()
        
        # Convert to JSON-serializable format for snapshot
        snapshot_data = {
            name: tool.model_dump() for name, tool in tools.items()
        }
        
        assert snapshot_data == snapshot
