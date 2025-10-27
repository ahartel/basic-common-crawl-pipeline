#!/bin/bash

# Script to run the Docker setup for Common Crawl Pipeline
# Usage: 
#   ./run_docker.sh stop                  # Stop all services
#   ./run_docker.sh [--version <crawl>] [--worker-count <count>]  # Deploy with workers (default: 1)
# Arguments:
#   stop: Stop all Docker services
#   --version: Common Crawl version (e.g., CC-MAIN-2024-30) - will auto-download cluster.idx to input/
#   --worker-count: Number of worker instances to run (default: 1)
#   worker_count: Optional number of workers (positional argument)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOYMENT_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="$(dirname "$DEPLOYMENT_DIR")"

WORKER_COUNT=1
POSITIONAL_ARGS=()
CRAWL_VERSION=""

# Check for stop command
if [ "$1" = "stop" ]; then
    echo "Stopping Docker services..."
    cd "$DEPLOYMENT_DIR/docker"
    docker-compose down
    exit 0
fi

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
if [ "$WORKER_COUNT" = "1" ] && [ ${#POSITIONAL_ARGS[@]} -gt 0 ]; then
    WORKER_COUNT="${POSITIONAL_ARGS[0]}"
fi

echo "Setting up Docker environment with $WORKER_COUNT worker(s)..."

# Check if .env exists in deployment directory, if not copy from env-example
if [ ! -f "$DEPLOYMENT_DIR/.env" ]; then
    if [ -f "$DEPLOYMENT_DIR/env-example" ]; then
        echo "Creating .env file from env-example..."
        cp "$DEPLOYMENT_DIR/env-example" "$DEPLOYMENT_DIR/.env"
        echo "Using default configuration. Edit $DEPLOYMENT_DIR/.env to customize."
    else
        echo "Error: env-example not found at $DEPLOYMENT_DIR/env-example"
        exit 1
    fi
fi

# Change to docker directory
cd "$DEPLOYMENT_DIR/docker"

# Create input directory if it doesn't exist
mkdir -p input

# Download cluster.idx if version is provided
if [ ! -z "$CRAWL_VERSION" ]; then
    mkdir -p input
    CLUSTER_IDX_URL="https://data.commoncrawl.org/cc-index/collections/${CRAWL_VERSION}/indexes/cluster.idx"
    
    if [ ! -f "input/cluster.idx" ]; then
        echo "Downloading cluster.idx for ${CRAWL_VERSION}..."
        wget -O "input/cluster.idx" "$CLUSTER_IDX_URL"
        echo "✓ Downloaded to: input/cluster.idx"
    else
        echo "Using existing input/cluster.idx"
    fi
fi

# Check if cluster.idx exists
if [ ! -f "input/cluster.idx" ]; then
    echo "Warning: input/cluster.idx not found."
    echo "Either provide --version CC-MAIN-2024-30 or place your cluster.idx file at input/cluster.idx"
    echo "The batcher will fail without this file."
fi

# Build and start services
echo "Building Docker images..."
docker-compose build

echo "Starting services with $WORKER_COUNT worker(s)..."
docker-compose up -d

if [ "$WORKER_COUNT" -gt 1 ]; then
    echo "Scaling workers to $WORKER_COUNT..."
    docker-compose up -d --scale worker=$WORKER_COUNT
fi

echo ""
echo "Services are running:"
echo "- RabbitMQ Management: http://localhost:15672 (guest/guest)"
echo "- MinIO Console: http://localhost:9003 (minioadmin/minioadmin)"
echo "- Prometheus: http://localhost:9090"
echo ""
echo "View logs with:"
echo "  docker-compose logs -f batcher"
echo "  docker-compose logs -f worker"
echo ""
echo "To scale workers:"
echo "  docker-compose up -d --scale worker=N"
echo ""
echo "To stop services:"
echo "  docker-compose down"

