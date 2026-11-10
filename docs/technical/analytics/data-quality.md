# Financial Data Quality & Testing Framework

Data quality in the **Enterprise AI Analytics Platform** is enforced through **461 automated dbt tests** combining schema-level generic assertions and 11 singular financial SQL invariant tests.

---

## 1. Execution Summary (`dbt build`)

- **Total Nodes Executed:** 487 (26 models + 461 data tests)
- **Generic Schema Tests:** 450 (`unique`, `not_null`, `relationships`, `accepted_values`)
- **Singular Financial Invariant Tests:** 11
- **Execution Result:** `PASS=487 WARN=0 ERROR=0 SKIP=0`

---

## 2. Singular Financial Invariant Tests (`packages/data_platform/dbt_analytics/tests/`)

Every singular test is written as a SQL query that returns violating rows. A return count of `0 rows` indicates the invariant holds across the warehouse.

| Test File | Financial Invariant Enforced | Target Models | Result |
| :--- | :--- | :--- | :--- |
| `assert_journal_balanced_per_currency.sql` | $\sum \text{Debit} = \sum \text{Credit}$ independently for every `(journal_id, currency)` pair. | `fct_ledger_entries` | `PASS` (0 violations) |
| `assert_no_ledger_postings_for_unsettled_txns.sql` | `FAILED` and `PENDING` transactions never produce General Ledger postings. | `fct_transactions`, `fct_ledger_entries` | `PASS` (0 violations) |
| `assert_fee_assessment_decomposition.sql` | $\text{Gross Assessed} = \text{Waived} + \text{Net Collectible}$, with all components $\ge 0$. | `fct_fee_assessments` | `PASS` (0 violations) |
| `assert_collection_attempt_balance.sql` | $\text{Target Amount} = \text{Collected Amount} + \text{Outstanding Amount}$, and `SETTLED` attempts have `outstanding_amount = 0.0000`. | `fct_fee_collections` | `PASS` (0 violations) |
| `assert_no_assessment_overcollection.sql` | Cumulative `collected_amount` per assessment never exceeds `net_collectible_amount`, and $\text{Net Collectible} = \text{Collected} + \text{Outstanding}$. | `fct_fee_assessments` | `PASS` (0 violations) |
| `assert_reversal_within_original_amount.sql` | Reversed revenue never exceeds gross collected revenue, and reversal ledger entries never exceed their original entry amount. | `stg_revenue_recognitions`, `fct_ledger_entries` | `PASS` (0 violations) |
| `assert_failed_collections_zero_revenue.sql` | `FAILED` collection attempts never record positive collected cash, recognized revenue, or ledger postings. | `fct_fee_collections` | `PASS` (0 violations) |
| `assert_fx_rate_spread_ordering.sql` | $0 < \text{Bid Rate} \le \text{Mid Rate} \le \text{Ask Rate}$, and identity currency pairs equal `1.000000`. | `stg_fx_rates` | `PASS` (0 violations) |
| `assert_no_missing_fx_rates_in_marts.sql` | All fact rows have a valid, non-null, positive EUR conversion rate, and non-EUR records never default to `1.000000`. | `fct_transactions`, `fct_ledger_entries`, `fct_fee_assessments`, `fct_fee_collections` | `PASS` (0 violations) |
| `assert_revenue_recognition_equation.sql` | $\text{Net Recognized Revenue} = \text{Gross Collected Revenue} - \text{Reversed Revenue} - \text{Pass-Through Cost}$ across all fee and revenue marts. | `fct_fee_assessments`, `fct_fee_collections`, `fct_customer_revenue` | `PASS` (0 violations) |
| `assert_no_customer_revenue_fanout.sql` | Summing `fct_customer_revenue` by currency matches `fct_fee_assessments` to 4 decimal places across all fee and revenue columns, proving zero join fan-out. | `fct_customer_revenue`, `fct_fee_assessments` | `PASS` (0 violations) |

---

## 3. Generic Test Coverage by Layer

| Layer | `unique` | `not_null` | `relationships` | `accepted_values` | Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Raw Sources (`raw.*`)** | Primary & natural keys across all 12 tables | All required columns | Foreign keys (`accounts` -> `customers`, `transactions` -> `accounts`, `ledger_entries` -> `journals` & `gl_accounts`, `fee_assessments` -> `transactions`, `fee_collections` -> `fee_assessments`, `revenue_recognitions` -> `fee_collections`) | Currencies, statuses, segments, categories, directions | Guards source integrity before transformations run. |
| **Staging (`stg_*`)** | Primary keys on all 12 views | Primary keys, foreign keys, monetary amounts | Referential links across staging views | Normalized uppercase enums | Verifies type casting and string normalization. |
| **Intermediate (`int_*`)** | Grain keys (`account_id`, `transaction_id`, `assessment_id`) | Monetary columns, FX rates, `is_balanced` | Customer, account, journal, and transaction FKs | `is_balanced = [true]`, currencies, segments | Verifies pre-aggregation and FX join completeness. |
| **Marts (`dim_*`, `fct_*`)** | Surrogate/natural keys (`customer_id`, `account_id`, `gl_account_id`, `date_day`, `transaction_id`, `entry_id`, `assessment_id`, `collection_id`, `customer_revenue_id`) | All dimensional keys, native amounts, EUR amounts, FX rates | Full Kimball star-schema referential integrity (`fct_*` -> `dim_*`) | Currencies, transaction types, statuses, entry types | Certifies business-facing analytical tables. |
