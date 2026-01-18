"""MCP Client for communicating with MCP Server using FastMCP."""
import logging
from typing import Any, Optional

from mcp import ClientSession
from mcp.client.http import HTTPClientTransport

from src.config import get_logger, settings

logger = get_logger(__name__)


class MCPClient:
    """FastMCP client for MCP Server."""

    def __init__(self, server_url: Optional[str] = None) -> None:
        """
        Initialize MCP Client.
        
        Args:
            server_url: Optional MCP Server URL (defaults to config).
        """
        self.server_url = server_url or settings.client.mcp_server_url
        self._session: Optional[ClientSession] = None
        self._tools_cache: Optional[list[dict[str, Any]]] = None

    async def _get_session(self) -> ClientSession:
        """Get or create MCP client session."""
        if self._session is None:
            # Use HTTP transport for communication with FastMCP Server
            transport = HTTPClientTransport(self.server_url)
            self._session = ClientSession(transport)
            await self._session.initialize()
        return self._session

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
            session = await self._get_session()
            
            # List available tools using MCP protocol
            response = await session.list_tools()
            
            tools_list = []
            if hasattr(response, 'tools') and response.tools:
                for tool in response.tools:
                    tool_info = {
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": tool.inputSchema if hasattr(tool, 'inputSchema') else {},
                    }
                    tools_list.append(tool_info)
            
            logger.info(f"Discovered {len(tools_list)} tools")
            self._tools_cache = tools_list
            return tools_list
            
        except Exception as e:
            logger.error(f"Tool discovery failed: {e}")
            raise RuntimeError(f"Tool discovery failed: {e}") from e

    async def get_cached_tools(self) -> Optional[list[dict[str, Any]]]:
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
            session = await self._get_session()
            
            # Call tool using MCP protocol
            result = await session.call_tool(tool_name, arguments)
            
            if result.isError:
                raise RuntimeError(f"Tool call returned error: {result.content}")
            
            logger.info(f"Tool invocation successful: {tool_name}")
            
            # Extract content from result
            if hasattr(result, 'content') and result.content:
                # Get first content item if it's a list
                if isinstance(result.content, list) and len(result.content) > 0:
                    content = result.content[0]
                    if hasattr(content, 'text'):
                        import json
                        try:
                            return json.loads(content.text)
                        except json.JSONDecodeError:
                            return {"result": content.text}
                    return content
                return result.content
            
            return {}
            
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
            session = await self._get_session()
            # Try to list tools as a health check
            await session.list_tools()
            return True
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False

    async def close(self) -> None:
        """Close MCP client session."""
        if self._session is not None:
            await self._session.close()
            self._session = None


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
