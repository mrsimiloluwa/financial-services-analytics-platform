# Enterprise AI Analytics Platform for Financial Services

Welcome to the technical documentation for the **Enterprise AI Analytics Platform for Financial Services**.

This platform is a modular, production-grade financial analytics and AI system designed to demonstrate enterprise-level engineering standards across:

- **Analytics Engineering**: Kimball dimensional modeling, dbt Core transformations, deterministic metric definitions, and semantic layer testing.
- **Data Engineering**: Multi-tier synthetic banking data generation, idempotent ingestion pipelines, and orchestrated workflows.
- **AI Engineering**: LangGraph multi-agent orchestration, AST SQL parsing via SQLGlot, policy RAG retrieval, and Model Context Protocol (MCP) tool exposure.
- **Data Product Engineering**: Typed FastAPI REST/SSE backends and interactive Streamlit executive interfaces.
- **Software Engineering & DevOps**: Strict linting/formatting via Ruff, reproducible virtual environments with `uv`, containerized local infrastructure, and automated GitHub Actions CI/CD.

---

## Business Domain & Problem Statement

Financial institutions (commercial banks, fintechs, and payment gateways) require precise, governed insights into customer economics without risking metric hallucination or security breaches:

1. **Customer & Account Profitability**: Tracking Net Interest Margin (NIM), direct operational servicing costs, and Risk-Adjusted Return on Capital (RAROC).
2. **Transaction Fees & Billing Leakage**: Identifying fee waiver exceptions, interchange fee variances, and wire/ACH margin capture.
3. **Contractual Pricing Compliance**: Auditing realized transaction fees against contracted pricing tiers and customer volume commitments.
4. **Operational Performance**: Tracking dispute resolution turnaround times, SLA compliance, and transaction failure rates.

---

## Architectural Principles

1. **Deterministic Analytics over LLM Guesswork**: The LLM is never the source of truth for calculations. Calculations are governed in dbt dimensional marts and validated through AST query bounds.
2. **Strict Financial Precision**: Authoritative financial calculations must never use IEEE-754 floating-point arithmetic. All monetary values are enforced as `DECIMAL(18, 4)`.
3. **Memory & Resource Efficiency**: Architected to run smoothly on a **16GB RAM Mac** using lightweight Docker containers (`<512MB` RAM) and serverless cloud tiers (`free-for.dev`).
4. **Defense in Depth**: Text-to-SQL generation is treated as a security boundary: read-only database roles, `SELECT`-only AST parsing, mandatory date partitions, and timeout enforcement.
