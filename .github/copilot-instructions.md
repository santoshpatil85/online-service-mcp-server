# GitHub Copilot Instructions

This document provides guidelines for GitHub Copilot when working with this production-grade MCP system on AKS.

## 🎯 Project Context

**Repository**: `online-service-mcp-server` - Production-grade Model Context Protocol (MCP) implementation using FastMCP on Azure Kubernetes Service (AKS) with Azure Workload Identity authentication.

**Structure**: Two independent projects:
- `mcp-server/` - FastMCP Server exposing REST API-backed tools
- `mcp-client/` - FastMCP Client for tool discovery and invocation

## 🏗️ Architecture Principles

### Core Design Patterns

1. **Azure Workload Identity (AWI)** - OIDC-based, credential-less authentication
   - Primary: `WorkloadIdentityCredential` in AKS pods
   - Fallback: `ClientSecretCredential` for local development
   - Token file: `/var/run/secrets/azure/tokens/token`

2. **FastMCP Server Pattern**
   - Strongly typed Pydantic v2 models for I/O
   - Async/await for all operations
   - Health probes: `/health/live` and `/health/ready`
   - Tool definitions with explicit schemas

3. **Async HTTP Client**
   - Use `httpx.AsyncClient` for REST calls
   - Always include timeout parameters (default: 10s)
   - Include `Authorization: Bearer {token}` headers
   - Handle retries and exponential backoff

4. **Contract Testing**
   - Client-server compatibility is CI/CD blocking
   - Validate tool schemas, names, and invocation
   - Use `pytest` with `syrupy` snapshots
   - Tests in `mcp-client/tests/contract/`

## 🔐 Authentication & Configuration

### Environment Variables

**MCP Server** (`mcp-server/src/config.py`):
```python
AZURE_TENANT_ID           # Azure AD tenant ID (required)
AZURE_CLIENT_ID           # UAMI client ID (required)
AZURE_AUTHORITY_HOST      # Default: https://login.microsoftonline.com
AZURE_FEDERATED_TOKEN_FILE # Default: /var/run/secrets/azure/tokens/token
AZURE_CLIENT_SECRET       # Local dev / CI fallback only
BACKEND_API_URL           # Downstream service URL (required)
BACKEND_API_TIMEOUT       # Default: 10 seconds
LOG_LEVEL                 # Default: INFO
READINESS_CHECK_BACKEND   # Default: true
```

**MCP Client** (`mcp-client/src/config.py`):
```python
AZURE_TENANT_ID           # Azure AD tenant ID (required)
AZURE_CLIENT_ID           # UAMI client ID (required)
MCP_SERVER_URL            # Default: http://mcp-server:8000
LOG_LEVEL                 # Default: INFO
REQUEST_TIMEOUT           # Default: 30 seconds
DISCOVERY_TIMEOUT         # Default: 10 seconds
```

### Kubernetes Workload Identity Setup

All pods require:
1. ServiceAccount with annotations:
   - `azure.workload.identity/client-id: {UAMI_CLIENT_ID}`
   - `azure.workload.identity/tenant-id: {TENANT_ID}`
2. Federated identity credential linking K8s ServiceAccount to UAMI
3. UAMI with appropriate Azure RBAC role assignments

## 📝 Code Style & Conventions

### Python Standards

- **Version**: Python 3.11+
- **Async**: All I/O operations must be async
- **Type hints**: Always use full type hints (Pydantic BaseModel for schemas)
- **Logging**: Use structured JSON logging via `src.logging.setup_structured_logging()`
- **Error handling**: Raise `src.models.errors.ServiceError` or appropriate exceptions
- **Dependencies**: Manage via `requirements.txt` and `requirements-dev.txt`

### File Organization

```
src/
├── main.py              # FastMCP server/client entry point
├── config.py            # Settings using Pydantic BaseSettings
├── auth/
│   └── azure_identity.py # Azure credential handling
├── clients/
│   └── rest_client.py   # Async HTTP client wrapper
├── models/
│   ├── schemas.py       # Pydantic request/response models
│   └── errors.py        # Custom exception types
├── tools/
│   ├── user_tools.py    # User-related tools
│   ├── ticket_tools.py  # Ticket-related tools
│   └── data_tools.py    # Data query tools
└── logging/
    └── structured_logger.py
```

