# MCP Client

Production-grade MCP Client consuming tools from a FastMCP Server, with Azure Workload Identity authentication and contract-based testing.

## Overview

This MCP Client provides:

- **Tool Discovery**: Automatically discovers MCP tools from the server
- **Typed Tool Invocation**: Invokes tools with full type safety
- **Contract Testing**: Validates client-server compatibility
- **Azure Workload Identity**: Secure credential-less authentication in AKS
- **Error Handling**: Comprehensive error handling and retries

## Local Development

### Setup

```bash
cd mcp-client
python -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
```

### Environment Configuration

Create `.env`:

```bash
MCP_SERVER_URL="http://localhost:8000"
LOG_LEVEL="DEBUG"
AZURE_TENANT_ID="your-tenant-id"
AZURE_CLIENT_ID="your-client-id"
AZURE_CLIENT_SECRET="your-secret"  # For local dev only
```

### Run Client

```bash
# Run example discovery and tool invocation
python -m src.main

# Or import and use programmatically
python
>>> from src.client import get_mcp_client, ToolDiscoverer
>>> import asyncio
>>> async def test():
...     discoverer = ToolDiscoverer()
...     tools = await discoverer.discover_tools()
...     print([t.name for t in tools.values()])
>>> asyncio.run(test())
```

### Run Tests

```bash
# Unit tests
pytest tests/ -v --cov=src

# Contract tests (requires MCP Server running)
MCP_SERVER_URL=http://localhost:8000 pytest tests/contract/ -v

# All tests
pytest tests/ -v
```

## Docker

### Build

```bash
docker build -t mcp-client:latest .
```

### Run

```bash
docker run -e MCP_SERVER_URL=http://mcp-server:8000 \
           -e AZURE_TENANT_ID=xxx \
           -e AZURE_CLIENT_ID=xxx \
           mcp-client:latest
```

## Kubernetes Deployment

### Prerequisites

Same as MCP Server:
- AKS cluster with Workload Identity enabled
- UAMI with federated credentials configured

### Deploy with Helm

```bash
helm install mcp-client ./helm/mcp-client-chart \
  --namespace mcp-system \
  --create-namespace \
  --set azure.clientId=$UAMI_ID \
  --set azure.tenantId=$(az account show --query tenantId -o tsv) \
  --set app.mcpServerUrl=http://mcp-server:8000
```

### Verify

```bash
kubectl get pods -n mcp-system -l app.kubernetes.io/name=mcp-client
kubectl logs -n mcp-system -l app.kubernetes.io/name=mcp-client
```

## API Reference

### MCPClient

```python
from src.client import get_mcp_client

client = get_mcp_client()

# Discover tools
tools = await client.discover_tools()

# Invoke a tool
result = await client.invoke_tool("get_user_profile", {"user_id": "123"})

# Simple tool call
result = await client.call_tool("get_user_profile", user_id="123")

# Check server health
is_healthy = await client.check_server_health()
```

### ToolDiscoverer

```python
from src.client import ToolDiscoverer

discoverer = ToolDiscoverer()

# Discover all tools
tools = await discoverer.discover_tools()

# List tool names
names = discoverer.list_tools()

# Get specific tool
tool = discoverer.get_tool("get_user_profile")

# Validate arguments
is_valid = discoverer.validate_arguments("get_user_profile", {"user_id": "123"})

# Get tool schema
schema_json = discoverer.get_tool_schema_json("get_user_profile")
```

## Contract Testing

Contract tests validate that the client and server adhere to their interface contract.

### Running Contract Tests

```bash
# Start MCP Server first
cd ../mcp-server
python -m uvicorn src.main:app &

# Run contract tests
cd ../mcp-client
pytest tests/contract/ -v
```

### Contract Validations

- Tool names match expected set
- Tool descriptions not empty
- Input/output schemas are valid JSON
- Required fields are documented
- Error responses have standard format

### Snapshot Testing

Contracts include snapshot tests of tool schemas:

```bash
# Update snapshots if schemas change
pytest tests/contract/ --snapshot-update
```

## Error Handling

The client handles various error scenarios:

```python
from src.models.errors import ServiceError, TimeoutError

try:
    result = await client.invoke_tool("some_tool", {})
except TimeoutError:
    # Tool invocation timed out
    pass
except ServiceError as e:
    # Backend service error
    print(e.error_code)
    print(e.details)
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_SERVER_URL` | MCP Server URL | `http://mcp-server:8000` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `REQUEST_TIMEOUT` | HTTP request timeout (seconds) | `30` |
| `DISCOVERY_TIMEOUT` | Tool discovery timeout (seconds) | `10` |
| `AZURE_TENANT_ID` | Azure AD tenant ID | - |
| `AZURE_CLIENT_ID` | UAMI/SPN client ID | - |
| `AZURE_CLIENT_SECRET` | SPN secret (local dev only) | - |

## Azure Workload Identity

The client uses the same Azure auth abstraction as the server:

1. **In AKS**: Uses Workload Identity with OIDC token exchange
2. **Local Dev**: Falls back to Service Principal (environment variables)

### Token Acquisition Flow

```
Client Pod (AKS)
  ↓ (has K8s service account token)
K8s Workload Identity Webhook
  ↓ (projects token to /var/run/secrets/azure/tokens/token)
WorkloadIdentityCredential
  ↓ (exchanges K8s JWT for Azure AD access token)
Azure AD
  ↓ (returns access token)
MCP Server (authenticated calls)
```

## Performance

### Resource Limits

Current Helm values:
- CPU request: 100m, limit: 500m
- Memory request: 128Mi, limit: 512Mi

### Scaling

HPA is configured:
- Min replicas: 1
- Max replicas: 5
- Target CPU: 75%

## Troubleshooting

### Client can't connect to server

```bash
# Check server URL
echo $MCP_SERVER_URL

# Test connectivity
curl http://mcp-server:8000/health/live

# Check logs
kubectl logs -n mcp-system <client-pod> -f
```

### Tool discovery times out

```bash
# Increase timeout
DISCOVERY_TIMEOUT=30 python -m src.main

# Check server tool registration
curl http://mcp-server:8000/_mcp/tools
```

### Authentication fails

```bash
# Check if running in AKS
env | grep AZURE

# Verify service account token exists
kubectl exec <pod> -- ls -la /var/run/secrets/azure/tokens/

# Test token acquisition
kubectl exec <pod> -- python -c "from src.auth import get_access_token; import asyncio; print(asyncio.run(get_access_token()))"
```

## Contributing

1. Make changes
2. Run: `pytest tests/ -v --cov=src`
3. Run contract tests: `MCP_SERVER_URL=http://localhost:8000 pytest tests/contract/ -v`
4. Submit MR

## License

Apache 2.0
