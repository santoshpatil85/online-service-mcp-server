# AKS Deployment Guide: MCP Client

This guide provides step-by-step instructions for deploying the MCP Client to Azure Kubernetes Service (AKS).

## Prerequisites

- Azure CLI installed and authenticated
- AKS cluster (version 1.28+)
- kubectl configured to access your AKS cluster
- Helm 3.0+
- Docker image pushed to ACR/GitLab Registry
- MCP Server already deployed in the cluster

## Step 1: Create Kubernetes Namespace

The client should be deployed to the same namespace as the server:

```bash
kubectl create namespace mcp-system
```

## Step 2: Deploy MCP Client with Helm

Create values file `mcp-client-values.yaml`:

```yaml
image:
  repository: "<registry>.azurecr.io/mcp-client"
  tag: "1.0.0"

replicaCount: 1

autoscaling:
  enabled: true
  minReplicas: 1
  maxReplicas: 5
  targetCPUUtilizationPercentage: 75

app:
  logLevel: "INFO"
  mcpServerUrl: "http://mcp-server:3333"

resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "500m"
    memory: "512Mi"
```

Deploy:

```bash
helm install mcp-client ./helm/mcp-client-chart \
  --namespace mcp-system \
  --values mcp-client-values.yaml \
  --wait \
  --timeout 5m
```

Verify:

```bash
# Check pods
kubectl get pods -n mcp-system -l app.kubernetes.io/name=mcp-client

# Check logs (should show tool discovery)
kubectl logs -n mcp-system -l app.kubernetes.io/name=mcp-client -f

# Expected: "Discovered X tools" in logs
```

## Step 3: Verify Client-Server Communication

### Check Client Discovery

```bash
# Get client pod name
CLIENT_POD=$(kubectl get pods -n mcp-system -l app.kubernetes.io/name=mcp-client -o jsonpath='{.items[0].metadata.name}')

# Check if client discovered tools
kubectl logs -n mcp-system $CLIENT_POD | grep -i "discovered\|tool"

# Expected output: "Discovered X tools"
```

### Test Communication

```bash
# Port-forward to client (if needed for debugging)
kubectl port-forward -n mcp-system svc/mcp-client 8000:8000 &

# From another pod, test server
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -n mcp-system -- \
  curl http://mcp-server:3333/health

# Stop port-forward
pkill -f "kubectl port-forward"
```

## Step 4: Monitoring and Troubleshooting

### View Pod Logs

```bash
# Client logs
kubectl logs -n mcp-system -l app.kubernetes.io/name=mcp-client -f

# With timestamps
kubectl logs -n mcp-system -l app.kubernetes.io/name=mcp-client --timestamps=true
```

### Check Pod Events

```bash
kubectl describe pod -n mcp-system <pod-name>
```

### Common Issues

**Pod won't start:**
- Check node resource availability: `kubectl top nodes`
- Check pod events: `kubectl describe pod <pod-name>`
- View logs: `kubectl logs <pod-name> --previous` (if crashed)

**Cannot connect to server:**
- Verify server URL is correct: `echo $MCP_SERVER_URL`
- Verify server is running: `kubectl get pods -n mcp-system -l app.kubernetes.io/name=mcp-server`
- Check DNS resolution: `kubectl run -it --rm -n mcp-system debug --image=busybox --restart=Never -- nslookup mcp-server`

**Tool discovery fails:**
- Check server health: `kubectl exec -n mcp-system <server-pod> -- curl http://localhost:3333/health`
- Verify network connectivity: `kubectl exec -n mcp-system <client-pod> -- curl http://mcp-server:3333/health`
- Check client logs for errors: `kubectl logs -n mcp-system <client-pod>`

## Step 5: Upgrade and Maintenance

### Update Image

```bash
helm upgrade mcp-client ./helm/mcp-client-chart \
  --namespace mcp-system \
  --set image.tag=1.1.0 \
  --values mcp-client-values.yaml \
  --wait
```

### Scale Manually

```bash
kubectl scale deployment mcp-client -n mcp-system --replicas=3
```

### View HPA Scaling

```bash
kubectl get hpa -n mcp-system -w
```

## Step 6: Cleanup

```bash
# Delete Helm release
helm uninstall mcp-client -n mcp-system

# Delete namespace (if no other services)
kubectl delete namespace mcp-system
```

## Architecture

The MCP Client uses FastMCP's HTTP transport to communicate with the MCP Server:

```
┌────────────────────────────────────────────┐
│     MCP Client Pod (AKS)                   │
│  ┌──────────────────────────────────────┐ │
│  │ FastMCP ClientSession                │ │
│  │ HTTPClientTransport                  │ │
│  │ ↓ HTTP calls to MCP Server           │ │
│  └──────────────────────────────────────┘ │
└────────────────────────────────────────────┘
         ↓ (HTTP calls)
┌────────────────────────────────────────────┐
│     MCP Server Pod (AKS)                   │
│  ┌──────────────────────────────────────┐ │
│  │ FastMCP HTTP Server (port 3333)      │ │
│  │ Service mesh DNS: mcp-server:3333    │ │
│  └──────────────────────────────────────┘ │
└────────────────────────────────────────────┘
```

## Network Policy (Optional)

To restrict client-server communication:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: mcp-network-policy
  namespace: mcp-system
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: mcp-server
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app.kubernetes.io/name: mcp-client
    ports:
    - protocol: TCP
      port: 3333
```

Apply:

```bash
kubectl apply -f network-policy.yaml
```

## Further Reading

- [Kubernetes Services](https://kubernetes.io/docs/concepts/services-networking/service/)
- [Kubectl Port-Forward](https://kubernetes.io/docs/tasks/access-application-cluster/port-forward-access-application-cluster/)
- [Debugging in Kubernetes](https://kubernetes.io/docs/tasks/debug-application-cluster/debug-pod-replication-controller/)
