# Setup Guide

Complete setup instructions for the Common Crawl Pipeline Python implementation.

## Prerequisites

- **Python 3.11+**
- **[uv](https://github.com/astral-sh/uv)** - Fast Python package installer
- **Docker & Docker Compose** - For RabbitMQ and Prometheus
- **Make** - For running convenience commands

### Installing Prerequisites

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Verify installations
uv --version
docker --version
docker compose version
make --version
```

## Installation Methods

### Method 1: Quick Setup (Recommended)

This sets up everything in one command:

```bash
cd python
make setup
```

This will:
1. Create a Python 3.11 virtual environment
2. Install all dependencies (production + dev tools)
3. Start Docker services (RabbitMQ + Prometheus)
4. Install pre-commit hooks

### Method 2: Step-by-Step Setup

If you prefer manual control:

```bash
cd python

# 1. Install dependencies
make install-dev

# 2. Start Docker services
make docker-up

# 3. Install pre-commit hooks (optional but recommended)
make pre-commit-install
```

### Method 3: Production-Only Setup

For production deployments without dev tools:

```bash
cd python
make install
make docker-up
```

## Download Common Crawl Data

Before running the pipeline, download the cluster index file:

```bash
# From the project root
cd /path/to/basic-common-crawl-pipeline
wget https://data.commoncrawl.org/cc-index/collections/CC-MAIN-2024-30/indexes/cluster.idx
```

## Environment Configuration

### Create .env file

The application works with defaults, but you can customize settings:

```bash
cp .env.example .env
```

Edit `.env` to customize:

## Running the Pipeline

### Start the Batcher

The batcher reads the cluster.idx file and publishes URL batches to RabbitMQ:

```bash
cd python
make run-batcher CLUSTER_FILE=../cluster.idx
```

### Start Worker(s)

Workers consume batches and process URLs. You can run multiple workers in parallel:

```bash
# Terminal 2
make run-worker

# Terminal 3 (optional - additional worker)
make run-worker
```

## Verifying the Setup

### Check Docker Services

```bash
cd python
make docker-status
```

Expected output:
```
NAME                      IMAGE                      STATUS    PORTS
commoncrawl-rabbitmq      rabbitmq:3.12-management   Up        5672->5672, 15672->15672
commoncrawl-prometheus    prom/prometheus:latest     Up        9090->9090
```

### Access Service UIs

1. **RabbitMQ Management UI**: http://localhost:15672
   - Username: `guest`
   - Password: `guest`
   - Check the "Queues" tab to see messages

2. **Prometheus**: http://localhost:9090
   - Query: `batcher_batches` to see published batches
   - Query: `worker_batches` to see consumed batches

3. **Batcher Metrics**: http://localhost:9000/metrics

4. **Worker Metrics**: http://localhost:9001/metrics

## Troubleshooting

### Port Already in Use

If you get port conflicts:

```bash
# Check what's using the ports
lsof -i :5672  # RabbitMQ AMQP
lsof -i :9090  # Prometheus
lsof -i :15672 # RabbitMQ Management
lsof -i :9000  # Batcher metrics
lsof -i :9001  # Worker metrics

# Kill the process or change ports in docker-compose.yml
```

### Docker Services Won't Start

```bash
# View logs
make docker-logs

# Restart services
make docker-down
make docker-up

# If issues persist, remove volumes and restart
docker compose down -v
make docker-up
```

### RabbitMQ Connection Errors

Ensure RabbitMQ is running and accessible:

```bash
# Check service status
make docker-status

# Check RabbitMQ logs
docker logs commoncrawl-rabbitmq

# Verify connection string
echo $RABBITMQ_CONNECTION_STRING
```

### Virtual Environment Issues

If you have Python version conflicts:

```bash
# Remove existing venv
rm -rf .venv

# Recreate with specific Python version
uv venv --python 3.11 --seed

# Reinstall dependencies
make install-dev
```

### Pre-commit Hook Failures

If pre-commit hooks fail:

```bash
# Fix formatting automatically
make format

# Check what's wrong
make lint
make type-check

# Skip hooks temporarily (not recommended)
git commit --no-verify
```

### Import Errors

If you get `ModuleNotFoundError`:

```bash
# Ensure you're in the virtual environment
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows

# Reinstall in editable mode
uv pip install -e ".[dev]"
```

## Uninstalling / Cleanup

### Remove Docker Containers and Volumes

```bash
cd python
make docker-down

# Remove volumes (deletes all data)
docker compose down -v
```

### Remove Virtual Environment

```bash
cd python
rm -rf .venv
```

### Clean Python Artifacts

```bash
cd python
make clean
```

This removes:
- `__pycache__` directories
- `.pyc` files
- `.pytest_cache`
- `.mypy_cache`
- `.ruff_cache`
- `*.egg-info`

## Next Steps

Once setup is complete:

1. Read [Development Guide](development.md) for workflows and best practices
2. Read [Architecture Documentation](architecture.md) to understand the system
3. Start modifying the code and add your features!

## Common Setup Issues

### Issue: `uv` command not found

**Solution**: Add uv to your PATH:
```bash
export PATH="$HOME/.cargo/bin:$PATH"
# Add to ~/.bashrc or ~/.zshrc for persistence
```

### Issue: Docker daemon not running

**Solution**: Start Docker Desktop or the Docker daemon:
```bash
# Linux
sudo systemctl start docker

# macOS (if using Docker Desktop)
open /Applications/Docker.app
```

### Issue: Permission denied for Docker

**Solution**: Add your user to the docker group:
```bash
sudo usermod -aG docker $USER
# Log out and log back in
```

### Issue: Make command not found

**Solution**: Install make:
```bash
# Ubuntu/Debian
sudo apt-get install build-essential

# macOS
xcode-select --install

# Or use Homebrew
brew install make
```
