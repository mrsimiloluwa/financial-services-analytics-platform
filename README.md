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
| **Data Orchestration** | Apache Airflow *(Phase 3)* | Automated ingestion and transformation workflows. |
| **Backend & APIs** | FastAPI + Pydantic v2 | High-throughput, typed REST APIs and MCP server endpoints. |
| **AI Orchestration** | LangGraph + SQLGlot | Controlled agentic state graph with AST SQL safety guardrails. |
| **Data Product UI** | Streamlit *(Phase 6)* | Executive financial dashboards and interactive conversational assistant. |
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

## 6. Running Code Quality & Automated Tests

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

## 7. Repository Structure

```
.
├── .github/
│   └── workflows/ci.yml       # GitHub Actions CI workflow
├── docker/
│   └── docker-compose.yml     # Lightweight Postgres service definition
├── docs/                      # Architecture Decision Records (ADRs) and runbooks
├── packages/
│   ├── shared/                # Centralized configuration, logging & DB helpers
│   ├── data_platform/         # Data ingestion pipelines & dbt project
│   ├── ai_services/           # LangGraph workflows, SQL AST guardrails & MCP
│   └── data_apps/             # Streamlit financial dashboard
├── tests/
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

## 8. Development Principles

This repository strictly enforces the principles defined in [AGENTS.md](file:///Users/soremekuns/test/AGENTS.md):
1. **Separation of Concerns**: Business logic is decoupled from infrastructure, presentation, and external LLM providers.
2. **Deterministic Financial Precision**: Authoritative financial calculations must never use IEEE-754 floating point arithmetic. Always use `DECIMAL(18, 4)` / `NUMERIC`.
3. **Defense in Depth**: LLM text-to-SQL output is untrusted and treated as a security boundary. Queries must be validated by AST parsers and executed by read-only roles with explicit limits and timeouts.
4. **16GB RAM Efficiency**: Services are profile-driven and lightweight. Heavy daemons and local 70B models are avoided in favor of clean cloud APIs and serverless alternatives.
