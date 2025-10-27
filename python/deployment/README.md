# Deployment Guide

This directory contains all deployment-related files for the Common Crawl Pipeline.

## Directory Structure

```
deployment/
├── scripts/           # Deployment scripts
│   ├── run_local.sh      # Local development (app on host, infrastructure in Docker)
│   ├── run_docker.sh     # Full Docker deployment
│   └── run_k8.sh         # Kubernetes deployment
├── docker/            # Docker-related files
│   ├── docker-compose.yaml
│   ├── Dockerfile.batcher
│   ├── Dockerfile.worker
│   └── env-example
├── kubernetes/        # Kubernetes manifests
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── rabbitmq.yaml
│   ├── minio.yaml
│   ├── prometheus.yaml
│   ├── batcher.yaml
│   ├── worker.yaml
│   ├── port-forward.sh
│   └── README.md
└── docs/              # Deployment documentation
    ├── README.docker.md
    ├── SUMMARY.md
    ├── ENV_VARIABLES.md
    └── PORTS.md
```

## Quick Start

### From Python directory:

```bash
cd python
./deployment/scripts/run_local.sh --version CC-MAIN-2024-30

# Or use the convenience script
./deploy.sh local --version CC-MAIN-2024-30
```

### Or from deployment directory:

```bash
cd python/deployment
./scripts/run_local.sh --version CC-MAIN-2024-30
```

## Deployment Options

1. **Local Development** - `scripts/run_local.sh` or `./deploy.sh local`
   - Infrastructure in Docker
   - App runs as Python processes on host
   - Best for development and debugging

2. **Docker** - `scripts/run_docker.sh` or `./deploy.sh docker`
   - Everything in Docker containers
   - Production-like environment
   - Use `deployment/docker/` directory

3. **Kubernetes** - `scripts/run_k8.sh` or `./deploy.sh k8`
   - Deploys to any Kubernetes cluster
   - Supports Minikube, Docker Desktop, or cloud clusters
   - Use `deployment/kubernetes/` directory

## Common Commands

All scripts support:
- `--version CC-MAIN-2024-30` - Auto-download cluster.idx
- `--worker-count <N>` - Number of workers
- `stop` - Stop all resources

## Environment Variables

Key environment variables can be configured in `env-example` or `.env`:

- `COMMONCRAWL_VERSION` - Common Crawl version (e.g., `CC-MAIN-2024-30`)
- `CLUSTER_IDX_FILENAME` - Path to cluster index file (required for Docker/K8s)
- `RABBITMQ_CONNECTION_STRING` - RabbitMQ connection
- `MINIO_ENDPOINT` - MinIO endpoint
- `BATCHER_BATCH_SIZE` - Batch size for processing
- `BATCHER_METRICS_PORT` - Batcher Prometheus port (9000)
- `WORKER_METRICS_PORT` - Worker Prometheus port (9001)

**Cluster Index File Configuration:**
- **Local**: Use command-line parameter or `--cluster-idx-filename` flag (explicit path)
- **Docker/K8s**: Set `CLUSTER_IDX_FILENAME` in env file (explicit path required)

See [README.md](../README.md) in the parent directory for detailed usage.

