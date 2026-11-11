# Enterprise AI Analytics Platform for Financial Services

[![CI](https://github.com/mrsimiloluwa/test/actions/workflows/ci.yml/badge.svg)](https://github.com/mrsimiloluwa/test/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v0.json)](https://github.com/astral-sh/ruff)

An enterprise-grade, modular financial analytics and AI platform demonstrating production-level engineering across **Analytics Engineering**, **Data Engineering**, **AI Engineering**, **Data Product Engineering**, and **DevOps / CI/CD**.

---

## 1. Product Vision

In financial institutions, business users, finance operations (FinOps), and relationship managers frequently need answers to critical business questions:
- **Customer Profitability**: Net interest margins, direct operating costs, and risk-adjusted return on capital (RAROC).
- **Transaction Fees & Revenue**: Interchange fee variances, wire/ACH processing margins, and fee waiver leakage.
- **Contractual Pricing & Compliance**: Realized transaction fee rates vs. agreed tiered pricing schedules.
- **Operational Performance**: SLA compliance, transaction failure rates, and dispute turnaround times.

This platform bridges **deterministic analytics engineering** (dbt Core + dimensional star schemas in PostgreSQL/DuckDB) with **controlled AI reasoning** (LangGraph multi-agent workflows, AST SQL parsing with SQLGlot, and Model Context Protocol).

> [!IMPORTANT]
> All financial data is synthetic or publicly available. Confidential employer, client, or live banking data is never used.

---

## 2. High-Level Architecture

```
                          ┌────────────────────────────────────────────────────────┐
                          │                   Presentation Layer                   │
                          │   Streamlit / React (Executive & FinOps Dashboards)    │
                          └──────────────────────┬─────────────────────────────────┘
                                                 │ HTTPS / SSE / JSON
                          ┌──────────────────────▼─────────────────────────────────┐
                          │             Data Product API Layer (FastAPI)           │
                          │   - REST Endpoints (/metrics, /query, /lineage)        │
                          │   - Model Context Protocol (MCP) Server                │
                          └──────────────────────┬─────────────────────────────────┘
                                                 │
                          ┌──────────────────────▼─────────────────────────────────┐
                          │               AI Engineering (LangGraph)               │
                          │   - Governed Text-to-SQL Node                          │
                          │   - AST Safety Validator (sqlglot: SELECT only)        │
                          │   - Financial Policy RAG & Metric Synthesizer          │
                          └──────────────────────┬─────────────────────────────────┘
                                                 │ Governed Queries
                 ┌───────────────────────────────┴───────────────────────────────┐
                 │                                                               │
┌────────────────▼────────────────┐                             ┌────────────────▼────────────────┐
│      Metadata & Governance      │                             │         Warehouse Layer         │
│  - dbt Artifacts (Manifests)    │◄────── Metadata Sync ───────┤ PostgreSQL (Dev) / Snowflake    │
│  - Data Lineage & Glossaries    │                             │  - staging, intermediate, marts │
└─────────────────────────────────┘                             └────────────────▲────────────────┘
                                                                                 │
                                                                ┌────────────────┴────────────────┐
                                                                │  Orchestration & Transformation │
                                                                │   - Apache Airflow (ELT DAGs)   │
                                                                │   - dbt Core (Dimensional models)│
                                                                └─────────────────────────────────┘
```

---

## 3. Approved Technology Stack

| Domain | Technology | Purpose |
| :--- | :--- | :--- |
| **Language & Environment** | Python 3.12 + `uv` | High-speed dependency management and virtual environments. |
| **Development Database** | PostgreSQL 16 (Docker) | Primary relational and dimensional data warehouse for development. |
| **Analytical Testing** | DuckDB | In-memory embedded analytical queries and fast local CI tests. |
| **Analytics Engineering** | dbt Core (`dbt-postgres`) | Dimensional Kimball star schemas, tests, and metric definitions. |
| **Data Orchestration** | Apache Airflow (LocalExecutor) | Automated daily ingestion, dbt build, reconciliation, and sample export. |
| **Backend & APIs** | FastAPI + Pydantic v2 | High-throughput, typed REST APIs and MCP server endpoints. |
| **AI Orchestration** | LangGraph + SQLGlot | Controlled agentic state graph with AST SQL safety guardrails. |
| **Data Product UI** | Streamlit | Executive financial dashboards and interactive conversational assistant. |
| **Code Quality & CI/CD** | Ruff + pytest + GitHub Actions | Automated linting, formatting checks, and deterministic unit testing. |

---

## 4. Local Development Setup

### Prerequisites
- macOS (Apple Silicon compatible, optimized for 16GB RAM) or Linux
- Python 3.12
- Docker Desktop
- [uv](https://docs.astral.sh/uv/) (Python package manager)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/mrsimiloluwa/test.git
   cd test
   ```

2. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```

3. **Install dependencies and create virtual environment:**
   ```bash
   uv sync --all-groups
   ```

---

## 5. Starting PostgreSQL with Docker Compose

A lightweight PostgreSQL 16 container with persistent storage and resource caps (512MB RAM max) is configured:

```bash
# Start PostgreSQL in background
docker compose up -d

# Verify container health
docker compose ps

# View database logs
docker compose logs -f postgres

# Stop PostgreSQL
docker compose down
```

---

## 6. Apache Airflow Pipeline Orchestration (Phase 3)

The platform includes an automated Apache Airflow 2.10.3 stack configured with `LocalExecutor` and strict database isolation:

```bash
# 1. Initialize Airflow metadata database and create default admin
docker compose up airflow-init

# 2. Start Airflow Webserver and Scheduler
docker compose up -d airflow-webserver airflow-scheduler

# 3. Access Airflow Web UI
# URL: http://127.0.0.1:8080 (User: admin / Password: admin)

# 4. Trigger the daily DEV financial analytics pipeline
docker compose exec airflow-webserver airflow dags trigger financial_analytics_dev_pipeline

# 5. Trigger the isolated automated test pipeline
docker compose exec airflow-webserver airflow dags trigger financial_analytics_test_pipeline
```

---

## 7. Running Code Quality & Automated Tests

All tests and linters run deterministically through `uv`:

```bash
# Run Ruff linting
uv run ruff check .

# Check code formatting
uv run ruff format --check .

# Auto-fix formatting issues
uv run ruff format .

# Run pytest unit and analytical tests
uv run pytest
```

---

## 8. Governed Metadata Catalog & Lineage (Phase 4)

The platform includes an automated metadata extraction, data lineage, and semantic catalog layer:
- **Immutable Snapshot Publishing**: dbt compilation artifacts (`manifest.json`, `catalog.json`, `run_results.json`) are version-snapshotted to `artifacts/dbt/<target>/<run_id>/` and atomically promoted to `latest/`.
- **Governed Semantic Catalog**: Parsed into PostgreSQL `metadata` schema (`metadata.artifact_runs`, `metadata.model_catalog`, `metadata.column_catalog`, `metadata.source_catalog`, `metadata.metric_catalog`, `metadata.lineage_edges`).
- **12 Governed Financial Metrics**: Validated formulas, grains, and currency rules stored in `packages/data_platform/src/data_platform/metadata/financial_metrics.yaml`.
- **Queryable Allowlist**: Restricts AI models and ad-hoc SQL generation exclusively to the 9 governed dimensional marts. Non-queryable staging and raw tables raise immediate `PermissionError`.
- **CLI Commands**:
  ```bash
  # Publish artifacts and persist metadata catalog
  PYTHONPATH="packages/data_platform/src:packages/shared/src" .venv/bin/python -m data_platform.metadata.cli publish-and-load

  # Inspect governed catalog models and metrics
  PYTHONPATH="packages/data_platform/src:packages/shared/src" .venv/bin/python -m data_platform.metadata.cli inspect

  # Generate AI QueryContext JSON (enforces governed queryable boundary)
  PYTHONPATH="packages/data_platform/src:packages/shared/src" .venv/bin/python -m data_platform.metadata.cli ai-context --model fct_transactions
  ```

---

## 9. Governed AI Financial Analytics & Applications (Phase 5)

Phase 5 introduces a stateful **LangGraph** multi-agent question-answering workflow, **SQLGlot AST security validation**, least-privilege database role isolation, and a **Streamlit** executive chat dashboard:

- **LangGraph Directed State Machine**: 8 specialized nodes with dynamic fast-paths that bypass execution on out-of-scope inquiries or security validation failures.
- **SQL Security Perimeter**: Read-only single-statement SELECT validation, analytical mart allowlisting, RESTRICTED column stripping, and LIMIT 1000 clamping.
- **Database Sandbox**: Physical queries execute under `analytics_reader` with 5000ms statement timeout.
- **Evaluation Suite**: 32 curated benchmark cases with 100.0% accuracy and 100.0% prompt injection defense.

```bash
# 1. Start the FastAPI analytics backend
uv run uvicorn ai_services.api.app:app --host 0.0.0.0 --port 8000

# 2. Launch the Streamlit executive analytics dashboard
uv run streamlit run packages/data_apps/src/data_apps/app.py --server.port 8501

# 3. Run the AI unit, integration, and security evaluation tests
uv run pytest tests/unit/test_ai_*.py tests/integration/test_ai_*.py -v
```

---

## 10. Application Engineering & Productisation (Phase 6)

Phase 6 unifies the data platform, dimensional marts, and LangGraph AI services into a production-grade REST API and executive dashboard:

- **FastAPI Backend (`ai_services.api`)**:
  - `GET /health` & `GET /api/v1/analytics/health`: Live database latency measurement and component statuses.
  - `GET /api/v1/analytics/overview`: High-level executive KPIs dynamically aggregated from warehouse marts (e.g. €408,602.64 net recognized revenue, 5.28% exception rate).
  - `GET /api/v1/analytics/trends`: Monthly revenue, assessed fees, and cash collection timeseries.
  - `GET /api/v1/analytics/customers`: Customer revenue leaderboard filterable by segment (`INSTITUTIONAL`, `COMMERCIAL_SME`, `CORPORATE`).
  - `GET /api/v1/analytics/arrears`: Itemized billing arrears registry with native and EUR balances.
  - `POST /api/v1/analytics/ask`: Natural-language question answering backed by governed SQL.
  - `X-Request-ID` and `X-Process-Time` tracing headers for observability.
- **Streamlit Executive Dashboard (`data_apps`)**:
  - **5 Functional Workspaces**: Executive Overview, Customer Rankings, Billing Arrears, AI Financial Copilot, and Governed Metric Catalog.
  - **Dynamic Environment Toggle**: Switch seamlessly between `DEV` (Showcase: 50 clients, 5k txns) and `TEST` (Isolation: 10 clients, 200 txns).
  - **Governed Accounting Bridge**: Visualizes $\text{Gross Assessed} - \text{Waivers} - \text{Arrears} - \text{Pass-Through} = \text{Net Recognized Revenue}$.
  - **Exportable Data**: 1-click CSV download for trends, rankings, and arrears tables.
- **Docker Compose Multi-Container Stack**:
  - Full application stack configured in `docker-compose.yml` (`postgres`, `airflow-webserver`, `airflow-scheduler`, `api`, `dashboard`).

```bash
# 1. Start application stack in Docker Compose
docker compose up -d postgres api dashboard

# 2. Or run services locally with uv
# FastAPI Backend (Port 8000)
uv run uvicorn ai_services.api.app:app --host 127.0.0.1 --port 8000

# Streamlit Executive Dashboard (Port 8501)
uv run streamlit run packages/data_apps/src/data_apps/app.py --server.port 8501

# 3. Interactive Documentation:
# API Swagger Docs: http://localhost:8000/docs
# Streamlit Dashboard: http://localhost:8501
```

---

## 11. Production Readiness, Security & Portfolio Walkthrough (Phase 7)

Phase 7 hardens the platform into a production-grade, secure, and reproducible public portfolio deployment:

- **Live LLM Integration & Financial Integrity**:
  - `OpenAICompatibleProvider` with configurable endpoint (`LLM_BASE_URL`), bearer authentication, and automated fallback to deterministic mock provider for zero-cost offline development.
  - Runtime secret masking ensures API keys never leak into logs, traces, or HTTP responses.
  - Enforces exact accounting bridge synthesis: reversals are explicitly itemized even when zero (`€0.00`).
- **Application Security & Hardening**:
  - **Authentication**: `verify_api_key` dependency supporting both `X-API-Key` and `Authorization: Bearer <key>`, with automatic exemption for public health/docs.
  - **Sliding-Window Rate Limiting**: In-memory rate limiter (default: 120 req/min) returning RFC-compliant `429 Too Many Requests` with `Retry-After`.
  - **Secure HTTP Headers**: Injected across all responses (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security`).
  - **SQL Defense Boundary**: AST-level SQLGlot validation, least-privilege `analytics_reader` PostgreSQL role, 5000ms statement timeouts, and 1,000-row clamping.
- **Observability & Telemetry**:
  - In-memory `TelemetryStats` tracking total requests, active requests, error rates, p50/p95 latency, and endpoint metrics via `GET /telemetry`.
  - Concurrency verified with 20 parallel requests executing in <150ms p95 latency.
- **Enterprise CI/CD Automation**:
  - Complete 4-job GitHub Actions workflow (`.github/workflows/ci.yml`) covering Ruff lint/format, MkDocs strict validation, PostgreSQL 16 containerized dbt build and pytest suite, and multi-stage Docker image builds.
- **Portfolio & Reviewer Documentation**:
  - [Recruiter & Reviewer Walkthrough](docs/portfolio/walkthrough.md): Comprehensive guide with architecture diagrams, financial equations, sample prompts, and engineering trade-offs.
  - [Production Deployment Runbook](docs/runbooks/deployment.md): Step-by-step production setup for Docker Compose, Streamlit Community Cloud, Render, and Railway with disaster recovery procedures.

```bash
# 1. Run all tests including performance benchmarks and security tests
PYTHONPATH="packages/shared/src:packages/data_platform/src:packages/ai_services/src:packages/data_apps/src" .venv/bin/pytest tests/ -v

# 2. Inspect API telemetry
curl -s http://127.0.0.1:8000/telemetry | jq .

# 3. Build the full MkDocs documentation site
.venv/bin/mkdocs build --strict
```

---

## 12. Public Deployment & Portfolio Launch (Phase 8)

Phase 8 elevates the platform into a decoupled, public, recruiter-accessible demonstration:

- **Decoupled Client-Server Communication**:
  - The Streamlit executive dashboard supports seamless REST API integration via `API_BASE_URL` and `API_KEY`.
  - When configured, the UI calls remote FastAPI endpoints over HTTPS with `X-API-Key` headers, falling back cleanly to direct in-process Python services in monolithic environments.
- **Safe Demonstration Mode & Transparency**:
  - Transparent sidebar indicator displays whether the platform is running in `🧪 Demo Mode: Deterministic Mock Provider` or `🟢 Live LLM`.
  - In demo mode, inquiries execute real SQL queries against the DEV PostgreSQL warehouse and return verified financial explanations without incurring API token costs or hallucinating numbers.
  - Every AI response card includes an **Engine** badge alongside metric, model, latency, and row count attributes.
- **Cloud Hosting Evaluation Matrix**:
  - **Streamlit Community Cloud + Neon PostgreSQL ($0 / month)**: 100% free serverless architecture with 0.5GB persistent storage on Neon with SSL.
  - **Railway.app Multi-Container (~$5 / month)**: Deploys the multi-container stack (`postgres`, `api`, `dashboard`) with persistent volumes and automatic HTTPS (`*.up.railway.app`).
  - **Single-Node VPS (€3.79 / month on Hetzner CAX11 / $5 AWS Lightsail)**: Complete institutional deployment running Airflow, Postgres, API, and Dashboard behind Caddy with Let's Encrypt SSL.
- **Portfolio & Verification Runbooks**:
  - [Recruiter & Reviewer Walkthrough](docs/portfolio/walkthrough.md): Comprehensive guide with architecture diagrams, domain concepts, sample prompts, and engineering trade-offs.
  - [Production Deployment Runbook](docs/runbooks/deployment.md): Step-by-step production setup across cloud providers with disaster recovery procedures.
  - [Phase 8 Milestone Documentation](docs/phases/phase-8-deployment.md): Detailed audit and public launch records.

```bash
# 1. Run complete public user journey verification
python3 -c "
import httpx
print('Health:', httpx.get('http://127.0.0.1:8000/health').json()['status'])
print('Overview Net Revenue: €{:,.2f}'.format(httpx.get('http://127.0.0.1:8000/api/v1/analytics/overview?environment=dev').json()['net_recognized_revenue_eur']))
print('Dashboard Health:', httpx.get('http://127.0.0.1:8501/_stcore/health').text)
"
```

---

## 13. Repository Structure

```
.
├── .github/
│   └── workflows/ci.yml       # GitHub Actions CI workflow
├── airflow/                   # Apache Airflow orchestration
│   ├── dags/                  # Governed financial DAG definitions
│   ├── logs/                  # Task instance logs
│   └── plugins/               # Airflow plugins
├── docker/
│   ├── airflow/               # Custom Airflow Dockerfile & requirements
│   └── docker-compose.yml     # Lightweight Postgres service definition
├── docs/                      # Architecture Decision Records (ADRs) and runbooks
├── packages/
│   ├── shared/                # Centralized configuration, logging & DB helpers
│   ├── data_platform/         # Data ingestion pipelines & dbt project
│   ├── ai_services/           # LangGraph workflows, SQL AST guardrails & MCP
│   └── data_apps/             # Streamlit financial dashboard
├── sample_data/               # Publicly inspectable CSV extracts
├── tests/
│   ├── airflow/               # DAG structure and DagBag tests
│   ├── unit/                  # Fast deterministic unit tests (DuckDB, Config)
│   └── integration/           # Database and API integration tests
├── .env.example               # Environment variable specification
├── .gitignore                 # Excludes secrets, caches, and local DBs
├── .pre-commit-config.yaml    # Pre-commit quality hooks
├── AGENTS.md                  # Permanent agent engineering rules and constraints
├── docker-compose.yml         # Root Docker Compose runner
├── pyproject.toml             # Project manifest & tool configurations
└── README.md                  # This file
```

---

## 14. Development Principles

This repository strictly enforces the principles defined in [AGENTS.md](file:///Users/soremekuns/test/AGENTS.md):
1. **Separation of Concerns**: Business logic is decoupled from infrastructure, presentation, and external LLM providers.
2. **Deterministic Financial Precision**: Authoritative financial calculations must never use IEEE-754 floating point arithmetic. Always use `DECIMAL(18, 4)` / `NUMERIC`.
3. **Defense in Depth**: LLM text-to-SQL output is untrusted and treated as a security boundary. Queries must be validated by AST parsers and executed by read-only roles with explicit limits and timeouts.
4. **16GB RAM Efficiency**: Services are profile-driven and lightweight. Heavy daemons and local 70B models are avoided in favor of clean cloud APIs and serverless alternatives.
