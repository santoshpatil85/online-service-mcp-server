"""MCP Client for communicating with MCP Server."""
import json
import logging
from typing import Any, Optional

import httpx

from src.config import get_logger, settings

logger = get_logger(__name__)


class MCPClient:
    """HTTP client for MCP Server."""

    def __init__(self, server_url: Optional[str] = None) -> None:
        """
        Initialize MCP Client.
        
        Args:
            server_url: Optional MCP Server URL (defaults to config).
        """
        self.server_url = server_url or settings.client.mcp_server_url
        self._client: Optional[httpx.AsyncClient] = None
        self._tools_cache: Optional[dict[str, Any]] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=settings.client.request_timeout,
                headers={"User-Agent": "mcp-client/1.0"},
            )
        return self._client

    async def discover_tools(self) -> list[dict[str, Any]]:
        """
        Discover available tools from MCP Server.
        
        Returns:
            List of tool definitions with names, descriptions, and schemas.
            
        Raises:
            RuntimeError: If discovery fails.
        """
        try:
            logger.info(f"Discovering tools from {self.server_url}")
            client = await self._get_client()
            
            # MCP tools are discovered via introspection endpoint
            # In a real implementation, this would use the MCP protocol
            # For now, we'll use a discovery endpoint
            response = await client.get(
                f"{self.server_url}/_mcp/tools",
                timeout=settings.client.discovery_timeout,
            )
            response.raise_for_status()
            
            tools = response.json()
            logger.info(f"Discovered {len(tools.get('tools', []))} tools")
            self._tools_cache = tools
            return tools.get("tools", [])
            
        except httpx.TimeoutException as e:
            logger.error(f"Tool discovery timeout: {e}")
            raise RuntimeError(f"Tool discovery timed out: {e}") from e
        except httpx.HTTPError as e:
            logger.error(f"Tool discovery failed: {e}")
            raise RuntimeError(f"Tool discovery failed: {e}") from e

    async def get_cached_tools(self) -> Optional[dict[str, Any]]:
        """Get cached tools from last discovery."""
        return self._tools_cache

    async def invoke_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Invoke a tool on the MCP Server.
        
        Args:
            tool_name: Name of the tool to invoke.
            arguments: Tool arguments.
            
        Returns:
            Tool execution result.
            
        Raises:
            RuntimeError: If tool invocation fails.
        """
        try:
            logger.info(f"Invoking tool: {tool_name}")
            client = await self._get_client()
            
            payload = {
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments,
                },
            }
            
            response = await client.post(
                f"{self.server_url}/_mcp/messages",
                json=payload,
            )
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"Tool invocation successful: {tool_name}")
            return result
            
        except httpx.TimeoutException as e:
            logger.error(f"Tool invocation timeout: {tool_name}")
            raise RuntimeError(f"Tool invocation timed out: {e}") from e
        except httpx.HTTPStatusError as e:
            logger.error(f"Tool invocation failed: {tool_name} - {e.response.status_code}")
            raise RuntimeError(
                f"Tool invocation failed: {e.response.status_code}"
            ) from e
        except Exception as e:
            logger.error(f"Tool invocation error: {tool_name} - {e}")
            raise RuntimeError(f"Tool invocation failed: {e}") from e

    async def call_tool(
        self,
        tool_name: str,
        **kwargs: Any,
    ) -> Any:
        """
        Simple interface to call a tool with keyword arguments.
        
        Args:
            tool_name: Name of the tool.
            **kwargs: Tool arguments.
            
        Returns:
            Tool result.
        """
        result = await self.invoke_tool(tool_name, kwargs)
        
        # Extract result from MCP response envelope
        if "result" in result:
            return result["result"]
        return result

    async def check_server_health(self) -> bool:
        """
        Check if MCP Server is healthy.
        
        Returns:
            True if server is healthy.
        """
        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.server_url}/health/ready",
                timeout=5.0,
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None


# Global client instance
_client: Optional[MCPClient] = None


def get_mcp_client() -> MCPClient:
    """Get or create global MCP client."""
    global _client
    if _client is None:
        _client = MCPClient()
    return _client


async def close_mcp_client() -> None:
    """Close global MCP client."""
    global _client
    if _client is not None:
        await _client.close()
        _client = None
