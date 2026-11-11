-- =============================================================================
-- Example SQL: Revenue Analysis by Period, Product, and Currency
-- =============================================================================

-- 1. Monthly Revenue Trend in EUR Reporting Currency
SELECT
    year_month,
    SUM(assessment_count) AS fee_assessments,
    SUM(gross_assessed_fee_amount_eur) AS gross_assessed_eur,
    SUM(waived_fee_amount_eur) AS waived_eur,
    SUM(collected_fee_amount_eur) AS gross_collected_eur,
    SUM(pass_through_cost_amount_eur) AS pass_through_cost_eur,
    SUM(net_recognized_revenue_eur) AS net_recognized_revenue_eur
FROM analytics.fct_customer_revenue
GROUP BY year_month
ORDER BY year_month;

-- 2. Revenue Breakdown by Product Category and Native Currency
SELECT
    revenue_category,
    currency,
    SUM(assessment_count) AS assessments,
    SUM(gross_assessed_fee_amount) AS gross_assessed_native,
    SUM(net_recognized_revenue) AS net_revenue_native,
    SUM(net_recognized_revenue_eur) AS net_revenue_eur
FROM analytics.fct_customer_revenue
GROUP BY revenue_category, currency
ORDER BY net_revenue_eur DESC;
