.PHONY: help install install-dev setup test lint format type-check clean run-batcher run-worker docker-up docker-down docker-logs docker-status pre-commit-install pre-commit-run

# Default target - show help
help:
	@echo "Common Crawl Pipeline - Available Make Targets"
	@echo "================================================"
	@echo ""
	@echo "Setup Commands:"
	@echo "  make install          - Install production dependencies with uv"
	@echo "  make install-dev      - Install all dependencies including dev tools"
	@echo "  make setup            - Full project setup (install-dev + docker-up + pre-commit)"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint             - Run ruff linter (check only)"
	@echo "  make format           - Auto-format code with ruff"
	@echo "  make type-check       - Run mypy type checking"
	@echo "  make test             - Run pytest tests"
	@echo "  make pre-commit-install - Install pre-commit hooks"
	@echo "  make pre-commit-run   - Run pre-commit on all files"
	@echo ""
	@echo "Run Pipeline:"
	@echo "  make run-batcher CLUSTER_FILE=<path> - Run batcher with cluster file"
	@echo "  make run-worker       - Run worker process"
	@echo ""
	@echo "Docker Services:"
	@echo "  make docker-up        - Start RabbitMQ and Prometheus containers"
	@echo "  make docker-down      - Stop and remove containers"
	@echo "  make docker-logs      - View docker compose logs"
	@echo "  make docker-status    - Show status of docker services"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean            - Remove Python cache files and artifacts"
	@echo ""

# Install production dependencies only
install:
	@echo "Creating virtual environment with uv..."
	uv venv --python 3.11 --seed
	@echo "Installing production dependencies with uv..."
	uv pip install -e .

# Install all dependencies including dev tools
install-dev:
	@echo "Creating virtual environment with uv..."
	uv venv --python 3.11 --seed
	@echo "Installing all dependencies (production + dev) with uv..."
	uv pip install -e ".[dev]"

# Full project setup
setup: install-dev docker-up pre-commit-install
	@echo ""
	@echo "✅ Setup complete!"
	@echo ""
	@echo "Services running:"
	@echo "  - RabbitMQ Management UI: http://localhost:15672 (guest/guest)"
	@echo "  - Prometheus: http://localhost:9090"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Download cluster.idx if not already present:"
	@echo "     wget https://data.commoncrawl.org/cc-index/collections/CC-MAIN-2024-30/indexes/cluster.idx -P .."
	@echo "  2. Run batcher: make run-batcher CLUSTER_FILE=../cluster.idx"
	@echo "  3. Run worker: make run-worker"
	@echo ""

# Code quality - linting (check only)
lint:
	@echo "Running ruff linter..."
	uv run ruff check .

# Code quality - auto-format
format:
	@echo "Formatting code with ruff..."
	uv run ruff check --fix .
	uv run ruff format .

# Type checking with mypy
type-check:
	@echo "Running mypy type checker..."
	uv run mypy src/

# Run tests
test:
	@echo "Running pytest tests..."
	uv run pytest -v

# Install pre-commit hooks
pre-commit-install:
	@echo "Installing pre-commit hooks..."
	uv run pre-commit install

# Run pre-commit on all files
pre-commit-run:
	@echo "Running pre-commit on all files..."
	uv run pre-commit run --all-files

# Run batcher (requires CLUSTER_FILE parameter)
run-batcher:
	@if [ -z "$(CLUSTER_FILE)" ]; then \
		echo "❌ Error: CLUSTER_FILE not specified"; \
		echo "Usage: make run-batcher CLUSTER_FILE=../cluster.idx"; \
		exit 1; \
	fi
	@echo "Starting batcher with cluster file: $(CLUSTER_FILE)"
	uv run python -m commoncrawl_pipeline.batcher --cluster-idx-filename $(CLUSTER_FILE)

# Run worker
run-worker:
	@echo "Starting worker..."
	uv run python -m commoncrawl_pipeline.worker

# Docker compose - start services
docker-up:
	@echo "Starting Docker services (RabbitMQ + Prometheus)..."
	docker compose up -d
	@echo ""
	@echo "✅ Services started!"
	@echo "  - RabbitMQ Management UI: http://localhost:15672 (guest/guest)"
	@echo "  - RabbitMQ AMQP: localhost:5672"
	@echo "  - Prometheus: http://localhost:9090"
	@echo ""

# Docker compose - stop services
docker-down:
	@echo "Stopping Docker services..."
	docker compose down

# View docker compose logs
docker-logs:
	docker compose logs -f

# Show docker service status
docker-status:
	docker compose ps

# Clean up Python cache and artifacts
clean:
	@echo "Cleaning up cache files and artifacts..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type f -name "*.coverage" -delete 2>/dev/null || true
	@echo "✅ Cleanup complete!"
