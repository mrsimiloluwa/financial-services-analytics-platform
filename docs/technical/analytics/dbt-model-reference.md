# dbt Model Reference

The dbt analytics engineering project resides at `packages/data_platform/dbt_analytics/` (`enterprise_ai_analytics_platform`) and transforms the 12 PostgreSQL `raw` tables into 26 governed analytical models in the `analytics` schema.

---

## 1. Materialisation Strategy & Layer Architecture

| Layer | Directory | Materialisation | Target Schema | Model Count | Design Rationale |
| :--- | :--- | :--- | :--- | ---: | :--- |
| **Sources** | `models/src/` | None (`raw.*`) | `raw` | 12 | Immutable raw banking tables populated by the Phase 1 ingestion pipeline. |
| **Staging** | `models/staging/` | `view` | `analytics` | 12 | 1:1 source normalization, explicit column casting, standardized naming, zero storage duplication. |
| **Intermediate** | `models/intermediate/` | `view` | `analytics` | 5 | Reusable business logic, pre-aggregation of 1:N relationships to prevent join fan-out, and explicit FX rate joins. |
| **Marts (Core)** | `models/marts/core/` | `table` | `analytics` | 5 | Kimball dimensions (`dim_*`) and commercial transaction fact (`fct_transactions`) persisted as physical tables for fast analytical querying. |
| **Marts (Finance)** | `models/marts/finance/` | `table` | `analytics` | 4 | Kimball financial facts (`fct_ledger_entries`, `fct_fee_assessments`, `fct_fee_collections`, `fct_customer_revenue`) persisted as physical tables. |

---

## 2. Complete Model Inventory

### Staging Models (`models/staging/`)

| Model Name | Materialisation | Grain | Source Table | Primary Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `stg_gl_accounts` | `view` | `gl_account_id` (14 rows) | `raw.gl_accounts` | Normalizes Chart of Accounts master records, categories, and normal balance sides. |
| `stg_customers` | `view` | `customer_id` (10 rows) | `raw.customers` | Standardizes customer master profiles, segments, and onboarding dates. |
| `stg_accounts` | `view` | `account_id` (24 rows) | `raw.accounts` | Casts opening and reserved balances to `NUMERIC(18,4)` and computes `initial_available_balance`. |
| `stg_overdraft_facilities` | `view` | `facility_id` (20 rows) | `raw.overdraft_facilities` | Exposes contractual overdraft limits and standard/penalty interest rates. |
| `stg_fx_rates` | `view` | `rate_id` (5,840 rows) | `raw.fx_rates` | Exposes daily `ECB_SYNTH` mid, bid, and ask quotes and computes `bid_ask_spread`. |
| `stg_transactions` | `view` | `transaction_id` (200 rows) | `raw.transactions` | Normalizes commercial transactions, extracts `transaction_date` and `settlement_date`, and flags settled/reversal states. |
| `stg_journals` | `view` | `journal_id` (328 rows) | `raw.journals` | Normalizes balanced double-entry accounting journal headers. |
| `stg_ledger_entries` | `view` | `entry_id` (770 rows) | `raw.ledger_entries` | Splits `amount` into explicit `debit_amount`, `credit_amount`, and `signed_debit_minus_credit` in native currency. |
| `stg_fee_assessments` | `view` | `assessment_id` (148 rows) | `raw.fee_assessments` | Normalizes fee evaluations (`gross_assessed_amount`, `waived_amount`, `net_collectible_amount`). |
| `stg_fee_collections` | `view` | `collection_id` (148 rows) | `raw.fee_collections` | Normalizes fee sweep collection attempts (`target_amount`, `collected_amount`, `outstanding_amount`). |
| `stg_revenue_recognitions` | `view` | `recognition_id` (140 rows) | `raw.revenue_recognitions` | Normalizes collection-based revenue recognition entries (`gross_collected_revenue`, `reversed_revenue_amount`, `pass_through_cost`, `net_recognized_revenue`). |
| `stg_ingestion_batch_manifests` | `view` | `batch_id` (2 rows) | `raw.ingestion_batch_manifests` | Exposes operational batch lineage metadata and entity counts. |

