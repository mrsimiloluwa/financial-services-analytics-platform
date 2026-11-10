# ADR 001: Monorepo Structure, uv Package Manager, and Baseline Infrastructure

- **Status**: Approved
- **Date**: 2026-11-10
- **Deciders**: Lead Architect, Lead Data Engineer, Lead AI Engineer

---

## Context

We are building an enterprise-grade Analytics and AI Platform for Financial Services. The development machine is a Mac with 16GB RAM. We need a modular, maintainable, and high-performance repository foundation that supports analytics engineering (dbt), data engineering (pipelines), AI engineering (LangGraph, SQLGlot), and presentation (FastAPI, Streamlit) without resource contention or tooling friction.

---

## Decision

1. **Modular Monorepo Structure**:
   Adopt a single monorepo with distinct packages (`packages/shared`, `packages/data_platform`, `packages/ai_services`, `packages/data_apps`). Business logic remains decoupled from presentation and infrastructure.
2. **Unified Package Management via `uv`**:
   Use Astral's `uv` for Python 3.12 environment management and dependency resolution. `uv` provides sub-second installs, deterministic lockfiles (`uv.lock`), and low memory usage.
3. **Primary Development Database**:
   PostgreSQL 16 running via Docker Compose, constrained to 512MB RAM and 1 CPU. DuckDB is adopted for zero-daemon in-memory analytical unit testing.
4. **Code Quality Baseline**:
   Use `ruff` for all Python linting and formatting. Use `pre-commit` hooks for secrets detection and file hygiene.
5. **Continuous Documentation & Hosting**:
   Use `mkdocs` with `mkdocs-material` for continuous documentation generation, local hosting (`uv run mkdocs serve`), and automated publishing via GitHub Actions to GitHub Pages.

---

## Consequences

- **Positive**:
  - Sub-second virtual environment synchronization.
  - Zero RAM bloat on macOS (Postgres uses ~60MB idle; no persistent heavy JVM or Kafka daemons).
  - Deterministic CI checks with sub-minute execution times.
  - Interactive, searchable technical documentation updated after every milestone.
- **Negative / Constraints**:
  - Developers must use `uv run <tool>` or activate `.venv`.
  - Docker Desktop must have memory allocation bounded to 6GB max.
