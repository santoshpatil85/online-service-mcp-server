"""FastMCP Server with Azure Workload Identity support."""
import logging

from fastmcp import FastMCP

from src.auth import validate_azure_auth
from src.clients import close_rest_client
from src.config import get_logger, settings
from src.logging import setup_structured_logging
from src.models.schemas import (
    CreateTicketRequest,
    GetUserProfileRequest,
    ListTicketsRequest,
    QueryDataRequest,
)
from src.tools import (
    create_ticket,
    get_user_profile,
    list_tickets,
    list_users,
    query_data,
)
from src.tools.user_tools import ListUsersRequest

# Setup structured logging
setup_structured_logging(settings.server.log_level)
logger = get_logger(__name__)

# Initialize FastMCP server
mcp_server = FastMCP(name="service-mcp-server")

# ============================================================================
# MCP Tools Registration
# ============================================================================


@mcp_server.tool(
    name="get_user_profile",
    description="Retrieve user profile from the service",
)
async def tool_get_user_profile(user_id: str, include_details: bool = False) -> dict:
    """MCP wrapper for get_user_profile."""
    request = GetUserProfileRequest(user_id=user_id, include_details=include_details)
    profile = await get_user_profile(request)
    return profile.model_dump(mode="json")


@mcp_server.tool(
    name="list_users",
    description="List users from the service with pagination",
)
async def tool_list_users(skip: int = 0, limit: int = 10) -> dict:
    """MCP wrapper for list_users."""
    request = ListUsersRequest(skip=skip, limit=limit)
    response = await list_users(request)
    return response.model_dump(mode="json")


@mcp_server.tool(
    name="create_ticket",
    description="Create a support ticket in the service",
)
async def tool_create_ticket(
    title: str,
    description: str,
    priority: str = "medium",
    assignee_id: str | None = None,
) -> dict:
    """MCP wrapper for create_ticket."""
    request = CreateTicketRequest(
        title=title,
        description=description,
        priority=priority,
        assignee_id=assignee_id,
    )
    ticket = await create_ticket(request)
    return ticket.model_dump(mode="json")


@mcp_server.tool(
    name="list_tickets",
    description="List support tickets from the service",
)
async def tool_list_tickets(
    status: str | None = None, skip: int = 0, limit: int = 10
) -> dict:
    """MCP wrapper for list_tickets."""
    request = ListTicketsRequest(status=status, skip=skip, limit=limit)
    response = await list_tickets(request)
    return response.model_dump(mode="json")


@mcp_server.tool(
    name="query_data",
    description="Query data from the service datasets",
)
async def tool_query_data(
    dataset: str,
    filters: dict | None = None,
    limit: int = 100,
) -> dict:
    """MCP wrapper for query_data."""
    request = QueryDataRequest(dataset=dataset, filters=filters, limit=limit)
    response = await query_data(request)
    return response.model_dump(mode="json")


if __name__ == "__main__":
    logger.info("MCP Server starting up...")
    logger.info(f"Host: {settings.server.host}:{settings.server.port}")
    logger.info(f"Log level: {settings.server.log_level}")
    
    # Log registered tools
    try:
        tools_list = mcp_server.list_tools()
        logger.info(f"Registered {len(tools_list)} MCP tools:")
        for tool in tools_list:
            logger.info(f"  - {tool.name}: {tool.description}")
    except Exception as e:
        logger.warning(f"Could not list tools during startup: {e}")
    
    try:
        # Run FastMCP server with HTTP transport
        mcp_server.run(
            transport="http",
            host=settings.server.host,
            port=settings.server.port,
        )
    except KeyboardInterrupt:
        logger.info("MCP Server shutdown requested")
    except Exception as e:
        logger.error(f"MCP Server error: {e}")
        raise
    finally:
        logger.info("MCP Server shutting down...")