---

### Intermediate Models (`models/intermediate/`)

| Model Name | Materialisation | Grain | Upstream Models | Primary Purpose & Anti-Fanout Design |
| :--- | :--- | :--- | :--- | :--- |
| `int_customer_accounts` | `view` | `account_id` (24 rows) | `stg_customers`, `stg_accounts`, `stg_overdraft_facilities` | Pre-aggregates `stg_overdraft_facilities` by `account_id` before joining to `stg_accounts` and `stg_customers`. |
| `int_transactions_enriched` | `view` | `transaction_id` (200 rows) | `stg_transactions`, `int_customer_accounts`, `stg_fx_rates` | Joins transactions to customer/account context and daily `ECB_SYNTH` FX rates (`to_currency = 'EUR'`) on `transaction_date`. Never defaults missing FX rates to `1.0`. |
| `int_journal_balances` | `view` | `(journal_id, currency)` (366 rows) | `stg_journals`, `stg_ledger_entries` | Aggregates `debit_amount` and `credit_amount` per journal and currency leg to verify double-entry accounting balance (`is_balanced = true`). |
| `int_fee_lifecycle` | `view` | `assessment_id` (148 rows) | `stg_fee_assessments`, `stg_fee_collections`, `stg_revenue_recognitions`, `int_transactions_enriched`, `stg_fx_rates` | Pre-aggregates collection attempts and revenue recognitions to `assessment_id` before joining to assessments, enforcing `net_collectible_amount = collected_amount + outstanding_amount`. |
| `int_customer_revenue` | `view` | `(customer_id, reporting_month, currency, revenue_category)` (128 rows) | `int_fee_lifecycle` | Aggregates assessment-level fee and revenue metrics by customer, month, native currency, and product category alongside explicit EUR equivalents. |

---

### Dimensional Mart Models (`models/marts/core/` & `models/marts/finance/`)

| Model Name | Category | Materialisation | Grain | Row Count | Description |
| :--- | :--- | :--- | :--- | ---: | :--- |
| `dim_customers` | Core Dimension | `table` | `customer_id` | 10 | Master customer attributes, segment, active account count, distinct currencies held, and transaction summary. |
| `dim_accounts` | Core Dimension | `table` | `account_id` | 24 | Bank account attributes, customer reference, opening/reserved balances, overdraft facility limits, and subledger closing balance (`closing_ledger_balance`). |
| `dim_gl_accounts` | Core Dimension | `table` | `gl_account_id` | 14 | General Ledger Chart of Accounts dimension (`account_category`, `normal_balance`, `default_currency`). |
| `dim_date` | Core Dimension | `table` | `date_day` | 365 | Calendar date dimension (2025-01-01 to 2025-12-31) with year, quarter, month, ISO day of week, and weekend flag. |
| `fct_transactions` | Core Fact | `table` | `transaction_id` | 200 | Commercial transaction fact table preserving native `transaction_currency` and `transaction_amount` alongside `transaction_amount_eur`. |
| `fct_ledger_entries` | Finance Fact | `table` | `entry_id` | 770 | Double-entry GL posting fact table with separate `debit_amount` and `credit_amount` in native currency and EUR (`debit_amount_eur`, `credit_amount_eur`). |
| `fct_fee_assessments` | Finance Fact | `table` | `assessment_id` | 148 | Assessment-grain fee lifecycle fact table distinguishing gross assessed, waived, net collectible, collected, outstanding arrears, reversed, pass-through cost, and net recognized revenue. |
| `fct_fee_collections` | Finance Fact | `table` | `collection_id` | 148 | Collection-attempt-grain fact table tracking sweep target, collected, and outstanding amounts, failure reasons, ledger posting link, and revenue recognition. |
| `fct_customer_revenue` | Finance Fact | `table` | `customer_revenue_id` (`customer_id\|YYYY-MM\|currency\|revenue_category`) | 128 | Governed customer revenue and fee performance mart with `fee_collection_rate`, `fee_waiver_rate`, and `total_fee_leakage_rate`. |
