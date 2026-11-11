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

### Development vs. Test Database Isolation

The platform enforces strict database separation between development/portfolio analytics and automated integration testing:

| Environment | Database Name | Configured Via | Purpose & Safety Controls |
| :--- | :--- | :--- | :--- |
| **Development / Portfolio** | `analytics_platform` | `POSTGRES_DB=analytics_platform` | Default target for `data_platform.ingestion.run`, `dbt build` (`--target dev`), and `export_samples`. Protected against accidental test truncation. |
| **Automated Integration Tests** | `analytics_platform_test` | `POSTGRES_TEST_DB=analytics_platform_test` | Dedicated database used exclusively by `tests/integration/`. Automatically provisioned by `ensure_test_database_exists()` without dropping existing databases. |

- **Integration Test Connection Routing:** All PostgreSQL integration tests in `tests/integration/` use `get_test_postgres_connection()`, which connects strictly to `analytics_platform_test` regardless of `POSTGRES_DB` in `.env`.
- **Destructive Operation Safety Guard:** `truncate_raw_tables()` in `packages/data_platform/src/data_platform/ingestion/ddl.py` executes `assert_is_test_database(conn)` (`SELECT current_database()`) and raises `PermissionError` if called against `analytics_platform` or any database other than `analytics_platform_test` (unless explicitly invoked via the CLI `--reset` flag).

---

## 4. Synthetic Data Generation & Ingestion

Run the ingestion CLI to generate synthetic banking datasets and stream them into the development database (`analytics_platform`) using staged bulk `COPY`:

```bash
# Verify which database is targeted before running a reset
uv run --env-file .env python -c "from shared.config import Settings; s = Settings(); print(f'Target DB: {s.postgres_host}:{s.postgres_port}/{s.postgres_db}')"

# Ingest TEST profile (10 customers, 200 transactions, seed=42)
PYTHONPATH=packages/shared/src:packages/data_platform/src .venv/bin/uv run --env-file .env python -m data_platform.ingestion.run --profile TEST --reset

# Ingest DEV showcase profile (50 customers, 5,000 transactions, seed=42)
PYTHONPATH=packages/shared/src:packages/data_platform/src .venv/bin/uv run --env-file .env python -m data_platform.ingestion.run --profile DEV --reset

# Inspect ingestion options
PYTHONPATH=packages/shared/src:packages/data_platform/src .venv/bin/uv run --env-file .env python -m data_platform.ingestion.run --help
```

> **Note on `--reset`:** Passing `--reset` truncates the 12 `raw.*` tables in the database specified by `POSTGRES_DB` (`analytics_platform`) before loading the newly generated batch. Always verify `POSTGRES_DB` before running with `--reset`, and run `dbt build` + `export_samples` afterward to synchronize the `analytics.*` marts and `sample_data/*.csv` exports.

---

## 5. Analytics Engineering (dbt Core)

The dbt Core project (`packages/data_platform/dbt_analytics/`) transforms the `raw` schema into dimensional marts in the `analytics` schema. Credentials are supplied exclusively through environment variables using a temporary profile outside the repository (`/tmp/dbt_profiles/profiles.yml`), which defines both `dev` (`analytics_platform`) and `test` (`analytics_platform_test`) targets.

```bash
# 1. Generate the environment-variable-driven /tmp/dbt_profiles/profiles.yml
PYTHONPATH=packages/shared/src:packages/data_platform/src .venv/bin/uv run python -m data_platform.dbt_setup

# 2. Verify PostgreSQL connection and dbt configuration (defaults to target: dev -> analytics_platform)
.venv/bin/uv run --env-file .env dbt debug \
  --project-dir packages/data_platform/dbt_analytics \
  --profiles-dir /tmp/dbt_profiles

# 3. Compile models and tests
.venv/bin/uv run --env-file .env dbt compile \
  --project-dir packages/data_platform/dbt_analytics \
  --profiles-dir /tmp/dbt_profiles

# 4. Build all staging views, intermediate views, Kimball marts, and run all 462 data tests on analytics_platform
.venv/bin/uv run --env-file .env dbt build \
  --project-dir packages/data_platform/dbt_analytics \
  --profiles-dir /tmp/dbt_profiles

# 5. (Optional) Build dbt models and tests in the isolated test database (analytics_platform_test)
.venv/bin/uv run --env-file .env dbt build \
  --project-dir packages/data_platform/dbt_analytics \
  --profiles-dir /tmp/dbt_profiles \
  --target test

# 6. Generate dbt catalog and lineage manifest
.venv/bin/uv run --env-file .env dbt docs generate \
  --project-dir packages/data_platform/dbt_analytics \
  --profiles-dir /tmp/dbt_profiles

# 7. Export representative raw and analytical CSV samples from analytics_platform to sample_data/
PYTHONPATH=packages/shared/src:packages/data_platform/src .venv/bin/uv run --env-file .env python -m data_platform.ingestion.export_samples
```

---

## 6. Code Quality & Test Suite

Because all PostgreSQL integration tests automatically route to `analytics_platform_test` and enforce `assert_is_test_database()`, running `pytest` is completely safe and never modifies or truncates `analytics_platform`:

```bash
# Run Ruff linting
.venv/bin/uv run ruff check .

# Run Ruff formatting check
.venv/bin/uv run ruff format --check .

# Execute full test suite (unit + isolated PostgreSQL integration tests on analytics_platform_test)
.venv/bin/uv run --env-file .env pytest -q
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
