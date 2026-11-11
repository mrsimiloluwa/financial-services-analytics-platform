# Runbook: Governed Metadata Catalog Operations & Troubleshooting

## 1. Quick Reference Commands

### Publish & Persist Metadata Snapshot
```bash
PYTHONPATH="packages/data_platform/src:packages/shared/src" \
.venv/bin/python -m data_platform.metadata.cli publish-and-load \
  --target-dir packages/data_platform/dbt_analytics/target \
  --environment dev
```

### Inspect Governed Catalog Summary
```bash
PYTHONPATH="packages/data_platform/src:packages/shared/src" \
.venv/bin/python -m data_platform.metadata.cli inspect
```

### Inspect Specific Model Columns & Classification
```bash
PYTHONPATH="packages/data_platform/src:packages/shared/src" \
.venv/bin/python -m data_platform.metadata.cli inspect --model fct_transactions
```

### Generate AI QueryContext JSON (Security Boundary Check)
```bash
PYTHONPATH="packages/data_platform/src:packages/shared/src" \
.venv/bin/python -m data_platform.metadata.cli ai-context --model fct_transactions
```

---

## 2. Airflow Orchestration Integration

In the Airflow DAG (`financial_analytics_dev_pipeline`), metadata lifecycle tasks are executed automatically after the dbt build:

```
validate_preflight
   ↓
ingest_dev_dataset
   ↓
dbt_build_analytics
   ↓
dbt_docs_generate        <-- Refreshes manifest.json and catalog.json
   ↓
publish_and_load_metadata <-- Extracts snapshot & loads into PostgreSQL metadata schema
   ↓
validate_metadata_catalog <-- Asserts minimum models, sources, and 12 metrics
   ↓
reconcile_financial_integrity
   ↓
export_sample_artifacts
   ↓
log_pipeline_completion
```

---

## 3. Common Failure Scenarios & Recovery

### Issue 1: Missing dbt Artifacts (`manifest.json` or `catalog.json` not found)
- **Symptom**: `FileNotFoundError: Required dbt artifact 'catalog.json' not found`.
- **Root Cause**: `dbt docs generate` was skipped or failed.
- **Resolution**:
  ```bash
  cd packages/data_platform/dbt_analytics
  dbt docs generate --profiles-dir /tmp/dbt_profiles --target dev
  ```

### Issue 2: Financial Metric Validation Failure
- **Symptom**: `Financial metric validation errors found: Metric 'gross_transaction_volume': column 'invalid_col' does not exist in model 'fct_transactions'`.
- **Root Cause**: A referenced column in `financial_metrics.yaml` was renamed or removed in the dbt model.
- **Resolution**: Inspect `packages/data_platform/src/data_platform/metadata/financial_metrics.yaml` and align column names with the current dbt model schema.

### Issue 3: PermissionError on AI Query Context Request
- **Symptom**: `PermissionError: Model 'stg_transactions' is not in the governed queryable allowlist`.
- **Root Cause**: Attempting to generate AI context for staging, intermediate, or raw tables.
- **Resolution**: Direct AI queries exclusively to the 9 approved dimensional marts (`dim_customers`, `dim_accounts`, `dim_gl_accounts`, `dim_date`, `fct_transactions`, `fct_fee_assessments`, `fct_fee_collections`, `fct_customer_revenue`, `fct_ledger_entries`).
