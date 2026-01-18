# MCP Server

Production-grade Model Context Protocol (MCP) Server using FastMCP, with Azure Workload Identity authentication and deployment on Azure Kubernetes Service (AKS).

## Overview

This MCP Server provides:

- **5 MCP Tools** for interacting with backend services (users, tickets, data queries)
- **Azure Workload Identity** integration for secure, credential-less authentication
- **Async FastMCP** implementation with full Pydantic v2 type safety
- **Kubernetes-native** health probes and Horizontal Pod Autoscaling
- **Production-grade** error handling, structured logging, and retry logic

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  MCP Server (FastMCP)                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  MCP Tools:                                               │
│  • get_user_profile(user_id, include_details)            │
│  • list_users(skip, limit)                               │
│  • create_ticket(title, description, priority)           │
│  • list_tickets(status, skip, limit)                     │
│  • query_data(dataset, filters, limit)                   │
│                                                             │
│  Health Endpoints:                                         │
│  • GET /health/live (K8s liveness probe)                 │
│  • GET /health/ready (K8s readiness probe)               │
│                                                             │
│  Authentication:                                           │
│  • Azure Workload Identity (in AKS)                       │
│  • Service Principal fallback (local dev/CI)             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
         ↓ (authenticated calls with Bearer token)
┌─────────────────────────────────────────────────────────────┐
│              Backend REST API                               │
│         (e.g., https://api.example.com)                     │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

### Local Development

- Python 3.11+
- pip or uv
- Azure CLI (for testing Workload Identity locally)

### AKS Deployment

- Azure Kubernetes Service cluster (1.28+)
- Workload Identity enabled on AKS
- User Assigned Managed Identity (UAMI) with federated credentials
- Helm 3.0+

## Local Development

### 1. Clone and Setup

```bash
cd mcp-server
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements-dev.txt
```

### 2. Configure Environment

Create `.env` file (for local testing with Service Principal):

```bash
AZURE_TENANT_ID="your-tenant-id"
AZURE_CLIENT_ID="your-client-id"
AZURE_CLIENT_SECRET="your-client-secret"
BACKEND_API_URL="https://api.example.com"
LOG_LEVEL="DEBUG"
```

### 3. Run Server

```bash
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Server will be available at `http://localhost:8000`

### 4. Test Health Endpoints

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

### 5. Run Tests

```bash
# Unit tests
pytest tests/unit/ -v --cov=src

# Integration tests
pytest tests/integration/ -v

# All tests
pytest tests/ -v --cov=src --cov-report=html
```

## Docker Build

### Build Locally

```bash
docker build -t mcp-server:latest .
```

### Run Container

```bash
docker run -p 8000:8000 \
  -e AZURE_TENANT_ID="your-tenant-id" \
  -e AZURE_CLIENT_ID="your-client-id" \
  -e AZURE_CLIENT_SECRET="your-client-secret" \
  -e BACKEND_API_URL="https://api.example.com" \
  mcp-server:latest
```

### Push to Registry

```bash
docker tag mcp-server:latest registry.example.com/mcp-server:1.0.0
docker push registry.example.com/mcp-server:1.0.0
```

## Kubernetes Deployment

### Prerequisites: Azure Workload Identity Setup

```bash
# 1. Create User Assigned Managed Identity
az identity create \
  --resource-group <rg> \
  --name mcp-system-uami

UAMI_ID=$(az identity show -g <rg> -n mcp-system-uami --query clientId -o tsv)

# 2. Get AKS OIDC Issuer
AKS_OIDC_ISSUER=$(az aks show -g <rg> -n <aks-cluster> \
  --query oidcIssuerProfile.issuerUrl -o tsv)

# 3. Create Federated Identity Credential
az identity federated-identity-credential create \
  --resource-group <rg> \
  --identity-name mcp-system-uami \
  --name mcp-server-credential \
  --issuer $AKS_OIDC_ISSUER \
  --subject system:serviceaccount:mcp-system:mcp-server \
  --audience api://AzureADTokenExchange
```

### Deploy with Helm

```bash
helm install mcp-server ./helm/mcp-server-chart \
  --namespace mcp-system \
  --create-namespace \
  --set azure.clientId=$UAMI_ID \
  --set azure.tenantId=$(az account show --query tenantId -o tsv) \
  --set image.tag=1.0.0
```

### Verify Deployment

```bash
# Check pods
kubectl get pods -n mcp-system

# Check service
kubectl get svc -n mcp-system

# View logs
kubectl logs -n mcp-system -l app.kubernetes.io/name=mcp-server --tail=100 -f

# Test health probes
kubectl port-forward -n mcp-system svc/mcp-server 8000:8000
curl http://localhost:8000/health/ready
```

### Scale Deployment

```bash
# Manual scaling
kubectl scale deployment mcp-server -n mcp-system --replicas=3

# HPA is configured in Helm chart
kubectl get hpa -n mcp-system
```

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `AZURE_TENANT_ID` | Azure AD tenant ID | - | Yes |
| `AZURE_CLIENT_ID` | UAMI client ID | - | Yes |
| `AZURE_AUTHORITY_HOST` | Azure AD authority | `https://login.microsoftonline.com` | No |
| `AZURE_CLIENT_SECRET` | Service Principal secret | - | No (SPN fallback only) |
| `AZURE_FEDERATED_TOKEN_FILE` | K8s service account token path | `/var/run/secrets/azure/tokens/token` | No |
| `BACKEND_API_URL` | Backend service URL | - | Yes |
| `BACKEND_API_TIMEOUT` | Backend request timeout (seconds) | `10` | No |
| `LOG_LEVEL` | Logging level | `INFO` | No |
| `DEBUG` | Debug mode | `false` | No |
| `READINESS_CHECK_BACKEND` | Include backend in readiness probe | `true` | No |

### Helm Configuration

See [values.yaml](helm/mcp-server-chart/values.yaml) for full Helm configuration options.

Key sections:
- `azure`: Azure Workload Identity settings
- `image`: Container image and pull policy
- `replicaCount` / `autoscaling`: Pod scaling
- `resources`: CPU/memory requests and limits
- `probes`: Health probe configuration
- `app`: Application settings

## Tools Reference

### get_user_profile

Retrieve a user's profile.

**Input:**
- `user_id` (string, required): User unique identifier
- `include_details` (boolean, optional): Include detailed profile info

**Output:**
- `id`: User ID
- `name`: User full name
- `email`: User email
- `created_at`: Account creation timestamp
- `details`: Additional profile details (if requested)

### list_users

List users with pagination.

**Input:**
- `skip` (integer, optional, default=0): Records to skip
- `limit` (integer, optional, default=10): Max records to return

**Output:**
- `total`: Total number of users
- `items`: Array of user profiles

### create_ticket

Create a support ticket.

**Input:**
- `title` (string, required): Ticket title (1-200 chars)
- `description` (string, required): Ticket description (10-5000 chars)
- `priority` (string, optional): Priority level (low, medium, high, critical)
- `assignee_id` (string, optional): Assignee user ID

**Output:**
- `id`: Ticket ID
- `title`: Ticket title
- `description`: Ticket description
- `priority`: Ticket priority
- `status`: Ticket status (open, in_progress, closed)
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp
- `assignee_id`: Assignee user ID (if set)

### list_tickets

List support tickets with filtering.

**Input:**
- `status` (string, optional): Filter by status (open, in_progress, closed)
- `skip` (integer, optional, default=0): Records to skip
- `limit` (integer, optional, default=10): Max records to return

**Output:**
- `total`: Total number of tickets
- `items`: Array of ticket objects

### query_data

Query data from datasets.

**Input:**
- `dataset` (string, required): Dataset name to query
- `filters` (object, optional): Query filters
- `limit` (integer, optional, default=100): Max rows to return

**Output:**
- `dataset`: Dataset name
- `rows`: Number of rows returned
- `data`: Query results array

## Health Probes

### Liveness Probe (`/health/live`)

Kubernetes uses this to determine if the pod process is alive.

- **Endpoint**: `GET /health/live`
- **Response**: `{"status": "alive", "timestamp": "...", "service_version": "1.0.0"}`
- **K8s Config**: Checked every 30 seconds after 10s delay

### Readiness Probe (`/health/ready`)

Kubernetes uses this to determine if the pod is ready to accept traffic.

Checks:
1. FastMCP server initialized
2. Azure AD token acquisition successful
3. Backend service health (optional, configured via `READINESS_CHECK_BACKEND`)

- **Endpoint**: `GET /health/ready`
- **Response**: `{"status": "ready", "timestamp": "...", "dependencies": {...}}`
- **K8s Config**: Checked every 10 seconds after 5s delay

## Authentication Flow

### In AKS with Workload Identity

1. Pod starts → AKS webhook injects service account token
2. Application calls `get_access_token()`
3. `WorkloadIdentityCredential` reads K8s token from `/var/run/secrets/azure/tokens/token`
4. Token is exchanged with Azure AD OIDC provider for access token
5. Access token cached by azure-identity SDK
6. All REST calls to backend include `Authorization: Bearer <token>`

### Local Development with Service Principal

1. Environment variables set: `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`
2. Application calls `get_access_token()`
3. `ClientSecretCredential` uses client secret to obtain token
4. Token cached and reused
5. All REST calls use Bearer token

**Important:** Never commit `AZURE_CLIENT_SECRET` to git. Use `.env` file with `.gitignore`.

## Error Handling

Errors are returned in standard format:

```json
{
  "error": "VALIDATION_ERROR|SERVICE_ERROR|AUTHENTICATION_ERROR|TIMEOUT_ERROR",
  "message": "Descriptive error message",
  "details": {
    "additional": "context"
  }
}
```

**Error Types:**
- `VALIDATION_ERROR`: Input validation failed
- `SERVICE_ERROR`: Downstream service call failed
- `AUTHENTICATION_ERROR`: Azure AD token acquisition failed
- `TIMEOUT_ERROR`: Request exceeded timeout
- `INTERNAL_ERROR`: Unexpected error

## Structured Logging

All logs are output as structured JSON for easy parsing:

```json
{
  "timestamp": "2024-01-18T10:30:45.123456",
  "level": "INFO",
  "logger": "src.tools.user_tools",
  "message": "Retrieved user profile: user-123",
  "module": "user_tools",
  "function": "get_user_profile",
  "line": 42,
  "trace_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

## Troubleshooting

### Readiness Probe Failing

**Symptoms**: Pods never reach "Ready" status

**Diagnosis:**
```bash
kubectl describe pod -n mcp-system <pod-name>
kubectl logs -n mcp-system <pod-name>
```

**Common Causes:**
- Azure Workload Identity not configured (federated credentials missing)
- Backend API URL incorrect or unreachable
- Azure AD token acquisition failing

**Solution:**
```bash
# Verify Workload Identity
kubectl get serviceaccount -n mcp-system mcp-server -o yaml

# Check environment variables
kubectl exec -n mcp-system <pod-name> -- env | grep AZURE

# Test token acquisition
kubectl exec -n mcp-system <pod-name> -- curl -s http://localhost:8000/health/ready
```

### High Memory Usage

**Symptoms**: Pod memory keeps increasing

**Diagnosis:**
```bash
kubectl top pod -n mcp-system
```

**Common Causes:**
- Large query results not being paginated
- Token cache growing excessively (unlikely, handled by SDK)

**Solution:**
- Reduce page size in tool calls
- Increase memory limits in Helm values
- Enable container memory limits

### Token Acquisition Fails

**Symptoms**: Error: "Azure token acquisition failed"

**Diagnosis:**
```bash
# Check if token file exists
kubectl exec -n mcp-system <pod-name> -- ls -la /var/run/secrets/azure/tokens/

# Check pod annotations
kubectl describe pod -n mcp-system <pod-name> | grep azure.workload.identity
```

**Solution:**
- Verify federated identity credentials are configured
- Ensure service account has correct annotations
- Check Azure RBAC role assignments on UAMI

## Performance Tuning

### Horizontal Pod Autoscaler (HPA)

Current configuration:
- Min replicas: 2
- Max replicas: 10
- Target CPU: 80%
- Target Memory: 85%

Adjust in Helm values:

```yaml
autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 20
  targetCPUUtilizationPercentage: 70
```

### Resource Limits

Current defaults (see values.yaml):
- CPU request: 200m, limit: 1000m
- Memory request: 256Mi, limit: 1Gi

Adjust based on load testing:

```yaml
resources:
  requests:
    cpu: "500m"
    memory: "512Mi"
  limits:
    cpu: "2000m"
    memory: "2Gi"
```

### Connection Pooling

The REST client uses httpx's built-in connection pooling for performance.

## Contributing

1. Create a feature branch
2. Make changes and add tests
3. Run `pytest tests/ -v --cov=src`
4. Commit and push
5. Create MR

## License

Apache 2.0

## Support

For issues or questions:
1. Check logs: `kubectl logs -n mcp-system -l app.kubernetes.io/name=mcp-server`
2. Review [ARCHITECTURE.md](../ARCHITECTURE.md)
3. Contact: engineering@example.com
