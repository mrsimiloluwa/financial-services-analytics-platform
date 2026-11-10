-- =============================================================================
-- Example SQL: Commercial Transaction Volume & Lifecycle Analysis
-- =============================================================================

-- 1. Transaction Funnel by Status and Payment Rail
SELECT
    transaction_type,
    transaction_status,
    transaction_currency,
    COUNT(transaction_id) AS transaction_count,
    SUM(transaction_amount) AS total_amount_native,
    SUM(transaction_amount_eur) AS total_amount_eur,
    ROUND(AVG(transaction_amount_eur), 2) AS avg_amount_eur
FROM analytics.fct_transactions
GROUP BY
    transaction_type,
    transaction_status,
    transaction_currency
ORDER BY
    transaction_type,
    transaction_status,
    transaction_currency;
