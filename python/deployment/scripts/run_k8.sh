#!/bin/bash

# Script to deploy Common Crawl Pipeline to Minikube
# Usage: 
#   ./run_minikube.sh stop                  # Stop all resources
#   ./run_minikube.sh [--worker-count <count>]  # Deploy with workers (default: 2)
# Cluster index file: Put your cluster.idx in k8s/cluster.idx
# Arguments:
#   stop: Stop all resources and port forwarding
#   --worker-count: Number of worker instances to run (default: 2)
#   worker_count: Optional number of workers (positional argument)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOYMENT_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="$(dirname "$DEPLOYMENT_DIR")"
# PROJECT_DIR is now python/, but we need the repository root (parent of python/)
REPO_ROOT="$(dirname "$PROJECT_DIR")"

# Check for stop command
if [ "$1" = "stop" ]; then
    echo "Stopping Common Crawl Pipeline in Minikube..."
    echo "Deleting all resources in commoncrawl namespace..."
    kubectl delete namespace commoncrawl --ignore-not-found=true
    echo "Stopping port forwarding processes..."
    pkill -f "kubectl port-forward.*commoncrawl" || true
    echo "✓ All resources and port-forwarding stopped."
    exit 0
fi

WORKER_COUNT=2
POSITIONAL_ARGS=()
CRAWL_VERSION=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --worker-count)
            WORKER_COUNT="$2"
            shift 2
            ;;
        --version)
            CRAWL_VERSION="$2"
            shift 2
            ;;
        -*)
            echo "Unknown option: $1"
            echo "Usage: $0 [--version <crawl>] [--worker-count <count>]"
            exit 1
            ;;
        *)
            POSITIONAL_ARGS+=("$1")
            shift
            ;;
    esac
done

