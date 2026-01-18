# Production-Grade MCP System Architecture on AKS

## 🏗️ High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          EXTERNAL SERVICES (Internet)                   │
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │
│  │  Azure AD    │  │  OAuth Provider  │  │  REST APIs  │                 │
│  │  (OIDC)      │  │  (SaaS)          │  │  (3rd Party)│                 │
│  └──────────────┘  └──────────────┘  └──────────────┘                 │
│         ▲                  ▲                    ▲                         │
└─────────┼──────────────────┼────────────────────┼─────────────────────────┘
          │                  │                    │
          │ Token Req        │ OAuth Req          │ Service Call
          │ (OIDC Flow)      │ (2-legged)         │ (Bearer Token)
          │                  │                    │
┌─────────┼──────────────────┼────────────────────┼─────────────────────────┐
│         ▼                  ▼                    ▼                         │
│ ┌──────────────────────────────────────────────────────────────────┐   │
│ │                    Azure Kubernetes Service (AKS)                │   │
│ │                                                                  │   │
│ │  ┌────────────────────────────────────────────────────────┐    │   │
│ │  │              MCP Server Pod (FastMCP)                 │    │   │
│ │  │  ┌─────────────────────────────────────────────────┐  │    │   │
│ │  │  │ FastMCP HTTP Transport                          │  │    │   │
│ │  │  │ ├─ GET /mcp/health/live → K8s liveness probe   │  │    │   │
│ │  │  │ ├─ GET /mcp/health/ready → K8s readiness probe │  │    │   │
│ │  │  │ └─ POST /_mcp/messages → MCP RPC endpoint      │  │    │   │
│ │  │  └─────────────────────────────────────────────────┘  │    │   │
│ │  │                       ▲                                │    │   │
│ │  │      ┌────────────────┴────────────────┐             │    │   │
│ │  │      │                                 │             │    │   │
│ │  │  ┌─────────────────┐  ┌─────────────────────────────┐│    │   │
│ │  │  │ Azure Identity  │  │ MCP Tool Registry           ││    │   │
│ │  │  │ (AWI + SPN)     │  │ ├─ get_user_profile()       ││    │   │
│ │  │  │                 │  │ ├─ create_ticket()          ││    │   │
│ │  │  │ WorkloadIdentity│  │ ├─ query_data()             ││    │   │
│ │  │  │ Credential Flow │  │ └─ ...other tools           ││    │   │
│ │  │  └─────────────────┘  └─────────────────────────────┘│    │   │
│ │  │                                                        │    │   │
│ │  │  ServiceAccount: "mcp-server"                         │    │   │
│ │  │  Annotations:                                         │    │   │
│ │  │  ├─ azure.workload.identity/client-id: <UAMI_ID>     │    │   │
│ │  │  └─ azure.workload.identity/tenant-id: <TENANT_ID>   │    │   │
│ │  │                                                        │    │   │
│ │  │  HPA: min 2 / max 10 pods (CPU: 80%, Memory: 85%)    │    │   │
│ │  └────────────────────────────────────────────────────┘    │   │
│ │                                                              │   │
│ │  ┌────────────────────────────────────────────────────┐    │   │
│ │  │         MCP Client Pod (FastMCP)                   │    │   │
│ │  │  ┌──────────────────────────────────────────────┐  │    │   │
│ │  │  │ FastMCP HTTP Client                          │  │    │   │
│ │  │  │ ├─ Tool Discovery Protocol                   │  │    │   │
│ │  │  │ ├─ Typed Tool Invocation                     │  │    │   │
│ │  │  │ └─ Async HTTP calls to MCP Server            │  │    │   │
│ │  │  └──────────────────────────────────────────────┘  │    │   │
│ │  │                       ▲                             │    │   │
│ │  │                       │ HTTP                        │    │   │
│ │  │                  ┌────┴────┐                        │    │   │
│ │  │                  │ Svc DNS  │                        │    │   │
│ │  │                  └──────────┘                        │    │   │
│ │  │                                                       │    │   │
│ │  │  ServiceAccount: "mcp-client"                        │    │   │
│ │  │  Annotations: (Same AWI pattern)                    │    │   │
│ │  │                                                       │    │   │
│ │  │  HPA: min 1 / max 5 pods (CPU: 75%)                │    │   │
│ │  └────────────────────────────────────────────────────┘    │   │
│ │                                                              │   │
│ │  ┌────────────────────────────────────────────────────┐    │   │
│ │  │  Workload Identity Webhook (System)                │    │   │
│ │  │  ├─ Injects Azure credentials into pods            │    │   │
│ │  │  ├─ Federated credential validation                │    │   │
│ │  │  └─ Token exchange via OIDC provider               │    │   │
│ │  └────────────────────────────────────────────────────┘    │   │
│ └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  Azure Resources (Control Plane):                                  │
│  ├─ AKS Cluster (1.28+)                                           │
│  ├─ User Assigned Managed Identity (UAMI): mcp-system-uami        │
│  ├─ Federated Identity Credentials:                               │
│  │  ├─ audience: api://AzureADTokenExchange                       │
│  │  ├─ issuer: https://<aks-region>.oic.prod-aks.azure.com/...   │
│  │  ├─ subject: system:serviceaccount:default:mcp-server         │
│  │  └─ subject: system:serviceaccount:default:mcp-client         │
│  └─ Role Assignments:                                             │
│     ├─ Reader on subscription                                    │
│     └─ Custom role for downstream service access                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🔐 Azure Workload Identity Authentication Flow

