"""Client module initialization."""
from src.client.mcp_client import (
    MCPClient,
    close_mcp_client,
    get_mcp_client,
)
from src.client.tool_discoverer import ToolDefinition, ToolDiscoverer

__all__ = [
    "MCPClient",
    "get_mcp_client",
    "close_mcp_client",
    "ToolDefinition",
    "ToolDiscoverer",
]