### MCP Tool Definition Pattern

```python
from fastmcp import FastMCP
from pydantic import BaseModel

app = FastMCP(name="service-server")

class GetUserProfileRequest(BaseModel):
    user_id: str
    include_details: bool = False

class UserProfile(BaseModel):
    id: str
    name: str
    email: str
    # ... other fields

@app.tool()
async def get_user_profile(request: GetUserProfileRequest) -> UserProfile:
    """Retrieve user profile from backend service."""
    client = get_rest_client()
    response = await client.get(f"/users/{request.user_id}")
    return UserProfile(**response)
```

### Health Probe Implementation

```python
@app.get("/health/live")
async def liveness_probe():
    """Kubernetes liveness probe: server process alive."""
    return {"status": "alive"}

@app.get("/health/ready")
async def readiness_probe():
    """
    Kubernetes readiness probe: service ready to accept traffic.
    Validates: FastMCP initialized, Azure AD auth working, dependencies.
    """
    try:
        # Verify Azure AD token acquisition
        token = await get_access_token()
        if not token:
            raise RuntimeError("Failed to acquire Azure AD token")
        
        # Lightweight dependency check
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(
                f"{BACKEND_API_URL}/health",
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
        
        return {"status": "ready", "dependencies": {...}}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
```

## 🐳 Docker & Deployment

### Multi-Stage Build Pattern

- **Build stage**: Install dependencies in virtual environment
- **Runtime stage**: Copy venv, run as non-root user (UID 1000)
- **Security**: Read-only root filesystem, no capabilities, token mount
- **Health check**: HEALTHCHECK instruction with 30s interval

### Helm Chart Structure

```
helm/{chart-name}-chart/
├── Chart.yaml              # Chart metadata (version, appVersion)
├── values.yaml             # Default values (fully parameterized)
├── templates/
│   ├── deployment.yaml     # Pod deployment with Workload Identity
│   ├── service.yaml        # ClusterIP service
│   ├── serviceaccount.yaml # ServiceAccount with AWI annotations
│   ├── configmap.yaml      # App configuration (non-secrets)
│   ├── hpa.yaml            # Horizontal Pod Autoscaler
│   ├── pdb.yaml            # Pod Disruption Budget (optional)
│   └── _helpers.tpl        # Template helpers
└── README.md               # Chart documentation
```

**Key Helm Values**:
- `azure.tenantId`, `azure.clientId`: Workload Identity setup
- `image.repository`, `image.tag`: Container image
- `replicaCount`, `autoscaling`: Pod scaling
- `resources.requests`, `resources.limits`: CPU/memory allocation
- `probes.liveness/readiness`: Health check configuration

## 🧪 Testing Guidelines

### Contract Tests (CI/CD Blocking)

Located in `mcp-client/tests/contract/test_contract.py`:

```python
@pytest.mark.asyncio
async def test_contract_tool_discovery():
    """Contract: Client must discover all expected tools."""
    discoverer = ToolDiscoverer()
    tools = await discoverer.discover_tools()
    
    expected_tools = {"get_user_profile", "list_users", "create_ticket", ...}
    assert set(tools.keys()) == expected_tools

@pytest.mark.asyncio
async def test_contract_schema_validation():
    """Contract: Tool schemas must be valid JSON Schema."""
    tool = discoverer.get_tool("get_user_profile")
    assert tool.input_schema["type"] == "object"
    assert "user_id" in tool.input_schema["properties"]

@pytest.mark.asyncio
async def test_contract_tool_invocation():
    """Contract: Tool invocation must return expected output shape."""
    result = await client.call_tool(
        "get_user_profile",
        user_id="user-123",
        include_details=False
    )
    assert isinstance(result, dict)
    assert all(key in result for key in ["id", "name", "email"])
```

### Unit Tests

- Use `pytest` with `pytest-asyncio` for async tests
- Mock external dependencies (`get_rest_client`, Azure auth)
- Test error handling and edge cases
- Aim for >80% code coverage

