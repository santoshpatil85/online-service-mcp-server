# AKS Deployment Guide: MCP Server with Azure Workload Identity

This guide provides step-by-step instructions for deploying the MCP Server to Azure Kubernetes Service (AKS) with Azure Workload Identity.

## Prerequisites

- Azure CLI installed and authenticated
- AKS cluster with Workload Identity enabled (version 1.28+)
- kubectl configured to access your AKS cluster
- Helm 3.0+
- Docker image pushed to ACR/GitLab Registry

### Verify AKS Workload Identity is Enabled

```bash
# Check if Workload Identity is enabled
az aks show -g <resource-group> -n <cluster-name> \
  --query oidcIssuerProfile.issuerUrl

# Should return something like:
# "https://uksouth.oic.prod-aks.azure.com/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/"
```

If not enabled, enable it:

```bash
az aks update -g <resource-group> -n <cluster-name> \
  --enable-oidc-issuer \
  --enable-workload-identity-on-kubelet
```

## Step 1: Create User Assigned Managed Identity

```bash
# Set variables
RG="<resource-group>"
CLUSTER_NAME="<cluster-name>"
UAMI_NAME="mcp-server-uami"

# Create UAMI
az identity create \
  --resource-group $RG \
  --name $UAMI_NAME

# Get UAMI details
UAMI_ID=$(az identity show -g $RG -n $UAMI_NAME --query clientId -o tsv)
UAMI_OBJECT_ID=$(az identity show -g $RG -n $UAMI_NAME --query principalId -o tsv)
TENANT_ID=$(az account show --query tenantId -o tsv)

# Export for later use
export UAMI_ID UAMI_OBJECT_ID TENANT_ID
echo "UAMI_ID=$UAMI_ID"
echo "TENANT_ID=$TENANT_ID"
```

## Step 2: Assign Azure Roles

Assign minimal required roles to the UAMI for accessing backend services:

```bash
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

# Reader role on subscription (adjust scope as needed)
az role assignment create \
  --role Reader \
  --assignee $UAMI_OBJECT_ID \
  --scope /subscriptions/$SUBSCRIPTION_ID
```

## Step 3: Create Kubernetes Namespace

```bash
kubectl create namespace mcp-system
```

## Step 4: Create Federated Identity Credentials

Get AKS OIDC issuer URL:

```bash
AKS_OIDC_ISSUER=$(az aks show -g $RG -n $CLUSTER_NAME \
  --query oidcIssuerProfile.issuerUrl -o tsv)

echo "AKS_OIDC_ISSUER=$AKS_OIDC_ISSUER"
```

Create federated credential for MCP Server:

```bash
az identity federated-identity-credential create \
  --resource-group $RG \
  --identity-name $UAMI_NAME \
  --name mcp-server-credential \
  --issuer $AKS_OIDC_ISSUER \
  --subject system:serviceaccount:mcp-system:mcp-server \
  --audience api://AzureADTokenExchange
```

Verify credential created:

```bash
az identity federated-identity-credential show \
  --resource-group $RG \
  --identity-name $UAMI_NAME \
  --name mcp-server-credential
```

## Step 5: Deploy MCP Server with Helm

Create values file `mcp-server-values.yaml`:

```yaml
azure:
  tenantId: "<TENANT_ID>"
  clientId: "<UAMI_ID>"
  authorityHost: "https://login.microsoftonline.com"
  scopes:
    - "https://management.azure.com/.default"

image:
  repository: "<registry>.azurecr.io/mcp-server"
  tag: "1.0.0"

replicaCount: 2

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 80

app:
  logLevel: "INFO"
  backendApiUrl: "https://api.example.com"
  backendApiTimeout: 10
  readinessCheckBackend: true

resources:
  requests:
    cpu: "200m"
    memory: "256Mi"
  limits:
    cpu: "1000m"
    memory: "1Gi"
```

Deploy:

```bash
helm install mcp-server ./helm/mcp-server-chart \
  --namespace mcp-system \
  --values mcp-server-values.yaml \
  --wait \
  --timeout 5m
```

Verify:

```bash
# Check pods
kubectl get pods -n mcp-system -l app.kubernetes.io/name=mcp-server

# Check service
kubectl get svc -n mcp-system -l app.kubernetes.io/name=mcp-server

# Check logs
kubectl logs -n mcp-system -l app.kubernetes.io/name=mcp-server --tail=50

# Test health
kubectl exec -n mcp-system <pod-name> -- curl -s http://localhost:3333/health
```

## Step 6: Verify Workload Identity

Check that Workload Identity is working:

