# Synthetic Banking Sample Data & Analytical Exports

This directory contains independently inspectable CSV exports extracted directly from the live PostgreSQL `raw` schema and the `analytics` dbt dimensional warehouse.

> [!NOTE]
> **Synthetic Data Guarantee**
> Every record in `sample_data/` is 100% synthetic, deterministically generated using `random_seed = 42` (`DEV` profile), and contains zero personal, customer, or confidential employer information.

---

## 1. Reproducible Regeneration Commands

To regenerate the synthetic banking dataset, ingest it into PostgreSQL, build all dbt models, and re-export all CSV files in this directory:

```bash
# 1. Run the deterministic synthetic generator & idempotent PostgreSQL ingestion pipeline
.venv/bin/uv run --env-file .env python -m data_platform.ingestion.run

# 2. Build and test the dbt dimensional warehouse in the analytics schema
.venv/bin/uv run --env-file .env dbt build \
  --project-dir packages/data_platform/dbt_analytics \
  --profiles-dir /tmp/dbt_profiles

# 3. Export raw and transformed analytical CSVs from PostgreSQL
.venv/bin/uv run --env-file .env python -m data_platform.ingestion.export_samples
```

---

## 2. Raw Banking Entity Exports (`raw.*`)

| CSV File | Rows | Grain | Primary Key | Foreign Keys / Relationships | Currency Fields & Conventions |
| :--- | ---: | :--- | :--- | :--- | :--- |
| `gl_accounts.csv` | 14 | One row per General Ledger account | `gl_account_id` | Referenced by `ledger_entries.gl_account_id` | `currency` (ISO 4217 base currency `EUR`) |
| `customers.csv` | 10 | One row per banking customer | `customer_id` | Referenced by `accounts.customer_id` | N/A |
| `accounts.csv` | 24 | One row per customer bank account | `account_id` | `customer_id` -> `customers.customer_id` | `currency` (`EUR`, `USD`, `GBP`); `opening_balance`, `reserved_funds` in `NUMERIC(18,4)` |
| `overdraft_facilities.csv` | 20 | One row per overdraft agreement | `facility_id` | `account_id` -> `accounts.account_id` | `authorized_limit` in linked account `currency` |
| `fx_rates.csv` | 240 | One row per daily currency pair quote (Jan 1–15, 2025 representative window of 5,840 full-year rows) | `rate_id` | Natural key `(rate_date, from_currency, to_currency)` | `from_currency`, `to_currency` (`EUR`, `USD`, `GBP`, `CHF`); `mid_rate`, `bid_rate`, `ask_rate` in `NUMERIC(18,6)` |
| `transactions.csv` | 200 | One row per commercial transaction | `transaction_id` | `account_id` -> `accounts.account_id`; `journal_id` -> `journals.journal_id` | `transaction_currency`, `settlement_currency`; `transaction_amount`, `base_currency_amount` in `NUMERIC(18,4)` |
| `journals.csv` | 328 | One row per accounting journal header | `journal_id` | `transaction_id` -> `transactions.transaction_id` | N/A (header) |
| `ledger_entries.csv` | 770 | One row per double-entry GL posting line | `entry_id` | `journal_id` -> `journals.journal_id`; `gl_account_id` -> `gl_accounts.gl_account_id` | `currency` (`EUR`, `USD`, `GBP`); `amount` in `NUMERIC(18,4)` |
| `fee_assessments.csv` | 148 | One row per transaction fee assessment | `assessment_id` | `transaction_id` -> `transactions.transaction_id`; `account_id` -> `accounts.account_id` | Assessed in linked account `currency`; `gross_assessed_amount`, `waived_amount`, `net_collectible_amount` in `NUMERIC(18,4)` |
| `fee_collections.csv` | 148 | One row per fee collection sweep attempt | `collection_id` | `assessment_id` -> `fee_assessments.assessment_id`; `linked_ledger_entry_id` -> `ledger_entries.entry_id` | Swept in linked account `currency`; `target_amount`, `collected_amount`, `outstanding_amount` in `NUMERIC(18,4)` |
| `revenue_recognitions.csv` | 140 | One row per settled collection revenue entry | `recognition_id` | `collection_id` -> `fee_collections.collection_id` | Recognized in linked account `currency`; `gross_collected_revenue`, `reversed_revenue_amount`, `pass_through_cost`, `net_recognized_revenue` in `NUMERIC(18,4)` |
| `ingestion_batch_manifests.csv` | 2 | One row per ingestion batch run | `batch_id` | Operational audit log | `reporting_base_currency` (`EUR`) |

---

## 3. Transformed Analytical Mart Exports (`analytics.*`)

| CSV File | Rows | Source Mart / Query | Grain | Purpose & Currency Treatment |
| :--- | ---: | :--- | :--- | :--- |
| `customer_revenue.csv` | 128 | `analytics.fct_customer_revenue` | `(customer_id, reporting_month, currency, revenue_category)` | Monthly customer fee and net recognized revenue preserving native `currency` alongside explicit `*_eur` columns. |
| `fee_assessments_analytics.csv` | 148 | `analytics.fct_fee_assessments` | `assessment_id` | End-to-end fee lifecycle reconciling gross assessed, waived, net collectible, collected, outstanding arrears, and net recognized revenue. |
| `transaction_analytics.csv` | 200 | `analytics.fct_transactions` | `transaction_id` | Enriched commercial transactions with customer segment, account attributes, and daily ECB FX conversion to EUR (`transaction_amount_eur`). |
| `revenue_by_segment.csv` | 6 | Aggregated from `analytics.fct_customer_revenue` | `(customer_segment, currency)` | Executive segment summary across `COMMERCIAL_SME`, `INSTITUTIONAL`, and `RETAIL_WEALTH` by native currency and EUR equivalent. |