### Local Testing

```bash
# Start MCP Server
cd mcp-server
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# In another terminal, run client
cd mcp-client
MCP_SERVER_URL=http://localhost:8000 python -m src.main

# Run contract tests
pytest tests/contract/ -v
```

## 🚀 CI/CD Pipeline

**Pipeline Stages** (`.gitlab-ci.yml`):
1. **lint** - pylint, black, isort
2. **unit-test** - pytest with coverage
3. **contract-test** - ⚠️ BLOCKING (must pass)
4. **build** - Docker multi-stage build, image scan
5. **helm-package** - Helm lint, template validation
6. **deploy** - Manual approval, AKS deployment (main branch only)

**Critical**: Contract tests MUST pass before build stage.

## 📊 Tools Reference

### MCP Server Tools

| Tool | Input | Output | Purpose |
|------|-------|--------|---------|
| `get_user_profile` | `user_id` (str), `include_details` (bool) | `UserProfile` | Retrieve user profile |
| `list_users` | `skip` (int), `limit` (int) | `ListUsersResponse` | List users with pagination |
| `create_ticket` | `title` (str), `description` (str), `priority` (str), `assignee_id` (str, opt) | `TicketResponse` | Create support ticket |
| `list_tickets` | `status` (str, opt), `skip` (int), `limit` (int) | `ListTicketsResponse` | List tickets with filtering |
| `query_data` | `dataset` (str), `filters` (dict, opt), `limit` (int) | `QueryDataResponse` | Query datasets |

### Pydantic Models

**Location**: `mcp-server/src/models/schemas.py`

Key models:
- `GetUserProfileRequest`, `UserProfile`
- `ListUsersRequest`, `ListUsersResponse`
- `CreateTicketRequest`, `TicketResponse`
- `ListTicketsRequest`, `ListTicketsResponse`
- `QueryDataRequest`, `QueryDataResponse`

All models use `Field()` with descriptions and validation.

## 🔧 Common Development Tasks

### Adding a New Tool

1. **Define request/response models** in `src/models/schemas.py`:
   ```python
   class NewToolRequest(BaseModel):
       param1: str = Field(..., description="...")
       param2: int = Field(default=10, ge=1, le=100)

   class NewToolResponse(BaseModel):
       result: str = Field(..., description="...")
   ```

2. **Implement tool function** in `src/tools/new_tools.py`:
   ```python
   async def new_tool(request: NewToolRequest) -> NewToolResponse:
       """Docstring with description."""
       client = get_rest_client()
       # Implementation
       return NewToolResponse(...)
   ```

3. **Register with FastMCP** in `src/main.py`:
   ```python
   @mcp_server.tool(name="new_tool", description="...")
   async def tool_new_tool(...) -> dict:
       """MCP wrapper."""
       # Convert to/from Pydantic models
   ```

4. **Add contract tests** in `mcp-client/tests/contract/test_contract.py`

5. **Update tool reference** in README.md

### Debugging Azure Workload Identity

```bash
# Check pod annotations
kubectl get pod <pod-name> -n mcp-system -o yaml | grep azure.workload.identity

# Verify token file
kubectl exec <pod-name> -n mcp-system -- ls -la /var/run/secrets/azure/tokens/

# Check environment variables
kubectl exec <pod-name> -n mcp-system -- env | grep AZURE

# View pod logs
kubectl logs <pod-name> -n mcp-system -f

# Test token acquisition from inside pod
kubectl exec <pod-name> -n mcp-system -- python -c "from azure.identity import WorkloadIdentityCredential; cred = WorkloadIdentityCredential(); token = cred.get_token('https://management.azure.com'); print(token)"
```

### Local Development with Service Principal

For local development (not in AKS), use Service Principal:

```bash
# Set environment variables
export AZURE_TENANT_ID="your-tenant-id"
export AZURE_CLIENT_ID="your-sp-client-id"
export AZURE_CLIENT_SECRET="your-sp-secret"
export BACKEND_API_URL="https://api.example.com"

# Run server
cd mcp-server
python -m uvicorn src.main:app --reload
```

## 📚 Key Files & Links

