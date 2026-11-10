-- =============================================================================
-- REPRESENTATIVE BUSINESS & ANALYTICAL SQL QUERIES
-- Enterprise AI Analytics Platform for Financial Services
-- =============================================================================

-- Business Question 1: Customer Aggregate Deposit Balances by Currency
-- Purpose: Calculate total customer deposit liabilities per currency subledger.
SELECT 
    c.customer_segment,
    a.currency,
    COUNT(DISTINCT a.account_id) AS active_accounts,
    SUM(a.opening_balance) AS total_opening_balance,
    SUM(a.reserved_funds) AS total_reserved_funds
FROM raw.accounts a
JOIN raw.customers c ON a.customer_id = c.customer_id
WHERE a.status = 'ACTIVE'
GROUP BY c.customer_segment, a.currency
ORDER BY c.customer_segment, a.currency;

-- Business Question 2: Fee Leakage Audit (Assessed Fees vs Contractual Waivers)
-- Purpose: Identify fee revenue leakage across payment channels and reasons.
SELECT 
    t.transaction_type,
    fa.waiver_reason,
    COUNT(fa.assessment_id) AS assessed_count,
    SUM(fa.gross_assessed_amount) AS total_gross_assessed_eur,
    SUM(fa.waived_amount) AS total_waived_leakage_eur,
    SUM(fa.net_collectible_amount) AS total_net_collectible_eur,
    ROUND((SUM(fa.waived_amount) / NULLIF(SUM(fa.gross_assessed_amount), 0)) * 100, 2) AS leakage_percentage
FROM raw.fee_assessments fa
JOIN raw.transactions t ON fa.transaction_id = t.transaction_id
GROUP BY t.transaction_type, fa.waiver_reason
ORDER BY total_waived_leakage_eur DESC;

-- Business Question 3: Foreign Exchange Spread Capture & Trading Margin
-- Purpose: Quantify realized FX spread revenue across currency corridors.
SELECT 
    t.transaction_currency AS sell_currency,
    t.settlement_currency AS buy_currency,
    COUNT(t.transaction_id) AS conversion_count,
    SUM(t.transaction_amount) AS total_sold_amount,
    AVG(t.customer_fx_rate) AS avg_realized_rate,
    SUM(t.base_currency_amount) AS total_base_amount_eur
FROM raw.transactions t
WHERE t.transaction_type = 'FX_CONVERSION'
  AND t.status = 'SETTLED'
GROUP BY t.transaction_currency, t.settlement_currency
ORDER BY conversion_count DESC;

-- Business Question 4: Fee Collection Success Rate and Outstanding Balances
-- Purpose: Track operational fee recovery efficiency and uncollected fee backlog.
SELECT 
    fc.collection_status,
    COUNT(fc.collection_id) AS sweep_count,
    SUM(fc.target_amount) AS total_target_eur,
    SUM(fc.collected_amount) AS total_collected_eur,
    SUM(fc.outstanding_amount) AS total_uncollected_backlog_eur
FROM raw.fee_collections fc
GROUP BY fc.collection_status
ORDER BY sweep_count DESC;