```bash
# Get server pod name
SERVER_POD=$(kubectl get pods -n mcp-system -l app.kubernetes.io/name=mcp-server -o jsonpath='{.items[0].metadata.name}')

# Check environment variables
kubectl exec -n mcp-system $SERVER_POD -- env | grep AZURE

# Check service account annotations
kubectl get sa -n mcp-system mcp-server -o yaml

# Check pod annotations
kubectl get pod -n mcp-system $SERVER_POD -o yaml | grep azure.workload.identity

# Verify token file is mounted
kubectl exec -n mcp-system $SERVER_POD -- ls -la /var/run/secrets/azure/tokens/
```

## Step 7: Test Server Health and Tools

### Test Server Health

```bash
# Port-forward to server
kubectl port-forward -n mcp-system svc/mcp-server 3333:3333 &

# Test health endpoint
curl http://localhost:3333/health

# Test tool discovery
curl http://localhost:3333/tools

# Call a tool
curl -X POST http://localhost:3333/messages \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "get_user_profile",
      "arguments": {"user_id": "123"}
    }
  }'

# Stop port-forward
pkill -f "kubectl port-forward"
```

## Step 8: Monitoring and Troubleshooting

### Check Pod Events

```bash
kubectl describe pod -n mcp-system <pod-name>
```

### View Pod Logs

```bash
# Server logs
kubectl logs -n mcp-system -l app.kubernetes.io/name=mcp-server -f

# With timestamps
kubectl logs -n mcp-system -l app.kubernetes.io/name=mcp-server --timestamps=true
```

### Check HPA Status

```bash
kubectl get hpa -n mcp-system
kubectl describe hpa -n mcp-system mcp-server
```

### Common Issues

**Pods stuck in Pending:**
- Check node resource availability: `kubectl top nodes`
- Check pod events: `kubectl describe pod <pod-name>`

**Readiness probe failing:**
- Check logs: `kubectl logs <pod-name>`
- Verify Azure credentials: Check `/var/run/secrets/azure/tokens/token` exists
- Verify backend service is reachable

**Token acquisition fails:**
- Verify federated identity credentials exist
- Verify service account name matches subject in credential
- Check UAMI has correct role assignments
- Verify OIDC issuer URL in credential matches actual issuer

## Step 9: Upgrade and Maintenance

### Update Image

```bash
helm upgrade mcp-server ./helm/mcp-server-chart \
  --namespace mcp-system \
  --set image.tag=1.1.0 \
  --values mcp-server-values.yaml \
  --wait
```

### Scale Manually

```bash
kubectl scale deployment mcp-server -n mcp-system --replicas=5
```

### View HPA Scaling

```bash
kubectl get hpa -n mcp-system -w
```

## Step 10: Cleanup

```bash
# Delete Helm release
helm uninstall mcp-server -n mcp-system

# Delete namespace
kubectl delete namespace mcp-system

# Delete Azure resources (if not needed)
az identity delete --name $UAMI_NAME --resource-group $RG
```

## Reference: Identity Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Azure AD                           │
│  (User Assigned Managed Identity: mcp-server-uami)  │
│                                                     │
│  Role Assignments:                                  │
│  ├─ Reader on /subscriptions/...                   │
│  └─ Custom roles for specific API access           │
└─────────────────────────────────────────────────────┘
         ▲                           ▲
         │ Token Exchange            │
         │ (RFC 8693)                │ OIDC Discovery
         │                           │
┌────────┴───────────────────────────┴──────────────┐
│         AKS Cluster (Workload Identity Enabled)    │
│                                                   │
│  ┌────────────────────────────────────────────┐  │
│  │     MCP Server Pod                         │  │
│  │  ┌──────────────────────────────────────┐ │  │
│  │  │ K8s Service Account: mcp-server     │ │  │
│  │  │ Annotations:                        │ │  │
│  │  │  - azure.workload.identity/use: true│ │  │
│  │  │  - azure.workload.identity/client-id│ │  │
│  │  │  - azure.workload.identity/tenant-id│ │  │
│  │  └──────────────────────────────────────┘ │  │
│  │                    ▲                       │  │
│  │        ┌───────────┴─────────────┐        │  │
│  │        │                         │        │  │
│  │  ┌─────────────────┐    ┌─────────────────┐│  │
│  │  │ WorkloadIdentity│    │  App Container  ││  │
│  │  │ Webhook injects │    │ (FastMCP)       ││  │
│  │  │ K8s JWT Token   │    │                 ││  │
│  │  │ to pod          │    │ WorkloadIdentity││  │
│  │  │                 │    │ Credential Flow ││  │
│  │  └─────────────────┘    │ ↓ Exchange token││  │
│  │        ▼                │ ↓ Get token     ││  │
│  │  /var/run/secrets/      │ ↓ Cache token   ││  │
│  │   azure/tokens/token    └─────────────────┘│  │
│  └────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────┘
```

## Further Reading

- [Azure Workload Identity Documentation](https://learn.microsoft.com/en-us/azure/aks/workload-identity-overview)
- [AKS Security Best Practices](https://learn.microsoft.com/en-us/azure/aks/security)
- [Helm Documentation](https://helm.sh/docs/)