### OAuth 2.0 / OIDC Token Exchange (Workload Identity v2)

```
┌──────────────────────────────────────────────────────────────────┐
│              MCP Server Pod (Kubernetes ServiceAccount)           │
│                                                                  │
│  1️⃣  WorkloadIdentityCredential Initialization                  │
│   └─ Checks: K8s volume-mounted service account JWT             │
│      Location: /var/run/secrets/azure/tokens/token              │
│      File contains: Signed K8s JWT with:                        │
│       • subject: system:serviceaccount:default:mcp-server       │
│       • audience: api://AzureADTokenExchange                    │
│                                                                  │
│  2️⃣  OIDC Discovery                                             │
│   └─ Fetches metadata from AKS OIDC issuer:                     │
│      https://<aks-region>.oic.prod-aks.azure.com/.well-known/… │
│      → token_endpoint, jwks_uri, etc.                           │
│                                                                  │
│  3️⃣  Token Exchange (RFC 8693)                                  │
│   ├─ Sends K8s JWT → Azure AD                                  │
│   ├─ Assertion Type: urn:ietf:params:oauth:grant-type:token-… │
│   ├─ Scope: https://<service>/.default                         │
│   └─ Response: Azure AD access token                           │
│                                                                  │
│  4️⃣  Azure Service Call                                         │
│   └─ Authorization: Bearer <access_token>                      │
│      → Azure Management API / Custom REST endpoints            │
│                                                                  │
│  5️⃣  Token Caching                                              │
│   └─ azure-identity SDK caches token in memory                 │
│      Refresh: 5 min before expiry                              │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Configuration Flow

```
┌────────────────────────────────────────────────┐
│  Environment Variables (Pod Runtime)            │
├────────────────────────────────────────────────┤
│ AZURE_TENANT_ID=<tenant-uuid>                  │
│ AZURE_CLIENT_ID=<uami-client-id>               │
│ AZURE_AUTHORITY_HOST=https://login.microsoftonline.com/  │
│ AZURE_FEDERATED_TOKEN_FILE=/var/run/secrets/azure/tokens/token │
├────────────────────────────────────────────────┤
│ Optional (Service Principal fallback)           │
│ AZURE_CLIENT_SECRET=<secret>                    │
│ (Only in local dev / CI; never in container)    │
└────────────────────────────────────────────────┘
         ▼
    ┌────────────────────────────┐
    │ Azure Identity Client       │
    │ Strategy Selection:         │
    │ 1. WorkloadIdentityCredential (if running in AKS) │
    │ 2. ClientSecretCredential (if env vars set)  │
    │ 3. DefaultAzureCredential (fallback)          │
    └────────────────────────────┘
```

---

## 🚀 FastMCP Server Design

### MCP Tool Definition Pattern

```python
from fastmcp import FastMCP
from pydantic import BaseModel

app = FastMCP(name="service-server")

# Strongly typed inputs/outputs
class GetUserProfileRequest(BaseModel):
    user_id: str
    include_details: bool = False

class UserProfile(BaseModel):
    id: str
    name: str
    email: str
    details: Optional[dict] = None

