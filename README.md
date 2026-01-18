# Production-Grade MCP System on Azure Kubernetes Service (AKS)

## 🎯 Overview

This repository contains a **complete, production-grade implementation** of the Model Context Protocol (MCP) using **FastMCP**, deployed on **Azure Kubernetes Service (AKS)** with **Azure Workload Identity** for secure, credential-less authentication.

### Two Independent Projects

- **`mcp-server/`** - FastMCP Server exposing REST API-backed tools
- **`mcp-client/`** - FastMCP Client for tool discovery and invocation

## 📋 What's Included

✅ **Complete Architecture** - System design, authentication flow, MCP patterns  
✅ **Azure Workload Identity** - OIDC-based, credential-less authentication  
✅ **Production Helm Charts** - Kubernetes deployment with full security  
✅ **Contract Tests** - Client-server compatibility validation (CI/CD blocking)  
✅ **GitLab CI/CD** - Full pipelines for lint, test, build, deploy  
✅ **Comprehensive Docs** - Architecture guide, deployment guide, API docs  

## 🚀 Quick Start

### Local Development

**MCP Server:**
```bash
cd mcp-server
python -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
pytest tests/ -v --cov=src
python -m uvicorn src.main:app --reload
# Server at http://localhost:8000
```

**MCP Client:**
```bash
cd mcp-client
python -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
MCP_SERVER_URL=http://localhost:8000 pytest tests/ -v
python -m src.main  # Discovers tools and invokes examples
```

### Deploy to AKS

**See [AKS_DEPLOYMENT_GUIDE.md](AKS_DEPLOYMENT_GUIDE.md) for complete step-by-step instructions.**

Quick overview:
```bash
# Setup Azure Workload Identity (see full guide for details)
az identity create -g $RG -n mcp-system-uami
# ... Create federated credentials (see guide) ...

# Deploy MCP Server
helm install mcp-server mcp-server/helm/mcp-server-chart \
  -n mcp-system --create-namespace \
  --set azure.clientId=$UAMI_ID \
  --set azure.tenantId=$TENANT_ID

# Deploy MCP Client
helm install mcp-client mcp-client/helm/mcp-client-chart \
  -n mcp-system \
  --set azure.clientId=$UAMI_ID \
  --set azure.tenantId=$TENANT_ID

# Verify
kubectl get pods -n mcp-system
```

## 📚 Documentation

| Document | Content |
|----------|---------|
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | System design, auth flows, MCP patterns, Helm architecture |
| **[AKS_DEPLOYMENT_GUIDE.md](AKS_DEPLOYMENT_GUIDE.md)** | Step-by-step AKS deployment with Azure Workload Identity |
| **[mcp-server/README.md](mcp-server/README.md)** | Server API, tools, health probes, deployment details |
| **[mcp-client/README.md](mcp-client/README.md)** | Client API, tool discovery, contract testing |

## 🔐 Azure Workload Identity

This system uses **Azure Workload Identity** - a production-grade, OIDC-based, credential-less authentication method:

```
MCP Pod (AKS)
  ├─ K8s ServiceAccount with Workload Identity annotations
  └─ AKS Workload Identity Webhook injects K8s JWT token
         ↓ (Token file: /var/run/secrets/azure/tokens/token)
WorkloadIdentityCredential
  └─ Exchanges K8s JWT for Azure AD access token (RFC 8693)
         ↓
Azure AD OIDC Provider
  └─ Returns access token with specified scopes
         ↓
Authenticated REST API Calls (Bearer token)
```

**Key Benefits:**
- ✅ No secrets in container images
- ✅ No environment variables with credentials
- ✅ Tokens automatically refreshed by SDK
- ✅ Service Principal fallback for local development
- ✅ Compliance with security best practices

## 🧪 Testing & CI/CD

### Contract Tests (CI/CD Blocking)

```bash
# Start MCP Server
cd mcp-server && python -m uvicorn src.main:app &

# Run contract tests
cd mcp-client
pytest tests/contract/ -v

# Validates:
# ✅ Tool names match expected set
# ✅ Input/output schemas are valid JSON
# ✅ Error responses have standard format
# ✅ Tool invocation works end-to-end
# ❌ Pipeline FAILS if contracts break
```

### CI/CD Pipeline Stages

```
lint → unit-test → contract-test → build → helm-package → deploy
                        ↑ (BLOCKING)
```

Each project has `.gitlab-ci.yml` with:
- Pylint, Black, isort formatting
- pytest with coverage reports
- Contract tests (blocking gate)
- Docker multi-stage builds
- Helm chart validation
- AKS deployment (manual approval)

## 📦 MCP Tools

The server exposes **5 production-ready tools**:

| Tool | Purpose | Example |
|------|---------|---------|
| `get_user_profile` | Retrieve user profile | `get_user_profile(user_id="123", include_details=true)` |
| `list_users` | List users with pagination | `list_users(skip=0, limit=10)` |
| `create_ticket` | Create support ticket | `create_ticket(title="Bug", description="...", priority="high")` |
| `list_tickets` | List tickets with filter | `list_tickets(status="open", skip=0, limit=10)` |
| `query_data` | Query datasets | `query_data(dataset="users", filters={...}, limit=100)` |

All tools are:
- **Strongly typed** (Pydantic v2)
- **Async** (non-blocking I/O)
- **Error handling** (detailed error responses)
- **Documented** (descriptions, schemas)

## 🏗️ Project Structure

