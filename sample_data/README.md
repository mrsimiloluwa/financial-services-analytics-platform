# Synthetic Sample Data & Analytical Exports

This directory contains representative raw banking table extracts and dbt analytical outputs produced by the **Enterprise AI Analytics Platform**'s deterministic financial simulation engine.

All datasets are 100% synthetic, reproducible, and mathematically verified against double-entry General Ledger balancing and pricing schedule accounting rules.

---

## 1. Directory Structure

```
sample_data/
├── README.md                          # Directory guide and reproduction instructions
├── accounts.csv                       # Subledger accounts across EUR, USD, GBP, CHF
├── customers.csv                      # Corporate SME, institutional, and wealth customers
├── overdraft_facilities.csv           # Contractual overdraft facility agreements
├── fx_rates.csv                       # Historical daily FX rates (first 15 days sample)
├── transactions.csv                   # Multi-channel commercial payment transactions
├── journals.csv                       # Balanced double-entry accounting journal events
├── ledger_entries.csv                 # General Ledger debit and credit postings
├── fee_assessments.csv                # Contractual fee assessments and waiver records
├── fee_collections.csv                # Fee sweep collection attempts and failure logs
├── revenue_recognitions.csv           # Accounting revenue recognition records
├── gl_accounts.csv                    # Governed Master Chart of Accounts
├── ingestion_batch_manifests.csv      # Ingestion audit and lineage tracking
├── customer_revenue.csv               # Analytical mart: monthly customer revenue by segment
├── fee_assessments_analytics.csv      # Analytical mart: full fee lifecycle from assessment to settled cash
├── transaction_analytics.csv          # Analytical mart: enriched commercial transactions with EUR conversion
├── dim_customers.csv                  # Analytical mart: governed customer dimensions and tiers
├── dim_accounts.csv                   # Analytical mart: governed account dimensions and take-rate tiers
├── fct_fee_collections.csv           # Analytical mart: fee sweep attempts and collection lifecycle
├── revenue_by_segment.csv             # Summary mart: customer segment profitability roll-up
└── test/                              # Preserved sample exports from the small TEST profile
    ├── README.md                      # TEST profile documentation
    └── *.csv                          # Complete snapshot of raw and analytical TEST CSVs
```

---

## 2. Profile Comparison & Summary

| Entity / Metric | DEV Showcase (Root `sample_data/`) | TEST Profile (`sample_data/test/`) | Purpose & Invariants |
| :--- | :--- | :--- | :--- |
| **Profile Name** | `DEV` | `TEST` | Development showcase vs. rapid CI testing |
| **Random Seed** | `42` | `42` | Deterministic PRNG seed across all engines |
| **Reporting Currency** | `EUR` | `EUR` | Base currency for unified reporting and FX |
| **Customers** | 50 | 10 | Retail Wealth, Commercial SME, Institutional |
| **Accounts** | 111 | 24 | Operating, Treasury Sweep, Merchant Settlement |
| **Overdraft Facilities** | 74 | 20 | Authorized credit facilities |
| **Transactions** | 5,000 | 200 | Wires, ACH, Cards, FX conversions |
| **Journals** | 8,273 | 328 | Balanced double-entry journal headers |
| **Ledger Entries** | 19,021 | 770 | Immutable debits and credits ($\sum D = \sum C$) |
| **Fee Assessments** | 3,791 | 148 | Pricing schedules with volume waivers |
| **Fee Collections** | 3,791 | 148 | Sweep attempts (Settled, Partial, Failed) |
| **Revenue Recognitions**| 3,591 | 140 | Recognized net revenue after pass-through |
| **Customer Revenue Mart**| 1,667 rows | 128 rows | Grain: `(reporting_month, customer_id, currency, revenue_category)` |

---

## 3. Reproduction Commands

### Reproducing the DEV Showcase Dataset (`analytics_platform`)
```bash
# 1. Ingest synthetic DEV batch into PostgreSQL raw schema
PYTHONPATH=packages/shared/src:packages/data_platform/src .venv/bin/uv run --env-file .env python -m data_platform.ingestion.run --profile DEV --reset

# 2. Build dbt dimensional marts and execute all 462 data tests
.venv/bin/uv run --env-file .env dbt build --project-dir packages/data_platform/dbt_analytics --profiles-dir /tmp/dbt_profiles --target dev

# 3. Export fresh CSVs to sample_data/
PYTHONPATH=packages/shared/src:packages/data_platform/src .venv/bin/uv run --env-file .env python -m data_platform.ingestion.export_samples
```

### Reproducing the TEST Profile Dataset (`analytics_platform_test`)
```bash
# 1. Integration tests automatically provision and populate analytics_platform_test:
.venv/bin/uv run --env-file .env pytest -q

# 2. (Optional) Build dbt models in the test database:
.venv/bin/uv run --env-file .env dbt build --project-dir packages/data_platform/dbt_analytics --profiles-dir /tmp/dbt_profiles --target test
```
