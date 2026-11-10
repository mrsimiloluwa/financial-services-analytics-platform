# Governed Financial Metric Catalogue

This catalogue establishes the single source of truth for financial, fee lifecycle, and commercial transaction metrics across the **Enterprise AI Analytics Platform**.

> [!IMPORTANT]
> **Governance Rules**
> 1. **Currency Integrity:** Native currency amounts (`EUR`, `USD`, `GBP`, `CHF`) are **never** summed across different currencies. Multi-currency aggregations must either group by `currency` or sum the explicitly converted `*_eur` columns.
> 2. **Fee Lifecycle Separation:** Gross assessed fees, waived fees, net collectible fees, collected fees, outstanding arrears, reversed revenue, pass-through costs, and net recognized revenue are distinct financial concepts and must never be treated as interchangeable.
> 3. **AI SQL Boundary:** Downstream AI agents and analytical applications must reference these governed definitions and mart models rather than redefining calculations ad hoc.

---

## Summary Matrix

| Metric ID | Metric Name | Primary Source Model | Native Formula | EUR Reporting Column |
| :--- | :--- | :--- | :--- | :--- |
| `MET-01` | **Gross Assessed Fees** | `analytics.fct_fee_assessments` | `SUM(gross_assessed_amount)` | `SUM(gross_assessed_amount_eur)` |
| `MET-02` | **Waived Fees** | `analytics.fct_fee_assessments` | `SUM(waived_amount)` | `SUM(waived_amount_eur)` |
| `MET-03` | **Net Collectible Fees** | `analytics.fct_fee_assessments` | `SUM(net_collectible_amount)` | `SUM(net_collectible_amount_eur)` |
| `MET-04` | **Collected Fees** | `analytics.fct_fee_assessments` | `SUM(collected_amount)` | `SUM(collected_amount_eur)` |
| `MET-05` | **Outstanding Fees (Arrears)** | `analytics.fct_fee_assessments` | `SUM(outstanding_amount)` | `SUM(outstanding_amount_eur)` |
| `MET-06` | **Reversed Fee Revenue** | `analytics.fct_fee_assessments` | `SUM(reversed_amount)` | `SUM(reversed_amount_eur)` |
| `MET-07` | **Pass-Through Costs** | `analytics.fct_fee_assessments` | `SUM(pass_through_cost)` | `SUM(pass_through_cost_eur)` |
| `MET-08` | **Net Recognised Revenue** | `analytics.fct_customer_revenue` | `SUM(net_recognized_revenue)` | `SUM(net_recognized_revenue_eur)` |
| `MET-09` | **Eligible Transaction Volume** | `analytics.fct_transactions` | `COUNT(transaction_id)` (`SETTLED`) | N/A (Count) |
| `MET-10` | **Settled Transaction Value** | `analytics.fct_transactions` | `SUM(transaction_amount)` | `SUM(transaction_amount_eur)` |
| `MET-11` | **Average Transaction Value** | `analytics.fct_transactions` | `AVG(transaction_amount)` | `AVG(transaction_amount_eur)` |
| `MET-12` | **Average Fee per Transaction** | `analytics.fct_fee_assessments` | `SUM(gross_assessed_amount) / COUNT(assessment_id)` | `SUM(gross_assessed_amount_eur) / COUNT(assessment_id)` |
| `MET-13` | **Fee Collection Rate** | `analytics.fct_customer_revenue` | `SUM(collected_fee_amount) / NULLIF(SUM(net_collectible_fee_amount), 0)` | Ratio (Currency-Invariant per Currency) |
| `MET-14` | **Fee Waiver Rate** | `analytics.fct_customer_revenue` | `SUM(waived_fee_amount) / NULLIF(SUM(gross_assessed_fee_amount), 0)` | Ratio |
| `MET-15` | **Total Fee Leakage Rate** | `analytics.fct_customer_revenue` | `SUM(waived_fee_amount + outstanding_fee_amount) / NULLIF(SUM(gross_assessed_fee_amount), 0)` | Ratio |
| `MET-16` | **Customer Net Revenue** | `analytics.fct_customer_revenue` | `SUM(net_recognized_revenue)` grouped by `customer_id, currency` | `SUM(net_recognized_revenue_eur)` grouped by `customer_id` |
| `MET-17` | **Revenue by Segment** | `analytics.fct_customer_revenue` | `SUM(net_recognized_revenue)` grouped by `customer_segment, currency` | `SUM(net_recognized_revenue_eur)` grouped by `customer_segment` |
| `MET-18` | **Revenue by Transaction Type** | `analytics.fct_customer_revenue` | `SUM(net_recognized_revenue)` grouped by `revenue_category, currency` | `SUM(net_recognized_revenue_eur)` grouped by `revenue_category` |

