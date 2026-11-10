# AGENTS.md — Enterprise AI Analytics Platform

## 1. Project Identity

Project: Enterprise AI Analytics Platform for Financial Services.

This repository contains a modular financial analytics and AI platform designed to demonstrate enterprise-level engineering practices across:

- Analytics Engineering
- Data Engineering
- AI Engineering
- Data Product Engineering
- Software Engineering
- DevOps and CI/CD

The platform will enable business users to explore governed financial information and ask questions about customer profitability, transaction fees, revenue, pricing, billing exceptions and operational performance.

This is a long-term portfolio project. Maintain production-quality engineering standards throughout development.

## 2. Core Engineering Principles

All agents MUST follow these principles:

1. Prefer simple, maintainable and modular solutions.
2. Avoid unnecessary abstraction and overengineering.
3. Keep business logic separate from infrastructure and presentation logic.
4. Use clear interfaces and explicit data contracts.
5. Write testable code.
6. Include appropriate error handling and structured logging.
7. Document non-obvious architectural decisions.
8. Use meaningful names for files, variables, functions and classes.
9. Never hardcode credentials, API keys or environment-specific configuration.
10. Never silently modify or delete unrelated files.
11. Never assume an external service or dependency is available without checking.
12. Do not introduce a technology unless it provides a clear architectural benefit.
13. Keep the application compatible with a Mac running 16GB RAM.
14. Prefer free and open-source tools where practical.
15. Do not claim functionality is production-ready unless it has been implemented and tested.

## 3. Approved Technology Stack

Use these technologies as the architectural baseline.

### Languages and runtime

- Python 3.12
- SQL
- uv for Python package management

### Data engineering

- PostgreSQL
- DuckDB for lightweight analytical testing
- Python for ingestion and data processing
- Apache Airflow for orchestration in a later phase

### Analytics engineering

- dbt Core
- dbt-postgres
- SQLFluff
- dbt tests
- Dimensional data modelling

### AI engineering

- LangGraph
- LLM APIs through configurable provider interfaces
- SQLGlot for SQL parsing and validation
- RAG for document retrieval
- Qdrant when vector retrieval is introduced
- MCP for exposing selected governed tools

### Application engineering

- FastAPI
- Pydantic
- Streamlit

### Governance

- dbt metadata artifacts as the initial foundation
- OpenMetadata or DataHub in a later phase
- Documented business glossary
- Metric definitions
- Data lineage
- Data classification

### DevOps and quality

- Git and GitHub
- Docker
- Docker Compose
- GitHub Actions
- pytest
- Ruff
- Pre-commit

Do not introduce all technologies at once.

Use the simplest suitable implementation for the current development phase.

Any proposal to replace a core technology must include the reason, benefits, drawbacks and migration implications.

## 4. Repository Architecture

Maintain clear separation of responsibilities.

Expected logical areas:

- packages/data_platform: ingestion, source data and data engineering.
- packages/data_platform/dbt_analytics: dbt project and analytical models.
- packages/ai_services: AI workflows, APIs, RAG and MCP.
- packages/data_apps: Streamlit applications and user interfaces.
- packages/shared: reusable shared utilities and contracts.
- tests: unit, integration and AI evaluation tests.
- docs: architecture, domain documentation, decisions and runbooks.
- docker: Dockerfiles and Compose configurations.
- .github/workflows: CI/CD automation.

The actual directory structure may evolve as the project grows.

Do not create unnecessary empty folders or duplicate functionality across packages.

## 5. Python Standards

- Use Python 3.12.
- Use uv for dependency installation and environment management.
- Declare project dependencies in pyproject.toml.
- Keep uv.lock synchronized.
- Use type hints for public functions and important interfaces.
- Prefer small functions with clear responsibilities.
- Use Pydantic for external data validation and configuration where appropriate.
- Avoid unnecessary global state.
- Use asynchronous code only where it provides a meaningful benefit.
- Use dependency injection for services that require external resources.
- Keep business logic independent of FastAPI, Streamlit and specific LLM providers where practical.

Use Ruff for linting and formatting.

Use pytest for automated tests.

## 6. SQL and Analytics Engineering Standards

Follow dimensional modelling principles where appropriate.

Use a layered dbt structure:

- staging: source cleanup, renaming and type normalization.
- intermediate: reusable business transformations.
- marts: business-facing facts, dimensions and metrics.

Prefer explicit transformations over opaque SQL.

Every important model should have:

- A clear purpose.
- Appropriate model and column descriptions.
- Tests for key constraints.
- Documented grain.
- Defined relationships.
- Business terminology.

