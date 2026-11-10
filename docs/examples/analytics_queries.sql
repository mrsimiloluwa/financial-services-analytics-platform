-- =============================================================================
-- GOVERNED ANALYTICAL SQL QUERIES — ENTERPRISE AI ANALYTICS PLATFORM
-- Target Schema: analytics (built via dbt Core)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Monthly Fee Revenue (Native Currency and Explicit EUR Reporting Equivalent)
-- Business Question: How much gross assessed fee, waived fee, collected fee,
-- and net recognized revenue did the bank generate each month?
-- -----------------------------------------------------------------------------
SELECT
    year_month,
    currency,
    SUM(assessment_count) AS total_assessments,
    SUM(gross_assessed_fee_amount) AS gross_assessed_native,
    SUM(waived_fee_amount) AS waived_native,
    SUM(net_collectible_fee_amount) AS net_collectible_native,
    SUM(collected_fee_amount) AS collected_native,
    SUM(outstanding_fee_amount) AS outstanding_native,
    SUM(net_recognized_revenue) AS net_revenue_native,
    SUM(net_recognized_revenue_eur) AS net_revenue_eur
FROM analytics.fct_customer_revenue
GROUP BY year_month, currency
ORDER BY year_month, currency;

-- -----------------------------------------------------------------------------
-- 2. Highest-Revenue Customers (EUR Reporting Currency)
-- Business Question: Which customers generate the highest net recognized fee
-- revenue in EUR across all accounts and currencies?
-- -----------------------------------------------------------------------------
SELECT
    customer_id,
    customer_name,
    customer_segment,
    SUM(assessment_count) AS fee_assessments_count,
    SUM(gross_assessed_fee_amount_eur) AS gross_assessed_eur,
    SUM(waived_fee_amount_eur) AS waived_eur,
    SUM(collected_fee_amount_eur) AS collected_eur,
    SUM(outstanding_fee_amount_eur) AS outstanding_eur,
    SUM(pass_through_cost_amount_eur) AS pass_through_cost_eur,
    SUM(net_recognized_revenue_eur) AS net_recognized_revenue_eur
FROM analytics.fct_customer_revenue
GROUP BY customer_id, customer_name, customer_segment
ORDER BY net_recognized_revenue_eur DESC;

-- -----------------------------------------------------------------------------
-- 3. Revenue by Customer Segment
-- Business Question: How does fee revenue, waiver concession, and collection
-- performance compare across INSTITUTIONAL, COMMERCIAL_SME, and RETAIL_WEALTH?
-- -----------------------------------------------------------------------------
SELECT
    customer_segment,
    COUNT(DISTINCT customer_id) AS customer_count,
    SUM(assessment_count) AS assessment_count,
    SUM(gross_assessed_fee_amount_eur) AS gross_assessed_eur,
    SUM(waived_fee_amount_eur) AS waived_eur,
    SUM(net_collectible_fee_amount_eur) AS net_collectible_eur,
    SUM(collected_fee_amount_eur) AS collected_eur,
    SUM(outstanding_fee_amount_eur) AS outstanding_eur,
    SUM(net_recognized_revenue_eur) AS net_recognized_revenue_eur,
    ROUND(
        SUM(collected_fee_amount_eur) / NULLIF(SUM(net_collectible_fee_amount_eur), 0) * 100,
        2
    ) AS collection_rate_pct
FROM analytics.fct_customer_revenue
GROUP BY customer_segment
ORDER BY net_recognized_revenue_eur DESC;