---

## Detailed Metric Specifications

### 1. Gross Assessed Fees (`MET-01`)
- **Business Definition:** Total contractual fees evaluated on eligible settled transactions before applying commercial or tier-based fee waivers.
- **Exact Formula:** `SUM(gross_assessed_amount)` by `currency`, or `SUM(gross_assessed_amount_eur)` in EUR reporting currency.
- **Source Model:** `analytics.fct_fee_assessments` (or `analytics.fct_customer_revenue`).
- **Grain:** Assessment level (`assessment_id`) or monthly customer-category grain (`customer_revenue_id`).
- **Currency Treatment:** Evaluated in the account/transaction native currency (`EUR`, `USD`, `GBP`, `CHF`). Converted to `EUR` using the daily `ECB_SYNTH` mid-rate on `assessed_date`.
- **Date Field Used:** `assessed_date` (or `reporting_month`).
- **Treatment of Failed/Pending Transactions:** Excluded (`FAILED` and `PENDING` transactions do not trigger fee assessments).
- **Treatment of Waivers:** Included prior to deduction (`gross_assessed_amount = waived_amount + net_collectible_amount`).
- **Treatment of Partial Collections & Reversals:** Unaffected; reflects initial contractual fee calculation.
- **Known Limitations:** Synthetic pricing schedules evaluate flat base fees plus basis points in native currency without multi-tier monthly retro-rebates.

### 2. Waived Fees (`MET-02`)
- **Business Definition:** Portion of gross assessed fees foregone by the bank due to contractual relationship discounts, promotional waivers, or volume tier concessions.
- **Exact Formula:** `SUM(waived_amount)` by `currency`, or `SUM(waived_amount_eur)` in EUR.
- **Source Model:** `analytics.fct_fee_assessments`.
- **Grain:** Assessment level (`assessment_id`).
- **Currency Treatment:** Native `currency` or explicitly converted `waived_amount_eur`.
- **Date Field Used:** `assessed_date`.
- **Treatment of Failed Transactions:** Excluded.
- **Treatment of Waivers:** Captures both `PARTIALLY_WAIVED` and `WAIVED_IN_FULL` assessments.
- **Treatment of Partial Collections & Reversals:** Waived fees are never billed or collected.
- **Known Limitations:** Waiver reason codes are synthetic descriptors (`Commercial relationship tier partial waiver`).

### 3. Net Collectible Fees (`MET-03`)
- **Business Definition:** Net contractual fee amount due from the customer after deducting commercial waivers from gross assessed fees.
- **Exact Formula:** `SUM(net_collectible_amount)` where `net_collectible_amount = gross_assessed_amount - waived_amount`.
- **Source Model:** `analytics.fct_fee_assessments`.
- **Grain:** Assessment level (`assessment_id`).
- **Currency Treatment:** Native `currency` or `net_collectible_amount_eur`.
- **Date Field Used:** `assessed_date`.
- **Treatment of Failed Transactions:** Excluded.
- **Treatment of Waivers:** Net of waivers.
- **Treatment of Partial Collections:** Represents the ceiling that collection sweeps may collect (`collected_amount + outstanding_amount = net_collectible_amount`).
- **Treatment of Reversals:** Unchanged by post-collection reversals.
- **Known Limitations:** Assumes synchronous assessment at transaction settlement.

### 4. Collected Fees (`MET-04`)
- **Business Definition:** Total fee cash successfully swept from customer subledger accounts into bank fee revenue accounts.
- **Exact Formula:** `SUM(collected_amount)` by `currency`, or `SUM(collected_amount_eur)` in EUR.
- **Source Model:** `analytics.fct_fee_assessments` (assessment-level roll-up) or `analytics.fct_fee_collections` (attempt-level grain).
- **Grain:** `assessment_id` or `collection_id`.
- **Currency Treatment:** Native `currency` or `collected_amount_eur`.
- **Date Field Used:** `assessed_date` (on `fct_fee_assessments`) or `attempted_date` / `settled_date` (on `fct_fee_collections`).
- **Treatment of Failed Transactions:** Excluded.
- **Treatment of Waivers:** Waived amounts are excluded before collection targets are set.
- **Treatment of Partial Collections:** Includes settled and partial sweep amounts; failed sweeps contribute `0.0000`.
- **Treatment of Reversals:** Gross collected cash prior to any subsequent revenue reversal.
- **Known Limitations:** Collection attempts in the current DEV dataset execute as a single sweep attempt (`collection_attempt_number = 1`).

