# Kubernetes Deployment

This directory contains Kubernetes manifests for deploying the Common Crawl Pipeline.

## Prerequisites

- Kubernetes cluster (minikube, kind, or cloud)
- `kubectl` configured to connect to your cluster
- Docker images built and available to the cluster

## Development vs Production

- **Development (Minikube)**: Port forwarding is automatically enabled
- **Production**: Services use `ClusterIP` by default. For external access, use:
  - `LoadBalancer` services (see `services-production.yaml`)
  - Ingress controller with proper routing
  - Manual port-forwarding for debugging

## Directory Structure

```
k8s/
├── namespace.yaml       # Creates commoncrawl namespace
├── configmap.yaml       # Application configuration
├── rabbitmq.yaml       # RabbitMQ deployment and service
├── minio.yaml          # MinIO deployment and service
├── prometheus.yaml     # Prometheus deployment and service
├── batcher.yaml        # Batcher job (runs once)
└── worker.yaml         # Worker deployment (scalable)

```

## Deployment Steps

### 1. Create Namespace

```bash
kubectl apply -f namespace.yaml
```

### 2. Create ConfigMaps

```bash
kubectl apply -f configmap.yaml
```

### 3. Deploy Infrastructure Services

```bash
kubectl apply -f rabbitmq.yaml
kubectl apply -f minio.yaml
kubectl apply -f prometheus.yaml
```

### 4. Build and Tag Docker Images

Build your images locally or push to a registry:

```bash
# Build local images
cd ..
docker build -f Dockerfile.batcher -t batcher:latest .
docker build -f Dockerfile.worker -t worker:latest .

# For Kubernetes (minikube or kind), load images into cluster
minikube image load batcher:latest worker:latest
# OR for kind:
kind load docker-image batcher:latest worker:latest --name <cluster-name>
```

### 5. Create Cluster Index ConfigMap

```bash
# Create ConfigMap from your cluster.idx file
kubectl create configmap cluster-idx --from-file=cluster.idx=path/to/cluster.idx -n commoncrawl

# Or embed directly in the ConfigMap
kubectl create configmap cluster-idx -n commoncrawl --from-literal=cluster.idx="$(cat path/to/cluster.idx)"
```

### 6. Deploy Application

```bash
kubectl apply -f batcher.yaml
kubectl apply -f worker.yaml
```

### 7. Scale Workers

```bash
# Scale to 3 workers
kubectl scale deployment worker -n commoncrawl --replicas=3
```

## Monitoring

### Check Pod Status

```bash
kubectl get pods -n commoncrawl
```

### View Logs

```bash
# Batcher logs (if job is still running)
kubectl logs -n commoncrawl -l app=batcher --tail=50

# Worker logs
kubectl logs -n commoncrawl -l app=worker --tail=50

# Specific worker
kubectl logs -n commoncrawl -l app=worker --tail=50 | head -n 20
```

### Access Services

```bash
# Port forward to access services locally

# RabbitMQ Management
kubectl port-forward svc/rabbitmq 15672:15672 -n commoncrawl
# Open http://localhost:15672 (guest/guest)

# MinIO Console
kubectl port-forward svc/minio 9002:9000 9003:9001 -n commoncrawl
# Open http://localhost:9003 (minioadmin/minioadmin) - Console
# Open http://localhost:9002 (minioadmin/minioadmin) - API

# Prometheus
kubectl port-forward svc/prometheus 9090:9090 -n commoncrawl
# Open http://localhost:9090
```

## Configuration

### Environment Variables

Edit `configmap.yaml` to change:
- `BATCHER_BATCH_SIZE`: URLs per batch
- `MIN_TEXT_LENGTH`: Minimum text length
- `MAX_TEXT_LENGTH`: Maximum text length
- `TOKENIZER_NAME`: Tokenizer model name
- `BUCKET_NAME`: MinIO bucket name
- `COMMONCRAWL_VERSION`: Common Crawl version

### Worker Count

Edit `worker.yaml` to change initial replica count:
```yaml
spec:
  replicas: 2  # Change this number
```

Or scale at runtime:
```bash
kubectl scale deployment worker -n commoncrawl --replicas=5
```

## Cleanup

To remove all resources:

```bash
kubectl delete namespace commoncrawl
```

Or delete individual resources:
```bash
kubectl delete -f worker.yaml
kubectl delete -f batcher.yaml
# etc.
```

## Production Considerations

1. **Image Registry**: Push images to a container registry (Docker Hub, GCR, ECR, etc.)
   - Change `imagePullPolicy: IfNotPresent`
   - Use full image path with registry

2. **Persistent Storage**: Use PersistentVolumes for MinIO and Prometheus data
   - Replace `emptyDir` with PersistentVolumeClaims
   - Configure appropriate storage classes

3. **Resource Limits**: Adjust CPU/memory limits based on your workload

4. **Secrets**: Use Kubernetes Secrets instead of hardcoded credentials
   ```bash
   kubectl create secret generic rabbitmq-credentials \
     --from-literal=username=guest \
     --from-literal=password=guest \
     -n commoncrawl
   ```

5. **Security**: Enable network policies, use non-root users, etc.

6. **High Availability**: Consider multiple replicas for critical services

7. **Ingress**: Add Ingress resources for external access

## Example: Using with Minikube

```bash
# Start minikube
minikube start

# Build images in minikube context
eval $(minikube docker-env)
docker build -f Dockerfile.batcher -t batcher:latest .
docker build -f Dockerfile.worker -t worker:latest .

# Deploy
kubectl apply -f k8s/

# Check status
kubectl get all -n commoncrawl
```

## Comparison with Docker Compose

| Feature | Docker Compose | Kubernetes |
|---------|---------------|------------|
| Local Development | ✅ Easy | ⚠️ More setup |
| Orchestration | ✅ Simple | ✅ Advanced |
| Scaling | Manual | ✅ Automatic |
| Service Discovery | ✅ Built-in | ✅ Built-in |
| Load Balancing | ⚠️ Manual | ✅ Automatic |
| Health Checks | ✅ Configurable | ✅ Native |
| Secrets Management | ⚠️ Basic | ✅ Native |
| Production Ready | ⚠️ Limited | ✅ Enterprise |