Use appropriate tests for:

- Uniqueness.
- Not-null constraints.
- Referential integrity.
- Accepted values.
- Financial consistency.
- Business-specific rules.

Avoid duplicating financial calculation logic across multiple models.

Use a single governed definition for important financial metrics.

Do not allow AI-generated SQL to redefine business metrics independently.

## 7. Financial Domain Rules

The platform uses synthetic or publicly available data only.

Never use confidential employer data, customer records, real account details or proprietary internal documentation.

Financial calculations must be explicit and reproducible.

Pay particular attention to:

- Transaction currencies.
- FX conversion.
- Gross versus net revenue.
- Fee waivers.
- Contractual pricing.
- Effective dates.
- Reversals and refunds.
- Duplicate transactions.
- Customer and account relationships.
- Reporting periods.
- Time zones.
- Decimal precision and rounding.

Use appropriate decimal/numeric types for financial calculations.

Do not use floating-point arithmetic for authoritative monetary calculations.

Document assumptions whenever the underlying financial definition is ambiguous.

## Synthetic Data Transparency and Reproducibility

The project must make its synthetic data independently inspectable and reproducible.

### 1. Sample Data Exports
- Maintain a `sample_data/` directory containing representative CSV exports of the raw banking entities.
- Include customers, accounts, transactions, GL accounts, journals, ledger entries, fee assessments, fee collections, revenue recognition and FX rates where applicable.
- Include representative transformed analytical outputs where useful.
- Ensure CSV exports reflect actual generated database records. Never invent sample outputs and present them as database extracts.
- Include headers, consistent data types and documented currency conventions.
- Never publish credentials, real personal information or confidential employer data.

### 2. Generation Transparency
- Document how synthetic records are generated.
- Expose the actual Python generation code.
- Document generation configuration, distributions, assumptions and random seeds.
- Provide reproducible commands to regenerate the data.
- Explain how transaction, ledger, fee and reversal relationships are maintained.

### 3. Data Documentation
- Document every published CSV, including its grain, columns, primary identifiers, relationships and currency fields.
- Explain which records are synthetic and which business behaviours they represent.
- Include representative data quality and reconciliation results.

### 4. Reproducibility
- A new developer must be able to generate the synthetic dataset and load it into PostgreSQL using documented instructions.
- CSV exports must be reproducible from the generation pipeline.
- Large datasets should use representative downloadable samples rather than unnecessarily large Git commits.
- Keep sample exports and documentation synchronised with the actual database schema.

## 8. AI Engineering Standards

AI must operate on governed data and approved tools.

The LLM is not the source of truth for financial calculations.

The AI workflow should:

1. Understand the user's request.
2. Identify the appropriate business metric or knowledge source.
3. Retrieve relevant approved metadata or documentation.
4. Select an approved tool.
5. Validate inputs and generated queries.
6. Execute only authorized operations.
7. Validate the returned results.
8. Explain the answer with relevant evidence and assumptions.

Start with a single controlled LangGraph workflow.

Do not introduce multiple agents unless a specific use case justifies them.

Keep prompts, model configuration, tools and workflow logic separate.

Make the LLM provider and model configurable through environment variables.

Do not hardcode model identifiers throughout the application.

## 9. SQL Security Requirements

The AI query execution layer must be treated as a security boundary.

Requirements:

- Use SQLGlot or an equivalent SQL parser.
- Reject DDL and DML statements.
- Permit only explicitly approved read-only query operations.
- Restrict accessible schemas, tables and columns.
- Use a separate read-only database account.
- Restrict that account to approved analytical objects.
- Apply query timeouts.
- Apply appropriate row limits.
- Enforce required date filters on large fact tables.
- Prevent unauthorized tenant or customer data access.
- Validate queries before execution.
- Do not rely on prompt instructions as a security control.

A SQL LIMIT clause alone is not sufficient protection against expensive queries.

All security controls must be enforced by application code and database permissions.

## 10. RAG and Knowledge Retrieval Standards

RAG is intended for supporting financial knowledge such as:

- Synthetic fee schedules.
- Contractual pricing examples.
- Service-level agreements.
- Product documentation.
- Financial definitions.
- Synthetic banking policies.

Requirements:

- Preserve document source information.
- Track document identifiers and versions.
- Use reproducible chunking and indexing processes.
- Return source references with retrieved evidence.
- Avoid presenting retrieved content as verified fact without checking its source.
- Protect against prompt injection in retrieved documents.
- Do not use a vector database unless the retrieval use case requires one.

## 11. API and Application Standards

