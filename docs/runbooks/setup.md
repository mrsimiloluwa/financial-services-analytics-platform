# Local Setup & Operations Runbook

This guide covers local environment setup, starting infrastructure, running tests, and hosting technical documentation.

---

## 1. Prerequisites

- macOS (Apple Silicon compatible, optimized for 16GB RAM) or Linux
- Python 3.12
- Docker Desktop
- [uv](https://docs.astral.sh/uv/) (Astral Python package manager)

---

## 2. Environment Configuration

1. **Clone the repository:**
   ```bash
   git clone https://github.com/mrsimiloluwa/test.git
   cd test
   ```

2. **Copy the environment configuration template:**
   ```bash
   cp .env.example .env
   ```

3. **Install dependencies and create virtual environment:**
   ```bash
   uv sync --all-groups
   ```

---

## 3. Database Management

### Starting PostgreSQL
```bash
# Start PostgreSQL container in detached mode
docker compose up -d

# Verify container health
docker compose ps

# Inspect live logs
docker compose logs -f postgres
```

### Stopping PostgreSQL
```bash
docker compose down
```

---

## 4. Synthetic Data Generation & Ingestion

Run the ingestion CLI to generate synthetic banking datasets and stream them into PostgreSQL using staged bulk `COPY`:

```bash
# Ingest TEST profile (200 transactions, fast test verification)
PYTHONPATH=packages/shared/src:packages/data_platform/src uv run python -m data_platform.ingestion.run --profile TEST --reset

# Ingest DEV profile (5,000 transactions, ~50,000 records across 11 entities)
PYTHONPATH=packages/shared/src:packages/data_platform/src uv run python -m data_platform.ingestion.run --profile DEV --reset

# Inspect ingestion options
PYTHONPATH=packages/shared/src:packages/data_platform/src uv run python -m data_platform.ingestion.run --help
```

---

## 5. Code Quality & Test Suite

```bash
# Run Ruff linting
uv run ruff check .

# Run Ruff formatting check
uv run ruff format --check .

# Auto-format codebase
uv run ruff format .

# Execute full test suite (unit + PostgreSQL integration)
uv run pytest
```

---

## 5. Hosting Technical Documentation

The documentation is built with MkDocs and the Material theme.

### Local Live-Reload Server
Run the local documentation server to preview documentation with live-reload:
```bash
uv run mkdocs serve
```
Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

### Building Static Site
To compile the static documentation bundle:
```bash
uv run mkdocs build
```
The compiled HTML site is generated in the `site/` directory.