-- -----------------------------------------------------------------------------
-- 4. Fee Leakage and Outstanding Collections Analysis
-- Business Question: How much potential fee revenue is lost to commercial
-- waivers versus failed collection sweeps (operational arrears)?
-- -----------------------------------------------------------------------------
SELECT
    fee_type,
    currency,
    COUNT(assessment_id) AS assessment_count,
    SUM(gross_assessed_amount) AS gross_assessed_native,
    SUM(waived_amount) AS commercial_waiver_leakage_native,
    SUM(outstanding_amount) AS uncollected_arrears_leakage_native,
    SUM(waived_amount + outstanding_amount) AS total_fee_leakage_native,
    SUM(collected_amount) AS collected_native,
    SUM(gross_assessed_amount_eur) AS gross_assessed_eur,
    SUM(waived_amount_eur + outstanding_amount_eur) AS total_fee_leakage_eur,
    ROUND(
        SUM(waived_amount_eur + outstanding_amount_eur)
        / NULLIF(SUM(gross_assessed_amount_eur), 0) * 100,
        2
    ) AS total_leakage_pct
FROM analytics.fct_fee_assessments
GROUP BY fee_type, currency
ORDER BY total_fee_leakage_eur DESC;

-- -----------------------------------------------------------------------------
-- 5. Revenue by Transaction Type
-- Business Question: Which payment rails (WIRE_TRANSFER, CARD_SETTLEMENT,
-- ACH_PAYMENT) drive the bank's fee revenue and pass-through costs?
-- -----------------------------------------------------------------------------
SELECT
    revenue_category AS transaction_type,
    SUM(assessment_count) AS assessment_count,
    SUM(gross_assessed_fee_amount_eur) AS gross_assessed_eur,
    SUM(waived_fee_amount_eur) AS waived_eur,
    SUM(collected_fee_amount_eur) AS gross_collected_eur,
    SUM(pass_through_cost_amount_eur) AS pass_through_cost_eur,
    SUM(net_recognized_revenue_eur) AS net_recognized_revenue_eur
FROM analytics.fct_customer_revenue
GROUP BY revenue_category
ORDER BY net_recognized_revenue_eur DESC;

-- -----------------------------------------------------------------------------
-- 6. Reversed Transactions and Reversed Revenue Audit
-- Business Question: What reversals occurred in commercial transactions,
-- general ledger entries, and recognized fee revenue?
-- -----------------------------------------------------------------------------
SELECT
    le.journal_id,
    le.entry_id,
    le.original_entry_id,
    le.transaction_id,
    le.gl_account_id,
    le.entry_type,
    le.currency,
    le.amount,
    le.amount_eur,
    le.posting_status,
    le.posting_date
FROM analytics.fct_ledger_entries le
WHERE le.posting_status = 'REVERSED'
   OR le.original_entry_id IS NOT NULL
ORDER BY le.journal_id, le.entry_id;

-- -----------------------------------------------------------------------------
-- 7. Double-Entry General Ledger Journal Balancing Verification
-- Business Question: Do all accounting journals balance to 0.0000 per currency?
-- -----------------------------------------------------------------------------
SELECT
    journal_type,
    currency,
    COUNT(DISTINCT journal_id) AS journal_count,
    SUM(entry_count) AS posting_line_count,
    SUM(total_debit_amount) AS total_debits_native,
    SUM(total_credit_amount) AS total_credits_native,
    SUM(net_imbalance_amount) AS total_net_imbalance
FROM analytics.int_journal_balances
GROUP BY journal_type, currency
ORDER BY journal_type, currency;

-- -----------------------------------------------------------------------------
-- 8. Multi-Currency Revenue Reporting (Native vs. EUR Reporting Comparison)
-- Business Question: How do native currency revenue totals translate into EUR
-- reporting figures across EUR, USD, and GBP?
-- -----------------------------------------------------------------------------
SELECT
    currency AS native_currency,
    SUM(assessment_count) AS assessments,
    SUM(gross_assessed_fee_amount) AS gross_assessed_native,
    SUM(net_recognized_revenue) AS net_revenue_native,
    ROUND(
        SUM(net_recognized_revenue_eur) / NULLIF(SUM(net_recognized_revenue), 0),
        6
    ) AS effective_weighted_eur_fx_rate,
    SUM(gross_assessed_fee_amount_eur) AS gross_assessed_eur,
    SUM(net_recognized_revenue_eur) AS net_revenue_eur
FROM analytics.fct_customer_revenue
GROUP BY currency
ORDER BY net_revenue_eur DESC;