FastAPI should own backend application interfaces.

Streamlit should be responsible for presentation and user interaction.

Keep API endpoints versioned where appropriate.

Validate incoming and outgoing data using explicit schemas.

Implement:

- Appropriate HTTP status codes.
- Centralized error handling.
- Request validation.
- Structured logging.
- Health checks.
- API documentation.
- Timeouts for external service calls.

Do not expose credentials or sensitive internal information through API responses.

Do not expose internal model reasoning to end users.

It is acceptable to expose user-facing progress events, tool execution status and relevant query metadata.

## 12. Data Governance and Observability

Build governance incrementally.

The initial governance foundation should include:

- dbt model documentation.
- Column descriptions.
- Metric definitions.
- Data lineage artifacts.
- Data classification.
- Ownership documentation.

Introduce a full catalog platform only when its functionality is required.

Capture useful operational metadata, including:

- Pipeline execution status.
- Data freshness.
- Model test results.
- Query execution status.
- AI request outcomes.
- Latency.
- Errors.
- Evaluation results.

Never log API keys, passwords or unnecessary sensitive data.

## 13. Testing Requirements

Write tests alongside implementation.

Use the following testing categories:

### Unit tests

Test individual functions, transformations, validators, services and agent nodes.

### Integration tests

Test interactions between:

- PostgreSQL.
- dbt.
- FastAPI.
- AI tool interfaces.
- MCP integrations when introduced.

### Data quality tests

Test financial rules, uniqueness, referential integrity and expected business constraints.

### AI evaluation tests

Maintain a curated evaluation dataset for:

- Metric selection accuracy.
- SQL correctness.
- Financial calculation accuracy.
- Retrieval relevance.
- Evidence quality.
- Unsupported answer detection.
- Security and prompt-injection resistance.

Use deterministic tests wherever possible.

Do not make ordinary CI dependent on unpredictable external LLM responses unless specifically configured.

## 14. Configuration and Secrets

Use environment variables for environment-specific configuration.

Provide `.env.example` with documented placeholder values.

Never commit:

- `.env`
- API keys
- Passwords
- Access tokens
- Private certificates
- Real customer data

Use a centralized configuration module.

Validate required configuration during application startup.

Do not silently fall back to insecure defaults.

## 15. Docker and Resource Management

The development environment must be suitable for a 16GB RAM Mac.

Keep Docker services lightweight.

Avoid running all infrastructure continuously.

Use optional Compose profiles for heavyweight services introduced later.

Prefer cloud inference rather than running large language models locally.

Do not assume local Docker resources are unlimited.

Document service startup and shutdown commands.

## 16. Git and Change Management

- Work on feature branches.
- Never push directly to main.
- Do not reset or clean the user's Git workspace.
- Never discard existing staged or unstaged changes without explicit approval.
- Do not commit or push without explicit user approval.
- Use meaningful commit messages when commits are authorized.
- Keep changes focused on the requested task.
- Review diffs before declaring a task complete.

Do not modify unrelated files.

## 17. Dependency Management

Before introducing a new dependency:

1. Check whether the functionality already exists in the project.
2. Determine whether the dependency is necessary.
3. Prefer established and maintained libraries.
4. Check compatibility with Python 3.12.
5. Consider package size and resource consumption.
6. Explain significant new dependencies.

Do not add dependencies speculatively for future phases.

## 18. Documentation Standards

Maintain documentation as the architecture evolves.

Important architectural decisions should be recorded in docs/architecture/ as Architecture Decision Records (ADRs).

Document:

- Why a technology was selected.
- Alternatives considered.
- Trade-offs.
- Security implications.
- Operational implications.

Keep README setup instructions accurate.

Update documentation when changing interfaces, configurations or architectural behaviour.

## 19. Agent Behaviour and Workflow

Before starting any significant task:

1. Inspect the relevant files.
2. Understand existing architecture.
3. Identify dependencies and affected components.
4. Propose a focused implementation plan when the task is substantial.
5. Make the smallest complete change.
6. Run relevant tests and quality checks.
7. Review the Git diff.
8. Report changes and validation results.

Do not assume approval for work beyond the requested phase.

Do not silently change the architecture.

If an architectural decision is unclear, explain the alternatives and ask before making a consequential change.

Never claim a test, deployment or validation succeeded unless it was actually executed and verified.

## 20. Current Development Strategy

Build the platform in the following order:

Phase 0: Repository foundations and developer standards.

Phase 1: Synthetic financial data generation and ingestion.

Phase 2: dbt dimensional modelling and governed financial metrics.