### 5. Outstanding Fees / Uncollected Arrears (`MET-05`)
- **Business Definition:** Collectible fee balance remaining unpaid after collection sweep attempts fail (e.g., due to `INSUFFICIENT_FUNDS` or `ACCOUNT_FROZEN`).
- **Exact Formula:** `SUM(outstanding_amount)` where `outstanding_amount = net_collectible_amount - collected_amount`.
- **Source Model:** `analytics.fct_fee_assessments`.
- **Grain:** `assessment_id`.
- **Currency Treatment:** Native `currency` or `outstanding_amount_eur`.
- **Date Field Used:** `assessed_date`.
- **Treatment of Failed Collection Attempts:** Directly captures operational revenue leakage from failed collection sweeps.
- **Known Limitations:** Does not model aging buckets (30/60/90 days past due) or bad-debt write-offs.

### 6. Reversed Fee Revenue (`MET-06`)
- **Business Definition:** Previously collected fee revenue refunded or reversed back to the customer.
- **Exact Formula:** `SUM(reversed_amount)` (on `fct_fee_assessments`) or `SUM(reversed_revenue_amount)` (on `fct_customer_revenue`).
- **Source Model:** `analytics.fct_fee_assessments` / `analytics.fct_customer_revenue`.
- **Grain:** `assessment_id` or `customer_revenue_id`.
- **Currency Treatment:** Native `currency` or `reversed_amount_eur`.
- **Date Field Used:** `assessed_date` / `recognized_date`.
- **Treatment of Reversals:** Deducted from `gross_collected_revenue` when computing `net_recognized_revenue`.
- **Known Limitations:** Synthetic DEV dataset has `0.0000` reversed fee revenue on settled fee collections (while transaction reversals are tested in ledger entries).

### 7. Net Recognised Revenue (`MET-08`)
- **Business Definition:** Authoritative bottom-line fee revenue recognised by the bank after deducting fee reversals and direct network/interchange pass-through costs from gross collected fees.
- **Exact Formula:**
  $$\text{Net Recognised Revenue} = \text{Gross Collected Revenue} - \text{Reversed Revenue} - \text{Pass-Through Cost}$$
- **Source Model:** `analytics.fct_customer_revenue` / `analytics.fct_fee_assessments`.
- **Grain:** `customer_revenue_id` or `assessment_id`.
- **Currency Treatment:** Native `currency` (`net_recognized_revenue`) or EUR (`net_recognized_revenue_eur`).
- **Date Field Used:** `reporting_month` / `assessed_date` / `recognized_date`.
- **Treatment of Failed Collections:** Failed collection attempts (`collection_status = 'FAILED'`) generate zero recognized revenue.
- **Known Limitations:** Uses cash-collection-based revenue recognition rather than IFRS 15 multi-period accrual accounting.

### 8. Transaction Volume (`MET-09`), Value (`MET-10`), and Average Value (`MET-11`)
- **Business Definition:** Count, total principal amount, and mean principal amount of commercial transactions, segmented by `transaction_status` (`SETTLED`, `PENDING`, `REVERSED`, `FAILED`).
- **Exact Formula:**
  - Volume: `COUNT(transaction_id)`
  - Value (Native): `SUM(transaction_amount)` grouped by `transaction_currency`
  - Value (EUR): `SUM(transaction_amount_eur)`
  - Average Value (EUR): `AVG(transaction_amount_eur)`
- **Source Model:** `analytics.fct_transactions`.
- **Grain:** `transaction_id`.
- **Currency Treatment:** Never sum `transaction_amount` across currencies; use `transaction_amount_eur` for cross-currency totals.
- **Date Field Used:** `transaction_date` (`initiated_at::date`).
- **Treatment of Failed/Pending/Reversed Transactions:** Filter on `transaction_status = 'SETTLED'` for settled commercial volume, or inspect all statuses for operational funnel analysis.

### 9. Fee Collection Rate (`MET-13`) and Fee Leakage Indicators (`MET-14`, `MET-15`)
- **Business Definition:**
  - **Fee Collection Rate (`MET-13`):** Percentage of net collectible fees successfully swept into cash (`SUM(collected_amount) / NULLIF(SUM(net_collectible_amount), 0)`).
  - **Commercial Waiver Rate (`MET-14`):** Percentage of gross assessed fees conceded via waivers (`SUM(waived_amount) / NULLIF(SUM(gross_assessed_amount), 0)`).
  - **Total Fee Leakage Rate (`MET-15`):** Combined share of gross assessed fees lost to commercial waivers plus operational collection failures (`SUM(waived_amount + outstanding_amount) / NULLIF(SUM(gross_assessed_amount), 0)`).
- **Source Model:** `analytics.fct_fee_assessments` / `analytics.fct_customer_revenue`.
- **Currency Treatment:** Computed per native currency or using EUR-converted numerator and denominator.
