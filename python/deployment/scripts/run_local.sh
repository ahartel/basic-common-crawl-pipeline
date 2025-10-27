#!/bin/bash

# Script to run the Common Crawl Pipeline locally (batcher and worker on host, infrastructure in Docker)
# Usage:
#   ./run_local.sh stop                  # Stop running application
#   ./run_local.sh --version CC-MAIN-2024-30 [--worker-count <count>]
#   ./run_local.sh --cluster-idx-filename <file> [--worker-count <count>]
#   ./run_local.sh <file> [worker_count]
# Arguments:
#   stop: Stop all running batcher and worker processes
#   --version: Common Crawl version (e.g., CC-MAIN-2024-30) - will auto-download cluster.idx
#   --cluster-idx-filename: Path to cluster index file
#   --worker-count: Number of worker processes to run (default: 1)
#   worker_count: Optional number of worker processes (positional argument)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOYMENT_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="$(dirname "$DEPLOYMENT_DIR")"

CLUSTER_IDX_FILE=""
WORKER_COUNT=1
POSITIONAL_ARGS=()
CRAWL_VERSION=""

# Check for stop command
if [ "$1" = "stop" ]; then
    echo "Stopping Common Crawl Pipeline processes..."
    
    # Find and kill batcher
    BATCHER_PIDS=$(pgrep -f "python.*batcher.py" || true)
    if [ ! -z "$BATCHER_PIDS" ]; then
        echo "Stopping batcher (PIDs: $BATCHER_PIDS)..."
        pkill -f "python.*batcher.py" || true
    fi
    
    # Find and kill workers
    WORKER_PIDS=$(pgrep -f "python.*worker.py" || true)
    if [ ! -z "$WORKER_PIDS" ]; then
        echo "Stopping workers (PIDs: $WORKER_PIDS)..."
        pkill -f "python.*worker.py" || true
    fi
    
    if [ -z "$BATCHER_PIDS" ] && [ -z "$WORKER_PIDS" ]; then
        echo "No running processes found."
    else
        echo "All processes stopped."
    fi
    exit 0
fi

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --cluster-idx-filename)
            CLUSTER_IDX_FILE="$2"
            shift 2
            ;;
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
            echo "Usage: $0 [--version <crawl>] [--cluster-idx-filename <file>] [--worker-count <count>]"
            echo "   or: $0 <cluster.idx> [worker_count]"
            exit 1
            ;;
        *)
            POSITIONAL_ARGS+=("$1")
            shift
            ;;
    esac
done

# If version provided, download cluster.idx automatically
if [ ! -z "$CRAWL_VERSION" ]; then
    CLUSTER_IDX_URL="https://data.commoncrawl.org/cc-index/collections/${CRAWL_VERSION}/indexes/cluster.idx"
    DEFAULT_CLUSTER_FILE="cluster-${CRAWL_VERSION}.idx"
    
    if [ ! -f "$DEFAULT_CLUSTER_FILE" ]; then
        echo "Downloading cluster.idx for ${CRAWL_VERSION}..."
        wget -O "$DEFAULT_CLUSTER_FILE" "$CLUSTER_IDX_URL"
        echo "✓ Downloaded to: $DEFAULT_CLUSTER_FILE"
    else
        echo "Using existing cluster.idx: $DEFAULT_CLUSTER_FILE"
    fi
    CLUSTER_IDX_FILE="$DEFAULT_CLUSTER_FILE"
fi

# If cluster index file not provided via flag or version, try positional args
if [ -z "$CLUSTER_IDX_FILE" ]; then
    if [ ${#POSITIONAL_ARGS[@]} -lt 1 ]; then
        echo "Error: Please provide the cluster index file path or version"
        echo "Usage: $0 [--version <crawl>] [--cluster-idx-filename <file>] [--worker-count <count>]"
        echo "   or: $0 <cluster.idx> [worker_count]"
        exit 1
    fi
    CLUSTER_IDX_FILE="${POSITIONAL_ARGS[0]}"
    # Use positional worker count only if --worker-count wasn't set
    if [ "$WORKER_COUNT" = "1" ] && [ ${#POSITIONAL_ARGS[@]} -ge 2 ]; then
        WORKER_COUNT="${POSITIONAL_ARGS[1]}"
    fi
fi

# Check if file exists
if [ ! -f "$CLUSTER_IDX_FILE" ]; then
    echo "Error: File not found: $CLUSTER_IDX_FILE"
    exit 1
fi

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

# Source environment variables from deployment directory
if [ -f "$DEPLOYMENT_DIR/.env" ]; then
    export $(grep -v '^#' "$DEPLOYMENT_DIR/.env" | xargs)
elif [ -f "$DEPLOYMENT_DIR/env-example" ]; then
    export $(grep -v '^#' "$DEPLOYMENT_DIR/env-example" | xargs)
fi

# Start infrastructure services in Docker
echo "Starting infrastructure services (RabbitMQ, MinIO, Prometheus)..."
cd "$DEPLOYMENT_DIR/docker"

if ! docker-compose ps | grep -q rabbitmq; then
    echo "Starting infrastructure containers..."
    docker-compose up -d rabbitmq minio prometheus
    
    echo "Waiting for services to be ready..."
    sleep 5
else
    echo "Infrastructure services already running"
fi

# Check if RabbitMQ is accessible
echo "Checking RabbitMQ connection..."
python3 -c "
import pika
import os
import sys
try:
    conn_str = os.getenv('RABBITMQ_CONNECTION_STRING', 'amqp://guest:guest@localhost:5672/')
    connection = pika.BlockingConnection(pika.URLParameters(conn_str))
    channel = connection.channel()
    channel.close()
    connection.close()
    print('✓ RabbitMQ is accessible')
except Exception as e:
    print('✗ RabbitMQ is not accessible:', e)
    print('Please start RabbitMQ:')
    print('  docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:management')
    sys.exit(1)
"

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Stopping application processes..."
    if [ ! -z "$BATCHER_PID" ]; then
        kill $BATCHER_PID 2>/dev/null || true
    fi
    pkill -f "python.*worker.py" || true
    echo "Cleanup complete."
}

trap cleanup EXIT INT TERM

echo ""
echo "Starting batcher with index file: $CLUSTER_IDX_FILE"
echo "Starting $WORKER_COUNT worker(s)"
echo ""

cd "$PROJECT_DIR"

# Export cluster index filename to environment so batcher.py can use it if needed
export CLUSTER_IDX_FILENAME="$CLUSTER_IDX_FILE"

# Start batcher in background
# For local, we use --cluster-idx-filename flag (env var is fallback)
python3 batcher.py --cluster-idx-filename "$CLUSTER_IDX_FILE" &
BATCHER_PID=$!

# Start workers
WORKER_PIDS=()
for i in $(seq 1 $WORKER_COUNT); do
    python3 worker.py &
    WORKER_PIDS+=($!)
    echo "Started worker $i (PID: ${WORKER_PIDS[-1]})"
done

echo ""
echo "Batcher and workers are running. Press Ctrl+C to stop."
echo ""

# Wait for all processes
wait $BATCHER_PID
