"""Tool discoverer and schema validator."""
import json
import logging
from typing import Any, Optional

from pydantic import ValidationError, BaseModel

from src.client.mcp_client import get_mcp_client
from src.config import get_logger

logger = get_logger(__name__)


class ToolDefinition(BaseModel):
    """Tool definition model."""

    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: Optional[dict[str, Any]] = None


class ToolDiscoverer:
    """Discovers and validates tools from MCP Server."""

    def __init__(self) -> None:
        """Initialize tool discoverer."""
        self._discovered_tools: dict[str, ToolDefinition] = {}
        self._client = get_mcp_client()

    async def discover_tools(self) -> dict[str, ToolDefinition]:
        """
        Discover all tools from server.
        
        Returns:
            Dictionary of tool name -> ToolDefinition.
            
        Raises:
            RuntimeError: If discovery fails.
        """
        try:
            logger.info("Starting tool discovery")
            tools_list = await self._client.discover_tools()
            
            self._discovered_tools = {}
            for tool_data in tools_list:
                try:
                    tool = ToolDefinition(**tool_data)
                    self._discovered_tools[tool.name] = tool
                except ValidationError as e:
                    logger.warning(f"Invalid tool definition: {tool_data.get('name')} - {e}")
            
            logger.info(f"Discovered {len(self._discovered_tools)} valid tools")
            return self._discovered_tools
            
        except Exception as e:
            logger.error(f"Tool discovery failed: {e}")
            raise RuntimeError(f"Failed to discover tools: {e}") from e

    def get_tool(self, tool_name: str) -> Optional[ToolDefinition]:
        """Get a specific tool definition."""
        return self._discovered_tools.get(tool_name)

    def list_tools(self) -> list[str]:
        """List all discovered tool names."""
        return list(self._discovered_tools.keys())

    def validate_arguments(self, tool_name: str, arguments: dict[str, Any]) -> bool:
        """
        Validate arguments for a tool.
        
        Args:
            tool_name: Name of the tool.
            arguments: Tool arguments to validate.
            
        Returns:
            True if arguments are valid.
        """
        tool = self.get_tool(tool_name)
        if not tool:
            logger.warning(f"Tool not found: {tool_name}")
            return False
        
        try:
            # Simple validation: check required fields in input schema
            input_schema = tool.input_schema
            required_fields = input_schema.get("required", [])
            
            for field in required_fields:
                if field not in arguments:
                    logger.warning(f"Missing required argument '{field}' for tool '{tool_name}'")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Validation error for {tool_name}: {e}")
            return False

    def get_tool_schema_json(self, tool_name: str) -> Optional[str]:
        """Get tool schema as JSON."""
        tool = self.get_tool(tool_name)
        if tool:
            return json.dumps(tool.model_dump(), indent=2)
        return None
