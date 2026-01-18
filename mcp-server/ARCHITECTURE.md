# MCP Server - Architecture

This document describes the FastMCP Server architecture, authentication flows, and deployment on AKS with Azure Workload Identity.

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Azure Workload Identity Authentication](#azure-workload-identity-authentication)
3. [FastMCP Server Design](#fastmcp-server-design)
4. [Health Probes](#health-probes)
5. [Error Handling](#error-handling)
6. [Configuration](#configuration)
7. [Technology Stack](#technology-stack)
8. [Security](#security)

## System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                  EXTERNAL SERVICES (Internet)                   │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Azure AD    │  │ REST APIs    │  │  Downstream  │          │
│  │  (OIDC)      │  │  (3rd Party) │  │  Backend Svc │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│         ▲                  ▲                    ▲                │
└─────────┼──────────────────┼────────────────────┼─────────────────┘
          │ Token Exchange   │ Bearer Token       │ Bearer Token
          │ (OIDC)           │                    │
          │                  │                    │
┌─────────┼──────────────────┼────────────────────┼─────────────────┐
│         ▼                  ▼                    ▼                 │
│ ┌──────────────────────────────────────────────────────────┐   │
│ │         MCP Server Pod (FastMCP - HTTP on 3333)          │   │
│ │                                                          │   │
│ │  ┌────────────────────────────────────────────────────┐ │   │
│ │  │ FastMCP HTTP Transport                             │ │   │
│ │  │ ├─ GET /health → K8s probes                       │ │   │
│ │  │ ├─ POST /messages → MCP RPC protocol             │ │   │
│ │  │ └─ GET /tools → Tool discovery                   │ │   │
│ │  └────────────────────────────────────────────────────┘ │   │
│ │                       ▲                                  │   │
│ │  ┌────────────────────┴───────────────────┐            │   │
│ │  │                                        │            │   │
│ │  ▼                                        ▼            │   │
│ │ ┌──────────────────┐  ┌──────────────────────────┐   │   │
│ │ │ Azure Identity   │  │ MCP Tool Registry        │   │   │
│ │ │ (AWI + SPN)      │  │ ├─ get_user_profile()   │   │   │
│ │ │                  │  │ ├─ create_ticket()      │   │   │
│ │ │ WorkloadIdentity │  │ ├─ list_users()         │   │   │
│ │ │ Credential Flow  │  │ ├─ list_tickets()       │   │   │
│ │ │                  │  │ └─ query_data()         │   │   │
│ │ └──────────────────┘  └──────────────────────────┘   │   │
│ │                                                          │   │
│ │  ServiceAccount: "mcp-server"                           │   │
│ │  Annotations:                                           │   │
│ │  ├─ azure.workload.identity/client-id: <UAMI_ID>      │   │
│ │  └─ azure.workload.identity/tenant-id: <TENANT_ID>    │   │
│ │                                                          │   │
│ │  Pod Volume: /var/run/secrets/azure/tokens/token       │   │
│ │  HPA: min 2 / max 10 pods (CPU 70%, Memory 80%)        │   │
│ │                                                          │   │
│ └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Workload Identity Webhook (System):                           │
│  ├─ Injects Azure credentials into pods                       │
│  ├─ Federated credential validation                           │
│  └─ Token exchange via OIDC provider                          │
│                                                                 │
│  Azure Resources (Control Plane):                              │
│  ├─ User Assigned Managed Identity (UAMI): mcp-server-uami    │
│  ├─ Federated Identity Credentials:                           │
│  │  ├─ audience: api://AzureADTokenExchange                  │
│  │  ├─ issuer: https://<aks-region>.oic.prod-aks.azure.com/… │
│  │  └─ subject: system:serviceaccount:mcp-system:mcp-server  │
│  └─ Role Assignments:                                         │
│     └─ Reader on resource group / subscription                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Azure Workload Identity Authentication

### Authentication Flow

```
┌──────────────────────────────────────────────────────────────────┐
│              MCP Server Pod (Kubernetes ServiceAccount)           │
│                                                                  │
│  1️⃣  WorkloadIdentityCredential Initialization                  │
│   └─ Checks: K8s volume-mounted service account JWT             │
│      Location: /var/run/secrets/azure/tokens/token              │
│      File contains: Signed K8s JWT with:                        │
│       • subject: system:serviceaccount:mcp-system:mcp-server    │
│       • audience: api://AzureADTokenExchange                    │
│       • iss: AKS OIDC issuer URL                                │
│                                                                  │
│  2️⃣  OIDC Discovery                                             │
│   └─ Fetches metadata from AKS OIDC issuer:                     │
│      https://<aks-region>.oic.prod-aks.azure.com/.well-known/… │
│      → token_endpoint, jwks_uri, issuer validation              │
│                                                                  │
│  3️⃣  Token Exchange (RFC 8693 - SAML 2.0 Bearer Assertion)     │
│   ├─ Sends K8s JWT → Azure AD /token endpoint                  │
│   ├─ Grant Type: urn:ietf:params:oauth:grant-type:token-exchange │
│   ├─ Assertion: urn:ietf:params:oauth:assertion-type:jwt-bearer  │
│   ├─ Scope: https://management.azure.com/.default              │
│   └─ Response: Azure access token (JWT)                        │
│      ├─ iss: https://sts.windows.net/<tenant-id>/             │
│      ├─ sub: <object-id-of-uami>                              │
│      ├─ aud: https://management.azure.com                      │
│      └─ exp: 3600 seconds                                      │
│                                                                  │
│  4️⃣  Azure Service Call                                         │
│   └─ Authorization: Bearer <access_token>                      │
│      → Azure Management API or downstream REST services         │
│                                                                  │
│  5️⃣  Token Caching & Refresh                                   │
│   └─ azure-identity SDK caches token in memory                 │
│      Refresh: 5 minutes before expiry                          │
│      Automatic refresh on 401 Unauthorized                     │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Configuration Environment Variables

```
┌────────────────────────────────────────────┐
│  Pod Runtime Environment Variables          │
├────────────────────────────────────────────┤
│ AZURE_TENANT_ID=<tenant-uuid>              │
│ AZURE_CLIENT_ID=<uami-client-id>           │
│ AZURE_AUTHORITY_HOST=https://login.microsoftonline.com/  │
│ AZURE_FEDERATED_TOKEN_FILE=/var/run/secrets/azure/tokens/token │
│ BACKEND_API_URL=https://api.example.com    │
│ BACKEND_API_TIMEOUT=10                     │
│ LOG_LEVEL=INFO                             │
│ READINESS_CHECK_BACKEND=true               │
├────────────────────────────────────────────┤
│ (Local Dev Only - NOT in AKS)              │
│ AZURE_CLIENT_SECRET=<service-principal-secret> │
└────────────────────────────────────────────┘
         ▼
    ┌────────────────────────────────────┐
    │ Azure Identity Client               │
    │ Strategy Selection:                 │
    │ 1. WorkloadIdentityCredential       │
    │    (if /var/run/secrets/.../token exists) │
    │ 2. ClientSecretCredential           │
    │    (if AZURE_CLIENT_SECRET set)    │
    │ 3. DefaultAzureCredential           │
    │    (fallback: Visual Studio, CLI)   │
    └────────────────────────────────────┘
```

## FastMCP Server Design

### MCP Tool Implementation Pattern

All tools are registered as async callables with strongly-typed Pydantic I/O schemas:

```python
from fastmcp import FastMCP
from pydantic import BaseModel, Field
import httpx

app = FastMCP(name="service-mcp-server")

# 1️⃣  Define strongly-typed input/output models
class GetUserProfileRequest(BaseModel):
    user_id: str = Field(..., description="User ID to fetch")
    include_details: bool = Field(default=False, description="Include extended details")

class UserProfile(BaseModel):
    id: str
    name: str
    email: str
    details: Optional[dict] = None

# 2️⃣  Register async tool with MCP
@app.tool(name="get_user_profile", description="Retrieve user profile")
async def get_user_profile(request: GetUserProfileRequest) -> UserProfile:
    """Fetch user profile from backend service via Azure-authenticated HTTP call."""
    
    # Acquire Azure access token
    token = await get_access_token()
    
    # Make authenticated REST call to downstream backend
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{BACKEND_API_URL}/users/{request.user_id}",
            headers={"Authorization": f"Bearer {token}"},
            params={"details": request.include_details}
        )
        response.raise_for_status()
        
        return UserProfile(**response.json())
```

### Tool Registry

The server automatically registers 5 MCP tools:

| Tool | Input Model | Output Model | Description |
|------|-------------|--------------|-------------|
| `get_user_profile` | `GetUserProfileRequest` | `UserProfile` | Retrieve user profile |
| `list_users` | `ListUsersRequest` | `ListUsersResponse` | List users with pagination |
| `create_ticket` | `CreateTicketRequest` | `TicketResponse` | Create support ticket |
| `list_tickets` | `ListTicketsRequest` | `ListTicketsResponse` | List tickets with filtering |
| `query_data` | `QueryDataRequest` | `QueryDataResponse` | Query datasets |

All schemas defined in `src/models/schemas.py` with validation rules.

## Health Probes

### Kubernetes Integration

The server exposes a health endpoint at `GET /health` that Kubernetes uses for pod lifecycle management:

```python
@app.get("/health")
async def health_probe():
    """
    Kubernetes health check: combined liveness and readiness.
    Returns 200 OK if server can accept traffic.
    Returns 503 Service Unavailable if dependencies unavailable.
    """
    try:
        # Check 1: FastMCP server initialized
        if not mcp_server.tools():
            raise RuntimeError("MCP tools not registered")
        
        # Check 2: Azure authentication working
        token = await get_access_token()
        if not token:
            raise RuntimeError("Failed to acquire Azure AD token")
        
        # Check 3: Backend service connectivity (optional, configurable)
        if settings.readiness_check_backend:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(
                    f"{settings.backend_api_url}/health",
                    headers={"Authorization": f"Bearer {token}"}
                )
                response.raise_for_status()
        
        return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
    
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}, 503
```

### Deployment Configuration

```yaml
# Kubernetes Deployment probes
livenessProbe:
  httpGet:
    path: /health
    port: 3333
  initialDelaySeconds: 10
  periodSeconds: 30
  timeoutSeconds: 5
  failureThreshold: 3
  # Pod restart after 3 consecutive failures (30s * 3 = 90s total)

readinessProbe:
  httpGet:
    path: /health
    port: 3333
  initialDelaySeconds: 10
  periodSeconds: 10
  timeoutSeconds: 3
  failureThreshold: 3
  # Removed from load balancer after 3 failures (30s total)
```

## Error Handling

### Error Response Pattern

```python
from fastmcp.models.errors import ServiceError

try:
    # Tool logic
    result = await backend_call()
except httpx.TimeoutException:
    # Retry 3 times with exponential backoff
    raise ServiceError(
        code="TIMEOUT",
        message=f"Backend request timeout after {timeout}s"
    )
except httpx.HTTPStatusError as e:
    # 4xx/5xx errors from backend
    raise ServiceError(
        code="BACKEND_ERROR",
        message=f"Backend service returned {e.response.status_code}: {e.response.text}"
    )
except ValueError as e:
    # Validation errors
    raise ServiceError(
        code="INVALID_INPUT",
        message=f"Validation failed: {str(e)}"
    )
```

## Configuration

### Pydantic Settings Model

```python
# src/config.py
from pydantic_settings import BaseSettings

class ServerSettings(BaseSettings):
    # Server configuration
    host: str = "0.0.0.0"
    port: int = 3333
    
    # Azure configuration
    azure_tenant_id: str
    azure_client_id: str
    azure_authority_host: str = "https://login.microsoftonline.com"
    azure_federated_token_file: str = "/var/run/secrets/azure/tokens/token"
    
    # Backend configuration
    backend_api_url: str
    backend_api_timeout: float = 10.0
    readiness_check_backend: bool = True
    
    # Logging
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = ServerSettings()
```

## Technology Stack

### Core Dependencies

- **FastMCP >= 0.1.0**: MCP server implementation with native HTTP transport
- **MCP >= 0.1.0**: Protocol definitions
- **Pydantic >= 2.5.0**: Type validation and serialization
- **pydantic-settings**: Configuration management from environment
- **httpx >= 0.25.0**: Async HTTP client for downstream calls
- **azure-identity >= 1.13.0**: Azure Workload Identity support
- **azure-core >= 1.28.0**: Azure SDK core utilities
- **Python 3.11+**: Language requirement

### Development Dependencies

- **pytest >= 7.0**: Unit testing framework
- **pytest-asyncio >= 0.21.0**: Async test support
- **pytest-cov**: Coverage reporting
- **black**: Code formatter
- **isort**: Import sorting
- **pylint**: Linter
- **mypy**: Type checking

## Security

### Authentication & Authorization

1. **Pod Identity**: Azure Workload Identity (OIDC federation, no managed identity MSI)
2. **Token Acquisition**: Automatic via `WorkloadIdentityCredential` with token caching
3. **Downstream Auth**: Bearer token in Authorization header
4. **Secret Management**: Never hardcoded; injected via environment variables

### Network Security

1. **Service-to-Service**: Internal cluster communication only
2. **Ingress**: Optional via Kubernetes Ingress (mTLS can be added via service mesh)
3. **Network Policy**: Optional pod-to-pod firewall rules

### Image Security

1. **Base Image**: Microsoft Python slim image (minimal surface area)
2. **Non-root User**: Container runs as UID 1000 (unprivileged)
3. **Read-only Filesystem**: Security context enforces read-only root
4. **Vulnerability Scanning**: Container images scanned in CI/CD

### Compliance

- No hardcoded credentials in images/templates
- Audit logging enabled for Azure operations
- Token expiry: 1 hour (automatic refresh)
- Least privilege: RBAC roles scoped to resource group

---

**Version**: 1.0.0  
**Last Updated**: January 18, 2026
