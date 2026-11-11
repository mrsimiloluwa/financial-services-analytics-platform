# SQL Security Architecture & Threat Defense

## 1. Security Philosophy

In the Financial Services Analytics & AI Platform, the AI query execution boundary is treated as an adversarial perimeter. Large Language Models must **never** be granted unconstrained database access or relied upon to self-police query safety through prompt instructions.

Security is implemented in depth through three independent defensive perimeters:

```
[ Natural Language Input ]
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│ Perimeter 1: Intent & Prompt Injection Shield                │
│ (Rejects system overrides, SQL drop/delete directives)      │
└─────────────────────────────────────────────────────────────┘
           │ (Sanitized inquiry)
           ▼
┌─────────────────────────────────────────────────────────────┐
│ Perimeter 2: SQLGlot AST Semantic & Boundary Validator     │
│ - Single statement enforcement (rejects stacked semicolons) │
│ - Pure SELECT root only (rejects INSERT, UPDATE, DDL)       │
│ - Strict Schema & Mart Allowlist (schema 'analytics' only)  │
│ - RESTRICTED Column Pattern Scanning (password, secrets)    │
│ - Row Limit Clamping (enforces LIMIT 1000)                  │
└─────────────────────────────────────────────────────────────┘
           │ (Sanitized, clamped SQL)
           ▼
┌─────────────────────────────────────────────────────────────┐
│ Perimeter 3: PostgreSQL Database Role & Session Sandbox     │
│ - Role: analytics_reader (SELECT-only on analytics.*)       │
│ - Revoked: raw.*, staging.*, metadata.*, intermediate.*     │
│ - Session timeout: SET statement_timeout = '5000ms'         │
│ - autocommit=True, read-only transaction semantics          │
└─────────────────────────────────────────────────────────────┘
           │
           ▼
[ Analytics Mart Tables ]
```

---

## 2. Perimeter 1: Prompt Injection Shield

When incoming questions are processed by `QuestionUnderstanding`, the system tests for known adversarial prompt injection vectors:
- System prompt overrides (`"Ignore previous instructions"`, `"System override:"`)
- Destructive directives (`"drop table"`, `"delete from"`, `"truncate"`)
- Schema traversal hints (`"SELECT * FROM raw."`, `"information_schema"`)
- Secret credential exfiltration (`"password"`, `"api_key"`, `"secret tokens"`)

If detected, `is_out_of_scope` is flagged, causing immediate routing to narrative rejection without constructing database prompts.

---

## 3. Perimeter 2: SQLGlot AST Validator

The AST validator inspects the compiled query representation using `SQLGlot` under the `postgres` dialect before physical execution:

```python
validator = SQLGlotASTValidator(dialect="postgres", max_limit=1000)
result = validator.validate_and_sanitize(generated_sql)
```

### AST Enforcement Rules

1. **Single Statement Integrity**: Semicolon-delimited compound queries (`SELECT ...; DROP TABLE ...;`) generate multiple AST expression roots. Any query yielding `len(expressions) > 1` is immediately rejected.
2. **Forbidden Expressions**: Trees containing `exp.Insert`, `exp.Update`, `exp.Delete`, `exp.Create`, `exp.Drop`, `exp.Alter`, `exp.TruncateTable`, `exp.Command`, or `exp.Pragma` are blocked.
3. **Root Expression Validation**: The top-level AST root must evaluate strictly to `exp.Select`.
4. **Schema Allowlist**:
   - Permitted: `analytics` or empty (auto-normalized to `analytics`).
   - Disallowed: `raw`, `staging`, `intermediate`, `metadata`, `public`, `information_schema`, `pg_catalog`.
5. **Table Allowlist**:
   - Queries can only touch tables defined in `QUERYABLE_ALLOWLIST`:
     - `dim_accounts`, `dim_customers`, `fct_customer_revenue`, `fct_fee_assessments`, `fct_journal_entries`, `fct_transactions`.
6. **Restricted Column Redaction**:
   - Column identifiers matching sensitive terms (`password`, `secret`, `api_key`, `token`, `private_key`, `credential`) trigger rejection.
7. **Deterministic Row Clamping**:
   - If no `LIMIT` clause exists, `LIMIT 1000` is appended.
   - If a `LIMIT` clause requests more than 1,000 rows (e.g. `LIMIT 50000`), it is clamped to `1000`.

---

## 4. Perimeter 3: PostgreSQL `analytics_reader` Sandbox

Even if an attacker bypassed AST parsing, the database engine enforces physical permission isolation.

### Provisioning DDL

Role setup is provisioned via `packages/data_platform/src/data_platform/sql/provision_analytics_reader.sql`:

```sql
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'analytics_reader') THEN
        CREATE ROLE analytics_reader WITH LOGIN PASSWORD 'analytics_reader_secret';
    END IF;
END $$;

ALTER ROLE analytics_reader SET statement_timeout = '5000ms';

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM analytics_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA raw FROM analytics_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA staging FROM analytics_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA intermediate FROM analytics_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA metadata FROM analytics_reader;

GRANT USAGE ON SCHEMA analytics TO analytics_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO analytics_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA analytics GRANT SELECT ON TABLES TO analytics_reader;
```

### Statement Timeout Protection

To prevent denial-of-service (DoS) via Cartesian joins or table scans, `analytics_reader` has a role-level and session-level statement timeout of **5000ms**. If an analytical query takes longer than 5 seconds to complete, PostgreSQL forcibly terminates the backend transaction with `psycopg.errors.QueryCanceled`.