### Documentation
- [`ARCHITECTURE.md`](ARCHITECTURE.md) - System design, auth flows, patterns
- [`AKS_DEPLOYMENT_GUIDE.md`](AKS_DEPLOYMENT_GUIDE.md) - Step-by-step deployment
- [`README.md`](README.md) - Project overview and quick start
- [`mcp-server/README.md`](mcp-server/README.md) - Server-specific docs
- [`mcp-client/README.md`](mcp-client/README.md) - Client-specific docs

### Configuration
- [`mcp-server/src/config.py`](mcp-server/src/config.py) - Server settings
- [`mcp-client/src/config.py`](mcp-client/src/config.py) - Client settings
- [`mcp-server/helm/mcp-server-chart/values.yaml`](mcp-server/helm/mcp-server-chart/values.yaml)
- [`mcp-client/helm/mcp-client-chart/values.yaml`](mcp-client/helm/mcp-client-chart/values.yaml)

### Core Implementation
- [`mcp-server/src/main.py`](mcp-server/src/main.py) - Server entry point
- [`mcp-server/src/auth/azure_identity.py`](mcp-server/src/auth/azure_identity.py) - Auth logic
- [`mcp-server/src/tools/`](mcp-server/src/tools/) - Tool implementations
- [`mcp-client/src/client/mcp_client.py`](mcp-client/src/client/mcp_client.py) - Client implementation

### Testing
- [`mcp-client/tests/contract/test_contract.py`](mcp-client/tests/contract/test_contract.py) - Contract tests

## ⚙️ Technology Stack

- **Language**: Python 3.11+
- **MCP**: FastMCP, MCP Python SDK
- **Web**: FastAPI, uvicorn, httpx (async HTTP)
- **Azure**: azure-identity, azure-core (Workload Identity support)
- **Data**: Pydantic v2 (type safety)
- **Testing**: pytest, pytest-asyncio, syrupy (snapshots)
- **Deployment**: Helm 3.0+, Docker, Kubernetes, AKS
- **CI/CD**: GitLab CI/CD
- **Logging**: OpenTelemetry-compatible JSON logging

## ✅ Before Committing

1. **Format code**:
   ```bash
   black src/ && isort src/
   ```

2. **Lint**:
   ```bash
   pylint src/
   ```

3. **Run tests**:
   ```bash
   pytest tests/ -v --cov=src
   ```

4. **Run contract tests** (if modifying tools):
   ```bash
   # Start server
   cd mcp-server
   python -m uvicorn src.main:app &
   
   # Run contract tests
   cd ../mcp-client
   MCP_SERVER_URL=http://localhost:8000 pytest tests/contract/ -v
   ```

5. **Check Helm charts**:
   ```bash
   helm lint helm/mcp-*-chart/
   helm template mcp-server helm/mcp-server-chart/
   ```

## 🆘 Common Issues & Solutions

### "Azure token acquisition failed"
- **Cause**: Workload Identity not configured or token file missing
- **Solution**: 
  - Verify federated identity credentials exist
  - Check `/var/run/secrets/azure/tokens/token` exists in pod
  - Check service account annotations

### "Tool discovery times out"
- **Cause**: MCP Server not responding or network issue
- **Solution**:
  - Verify server is running: `curl http://mcp-server:8000/health/ready`
  - Increase `DISCOVERY_TIMEOUT` environment variable
  - Check network connectivity and DNS resolution

### "Contract test fails: Tool schema mismatch"
- **Cause**: Tool definition in server changed without updating client contract
- **Solution**:
  - Update snapshot in `mcp-client/tests/contract/snapshots/`
  - Re-run contract tests with `--snapshot-update` flag
  - Ensure backward compatibility before deployment

### "Readiness probe failing"
- **Cause**: Backend dependency unavailable or auth failed
- **Solution**:
  - Check backend service health
  - Verify Azure credentials (token file exists)
  - Check logs: `kubectl logs <pod-name> -n mcp-system`
  - Increase readiness probe initialDelaySeconds in Helm values

---

**Last Updated**: 2024-01-18  
**Maintained By**: Engineering Team  
**Version**: 1.0.0