```
.
├── ARCHITECTURE.md                    # System design & patterns
├── AKS_DEPLOYMENT_GUIDE.md            # Step-by-step AKS deployment
│
├── mcp-server/                        # MCP Server (Independent Project)
│   ├── src/
│   │   ├── main.py                   # FastMCP server entry point
│   │   ├── config.py                 # Configuration management
│   │   ├── auth/
│   │   │   └── azure_identity.py     # Azure auth (AWI + SPN)
│   │   ├── clients/
│   │   │   └── rest_client.py        # Async REST client
│   │   ├── models/
│   │   │   ├── schemas.py            # Pydantic models
│   │   │   └── errors.py             # Error types
│   │   ├── tools/                    # Tool implementations
│   │   │   ├── user_tools.py
│   │   │   ├── ticket_tools.py
│   │   │   └── data_tools.py
│   │   └── logging/
│   │       └── __init__.py           # Structured JSON logging
│   ├── tests/
│   │   ├── unit/                     # Unit tests
│   │   ├── integration/              # Integration tests
│   │   └── conftest.py               # Pytest fixtures
│   ├── helm/mcp-server-chart/        # Kubernetes Helm chart
│   │   ├── Chart.yaml
│   │   ├── values.yaml
│   │   ├── templates/
│   │   │   ├── deployment.yaml
│   │   │   ├── service.yaml
│   │   │   ├── serviceaccount.yaml   # Workload Identity
│   │   │   ├── configmap.yaml
│   │   │   ├── hpa.yaml
│   │   │   ├── pdb.yaml
│   │   │   └── _helpers.tpl
│   ├── Dockerfile                    # Multi-stage build
│   ├── .gitlab-ci.yml                # GitLab CI/CD pipeline
│   ├── pyproject.toml                # Python project config
│   └── README.md                     # Server documentation
│
├── mcp-client/                        # MCP Client (Independent Project)
│   ├── src/
│   │   ├── main.py                   # Client entry point
│   │   ├── config.py                 # Configuration
│   │   ├── auth/
│   │   │   └── azure_identity.py     # Azure auth (same pattern)
│   │   ├── client/
│   │   │   ├── mcp_client.py         # MCP HTTP client
│   │   │   └── tool_discoverer.py    # Tool discovery & validation
│   ├── tests/
│   │   ├── unit/                     # Unit tests
│   │   ├── contract/                 # Contract tests
│   │   │   └── test_contract.py
│   │   └── conftest.py
│   ├── helm/mcp-client-chart/        # Kubernetes Helm chart
│   │   ├── Chart.yaml
│   │   ├── values.yaml
│   │   ├── templates/
│   │   │   ├── deployment.yaml
│   │   │   ├── serviceaccount.yaml
│   │   │   ├── configmap.yaml
│   │   │   ├── hpa.yaml
│   │   │   └── _helpers.tpl
│   ├── Dockerfile                    # Multi-stage build
│   ├── .gitlab-ci.yml                # GitLab CI/CD pipeline
│   ├── pyproject.toml                # Python project config
│   └── README.md                     # Client documentation
```

## 🛡️ Security Features

- ✅ **Azure Workload Identity** - No hardcoded secrets
- ✅ **Non-root containers** - Runs as UID 1000
- ✅ **Read-only root filesystem** - `/tmp` as emptyDir
- ✅ **Dropped capabilities** - All Linux capabilities removed
- ✅ **OIDC-based** - No legacy pod identity
- ✅ **Least privilege Azure RBAC** - Minimal role assignments
- ✅ **Network policies** - Optional Kubernetes NetworkPolicy
- ✅ **Image scanning** - Vulnerabilities scanned in CI/CD

## ⚙️ Technology Stack

- **Language**: Python 3.11+
- **MCP**: FastMCP, MCP Python SDK
- **Web**: FastAPI, uvicorn, httpx
- **Azure**: azure-identity, azure-core
- **Data**: Pydantic v2
- **Testing**: pytest, pytest-asyncio, syrupy (snapshots)
- **Deployment**: Helm 3.0+, Docker, GitLab CI/CD
- **Logging**: OpenTelemetry-compatible JSON logging

## 📊 Scalability & Performance

### Horizontal Pod Autoscaler

**MCP Server:**
- Min replicas: 2
- Max replicas: 10
- Metrics: CPU 80%, Memory 85%

**MCP Client:**
- Min replicas: 1
- Max replicas: 5
- Metrics: CPU 75%

### Performance Targets

- **Tool invocation**: <1s (p99)
- **Token acquisition**: <200ms (cached)
- **Server startup**: <5s
- **Readiness probe**: <3s

## 🔄 Development Workflow

1. Make changes in `mcp-server/` or `mcp-client/`
2. Run tests: `pytest tests/ -v --cov=src`
3. Run contract tests: `pytest tests/contract/ -v`
4. Format code: `black src/ && isort src/`
5. Submit MR for review

## 📝 License

Apache 2.0

## ❓ Troubleshooting

### Can't connect to server?
```bash
kubectl logs -n mcp-system -l app.kubernetes.io/name=mcp-server
kubectl exec <pod> -n mcp-system -- curl http://localhost:8000/health/ready
```

### Tool discovery times out?
```bash
DISCOVERY_TIMEOUT=30 python -m src.main
```

### Authentication fails?
```bash
kubectl get sa -n mcp-system mcp-server -o yaml
kubectl exec <pod> -n mcp-system -- ls /var/run/secrets/azure/tokens/
```

**See [AKS_DEPLOYMENT_GUIDE.md#troubleshooting](AKS_DEPLOYMENT_GUIDE.md#troubleshooting) for more details.**

## 📞 Support & Contact

- Review [ARCHITECTURE.md](ARCHITECTURE.md) for system design
- Check [AKS_DEPLOYMENT_GUIDE.md](AKS_DEPLOYMENT_GUIDE.md) for deployment instructions
- See project READMEs for component-specific documentation
- Contact: engineering@example.com
