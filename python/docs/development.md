# Development Guide

Complete guide for developing and contributing to the Common Crawl Pipeline.

## Table of Contents

1. [Development Setup](#development-setup)
2. [Code Quality Tools](#code-quality-tools)
3. [Development Workflows](#development-workflows)
4. [Testing](#testing)
5. [Make Commands Reference](#make-commands-reference)
6. [Project Configuration](#project-configuration)
7. [Best Practices](#best-practices)

---

## Development Setup

### Initial Setup

```bash
cd python

# Full development setup
make setup
```

This installs:
- All production dependencies (trafilatura, pika, requests, etc.)
- Development tools (pytest, ruff, mypy, pre-commit)
- Pre-commit hooks
- Starts Docker services

### Manual Setup

If you prefer step-by-step:

```bash
# 1. Create virtual environment and install dependencies
make install-dev

# 2. Start Docker services
make docker-up

# 3. Install pre-commit hooks
make pre-commit-install
```

---

## Code Quality Tools

### Overview

| Tool | Purpose | Speed |
|------|---------|-------|
| **uv** | Package management | 10-100x faster than pip |
| **ruff** | Linting + Formatting | 10-100x faster than black/flake8 |
| **mypy** | Type checking | Industry standard |
| **pytest** | Testing framework | Fast and flexible |
| **pre-commit** | Git hooks | Automatic quality checks |

### Ruff (Linter + Formatter)

**Check code quality**:
```bash
make lint
```

**Auto-fix issues**:
```bash
make format
```

**What it checks**:
- Code style (PEP 8)
- Import sorting
- Common bugs (unused variables, etc.)
- Code simplification opportunities
- Best practices

**Configuration**: `pyproject.toml` → `[tool.ruff]`

### Mypy (Type Checker)

**Run type checking**:
```bash
make type-check
```

**What it checks**:
- Type hints consistency
- Function return types
- Variable types
- Third-party library stubs

**Configuration**: `pyproject.toml` → `[tool.mypy]`

**Current status**: Type checking is lenient (`disallow_untyped_defs = false`). Set to `true` to enforce strict typing.

### Pytest (Testing)

**Run all tests**:
```bash
make test
```

**Run specific test**:
```bash
uv run pytest tests/test_batcher.py::test_filter_non_english_documents
```

**Run with coverage**:
```bash
uv run pytest --cov=src --cov-report=html
open htmlcov/index.html
```

**Configuration**: `pyproject.toml` → `[tool.pytest.ini_options]`

### Pre-commit Hooks

**What runs automatically** on `git commit`:
1. Ruff formatting
2. Ruff linting
3. Mypy type checking
4. Trailing whitespace removal
5. End-of-file fixer
6. YAML/JSON/TOML validation
7. Secret detection
8. Large file prevention

**Run manually**:
```bash
# Run on all files
make pre-commit-run

# Run on staged files only
pre-commit run
```

**Skip hooks** (not recommended):
```bash
git commit --no-verify
```

**Configuration**: `.pre-commit-config.yaml`

---

## Development Workflows

### Starting Fresh

Clean slate for development:

```bash
make clean          # Remove Python cache files
make docker-down    # Stop services
rm -rf .venv        # Remove virtual environment
make setup          # Full setup from scratch
```

### Before Committing Code

**Recommended workflow**:

```bash
# 1. Format code
make format

# 2. Check for issues
make lint

# 3. Verify types
make type-check

# 4. Run tests
make test

# 5. Commit (pre-commit hooks will run automatically)
git add .
git commit -m "Your message"
```

**Quick check**:
```bash
make format && make lint && make type-check && make test
```

### Adding New Dependencies

#### Production Dependency

```bash
# 1. Add to pyproject.toml
vim pyproject.toml
# Add: "new-package>=1.0.0" to dependencies array

# 2. Install
uv pip install -e .
```

#### Development Dependency

```bash
# 1. Add to pyproject.toml
vim pyproject.toml
# Add: "new-dev-package>=1.0.0" to [project.optional-dependencies.dev]

# 2. Install
uv pip install -e ".[dev]"
```

#### Direct Installation

```bash
# Install and add to pyproject.toml manually
uv pip install package-name
```

### Working with Docker Services

**Start services**:
```bash
make docker-up
```

**Check status**:
```bash
make docker-status
```

**View logs**:
```bash
make docker-logs

# Follow logs (real-time)
make docker-logs

# Specific service
docker logs commoncrawl-rabbitmq -f
docker logs commoncrawl-prometheus -f
```

**Stop services**:
```bash
make docker-down
```

**Reset services** (remove volumes):
```bash
docker compose down -v
make docker-up
```

### Running the Pipeline Locally

**Terminal 1 - Batcher**:
```bash
cd python
make run-batcher CLUSTER_FILE=../cluster.idx
```

**Terminal 2 - Worker**:
```bash
cd python
make run-worker
```

**Terminal 3 - Additional Workers** (optional):
```bash
cd python
# Note: Will use port 9002 for metrics
uv run python -m commoncrawl_pipeline.worker
```

### Debugging

**Enable verbose logging** (add to code):
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Check RabbitMQ queue**:
- Open http://localhost:15672
- Navigate to "Queues" tab
- Click "batches" queue
- See messages, consumers, rates

**Check Prometheus metrics**:
```bash
# Batcher metrics
curl http://localhost:9000/metrics

# Worker metrics
curl http://localhost:9001/metrics

# Query Prometheus
open http://localhost:9090
# Query: batcher_batches
# Query: worker_batches
```

**Python debugger**:
```python
# Add breakpoint
import pdb; pdb.set_trace()

# Or use built-in breakpoint (Python 3.7+)
breakpoint()
```

---

## Testing

### Test Structure

```
tests/
├── __init__.py
└── test_batcher.py      # Batcher unit tests
```

### Writing Tests

**Use fake implementations** instead of mocks:

```python
from commoncrawl_pipeline.batcher import process_index
from commoncrawl_pipeline.commoncrawl import Downloader, IndexReader
from commoncrawl_pipeline.rabbitmq import MessageQueueChannel

class FakeReader(IndexReader):
    def __init__(self, data):
        self.data = data

    def __iter__(self):
        return iter(self.data)

class FakeDownloader(Downloader):
    def __init__(self, response: str):
        self.response = response

    def download_and_unzip(self, url: str, start: int, length: int) -> bytes:
        return self.response.encode("utf-8")

def test_my_feature():
    reader = FakeReader([...])
    downloader = FakeDownloader("...")
    channel = ChannelSpy()

    process_index(reader, channel, downloader, batch_size=2)

    assert channel.num_called == expected_value
```

**Benefits**:
- No mocking libraries needed
- Tests are clear and readable
- Leverages ABC pattern

### Running Tests

```bash
# All tests
make test

# Specific test file
uv run pytest tests/test_batcher.py

# Specific test function
uv run pytest tests/test_batcher.py::test_filter_non_english_documents

# With verbose output
uv run pytest -v

# With coverage
uv run pytest --cov=src --cov-report=term-missing

# With debugging (drops into pdb on failure)
uv run pytest --pdb
```

### Adding New Tests

1. Create test file in `tests/` directory: `test_<module>.py`
2. Write test functions: `def test_<feature>():`
3. Use fakes for dependencies
4. Run tests: `make test`

---

## Make Commands Reference

### Setup Commands

```bash
make install        # Install production dependencies only
make install-dev    # Install all dependencies (prod + dev)
make setup          # Full setup (install-dev + docker-up + hooks)
make help           # Show all available commands
```

### Code Quality Commands

```bash
make lint           # Run ruff linter (check only)
make format         # Auto-format code with ruff
make type-check     # Run mypy type checker
make test           # Run pytest tests
```

### Pre-commit Commands

```bash
make pre-commit-install  # Install git hooks
make pre-commit-run      # Run hooks on all files
```

### Pipeline Commands

```bash
make run-batcher CLUSTER_FILE=<path>  # Start batcher
make run-worker                       # Start worker
```

### Docker Commands

```bash
make docker-up      # Start RabbitMQ + Prometheus
make docker-down    # Stop services
make docker-logs    # View logs
make docker-status  # Check service status
```

### Cleanup Commands

```bash
make clean          # Remove Python cache files
```

---

## Project Configuration

### pyproject.toml

Central configuration file for:
- Project metadata
- Dependencies
- CLI entry points
- Ruff settings
- Mypy settings
- Pytest settings
- Coverage settings

**Key sections**:

```toml
[project]
name = "commoncrawl-pipeline"
dependencies = [...]

[project.optional-dependencies]
dev = [...]  # Development dependencies

[project.scripts]
cc-batcher = "commoncrawl_pipeline.batcher:main"
cc-worker = "commoncrawl_pipeline.worker:main"

[tool.ruff]
line-length = 88
target-version = "py311"

[tool.mypy]
python_version = "3.11"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

### .pre-commit-config.yaml

Defines git hooks that run before commits:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks:
      - id: ruff
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    hooks:
      - id: mypy

  - repo: https://github.com/pre-commit/pre-commit-hooks
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      # ... more hooks
```

### docker-compose.yml

Defines services:

```yaml
services:
  rabbitmq:
    image: rabbitmq:3.12-management
    ports:
      - "5672:5672"
      - "15672:15672"

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
```

### .env

Environment variables for configuration:

```bash
RABBITMQ_CONNECTION_STRING=amqp://guest:guest@localhost:5672
BATCH_SIZE=50
BATCHER_METRICS_PORT=9000
WORKER_METRICS_PORT=9001
```

---

## Common Issues & Solutions

### Import Errors

**Problem**: `ModuleNotFoundError: No module named 'commoncrawl_pipeline'`

**Solution**:
```bash
# Ensure you're in venv
source .venv/bin/activate

# Reinstall in editable mode
uv pip install -e ".[dev]"
```

### Pre-commit Failures

**Problem**: Hooks fail on commit

**Solution**:
```bash
# Fix issues automatically
make format

# Check what's wrong
make lint
make type-check

# Update hooks to latest versions
pre-commit autoupdate
```

### Docker Port Conflicts

**Problem**: Ports already in use

**Solution**:
```bash
# Find what's using the port
lsof -i :5672

# Kill the process or change ports in docker-compose.yml
```

### Type Checking Errors

**Problem**: Mypy reports type errors

**Solution**:
```bash
# Add type hints to function
def my_function(param: str) -> int:
    return len(param)

# Ignore specific line (use sparingly)
result = some_function()  # type: ignore

# Ignore missing imports for third-party libs
# Already configured in pyproject.toml for trafilatura, warcio, pika
```

---

## Next Steps

- Read [Architecture Documentation](architecture.md) to understand the system design
- Read [Setup Guide](setup.md) for detailed installation instructions
- Check out the [main README](../README.md) for project overview

## Additional Resources

- **Python Style Guide**: [PEP 8](https://pep8.org/)
- **Type Hints**: [PEP 484](https://peps.python.org/pep-0484/)
- **uv Documentation**: https://github.com/astral-sh/uv
- **Ruff Documentation**: https://docs.astral.sh/ruff/
- **Pytest Documentation**: https://docs.pytest.org/
- **Pre-commit Documentation**: https://pre-commit.com/