# MCP Tool with explicit schema
@app.tool()
async def get_user_profile(request: GetUserProfileRequest) -> UserProfile:
    """
    Retrieve user profile from backend service.
    
    Uses Azure Workload Identity to authenticate downstream REST call.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BACKEND_API_URL}/users/{request.user_id}",
            headers={"Authorization": f"Bearer {await get_access_token()}"},
            timeout=10.0
        )
        response.raise_for_status()
        return UserProfile(**response.json())

# Health endpoints for K8s probes
@app.get("/health/live")
async def liveness_probe():
    """Kubernetes liveness probe: server process alive."""
    return {"status": "alive"}

@app.get("/health/ready")
async def readiness_probe():
    """
    Kubernetes readiness probe: service ready to accept traffic.
    Validates: FastMCP initialized, Azure AD auth working, downstream dependencies.
    """
    try:
        # Verify FastMCP server initialized
        if not app.tools():
            raise RuntimeError("MCP tools not registered")
        
        # Verify Azure AD token acquisition works
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
        
        return {"status": "ready"}
    except Exception as e:
        logger.error(f"Readiness probe failed: {e}")
        raise HTTPException(status_code=503, detail="Service not ready")
```

### Tool Registry and Error Handling

```
MCP Server: Tool Inventory
├─ Tool Name: get_user_profile
│  ├─ Input Schema: GetUserProfileRequest (Pydantic)
│  ├─ Output Schema: UserProfile (Pydantic)
│  └─ Error Handling:
│     ├─ HTTPError (4xx/5xx) → MCP error response
│     ├─ TimeoutError → Retry logic (3x exponential backoff)
│     ├─ ValidationError → Clear schema mismatch error
│     └─ AuthError → Token refresh attempt
│
├─ Tool Name: create_ticket
│  ├─ Input Schema: CreateTicketRequest (Pydantic)
│  ├─ Output Schema: TicketResponse (Pydantic)
│  └─ Error Handling: ...
│
└─ Tool Name: query_data
   ├─ Input Schema: QueryRequest (Pydantic)
   ├─ Output Schema: QueryResult (Pydantic)
   └─ Error Handling: ...
```

---

## 🧪 Contract Testing Architecture

### Contract Definition

```
Contract: MCP Server ↔ MCP Client
├─ Tool Inventory
│  ├─ Tool names must match exactly
│  ├─ Input/output schemas must be compatible (JSON Schema)
│  ├─ Error response format must be standard
│  └─ Timeout constraints
│
├─ Protocol Compliance
│  ├─ Request/response envelope format
│  ├─ HTTP status codes
│  ├─ Header requirements
│  └─ MCP version compatibility
│
└─ Snapshot Tests
   ├─ Schema snapshots for tools
   ├─ Sample tool responses
   └─ Error response templates
```

### Test Execution Flow

```
┌─────────────────────────────────────────────┐
│  Contract Test Suite (pytest)                │
├─────────────────────────────────────────────┤
│                                              │
│  1. Tool Discovery Test                      │
│     ├─ Client discovers server tools         │
│     ├─ Compare against snapshot              │
│     └─ Fail if names don't match             │
│                                              │
│  2. Schema Validation Test                   │
│     ├─ Each tool's input/output schema       │
│     ├─ Validate JSON Schema compliance       │
│     └─ Fail on schema break                  │
│                                              │
│  3. Typed Invocation Test                    │
│     ├─ Call each tool with valid inputs      │
│     ├─ Validate output schema                │
│     └─ Timeout and error handling            │
│                                              │
│  4. Error Response Test                      │
│     ├─ Invalid inputs → standard errors      │
│     ├─ Service errors → graceful handling    │
│     └─ Verify error structure                │
│                                              │
│  5. Performance Test                         │
│     ├─ Tool execution time SLO (e.g., <1s)  │
│     └─ Concurrent call handling              │
│                                              │
└─────────────────────────────────────────────┘
    ↓ (on failure)
┌─────────────────────────────────────────────┐
│  CI/CD Pipeline FAILS                        │
│  (Cannot proceed to build/deploy)            │
└─────────────────────────────────────────────┘
```

---

## ☸️ Helm Chart Architecture

### MCP Server Helm Chart Structure

```
mcp-server-chart/
├── Chart.yaml                    # Chart metadata
├── values.yaml                   # Default configuration (fully parameterized)
├── templates/
│   ├── deployment.yaml           # Pod deployment with Workload Identity
│   ├── service.yaml              # Kubernetes Service (ClusterIP)
│   ├── serviceaccount.yaml       # ServiceAccount with AWI annotations
│   ├── configmap.yaml            # App configuration (non-secrets)
│   ├── hpa.yaml                  # Horizontal Pod Autoscaler
│   ├── pdb.yaml                  # Pod Disruption Budget
│   └── _helpers.tpl              # Template helpers
└── README.md                      # Chart documentation
```

### Key Helm Configuration

```yaml
# values.yaml excerpt
azure:
  tenantId: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  clientId: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  authorityHost: "https://login.microsoftonline.com"
  scopes:
    - "https://management.azure.com/.default"

image:
  repository: "myregistry.azurecr.io/mcp-server"
  tag: "1.0.0"
  pullPolicy: IfNotPresent

replicaCount: 2

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 80
  targetMemoryUtilizationPercentage: 85

resources:
  requests:
    cpu: "200m"
    memory: "256Mi"
  limits:
    cpu: "1000m"
    memory: "1Gi"

probes:
  liveness:
    initialDelaySeconds: 10
    periodSeconds: 30
    timeoutSeconds: 5
    failureThreshold: 3
  readiness:
    initialDelaySeconds: 5
    periodSeconds: 10
    timeoutSeconds: 3
    failureThreshold: 3
```

---

## 📦 Project Structure (Both Server & Client)

```
mcp-server/                        # Independent repo
├── README.md
├── pyproject.toml                 # Python project metadata
├── requirements.txt               # Production dependencies
├── requirements-dev.txt           # Dev dependencies (pytest, etc.)
├── Dockerfile                     # Multi-stage build
├── .dockerignore
├── .gitlab-ci.yml                 # GitLab CI/CD pipeline
├── .gitignore
│
├── src/
│   ├── __init__.py
│   ├── main.py                    # FastMCP server entry point
│   ├── config.py                  # Configuration management
│   ├── auth/
│   │   ├── __init__.py
│   │   └── azure_identity.py      # Azure auth abstraction (AWI + SPN)
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── user_tools.py          # User-related tools
│   │   ├── ticket_tools.py        # Ticket-related tools
│   │   └── data_tools.py          # Data query tools
│   ├── models/
│   │   ├── __init__.py
│   │   ├── schemas.py             # Pydantic models for I/O
│   │   └── errors.py              # Error types
│   ├── clients/
│   │   ├── __init__.py
│   │   └── rest_client.py         # Async REST client wrapper
│   └── logging/
│       ├── __init__.py
│       └── structured_logger.py   # OpenTelemetry-compatible logging
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                # pytest fixtures
│   ├── unit/
│   │   ├── test_auth.py
│   │   ├── test_tools.py
│   │   └── test_models.py
│   └── integration/
│       ├── test_server.py
│       └── test_health_probes.py
│
├── helm/
│   └── mcp-server-chart/
│       ├── Chart.yaml
│       ├── values.yaml
│       ├── templates/
│       │   ├── deployment.yaml
│       │   ├── service.yaml
│       │   ├── serviceaccount.yaml
│       │   ├── configmap.yaml
│       │   ├── hpa.yaml
│       │   └── _helpers.tpl
│       └── README.md
│
└── docs/
    ├── ARCHITECTURE.md
    ├── AKS_DEPLOYMENT.md
    └── LOCAL_DEV.md

mcp-client/                        # Independent repo (parallel structure)
├── src/
│   ├── main.py
│   ├── config.py
│   ├── auth/
│   │   └── azure_identity.py
│   ├── client/
│   │   ├── mcp_client.py          # FastMCP HTTP client
│   │   └── tool_discoverer.py
│   └── logging/
│
├── tests/
│   ├── contract/
│   │   ├── test_tool_discovery.py
│   │   ├── test_tool_schemas.py
│   │   ├── test_tool_invocation.py
│   │   └── snapshots/
│   │       └── tool_schemas.json  # Schema snapshots
│   └── unit/
│
├── helm/
│   └── mcp-client-chart/
│
└── .gitlab-ci.yml
```

---

## 🚀 CI/CD Pipeline Stages (Both Projects)

```
Pipeline Flow:
┌────────────┐
│   lint     │  Run pylint, black, isort
└─────┬──────┘
      │
┌────────────┐
│unit-test   │  pytest with coverage
└─────┬──────┘
      │
┌────────────────┐
│ contract-test  │  pytest (client+server) - FAIL IF BREAK
└─────┬──────────┘
      │
┌────────────┐
│   build    │  Docker build, scan image
└─────┬──────┘
      │
┌──────────────┐
│ helm-package │  Helm lint, template validation
└─────┬────────┘
      │
┌────────────┐
│  deploy    │  Deploy to AKS (only on main branch)
└────────────┘
```

---

## 🔗 Azure Workload Identity Setup (Prerequisites)

### Before Deploying to AKS

```bash
# 1. Create User Assigned Managed Identity
az identity create \
  --resource-group <rg> \
  --name mcp-system-uami

UAMI_ID=$(az identity show -g <rg> -n mcp-system-uami --query clientId -o tsv)
UAMI_OBJECT_ID=$(az identity show -g <rg> -n mcp-system-uami --query principalId -o tsv)
TENANT_ID=$(az account show --query tenantId -o tsv)

# 2. Assign Reader role (adjust scopes as needed)
az role assignment create \
  --role Reader \
  --assignee $UAMI_OBJECT_ID \
  --scope /subscriptions/<sub-id>

# 3. Get AKS OIDC Issuer URL
AKS_OIDC_ISSUER=$(az aks show -g <rg> -n <aks-cluster> --query oidcIssuerProfile.issuerUrl -o tsv)

# 4. Create Federated Identity Credentials (for each service account)
az identity federated-identity-credential create \
  --resource-group <rg> \
  --identity-name mcp-system-uami \
  --name mcp-server-credential \
  --issuer $AKS_OIDC_ISSUER \
  --subject system:serviceaccount:default:mcp-server \
  --audience api://AzureADTokenExchange

az identity federated-identity-credential create \
  --resource-group <rg> \
  --identity-name mcp-system-uami \
  --name mcp-client-credential \
  --issuer $AKS_OIDC_ISSUER \
  --subject system:serviceaccount:default:mcp-client \
  --audience api://AzureADTokenExchange

# 5. Deploy Helm releases
helm install mcp-server ./mcp-server-chart \
  --set azure.clientId=$UAMI_ID \
  --set azure.tenantId=$TENANT_ID

helm install mcp-client ./mcp-client-chart \
  --set azure.clientId=$UAMI_ID \
  --set azure.tenantId=$TENANT_ID
```

---

## 📊 Observability & Monitoring

### Health Probes

| Probe | Endpoint | Validates | Action on Failure |
|-------|----------|-----------|-------------------|
| **Liveness** | `GET /health/live` | Process alive | K8s restarts pod |
| **Readiness** | `GET /health/ready` | Ready for traffic | K8s removes from LB |

### Logging

- **Structured Logging**: OpenTelemetry-compatible JSON
- **Log Levels**: DEBUG, INFO, WARN, ERROR
- **Fields**: timestamp, level, component, trace_id, error, context

### Metrics

- Pod CPU/Memory (HPA controlled)
- Tool execution latency (p50, p99)
- Error rates by tool
- Token refresh events

---

## 🔒 Security Posture

| Layer | Control |
|-------|---------|
| **Identity** | Azure Workload Identity (no pod identity, no IMDS MSI) |
| **Secrets** | GitLab CI variables, never in images/templates |
| **Network** | Kubernetes NetworkPolicy (optional, add-on) |
| **RBAC** | K8s RBAC + Azure IAM roles (least privilege) |
| **Image** | Scanned for vulnerabilities, signed (optional) |
| **Compliance** | No hardcoded credentials, audit logging enabled |

---

## 📈 Scalability & Performance

### Horizontal Scaling

- **Stateless FastMCP server**: Can scale to 10+ pods
- **HPA targets**: CPU 80%, Memory 85%
- **Client connection pooling**: httpx async client with connection reuse

### Performance Targets

- Tool invocation: <1s (p99)
- Token acquisition: <200ms (cached)
- Server startup: <5s
- Readiness probe: <3s

---

## ✅ Key Differentiators

1. **Azure Workload Identity (v2)**: OIDC-based, no legacy pod identity
2. **Contract-driven testing**: CI fails on schema breaks
3. **Fully async**: Non-blocking I/O throughout
4. **Production-hardened**: Health probes, HPA, error handling
5. **Multi-environment**: AKS + local dev + CI (unified auth abstraction)
6. **Enterprise-grade**: Structured logging, observability, security
