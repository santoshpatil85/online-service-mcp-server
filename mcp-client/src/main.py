"""MCP Client main entry point."""
import asyncio
import logging
import sys

from src.config import get_logger, settings
from src.client import get_mcp_client, ToolDiscoverer

logger = get_logger(__name__)


async def main() -> None:
    """Run MCP Client discovery and example tool invocation."""
    try:
        logger.info("MCP Client starting...")
        
        client = get_mcp_client()
        
        # Check server health
        logger.info(f"Checking MCP Server health: {settings.client.mcp_server_url}")
        is_healthy = await client.check_server_health()
        if not is_healthy:
            logger.error("MCP Server is not healthy")
            return
        
        logger.info("MCP Server is healthy")
        
        # Discover tools
        logger.info("Discovering tools from MCP Server...")
        discoverer = ToolDiscoverer()
        tools = await discoverer.discover_tools()
        
        logger.info(f"Discovered {len(tools)} tools:")
        for tool_name in discoverer.list_tools():
            tool = discoverer.get_tool(tool_name)
            if tool:
                logger.info(f"  - {tool_name}: {tool.description}")
        
        # Example: Invoke a tool
        if "get_user_profile" in discoverer.list_tools():
            logger.info("Invoking get_user_profile tool...")
            result = await client.call_tool(
                "get_user_profile",
                user_id="user-123",
                include_details=False,
            )
            logger.info(f"Result: {result}")
        
        logger.info("MCP Client completed successfully")
        
    except Exception as e:
        logger.error(f"MCP Client failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        from src.client import close_mcp_client
        await close_mcp_client()


if __name__ == "__main__":
    asyncio.run(main())
