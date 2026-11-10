# Ingestion Pipeline Architecture

## High-Throughput PostgreSQL Batch Ingestion

This document details the architecture and operational mechanics of the synthetic data ingestion pipeline powering the Enterprise AI Analytics Platform.

---

## 1. End-to-End Pipeline Workflow

The ingestion pipeline decouples memory-intensive synthetic banking generation from relational persistence using unlogged staging tables, binary-efficient streaming `COPY`, and atomic transactional merges:

```mermaid
flowchart TD
    subgraph DataGeneration["1. Deterministic Synthetic Generation"]
        A["SyntheticDataGenerator (seed=42)"] --> B["CustomerEngine & AccountEngine"]
        A --> C["FXEngine (ECB Triangulated Matrix)"]
        A --> D["TransactionEngine (Commercial Flows)"]
        D --> E["LedgerEngine (Double-Entry Journals)"]
        D --> F["FeeEngine (Assessments & Sweeps)"]
    end

    subgraph StagingPhase["2. Staged Bulk COPY (psycopg 3)"]
        G["Unlogged Staging Tables (staging.*)"]
        B & C & D & E & F -->|Bulk Stream via COPY| G
    end

    subgraph MergePhase["3. Atomic Transactional Merge"]
        G -->|INSERT ... ON CONFLICT DO NOTHING| H[("PostgreSQL Raw Tables (raw.*)")]
        I["Audit Manifest Logging"] --> H
    end

    subgraph AuditPhase["4. Data Quality & Reconciliation"]
        H --> J{"DataReconciler Audit"}
        J -->|Check 1| K["Double-Entry Balanced per Currency Leg"]
        J -->|Check 2| L["Zero Postings on Unsettled Txns"]
        J -->|Check 3| M["Referential Integrity (No Orphans)"]
        J -->|Check 4| N["Fee Math & Collection Ceilings"]
        J -->|Check 5| O["Currency Domains (EUR, USD, GBP, CHF)"]
        K & L & M & N & O -->|All 7 Checks Passed| P["Batch Marked COMPLETED"]
        J -->|Any Check Fails| Q["Rollback Transaction & Alert"]
    end
```

---

## 2. Ingestion Mechanics & Design Decisions

### A. Unlogged Staging Tables
To achieve multi-thousand row-per-second ingestion without saturating disk I/O on development machines (16GB RAM Mac), the pipeline loads records into PostgreSQL `UNLOGGED` tables in the `staging` schema. Unlogged tables bypass Write-Ahead Logging (WAL) during the copy phase.

### B. Streaming COPY Protocol
Rather than generating thousands of parameterized `INSERT` statements, the pipeline uses `psycopg 3` COPY streams:
```python
with cur.copy("COPY staging.transactions FROM STDIN") as copy:
    for t in data.transactions:
        copy.write_row(...)
```

### C. Idempotent Transactional Merge
Once all tables are staged, the pipeline merges records into `raw.*` tables within a single database transaction using `ON CONFLICT (pk) DO NOTHING`. This ensures:
- Safe rerunability on duplicate executions.
- Zero duplicate records created on retries.
- Foreign key constraints are enforced atomically.
- Failures result in complete rollback, leaving no partial batches.

---

## 3. Entity-Relationship Data Model (Raw Schema)

```mermaid
erDiagram
    CUSTOMERS ||--o{ ACCOUNTS : "holds"
    ACCOUNTS ||--o{ OVERDRAFT_FACILITIES : "attached to"
    ACCOUNTS ||--o{ TRANSACTIONS : "initiates"
    ACCOUNTS ||--o{ LEDGER_ENTRIES : "subledger postings"
    GL_ACCOUNTS ||--o{ LEDGER_ENTRIES : "general ledger control"
    JOURNALS ||--|{ LEDGER_ENTRIES : "groups"
    TRANSACTIONS ||--o| JOURNALS : "settlement event"
    TRANSACTIONS ||--o{ FEE_ASSESSMENTS : "evaluated for"
    FEE_ASSESSMENTS ||--o{ FEE_COLLECTIONS : "collected via"
    FEE_COLLECTIONS ||--o| REVENUE_RECOGNITIONS : "recognized as"
```
