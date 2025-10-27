#!/bin/bash

# Port-forward script for accessing services locally
# Usage: ./k8s/port-forward.sh

set -e

# Check if namespace exists
if ! kubectl get namespace commoncrawl &> /dev/null; then
    echo "Error: commoncrawl namespace not found"
    echo "Run ./run_minikube.sh first to deploy"
    exit 1
fi

echo "Starting port forwarding for services in commoncrawl namespace..."
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Stopping port forwarding..."
    pkill -f "kubectl port-forward" || true
}

trap cleanup EXIT INT TERM

# Start port forwarding in background
kubectl port-forward svc/rabbitmq 15672:15672 -n commoncrawl &
PIDS="$!"

kubectl port-forward svc/minio 9001:9001 -n commoncrawl &
PIDS="$PIDS $!"

kubectl port-forward svc/prometheus 9090:9090 -n commoncrawl &
PIDS="$PIDS $!"

echo "✓ Port forwarding started!"
echo ""
echo "You can now access:"
echo "  - RabbitMQ Management: http://localhost:15672 (guest/guest)"
echo "  - MinIO Console:       http://localhost:9001 (minioadmin/minioadmin)"
echo "  - Prometheus:          http://localhost:9090"
echo ""
echo "Press Ctrl+C to stop port forwarding"

# Wait for all processes
wait

