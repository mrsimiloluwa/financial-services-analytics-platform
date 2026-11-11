# TEST Profile Sample Data Exports

This directory preserves representative raw banking tables and analytical outputs exported from the synthetic generator's **TEST** profile.

## Profile Metadata
- **Profile Name:** `TEST`
- **Random Seed:** `42`
- **Reporting Currency:** `EUR`
- **Supported Account Currencies:** `EUR`, `USD`, `GBP`, `CHF`
- **Purpose:** Fast automated testing, CI integration pipelines, and small inspectable reconciliation examples.

## Dataset Scale
- **Customers:** 10
- **Accounts:** 24
- **Overdraft Facilities:** 20
- **Transactions:** 200
- **Journals:** 328
- **Ledger Entries:** 770
- **Fee Assessments:** 148
- **Fee Collections:** 148
- **Revenue Recognitions:** 140
- **Total Raw Records:** 7,642

## Reproduction Command
To regenerate and ingest the TEST profile into PostgreSQL:
```bash
PYTHONPATH=packages/shared/src:packages/data_platform/src .venv/bin/uv run --env-file .env python -m data_platform.ingestion.run --profile TEST --reset
```