Phase 3: Airflow orchestration and pipeline reliability.

Phase 4: Metadata, lineage and data governance.

Phase 5: Governed AI analytics using LangGraph, SQLGlot and RAG.

Phase 6: FastAPI and Streamlit data product.

Phase 7: Security hardening, evaluation, CI/CD and deployment.

Do not skip phases or implement future functionality prematurely.

The objective is a coherent, working enterprise-style platform—not a collection of disconnected technology demonstrations.

## 21. Portfolio & Recruiter-Readiness Standards

This repository is a public-facing professional engineering portfolio project. It must demonstrate implementation quality, technical decision-making and the ability to explain complex engineering concepts.

### 1. Show the actual implementation

Prefer real, inspectable implementation artifacts over abstract descriptions.

Where relevant, include:
- Python source code with meaningful type hints and docstrings.
- SQL DDL, queries and database constraints.
- dbt SQL models, YAML schemas and tests.
- API endpoints and Pydantic schemas.
- AI orchestration, retrieval and SQL validation code.
- Docker, CI/CD and infrastructure configuration.
- Automated tests and representative execution outputs.

Do not replace implementation with pseudocode when working code is feasible.

### 2. Documentation must explain the engineering

For every significant component, document:
- What problem it solves.
- Why the technology or design was selected.
- How the implementation works.
- Important design decisions and trade-offs.
- How to execute and test it.
- Expected output and known limitations.

### 3. Demonstrate SQL and data engineering

SQL should be a first-class part of this repository, not hidden inside Python.

Use dedicated, well-organised SQL files for database DDL, analytical queries, reconciliation, transformations and dbt models.

Include representative business questions and their SQL implementations.

### 4. Make the repository easy to inspect

Maintain:
- A professional README with architecture, technology stack, setup instructions and project status.
- A clear repository structure.
- Architecture diagrams using Mermaid where useful.
- Documentation for each major phase.
- Sample datasets or safe synthetic examples.
- Reproducible commands and test instructions.
- Meaningful test coverage.

### 5. Demonstrate engineering judgement

Explain important decisions rather than merely listing technologies.

Document assumptions, limitations, trade-offs, security controls and areas requiring future improvement.

Never claim production readiness, enterprise security or accounting correctness without evidence.

### 6. Milestone reporting

At the end of every milestone, report:

1. What was implemented.
2. Exact files created or modified.
3. Important Python and SQL implementation examples.
4. Representative commands and outputs.
5. Tests executed and actual results.
6. Architecture and design decisions.
7. Known limitations.
8. Suggested next milestone.

Keep reports concise but technically substantive. Include actual code snippets where they help demonstrate the work.

### 7. Public portfolio quality

Use synthetic or public data only. Never include employer confidential data, credentials, personal data or proprietary internal business logic.

Keep the repository understandable to an external reviewer who has never seen the project before.

## 22. Enterprise Documentation Standards

Treat documentation as a first-class engineering deliverable.

The project must maintain four documentation layers:

1. **Overview documentation:** project purpose, capabilities, architecture and quick start.
2. **Technical documentation:** implementation details, database schemas, data contracts, APIs, SQL logic, dbt models, AI architecture and security.
3. **Operational documentation:** environment setup, execution procedures, testing, troubleshooting, recovery and deployment.
4. **User documentation:** instructions for business users interacting with the dashboard and AI analytics capabilities.

### Documentation rules

- Documentation must describe implemented functionality, not planned functionality as if it already exists.
- Keep documentation close to the code and update it whenever relevant implementation changes.
- Use Mermaid diagrams for architecture, sequence flows, ER diagrams and pipeline processes where useful.
- Include actual SQL, Python, configuration examples and representative outputs.
- Document assumptions, limitations, failure scenarios and recovery procedures.
- Maintain a data dictionary and governed metric catalogue.
- Maintain Architecture Decision Records (ADRs) for significant technology and design choices.
- Provide reproducible commands for setup, execution and testing.
- Include a clear distinction between local development, testing and production deployment configurations.
- Avoid duplicating information across documents. Link to the authoritative reference.
- Validate documentation links and build the documentation site in CI.
- Never invent execution results, performance figures or security guarantees.

### Documentation acceptance criteria

A developer unfamiliar with the repository should be able to:
1. Understand the architecture.
2. Set up the environment from scratch.
3. Run the data pipeline.
4. Inspect the database and execute example SQL.
5. Run automated tests.
6. Understand the main business metrics and their lineage.
7. Troubleshoot common failures.

A business user should eventually be able to operate the application using the user guide without needing to read the source code.


