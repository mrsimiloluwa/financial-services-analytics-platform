-- =============================================================================
-- Example SQL: Customer Profitability & Segment Performance
-- =============================================================================

-- 1. Customer Ranking by Net Recognized Fee Revenue (EUR)
SELECT
    c.customer_id,
    c.customer_name,
    c.customer_segment,
    c.total_accounts,
    c.currencies_held,
    c.settled_transactions_count,
    COALESCE(SUM(r.gross_assessed_fee_amount_eur), 0.0000) AS gross_assessed_eur,
    COALESCE(SUM(r.waived_fee_amount_eur), 0.0000) AS waived_eur,
    COALESCE(SUM(r.outstanding_fee_amount_eur), 0.0000) AS uncollected_arrears_eur,
    COALESCE(SUM(r.net_recognized_revenue_eur), 0.0000) AS net_recognized_revenue_eur
FROM analytics.dim_customers c
LEFT JOIN analytics.fct_customer_revenue r
    ON c.customer_id = r.customer_id
GROUP BY
    c.customer_id,
    c.customer_name,
    c.customer_segment,
    c.total_accounts,
    c.currencies_held,
    c.settled_transactions_count
ORDER BY net_recognized_revenue_eur DESC;
