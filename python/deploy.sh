#!/bin/bash

# Top-level deployment script wrapper
# This script runs the appropriate deployment script from the deployment/ directory

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOYMENT_DIR="$SCRIPT_DIR/deployment"

# Get the script to run (local, docker, or minikube)
if [ $# -eq 0 ]; then
    echo "Usage: ./deploy.sh {local|docker|k8} [args...]"
    echo ""
    echo "Examples:"
    echo "  ./deploy.sh local --version CC-MAIN-2024-30"
    echo "  ./deploy.sh docker --worker-count 5"
    echo "  ./deploy.sh k8 stop"
    exit 1
fi

DEPLOY_MODE=$1
shift

case $DEPLOY_MODE in
    local)
        exec "$DEPLOYMENT_DIR/scripts/run_local.sh" "$@"
        ;;
    docker)
        exec "$DEPLOYMENT_DIR/scripts/run_docker.sh" "$@"
        ;;
    k8)
        exec "$DEPLOYMENT_DIR/scripts/run_k8.sh" "$@"
        ;;
    *)
        echo "Unknown deployment mode: $DEPLOY_MODE"
        echo "Use: local, docker, or k8"
        exit 1
        ;;
esac