# If worker-count not provided via flag, use positional arg
if [ "$WORKER_COUNT" = "2" ] && [ ${#POSITIONAL_ARGS[@]} -gt 0 ]; then
    WORKER_COUNT="${POSITIONAL_ARGS[0]}"
fi

echo "Setting up Common Crawl Pipeline in Minikube with $WORKER_COUNT worker(s)..."

# Check if minikube is installed
if ! command -v minikube &> /dev/null; then
    echo "Error: minikube is not installed"
    echo "Install from: https://minikube.sigs.k8s.io/docs/start/"
    exit 1
fi

# Check if minikube is running
if ! minikube status &> /dev/null; then
    echo "Starting minikube..."
    minikube start
else
    echo "Minikube is running"
fi

# Set up minikube docker environment
echo "Setting up Docker environment for Minikube..."
eval $(minikube docker-env)

# Check for version flag to auto-download cluster.idx
if [ ! -z "$CRAWL_VERSION" ] && [ ! -f "$DEPLOYMENT_DIR/kubernetes/cluster.idx" ]; then
    echo "Downloading cluster.idx for ${CRAWL_VERSION}..."
    CLUSTER_IDX_URL="https://data.commoncrawl.org/cc-index/collections/${CRAWL_VERSION}/indexes/cluster.idx"
    wget -O "$DEPLOYMENT_DIR/kubernetes/cluster.idx" "$CLUSTER_IDX_URL"
    echo "✓ Downloaded to: kubernetes/cluster.idx"
fi

# Check if cluster index file exists
if [ ! -f "$DEPLOYMENT_DIR/kubernetes/cluster.idx" ]; then
    echo "Warning: kubernetes/cluster.idx not found."
    echo "Please provide --version CC-MAIN-2024-30 or place your cluster index file at: kubernetes/cluster.idx"
    read -p "Do you want to continue without it? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Build Docker images
echo "Building Docker images..."
if ! docker build -f "$DEPLOYMENT_DIR/docker/Dockerfile.batcher" -t batcher:latest "$REPO_ROOT"; then
    echo "Error: Failed to build batcher image"
    exit 1
fi

if ! docker build -f "$DEPLOYMENT_DIR/docker/Dockerfile.worker" -t worker:latest "$REPO_ROOT"; then
    echo "Error: Failed to build worker image"
    exit 1
fi

echo "✓ Docker images built successfully (already in minikube context)"

cd "$DEPLOYMENT_DIR/kubernetes"

# Apply namespace and config
echo "Creating namespace and configuration..."
kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml

# Copy cluster index file to minikube if it exists
if [ -f "cluster.idx" ]; then
    echo "Copying cluster.idx to Minikube..."
    # Use /tmp which is writable without root permissions
    minikube ssh "mkdir -p /tmp/input"
    # Copy the file into minikube
    minikube cp cluster.idx /tmp/input/cluster.idx
    echo "✓ Cluster index file copied to Minikube"
else
    echo "Warning: cluster.idx not found. The batcher will need to download it."
fi

# Update batcher.yaml and worker.yaml to use env from deployment
if [ -f "$DEPLOYMENT_DIR/env-example" ]; then
    export $(grep -v '^#' "$DEPLOYMENT_DIR/env-example" | xargs)
fi

# Deploy infrastructure services
echo "Deploying infrastructure services..."
kubectl apply -f rabbitmq.yaml
kubectl apply -f minio.yaml
kubectl apply -f prometheus.yaml

# Wait for services to be ready
echo "Waiting for services to be ready..."
kubectl wait --for=condition=available --timeout=120s deployment/rabbitmq -n commoncrawl || true
kubectl wait --for=condition=available --timeout=120s deployment/minio -n commoncrawl || true
kubectl wait --for=condition=available --timeout=120s deployment/prometheus -n commoncrawl || true

# Deploy workers
echo "Deploying workers..."
kubectl apply -f worker.yaml

# Scale workers
if [ "$WORKER_COUNT" -gt 2 ]; then
    echo "Scaling workers to $WORKER_COUNT..."
    kubectl scale deployment worker -n commoncrawl --replicas=$WORKER_COUNT
fi

# Deploy batcher
echo "Deploying batcher..."
kubectl apply -f batcher.yaml

echo ""
echo "✓ Deployment complete!"
echo ""
echo "Status:"
kubectl get pods -n commoncrawl
echo ""

# Check if running in minikube - only port forward for development
if minikube status &> /dev/null; then
    echo "Detected Minikube - Starting port forwarding for browser access..."
    # Kill any existing port-forward processes for this namespace
    pkill -f "kubectl port-forward.*commoncrawl" || true
    sleep 1

    # Start port forwarding in background
    nohup kubectl port-forward svc/rabbitmq 15672:15672 -n commoncrawl > /tmp/rabbitmq-pf.log 2>&1 &
    nohup kubectl port-forward svc/minio 9002:9000 9003:9001 -n commoncrawl > /tmp/minio-pf.log 2>&1 &
    nohup kubectl port-forward svc/prometheus 9090:9090 -n commoncrawl > /tmp/prometheus-pf.log 2>&1 &

    echo "✓ Port forwarding started!"
    sleep 2

    echo ""
    echo "You can now access:"
    echo "  - RabbitMQ Management: http://localhost:15672 (guest/guest)"
    echo "  - MinIO API:           http://localhost:9002 (minioadmin/minioadmin)"
    echo "  - MinIO Console:       http://localhost:9003 (minioadmin/minioadmin)"
    echo "  - Prometheus:          http://localhost:9090"
else
    echo "Production cluster detected - Port forwarding disabled."
    echo ""
    echo "To access services in production, consider:"
    echo "  1. Expose services as LoadBalancer (see service YAMLs)"
    echo "  2. Set up an Ingress controller"
    echo "  3. Use kubectl port-forward manually if needed:"
    echo "     kubectl port-forward svc/rabbitmq 15672:15672 -n commoncrawl"
    echo "     kubectl port-forward svc/minio 9002:9000 -n commoncrawl"
    echo "     kubectl port-forward svc/prometheus 9090:9090 -n commoncrawl"
fi

echo ""
echo "Useful commands:"
echo "  View logs:             kubectl logs -n commoncrawl -l app=worker -f"
echo "  View batcher logs:      kubectl logs -n commoncrawl -l app=batcher -f"
echo "  Watch pods:             kubectl get pods -n commoncrawl -w"
echo "  Scale workers:          kubectl scale deployment worker -n commoncrawl --replicas=N"
echo "  Stop everything:        ./deploy.sh k8 stop"

