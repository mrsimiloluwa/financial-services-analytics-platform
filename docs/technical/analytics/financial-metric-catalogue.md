# Governed Financial Metric Catalogue

## 1. Overview & Semantic Principles

Financial metrics in the Financial Services Analytics & AI Platform are strictly governed by explicit algebraic definitions, dimensional grains, and currency conversion rules.

LLMs, autonomous agents, and business dashboards are **prohibited from inventing ad-hoc formulas** or calculating financial totals without adhering to this certified catalogue.

### Currency Rules:
- **Native Currency Aggregation**: Multi-currency amounts (`EUR`, `USD`, `GBP`, `CHF`) must NEVER be summed together without grouping by currency.
- **Reporting Currency Conversion**: For cross-currency portfolio comparisons, queries MUST use the explicit `_eur` reporting columns (e.g. `transaction_amount_eur`, `net_recognized_revenue_eur`) which use synthetic daily mid-market FX rates (`ECB_SYNTH`).
- **Precision**: Monetary calculations use `numeric(18,4)` to prevent IEEE 754 floating-point inaccuracies.

---

## 2. Master Governed Financial Metrics Reference

| Metric ID | Metric Name | Business Definition | Governed Formula | Source Model | Grain | Date Field |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `gross_transaction_volume` | Gross Transaction Volume | Total commercial payments principal amount initiated before applying reversals. | `SUM(transaction_amount_eur)` | `fct_transactions` | `transaction_id` | `transaction_date` |
| `net_transaction_volume` | Net Transaction Volume | Settled and pending payments principal volume excluding reversed and failed movements. | `SUM(CASE WHEN transaction_status NOT IN ('REVERSED', 'FAILED') THEN transaction_amount_eur ELSE 0 END)` | `fct_transactions` | `transaction_id` | `transaction_date` |
| `reversal_rate` | Transaction Reversal Rate | Proportion of initiated transactions reversed due to disputes or cancellations. | `COUNT(*) FILTER (WHERE transaction_status = 'REVERSED')::float / NULLIF(COUNT(*), 0)` | `fct_transactions` | `transaction_id` | `transaction_date` |
| `assessed_fees` | Gross Assessed Fees | Gross contractual fee revenue calculated on transactions before discretionary waivers. | `SUM(gross_assessed_amount)` | `fct_fee_assessments` | `assessment_id` | `assessed_date` |
| `waived_fees` | Waived Fees | Total monetary value of contractual fees waived by relationship managers or promotions. | `SUM(waived_amount)` | `fct_fee_assessments` | `assessment_id` | `assessed_date` |
| `collected_fees` | Collected Fees | Total monetary value of fees successfully settled and swept from customer accounts. | `SUM(collected_amount)` | `fct_fee_assessments` | `assessment_id` | `assessed_date` |
| `fee_collection_rate` | Fee Collection Rate | Percentage of net collectible fees successfully collected into bank cash accounts. | `SUM(collected_amount_eur) / NULLIF(SUM(net_collectible_amount_eur), 0)` | `fct_fee_assessments` | `assessment_id` | `assessed_date` |
| `recognized_revenue` | Recognized Revenue | Governed earned banking fee revenue recognized under accrual principles. | `SUM(net_recognized_revenue_eur)` | `fct_customer_revenue` | `(customer, month, curr, category)` | `reporting_month` |
| `net_customer_profitability` | Net Customer Fee Contribution Margin | Net fee revenue earned from a commercial relationship after deducting waivers, reversals, and pass-through costs. | `SUM(net_recognized_revenue_eur)` | `fct_customer_revenue` | `(customer, month, curr, category)` | `reporting_month` |
| `average_customer_daily_balance` | Average Customer Ledger Balance | Average subledger closing balance across operating and treasury bank accounts. | `AVG(closing_ledger_balance)` | `dim_accounts` | `account_id` | `opened_date` |
| `billing_exception_rate` | Billing Exception & Arrears Rate | Proportion of fee assessments resulting in uncollected arrears or collection failures. | `COUNT(*) FILTER (WHERE outstanding_amount > 0)::float / NULLIF(COUNT(*), 0)` | `fct_fee_assessments` | `assessment_id` | `assessed_date` |
| `effective_take_rate` | Effective Fee Realization Rate | Net fee revenue earned as a percentage of gross assessed fees after waivers and arrears. | `SUM(net_recognized_revenue_eur) / NULLIF(SUM(gross_assessed_fee_amount_eur), 0)` | `fct_customer_revenue` | `(customer, month, curr, category)` | `reporting_month` |

---

## 3. Representative SQL Queries

### Query 1: Monthly Recognized Revenue by Commercial Customer Segment
```sql
SELECT
    c.customer_segment,
    r.reporting_month,
    SUM(r.net_recognized_revenue_eur) AS recognized_revenue_eur
FROM analytics.fct_customer_revenue r
JOIN analytics.dim_customers c ON r.customer_id = c.customer_id
GROUP BY c.customer_segment, r.reporting_month
ORDER BY r.reporting_month, recognized_revenue_eur DESC;
```

### Query 2: Fee Concessions & Realization Rate by Fee Type
```sql
SELECT
    fa.fee_type,
    fa.currency,
    SUM(fa.gross_assessed_amount) AS total_assessed,
    SUM(fa.waived_amount) AS total_waived,
    SUM(fa.collected_amount) AS total_collected,
    ROUND(
        (SUM(fa.collected_amount) / NULLIF(SUM(fa.net_collectible_amount), 0) * 100)::numeric,
        2
    ) AS collection_realization_pct
FROM analytics.fct_fee_assessments fa
GROUP BY fa.fee_type, fa.currency
ORDER BY total_assessed DESC;
```
