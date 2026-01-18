"""FastMCP Server with health probes and Azure Workload Identity support."""
import json
import logging
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from fastmcp import FastMCP

from src.auth import validate_azure_auth
from src.clients import close_rest_client, get_rest_client
from src.config import get_logger, settings
from src.logging import setup_structured_logging
from src.models.schemas import (
    CreateTicketRequest,
    GetUserProfileRequest,
    HealthResponse,
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

# Initialize FastAPI app for health endpoints
app = FastAPI(title="MCP Server", version="1.0.0")


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


# ============================================================================
# Health Endpoints (Kubernetes Probes)
# ============================================================================


@app.get("/health/live", response_model=HealthResponse)
async def liveness_probe() -> HealthResponse:
    """
    Kubernetes liveness probe.
    
    Returns:
        HealthResponse indicating if the server process is alive.
    """
    return HealthResponse(
        status="alive",
        timestamp=datetime.utcnow(),
        service_version="1.0.0",
    )


@app.get("/health/ready", response_model=HealthResponse)
async def readiness_probe() -> HealthResponse:
    """
    Kubernetes readiness probe.
    
    Validates:
    - FastMCP server initialized
    - Azure AD token acquisition works
    - Lightweight backend dependency check
    
    Returns:
        HealthResponse indicating if the server is ready for traffic.
        
    Raises:
        HTTPException: If any readiness check fails.
    """
    dependencies: dict[str, str] = {}

    try:
        # Check 1: FastMCP tools registered
        logger.debug("Checking FastMCP initialization...")
        registered_tools = mcp_server.list_tools()
        if not registered_tools:
            raise RuntimeError("No MCP tools registered")
        dependencies["mcp_server"] = "healthy"
        logger.debug(f"FastMCP initialized with {len(registered_tools)} tools")

        # Check 2: Azure AD authentication
        logger.debug("Validating Azure AD authentication...")
        is_auth_valid = await validate_azure_auth()
        if not is_auth_valid:
            raise RuntimeError("Azure AD token acquisition failed")
        dependencies["azure_auth"] = "healthy"

        # Check 3: Backend service health (optional)
        if settings.server.readiness_check_backend:
            logger.debug("Checking backend service health...")
            rest_client = get_rest_client()
            backend_healthy = await rest_client.health_check()
            dependencies["backend_service"] = "healthy" if backend_healthy else "unhealthy"

            if not backend_healthy:
                raise RuntimeError("Backend service is not healthy")

        return HealthResponse(
            status="ready",
            timestamp=datetime.utcnow(),
            service_version="1.0.0",
            dependencies=dependencies,
        )

    except Exception as e:
        logger.error(f"Readiness probe failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Service not ready: {str(e)}",
        ) from e


@app.get("/health")
async def health() -> dict:
    """Simple health check endpoint."""
    return {"status": "healthy"}


# ============================================================================
# MCP HTTP Transport & Tool Discovery
# ============================================================================


@app.get("/_mcp/tools")
async def discover_tools() -> dict[str, Any]:
    """
    Discover available MCP tools.
    
    Returns:
        Dictionary with list of available tools and their schemas.
    """
    try:
        logger.info("Tool discovery request received")
        tools_list = mcp_server.list_tools()
        
        tools_data = []
        for tool in tools_list:
            tool_info = {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema if hasattr(tool, "input_schema") else {},
            }
            tools_data.append(tool_info)
        
        logger.info(f"Discovered {len(tools_data)} tools")
        return {
            "tools": tools_data,
            "total": len(tools_data),
        }
    except Exception as e:
        logger.error(f"Tool discovery failed: {e}")
        raise HTTPException(status_code=500, detail="Tool discovery failed") from e


@app.post("/_mcp/messages")
async def mcp_messages(message: dict[str, Any]) -> dict[str, Any]:
    """
    Handle MCP protocol messages for HTTP transport.
    
    Supports:
    - tools/call: Invoke a tool with arguments
    - tools/list: List available tools
    
    Args:
        message: MCP message payload with method and params.
        
    Returns:
        MCP response envelope with result or error.
        
    Raises:
        HTTPException: If message handling fails.
    """
    try:
        method = message.get("method", "").strip()
        params = message.get("params", {})
        
        logger.info(f"MCP message: method={method}")
        
        # Handle tools/list
        if method == "tools/list":
            tools_list = mcp_server.list_tools()
            tools_data = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema if hasattr(tool, "input_schema") else {},
                }
                for tool in tools_list
            ]
            return {
                "method": method,
                "result": {
                    "tools": tools_data,
                },
            }
        
        # Handle tools/call
        elif method == "tools/call":
            tool_name = params.get("name", "").strip()
            arguments = params.get("arguments", {})
            
            if not tool_name:
                raise ValueError("Missing required parameter: 'name'")
            
            logger.info(f"Invoking tool: {tool_name}")
            
            # Find and invoke the tool
            tools_list = mcp_server.list_tools()
            tool = next((t for t in tools_list if t.name == tool_name), None)
            
            if not tool:
                raise ValueError(f"Tool not found: {tool_name}")
            
            # Call the tool implementation
            try:
                # Get the tool function from mcp_server's registry
                tool_func = getattr(mcp_server, f"_tool_{tool_name}", None)
                if not tool_func:
                    # Fallback: try to find in registered tools
                    # FastMCP stores tools in internal structure
                    logger.warning(f"Tool function not found in registry: {tool_name}")
                    raise ValueError(f"Tool implementation not found: {tool_name}")
                
                result = await tool_func(**arguments)
                
                logger.info(f"Tool execution successful: {tool_name}")
                return {
                    "method": method,
                    "result": result,
                }
            except TypeError as e:
                logger.error(f"Tool invocation argument error: {e}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid arguments for tool '{tool_name}': {str(e)}",
                ) from e
            except Exception as e:
                logger.error(f"Tool execution failed: {tool_name} - {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Tool execution failed: {str(e)}",
                ) from e
        
        else:
            logger.warning(f"Unknown MCP method: {method}")
            raise HTTPException(
                status_code=400,
                detail=f"Unknown MCP method: {method}",
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MCP message handling error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


# ============================================================================
# Startup/Shutdown Events
# ============================================================================


@app.on_event("startup")
async def startup() -> None:
    """Handle application startup."""
    logger.info("MCP Server starting up...")
    logger.info(f"Backend API: {settings.server.backend_api_url}")
    logger.info(f"Log level: {settings.server.log_level}")
    
    # Log registered tools
    try:
        tools_list = mcp_server.list_tools()
        logger.info(f"Registered {len(tools_list)} MCP tools:")
        for tool in tools_list:
            logger.info(f"  - {tool.name}: {tool.description}")
    except Exception as e:
        logger.warning(f"Could not list tools during startup: {e}")


@app.on_event("shutdown")
async def shutdown() -> None:
    """Handle application shutdown."""
    logger.info("MCP Server shutting down...")
    await close_rest_client()


# ============================================================================
# Root Endpoint
# ============================================================================


@app.get("/")
async def root() -> dict:
    """Root endpoint."""
    return {
        "service": "mcp-server",
        "version": "1.0.0",
        "status": "operational",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=settings.server.host,
        port=settings.server.port,
        log_level=settings.server.log_level.lower(),
    )
