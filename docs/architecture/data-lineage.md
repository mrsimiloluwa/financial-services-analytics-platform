# Architecture: End-to-End Data Lineage & Dependency Graphs

## 1. Overview & Lineage Strategy

Data lineage provides complete transparency into the origin, movement, and transformation of financial records as they travel from raw synthetic banking tables to Kimball-style analytical marts.

The platform implements two complementary levels of data lineage:
1. **Model-Level Lineage (Deterministic DAG)**: Derived directly from the compiled dbt dependency graph (`parent_map` and `child_map` in `manifest.json`). Guarantees 100% accuracy of inter-model dependencies.
2. **Column-Level Lineage (Conservative AST Analysis)**: Parsed from SQL queries using `sqlglot`. Conservative analysis extracts direct column projections and tracks simple arithmetic/case statements, while explicitly tagging ambiguous or windowed expressions as `AMBIGUOUS_COMPLEX_EXPRESSION` rather than fabricating speculative column ancestry.

---

## 2. Model Dependency Graph (End-to-End)

The full platform data lineage connects the 12 raw source tables through 12 staging views and 5 intermediate tables to the 9 core and finance dimensional marts:

```mermaid
graph LR
    subgraph RawSources["Raw Ingested Tables (PostgreSQL raw.*)"]
        raw_cust[("raw.customers")]
        raw_acct[("raw.accounts")]
        raw_txns[("raw.transactions")]
        raw_fees[("raw.fee_assessments")]
        raw_colls[("raw.fee_collections")]
        raw_rev[("raw.revenue_recognitions")]
        raw_gl[("raw.gl_accounts")]
        raw_jrnls[("raw.journals")]
        raw_ledg[("raw.ledger_entries")]
        raw_fx[("raw.fx_rates")]
        raw_ovd[("raw.overdraft_facilities")]
        raw_man[("raw.ingestion_batch_manifests")]
    end

    subgraph StagingLayer["Staging Views (dbt staging.*)"]
        stg_cust["stg_customers"]
        stg_acct["stg_accounts"]
        stg_txns["stg_transactions"]
        stg_fees["stg_fee_assessments"]
        stg_colls["stg_fee_collections"]
        stg_rev["stg_revenue_recognitions"]
        stg_gl["stg_gl_accounts"]
        stg_jrnls["stg_journals"]
        stg_ledg["stg_ledger_entries"]
        stg_fx["stg_fx_rates"]
        stg_ovd["stg_overdraft_facilities"]
        stg_man["stg_ingestion_batch_manifests"]
    end

    subgraph IntermediateLayer["Intermediate Transformations (dbt intermediate.*)"]
        int_cust_accts("int_customer_accounts")
        int_txns_enr("int_transactions_enriched")
        int_fee_life("int_fee_lifecycle")
        int_jrn_bal("int_journal_balances")
        int_cust_rev("int_customer_revenue")
    end

    subgraph DimensionalMarts["Dimensional Marts (dbt analytics.*)"]
        dim_c[/dim_customers/]
        dim_a[/dim_accounts/]
        dim_g[/dim_gl_accounts/]
        dim_d[/dim_date/]
        fct_t[/fct_transactions/]
        fct_fa[/fct_fee_assessments/]
        fct_fc[/fct_fee_collections/]
        fct_cr[/fct_customer_revenue/]
        fct_le[/fct_ledger_entries/]
    end

    raw_cust --> stg_cust
    raw_acct --> stg_acct
    raw_txns --> stg_txns
    raw_fees --> stg_fees
    raw_colls --> stg_colls
    raw_rev --> stg_rev
    raw_gl --> stg_gl
    raw_jrnls --> stg_jrnls
    raw_ledg --> stg_ledg
    raw_fx --> stg_fx
    raw_ovd --> stg_ovd
    raw_man --> stg_man

    stg_cust --> int_cust_accts
    stg_acct --> int_cust_accts
    stg_ovd --> int_cust_accts

    stg_txns --> int_txns_enr
    int_cust_accts --> int_txns_enr
    stg_fx --> int_txns_enr

    stg_fees --> int_fee_life
    stg_colls --> int_fee_life
    stg_rev --> int_fee_life

    stg_jrnls --> int_jrn_bal
    stg_ledg --> int_jrn_bal

    int_fee_life --> int_cust_rev
    stg_fx --> int_cust_rev

    int_cust_accts --> dim_c
    int_cust_accts --> dim_a
    stg_gl --> dim_g

    int_txns_enr --> fct_t
    int_fee_life --> fct_fa
    stg_colls --> fct_fc
    int_fee_life --> fct_fc
    int_cust_rev --> fct_cr
    stg_ledg --> fct_le
    stg_fx --> fct_le
```

---

## 3. Lineage Engine API & Traversal Methods

The `LineageEngine` class in `packages/data_platform/src/data_platform/metadata/lineage.py` provides bidirectional traversal capabilities:

### 3.1 Trace Mart to Raw Sources (`trace_mart_to_sources`)
Given a business mart (e.g. `fct_customer_revenue`), traverses upstream through intermediate and staging models to discover all underlying raw sources:
```python
engine = LineageEngine(parent_map=manifest_parser.parent_map)
sources = engine.trace_mart_to_sources("model.dbt_analytics.fct_customer_revenue")
# Returns:
# [
#   'source.dbt_analytics.raw.accounts',
#   'source.dbt_analytics.raw.customers',
#   'source.dbt_analytics.raw.fee_assessments',
#   'source.dbt_analytics.raw.fee_collections',
#   'source.dbt_analytics.raw.fx_rates',
#   'source.dbt_analytics.raw.revenue_recognitions'
# ]
```

### 3.2 Trace Source to Downstream Marts (`trace_source_to_marts`)
Given a raw source table (e.g. `raw.fee_assessments`), traverses downstream to determine which dimensional marts will be affected by schema changes or upstream data anomalies:
```python
marts = engine.trace_source_to_marts("source.dbt_analytics.raw.fee_assessments")
# Returns:
# [
#   'model.dbt_analytics.fct_customer_revenue',
#   'model.dbt_analytics.fct_fee_assessments',
#   'model.dbt_analytics.fct_fee_collections'
# ]
```

---

## 4. Column-Level Lineage with SQLGlot

The `ColumnLineageAnalyzer` uses SQLGlot's AST visitor to extract conservative column-to-column dependencies from model queries.

### Rules:
1. **Direct Projection**: `SELECT c.customer_id AS id` -> `id: ["customer_id"]`.
2. **Explicit Casts**: `SELECT CAST(amount AS numeric(18,4)) AS txn_amt` -> `txn_amt: ["amount"]`.
3. **Multi-Column Arithmetic**: `SELECT gross_amount - waived_amount AS net_amount` -> `net_amount: ["gross_amount", "waived_amount"]`.
4. **Ambiguous Window / Aggregation**: `SELECT SUM(amount) OVER (...)` -> mapped only to contained column identifiers without fabricating upstream columns.
5. **Jinja Pre-Processing**: Strips `{{ ref(...) }}` and `{{ source(...) }}` macros to valid SQL table aliases before AST parsing, avoiding unparseable syntax errors.
