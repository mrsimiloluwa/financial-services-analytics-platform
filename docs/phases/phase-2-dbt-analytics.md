# Phase 2: Analytics Engineering — dbt Dimensional Modelling & Governed Metrics

## 1. Executive Summary

Phase 2 implements the complete **dbt Core 1.12.6 (`dbt-postgres` 1.11.0)** dimensional analytics warehouse at `packages/data_platform/dbt_analytics/`. It transforms the 12 raw PostgreSQL banking tables (`raw.*`) into 26 governed models (12 staging views, 5 intermediate views, 4 core dimensions, and 5 fact tables) in the `analytics` schema, backed by **461 automated data quality tests** (`PASS=487 WARN=0 ERROR=0 SKIP=0`).

---

## 2. Project Structure

```text
packages/data_platform/dbt_analytics/
├── .gitignore
├── dbt_project.yml
├── analyses/
├── macros/
├── seeds/
├── models/
│   ├── src/
│   │   └── raw_sources.yml
│   ├── staging/
│   │   ├── _staging__models.yml
│   │   ├── stg_accounts.sql
│   │   ├── stg_customers.sql
│   │   ├── stg_fee_assessments.sql
│   │   ├── stg_fee_collections.sql
│   │   ├── stg_fx_rates.sql
│   │   ├── stg_gl_accounts.sql
│   │   ├── stg_ingestion_batch_manifests.sql
│   │   ├── stg_journals.sql
│   │   ├── stg_ledger_entries.sql
│   │   ├── stg_overdraft_facilities.sql
│   │   ├── stg_revenue_recognitions.sql
│   │   └── stg_transactions.sql
│   ├── intermediate/
│   │   ├── _intermediate__models.yml
│   │   ├── int_customer_accounts.sql
│   │   ├── int_customer_revenue.sql
│   │   ├── int_fee_lifecycle.sql
│   │   ├── int_journal_balances.sql
│   │   └── int_transactions_enriched.sql
│   └── marts/
│       ├── core/
│       │   ├── _core_marts__models.yml
│       │   ├── dim_accounts.sql
│       │   ├── dim_customers.sql
│       │   ├── dim_date.sql
│       │   ├── dim_gl_accounts.sql
│       │   └── fct_transactions.sql
│       └── finance/
│           ├── _finance_marts__models.yml
│           ├── fct_customer_revenue.sql
│           ├── fct_fee_assessments.sql
│           ├── fct_fee_collections.sql
│           └── fct_ledger_entries.sql
└── tests/
    ├── assert_collection_attempt_balance.sql
    ├── assert_failed_collections_zero_revenue.sql
    ├── assert_fee_assessment_decomposition.sql
    ├── assert_fx_rate_spread_ordering.sql
    ├── assert_journal_balanced_per_currency.sql
    ├── assert_no_assessment_overcollection.sql
    ├── assert_no_customer_revenue_fanout.sql
    ├── assert_no_ledger_postings_for_unsettled_txns.sql
    ├── assert_no_missing_fx_rates_in_marts.sql
    ├── assert_revenue_recognition_equation.sql
    └── assert_reversal_within_original_amount.sql
```

---

## 3. Architectural & Modelling Decisions

1. **Strict Separation of Native vs. Reporting Currencies:** Every financial model preserves the original transaction/account currency (`EUR`, `USD`, `GBP`, `CHF`) and never sums disparate currencies together. Where cross-currency reporting is needed, models join `stg_fx_rates` on the effective business date (`to_currency = 'EUR'`) to compute explicit `*_eur` columns using `NUMERIC(18, 4)` arithmetic. Missing FX rates are never defaulted to `1.0` and are guarded by `assert_no_missing_fx_rates_in_marts.sql`.
2. **Fan-Out Prevention via Intermediate Pre-Aggregation:**
   - `int_customer_accounts` pre-aggregates `stg_overdraft_facilities` by `account_id` before joining to `stg_accounts`.
   - `int_fee_lifecycle` joins `stg_fee_collections` to `stg_revenue_recognitions` at `collection_id` grain and pre-aggregates to `assessment_id` before joining to `stg_fee_assessments`.
   - `assert_no_customer_revenue_fanout.sql` mathematically verifies that `fct_customer_revenue` sums match `fct_fee_assessments` across every currency to `0.0000` tolerance.
3. **Collection-Based Revenue Recognition:** Following the Phase 1 accounting baseline, fee revenue is recognized upon successful cash collection (`collection_status IN ('SETTLED', 'PARTIAL')`), with direct pass-through costs and reversals deducted to arrive at `net_recognized_revenue`.

---

## 4. Actual Execution Commands & Outputs

```bash
# 1. Verify database connection
.venv/bin/uv run --no-sync --env-file .env dbt debug \
  --project-dir packages/data_platform/dbt_analytics \
  --profiles-dir /tmp/dbt_profiles

# 2. Build all 26 models and run all 461 data tests
.venv/bin/uv run --no-sync --env-file .env dbt build \
  --project-dir packages/data_platform/dbt_analytics \
  --profiles-dir /tmp/dbt_profiles

# 3. Generate dbt catalog and lineage manifest
.venv/bin/uv run --no-sync --env-file .env dbt docs generate \
  --project-dir packages/data_platform/dbt_analytics \
  --profiles-dir /tmp/dbt_profiles
```

### Actual Query Results from Built Marts (`analytics.*`)

#### Revenue by Customer Segment (`analytics.fct_customer_revenue`)

| Customer Segment | Customers | Assessments | Gross Assessed (EUR) | Waived (EUR) | Net Collectible (EUR) | Collected (EUR) | Outstanding Arrears (EUR) | Net Recognized Revenue (EUR) | Collection Rate (%) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `COMMERCIAL_SME` | 6 | 104 | 13,377.7863 | 35.9028 | 13,341.8835 | 13,205.0181 | 136.8654 | 12,544.7672 | 98.97% |
| `INSTITUTIONAL` | 2 | 21 | 4,852.4063 | 64.3476 | 4,788.0587 | 4,788.0587 | 0.0000 | 4,548.6556 | 100.00% |
| `RETAIL_WEALTH` | 2 | 23 | 363.7705 | 7.0434 | 356.7271 | 316.8145 | 39.9126 | 300.9738 | 88.81% |

#### Multi-Currency Revenue Reconciliation (`analytics.fct_customer_revenue`)

| Native Currency | Assessments | Gross Assessed (Native) | Net Revenue (Native) | Effective Weighted EUR FX Rate | Gross Assessed (EUR) | Net Recognized Revenue (EUR) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| `EUR` | 106 | 14,283.3335 | 13,432.0823 | 1.000000 | 14,283.3335 | 13,432.0823 |
| `USD` | 34 | 3,679.2060 | 3,350.4303 | 0.912842 | 3,358.5623 | 3,058.4144 |
| `GBP` | 8 | 803.1930 | 762.5584 | 1.185352 | 952.0673 | 903.8999 |

---

## 5. Known Limitations & Future Work

- **Collection-Based Recognition:** The platform uses cash-collection-based fee revenue recognition rather than multi-period IFRS 15 accrual accounting.
- **Single-Attempt Collection Simulation:** In the current synthetic DEV dataset, fee collections execute a single sweep attempt (`collection_attempt_number = 1`). The dbt intermediate and mart models (`int_fee_lifecycle`, `fct_fee_assessments`, `fct_fee_collections`) are engineered to handle multi-attempt retries without fan-out.
- **Static Dimension Attributes:** Customer segments and account statuses are modelled as Type 1 dimensions because the raw schema does not store historical SCD2 effective-date change logs for customer/account attributes.
