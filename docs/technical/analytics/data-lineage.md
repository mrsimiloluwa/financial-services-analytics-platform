# Data Lineage & Dimensional Architecture

This document illustrates the end-to-end lineage from the PostgreSQL `raw` schema through the dbt staging, intermediate, and Kimball dimensional mart layers in the `analytics` schema.

---

## 1. End-to-End dbt DAG Lineage

```mermaid
flowchart LR
    subgraph RAW["PostgreSQL raw Schema (12 Tables)"]
        R_CUST["raw.customers"]
        R_ACC["raw.accounts"]
        R_OD["raw.overdraft_facilities"]
        R_GL["raw.gl_accounts"]
        R_FX["raw.fx_rates"]
        R_TXN["raw.transactions"]
        R_JRN["raw.journals"]
        R_LE["raw.ledger_entries"]
        R_FA["raw.fee_assessments"]
        R_FC["raw.fee_collections"]
        R_RR["raw.revenue_recognitions"]
        R_MAN["raw.ingestion_batch_manifests"]
    end

    subgraph STG["Staging Layer (analytics.stg_* Views)"]
        S_CUST["stg_customers"]
        S_ACC["stg_accounts"]
        S_OD["stg_overdraft_facilities"]
        S_GL["stg_gl_accounts"]
        S_FX["stg_fx_rates"]
        S_TXN["stg_transactions"]
        S_JRN["stg_journals"]
        S_LE["stg_ledger_entries"]
        S_FA["stg_fee_assessments"]
        S_FC["stg_fee_collections"]
        S_RR["stg_revenue_recognitions"]
        S_MAN["stg_ingestion_batch_manifests"]
    end

    subgraph INT["Intermediate Layer (analytics.int_* Views)"]
        I_CA["int_customer_accounts"]
        I_TXN["int_transactions_enriched"]
        I_JB["int_journal_balances"]
        I_FL["int_fee_lifecycle"]
        I_CR["int_customer_revenue"]
    end

    subgraph MARTS["Kimball Dimensional Marts (analytics.dim_* & fct_* Tables)"]
        D_CUST["dim_customers"]
        D_ACC["dim_accounts"]
        D_GL["dim_gl_accounts"]
        D_DATE["dim_date"]
        F_TXN["fct_transactions"]
        F_LE["fct_ledger_entries"]
        F_FA["fct_fee_assessments"]
        F_FC["fct_fee_collections"]
        F_CR["fct_customer_revenue"]
    end

    R_CUST --> S_CUST
    R_ACC --> S_ACC
    R_OD --> S_OD
    R_GL --> S_GL
    R_FX --> S_FX
    R_TXN --> S_TXN
    R_JRN --> S_JRN
    R_LE --> S_LE
    R_FA --> S_FA
    R_FC --> S_FC
    R_RR --> S_RR
    R_MAN --> S_MAN

    S_CUST --> I_CA
    S_ACC --> I_CA
    S_OD --> I_CA

    S_TXN --> I_TXN
    I_CA --> I_TXN
    S_FX --> I_TXN

    S_JRN --> I_JB
    S_LE --> I_JB

    S_FA --> I_FL
    S_FC --> I_FL
    S_RR --> I_FL
    I_TXN --> I_FL
    S_FX --> I_FL

    I_FL --> I_CR

    S_CUST --> D_CUST
    I_CA --> D_CUST
    I_TXN --> D_CUST

    I_CA --> D_ACC
    S_LE --> D_ACC

    S_GL --> D_GL
    S_FX --> D_DATE

    I_TXN --> F_TXN

    S_LE --> F_LE
    S_JRN --> F_LE
    S_GL --> F_LE
    I_CA --> F_LE
    S_FX --> F_LE

    I_FL --> F_FA

    S_FC --> F_FC
    S_FA --> F_FC
    I_TXN --> F_FC
    S_RR --> F_FC
    S_FX --> F_FC

    I_CR --> F_CR
```

---

## 2. Dimensional Star Schema Relationships

```mermaid
erDiagram
    dim_customers ||--o{ dim_accounts : "holds (customer_id)"
    dim_customers ||--o{ fct_transactions : "initiates (customer_id)"
    dim_customers ||--o{ fct_fee_assessments : "assessed (customer_id)"
    dim_customers ||--o{ fct_fee_collections : "swept (customer_id)"
    dim_customers ||--o{ fct_customer_revenue : "generates (customer_id)"

    dim_accounts ||--o{ fct_transactions : "originates (account_id)"
    dim_accounts ||--o{ fct_fee_assessments : "charged (account_id)"
    dim_accounts ||--o{ fct_fee_collections : "debited (account_id)"

    dim_gl_accounts ||--o{ fct_ledger_entries : "classifies (gl_account_id)"

    dim_date ||--o{ fct_transactions : "transaction_date"
    dim_date ||--o{ fct_ledger_entries : "posting_date"
    dim_date ||--o{ fct_fee_assessments : "assessed_date"
    dim_date ||--o{ fct_fee_collections : "attempted_date"
    dim_date ||--o{ fct_customer_revenue : "reporting_month"

    fct_transactions ||--o| fct_fee_assessments : "triggers (transaction_id)"
    fct_fee_assessments ||--o{ fct_fee_collections : "swept via (assessment_id)"
```

---

## 3. Financial Fee Lifecycle & Revenue Calculation Flow

```mermaid
flowchart TD
    TXN["Settled Commercial Transaction<br/>(fct_transactions)"]
    ASSESS["Fee Assessment<br/>Gross Assessed Fee = Base Fee + (Amount * bps)"]
    WAIVE["Commercial Waiver Evaluation<br/>Net Collectible Fee = Gross Assessed - Waived Amount"]
    SWEEP{"Collection Sweep Attempt<br/>(fct_fee_collections)"}
    SETTLED["Collection Status: SETTLED<br/>Collected Amount = Target Amount<br/>Outstanding Amount = 0.0000"]
    FAILED["Collection Status: FAILED<br/>Collected Amount = 0.0000<br/>Outstanding Amount = Target Amount (Arrears)"]
    GL["Double-Entry Fee Journal (FEE_SETTLEMENT)<br/>DEBIT: GL_LIAB_CUSTOMER_DEPOSITS<br/>CREDIT: GL_REV_*_FEES"]
    REV["Revenue Recognition (Collection-Based)<br/>Net Recognized Revenue = Gross Collected - Reversed - Pass-Through Cost"]

    TXN --> ASSESS
    ASSESS --> WAIVE
    WAIVE --> SWEEP
    SWEEP -->|Sufficient Liquidity & Active Account| SETTLED
    SWEEP -->|Insufficient Funds / Frozen Account| FAILED
    SETTLED --> GL
    SETTLED --> REV
```

---

## 4. Accessing Interactive dbt Documentation

The dbt documentation catalog (`target/catalog.json`) and manifest (`target/manifest.json`) are generated via:

```bash
.venv/bin/uv run --env-file .env dbt docs generate \
  --project-dir packages/data_platform/dbt_analytics \
  --profiles-dir /tmp/dbt_profiles
```

To launch the local interactive dbt documentation server and lineage graph explorer:

```bash
.venv/bin/uv run --env-file .env dbt docs serve \
  --project-dir packages/data_platform/dbt_analytics \
  --profiles-dir /tmp/dbt_profiles \
  --port 8085
```
