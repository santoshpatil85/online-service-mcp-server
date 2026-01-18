# MCP Client - Architecture

This document describes the FastMCP Client architecture, tool discovery, invocation patterns, and deployment on AKS.

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Client Design](#client-design)
3. [Tool Discovery](#tool-discovery)
4. [Tool Invocation](#tool-invocation)
5. [Error Handling](#error-handling)
6. [Configuration](#configuration)
7. [Technology Stack](#technology-stack)
8. [Testing](#testing)

## System Architecture

### High-Level Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                    AKS Cluster                                   │
│                                                                  │
│  ┌─ Namespace: mcp-system ──────────────────────────────────┐   │
│  │                                                          │   │
│  │  ┌─────────────────────────────────────────────────────┐ │   │
│  │  │ MCP Client Pod (FastMCP HTTP Client)               │ │   │
│  │  │                                                     │ │   │
│  │  │ ┌──────────────────────────────────────────────┐  │ │   │
│  │  │ │ MCPClient (FastMCP SDK)                      │  │ │   │
│  │  │ │ ├─ ClientSession                            │  │ │   │
│  │  │ │ ├─ HTTPClientTransport                      │  │ │   │
│  │  │ │ ├─ Tool Discovery (list_tools)             │  │ │   │
│  │  │ │ └─ Tool Invocation (call_tool)             │  │ │   │
│  │  │ └──────────────────────────────────────────────┘  │ │   │
│  │  │                       │                            │ │   │
│  │  │                       │ HTTP/TCP                   │ │   │
│  │  │              ┌────────┴─────────┐                 │ │   │
│  │  │              │ Kubernetes DNS   │                 │ │   │
│  │  │              │ mcp-server:3333  │                 │ │   │
│  │  │              └──────────────────┘                 │ │   │
│  │  │                       │                            │ │   │
│  │  │                       ▼                            │ │   │
│  │  │ ┌──────────────────────────────────────────────┐  │ │   │
│  │  │ │ MCP Server Service (ClusterIP)               │  │ │   │
│  │  │ │ Port: 3333                                   │  │ │   │
│  │  │ │ Selector: app=mcp-server                     │  │ │   │
│  │  │ └──────────────────────────────────────────────┘  │ │   │
│  │  │                       │                            │ │   │
│  │  │ ┌─────────────────────┴──────────────────────────┐ │   │
│  │  │ │                                                │ │   │
│  │  │ ▼                                                ▼ │   │
│  │  │ ┌──────────────────────────┐  ┌──────────────────┐ │   │
│  │  │ │ MCP Server Pod (Replica) │  │ MCP Server Pod   │ │   │
│  │  │ │ FastMCP on :3333         │  │ (Replica 2)      │ │   │
│  │  │ │ ├─ Tool: get_user_profile│  │                  │ │   │
│  │  │ │ ├─ Tool: create_ticket   │  │ (Load balanced)  │ │   │
│  │  │ │ ├─ Tool: query_data      │  │                  │ │   │
│  │  │ │ └─ /health endpoint      │  │                  │ │   │
│  │  │ └──────────────────────────┘  └──────────────────┘ │   │
│  │  │                                                     │ │   │
│  │  │ ServiceAccount: "mcp-client"                       │ │   │
│  │  │ Replicas: 2-5 (HPA: CPU 70%, Memory 80%)          │ │   │
│  │  │ Environment:                                        │ │   │
│  │  │  ├─ MCP_SERVER_URL=http://mcp-server:3333        │ │   │
│  │  │  ├─ LOG_LEVEL=INFO                               │ │   │
│  │  │  ├─ REQUEST_TIMEOUT=30s                          │ │   │
│  │  │  └─ DISCOVERY_TIMEOUT=10s                        │ │   │
│  │  │                                                     │ │   │
│  │  └─────────────────────────────────────────────────────┘ │   │
│  │                                                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Client-Server Communication Flow

```
CLIENT POD                          SERVER POD
    │                                   │
    │  1. Discover Tools                │
    ├──────────────────────────────────>│
    │     GET /tools (MCP protocol)     │
    │                                   │
    │<──────────────────────────────────┤
    │     200 OK: [tool_name, schema]   │
    │                                   │
    │  2. Cache Tools Locally            │
    │     (until TTL expires)            │
    │                                   │
    │  3. Invoke Tool (on-demand)       │
    ├──────────────────────────────────>│
    │  POST /messages (MCP protocol)    │
    │  Body: {method: "tools/call",     │
    │         params: {name, args}}     │
    │                                   │
    │<──────────────────────────────────┤
    │     200 OK: {result} or error     │
    │                                   │
    │  4. Error Handling                │
    │     On timeout: Retry with backoff│
    │     On 503: Exponential backoff   │
    │     On bad schema: Log & skip     │
    │                                   │
```

## Client Design

### MCPClient Implementation

```python
# src/client/mcp_client.py
from mcp import ClientSession
from mcp.client.http import HTTPClientTransport
from typing import Any, Dict, List

class MCPClient:
    """FastMCP HTTP client with tool discovery and invocation."""
    
    def __init__(self, server_url: str = None):
        self.server_url = server_url or settings.mcp_server_url
        self._session: Optional[ClientSession] = None
        self._tools_cache: Optional[List[Tool]] = None
        self._cache_ttl = 300  # 5 minutes
    
    async def _get_session(self) -> ClientSession:
        """Get or create MCP client session with HTTP transport."""
        if not self._session:
            transport = HTTPClientTransport(
                self.server_url,
                timeout=settings.request_timeout
            )
            self._session = ClientSession(transport)
        
        return self._session
    
    async def discover_tools(self) -> Dict[str, Tool]:
        """
        Discover available tools from MCP server.
        
        Returns mapping of tool_name → Tool object with:
        - name: tool name
        - description: human-readable description
        - input_schema: JSON Schema for input validation
        """
        session = await self._get_session()
        
        try:
            # Use MCP protocol to list tools
            tools = await asyncio.wait_for(
                session.list_tools(),
                timeout=settings.discovery_timeout
            )
            
            # Convert to dict for easy lookup
            self._tools_cache = {tool.name: tool for tool in tools}
            
            logger.info(f"Discovered {len(self._tools_cache)} tools")
            return self._tools_cache
        
        except asyncio.TimeoutError:
            logger.error(f"Tool discovery timeout after {settings.discovery_timeout}s")
            raise
        except Exception as e:
            logger.error(f"Tool discovery failed: {e}")
            raise
    
    async def invoke_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Any:
        """
        Invoke a tool on the remote MCP server.
        
        Args:
            tool_name: Name of tool to invoke
            arguments: Tool input arguments (JSON serializable)
        
        Returns:
            Tool result (schema-validated on server side)
        
        Raises:
            ToolNotFound: If tool not registered on server
            ValidationError: If arguments don't match tool's input schema
            ServiceError: If tool execution fails on server
            TimeoutError: If invocation exceeds timeout
        """
        session = await self._get_session()
        
        try:
            logger.debug(f"Invoking tool: {tool_name} with args: {arguments}")
            
            # Use MCP protocol to call tool
            result = await asyncio.wait_for(
                session.call_tool(tool_name, arguments),
                timeout=settings.request_timeout
            )
            
            logger.debug(f"Tool {tool_name} completed successfully")
            return result
        
        except asyncio.TimeoutError:
            logger.error(f"Tool invocation timeout: {tool_name}")
            raise
        except Exception as e:
            logger.error(f"Tool invocation failed ({tool_name}): {e}")
            raise
    
    async def close(self):
        """Close MCP client session."""
        if self._session:
            await self._session.close()
            self._session = None
```

## Tool Discovery

### Discovery Protocol

Tool discovery is performed via the MCP protocol's `list_tools` method:

```python
async def discover_tools() -> List[Tool]:
    """
    Client sends: GET /tools (or MCP list_tools request)
    
    Server responds with:
    [
        {
            "name": "get_user_profile",
            "description": "Retrieve user profile from backend service",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User ID"},
                    "include_details": {"type": "boolean", "default": false}
                },
                "required": ["user_id"]
            }
        },
        {
            "name": "create_ticket",
            ...
        },
        ...
    ]
    """
```

### Schema Validation

Tool schemas are automatically validated:

```python
# Client validates incoming schemas
class Tool(BaseModel):
    name: str
    description: str
    inputSchema: Dict[str, Any]  # JSON Schema
    
# Before invocation, client checks:
# 1. Tool exists in schema
# 2. All required parameters provided
# 3. Parameter types match schema
# 4. String lengths/patterns respected

# Example: Invalid invocation detection
tools = await client.discover_tools()
get_user_profile_schema = tools["get_user_profile"].inputSchema

# ❌ Missing required parameter
try:
    await client.invoke_tool("get_user_profile", {})
    # Schema validation fails before sending to server
except ValidationError as e:
    logger.error(f"Schema validation failed: {e}")
```

## Tool Invocation

### Synchronous Wrapper

For applications that can't use async:

```python
# src/client/sync_wrapper.py
import asyncio
from typing import Any, Dict

class SyncMCPClient:
    """Synchronous wrapper around async MCPClient."""
    
    def __init__(self, server_url: str = None):
        self.client = MCPClient(server_url)
    
    def discover_tools(self) -> Dict[str, Any]:
        """Blocking tool discovery."""
        return asyncio.run(self.client.discover_tools())
    
    def invoke_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Blocking tool invocation."""
        return asyncio.run(self.client.invoke_tool(tool_name, arguments))
    
    def __del__(self):
        """Cleanup on deletion."""
        asyncio.run(self.client.close())
```

### Retry Strategy

```python
async def invoke_tool_with_retry(
    client: MCPClient,
    tool_name: str,
    arguments: Dict[str, Any],
    max_retries: int = 3
) -> Any:
    """
    Invoke tool with exponential backoff retry on transient errors.
    """
    for attempt in range(max_retries):
        try:
            return await client.invoke_tool(tool_name, arguments)
        
        except (asyncio.TimeoutError, ConnectionError) as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                logger.warning(f"Retry {attempt + 1}/{max_retries} after {wait_time}s")
                await asyncio.sleep(wait_time)
            else:
                raise
```

## Error Handling

### Error Response Structure

```python
# Server errors are formatted as MCP errors
{
    "error": {
        "code": "INVALID_INPUT",
        "message": "user_id is required",
        "data": {...}  # Optional context
    }
}

# Client error categories
class ToolError(Exception):
    """Base error for tool-related failures."""
    pass

class ToolNotFound(ToolError):
    """Tool does not exist on server."""
    pass

class InvalidInput(ToolError):
    """Input arguments don't match tool schema."""
    pass

class ServiceError(ToolError):
    """Tool execution failed on server side."""
    pass

class TimeoutError(ToolError):
    """Tool execution exceeded timeout."""
    pass
```

### Error Handling Pattern

```python
async def safe_invoke_tool(
    client: MCPClient,
    tool_name: str,
    arguments: Dict[str, Any]
) -> Tuple[bool, Any]:
    """
    Invoke tool with error handling.
    
    Returns:
        (success: bool, result: Any)
    """
    try:
        result = await client.invoke_tool(tool_name, arguments)
        return True, result
    
    except ToolNotFound:
        logger.error(f"Tool not available: {tool_name}")
        return False, {"error": "Tool not found"}
    
    except InvalidInput as e:
        logger.error(f"Invalid input for {tool_name}: {e}")
        return False, {"error": f"Invalid input: {e}"}
    
    except ServiceError as e:
        logger.error(f"Server error in {tool_name}: {e}")
        return False, {"error": f"Service error: {e}"}
    
    except asyncio.TimeoutError:
        logger.error(f"Tool invocation timeout: {tool_name}")
        return False, {"error": "Request timeout"}
    
    except Exception as e:
        logger.error(f"Unexpected error in {tool_name}: {e}")
        return False, {"error": f"Unexpected error: {e}"}
```

## Configuration

### Environment Variables

```yaml
# Pod environment in Kubernetes
env:
  - name: "MCP_SERVER_URL"
    value: "http://mcp-server:3333"
    # Full FQDN: http://mcp-server.mcp-system.svc.cluster.local:3333
  
  - name: "LOG_LEVEL"
    value: "INFO"  # DEBUG, INFO, WARNING, ERROR
  
  - name: "REQUEST_TIMEOUT"
    value: "30"    # Seconds for individual tool invocations
  
  - name: "DISCOVERY_TIMEOUT"
    value: "10"    # Seconds for tool discovery
```

### Pydantic Settings

```python
# src/config.py
from pydantic_settings import BaseSettings

class ClientSettings(BaseSettings):
    # Server connection
    mcp_server_url: str = "http://mcp-server:3333"
    request_timeout: float = 30.0
    discovery_timeout: float = 10.0
    
    # Logging
    log_level: str = "INFO"
    
    # Retry behavior
    max_retries: int = 3
    backoff_factor: float = 2.0  # exponential
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = ClientSettings()
```

## Technology Stack

### Core Dependencies

- **fastmcp >= 0.1.0**: MCP client SDK with HTTP transport
- **mcp >= 0.1.0**: Protocol definitions
- **pydantic >= 2.5.0**: Type validation
- **pydantic-settings**: Configuration from environment
- **httpx >= 0.25.0**: Async HTTP client (used by HTTP transport)
- **Python 3.11+**: Language requirement

### Development Dependencies

- **pytest >= 7.0**: Unit testing
- **pytest-asyncio >= 0.21.0**: Async test support
- **syrupy >= 4.0**: Snapshot testing for contract tests
- **black**: Code formatter
- **isort**: Import sorting
- **pylint**: Linter

## Testing

### Contract Tests

Contract tests verify that the client and server remain compatible:

```python
# tests/contract/test_contract.py
import pytest
from src.client.mcp_client import MCPClient

@pytest.mark.asyncio
async def test_tool_discovery():
    """Contract: Client must discover all expected tools."""
    client = MCPClient()
    tools = await client.discover_tools()
    
    expected_tools = {
        "get_user_profile",
        "list_users",
        "create_ticket",
        "list_tickets",
        "query_data"
    }
    
    assert set(tools.keys()) == expected_tools

@pytest.mark.asyncio
async def test_tool_schema_validation():
    """Contract: Tool schemas must be valid JSON Schema."""
    client = MCPClient()
    tools = await client.discover_tools()
    
    for tool_name, tool in tools.items():
        assert tool.inputSchema["type"] == "object"
        assert "properties" in tool.inputSchema

@pytest.mark.asyncio
async def test_tool_invocation(syrupy_snapshot):
    """Contract: Tool invocation returns expected schema."""
    client = MCPClient()
    
    result = await client.invoke_tool(
        "get_user_profile",
        {"user_id": "user-123"}
    )
    
    # Snapshot ensures schema doesn't change unexpectedly
    assert result == syrupy_snapshot
```

### Snapshot Testing

Contract snapshots track tool schemas over time:

```yaml
# tests/contract/snapshots/tool_schemas.json
{
  "get_user_profile": {
    "name": "get_user_profile",
    "description": "Retrieve user profile from backend service",
    "inputSchema": {
      "type": "object",
      "properties": {
        "user_id": {"type": "string"},
        "include_details": {"type": "boolean", "default": false}
      },
      "required": ["user_id"]
    }
  },
  ...
}
```

Breaking changes detected and test fails (preventing accidental breaking changes).

---

**Version**: 1.0.0  
**Last Updated**: January 18, 2026
