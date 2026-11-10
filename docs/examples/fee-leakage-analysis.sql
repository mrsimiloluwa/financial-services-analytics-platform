-- =============================================================================
-- Example SQL: Fee Leakage & Collection Arrears Analysis
-- =============================================================================

-- 1. Commercial Waivers vs. Failed Collection Arrears by Segment
SELECT
    customer_segment,
    COUNT(assessment_id) AS total_assessments,
    COUNT(CASE WHEN assessment_status = 'PARTIALLY_WAIVED' THEN 1 END) AS waived_assessments,
    COUNT(CASE WHEN collection_status = 'FAILED' THEN 1 END) AS failed_collections,
    SUM(gross_assessed_amount_eur) AS gross_assessed_eur,
    SUM(waived_amount_eur) AS waived_leakage_eur,
    SUM(outstanding_amount_eur) AS uncollected_arrears_eur,
    SUM(waived_amount_eur + outstanding_amount_eur) AS total_leakage_eur,
    SUM(collected_amount_eur) AS collected_eur,
    ROUND(
        SUM(waived_amount_eur + outstanding_amount_eur)
        / NULLIF(SUM(gross_assessed_amount_eur), 0) * 100,
        2
    ) AS leakage_rate_pct
FROM analytics.fct_fee_assessments
GROUP BY customer_segment
ORDER BY total_leakage_eur DESC;

-- 2. Detailed Inspection of Failed Fee Collection Attempts
SELECT
    collection_id,
    assessment_id,
    transaction_id,
    customer_id,
    customer_name,
    customer_segment,
    fee_type,
    currency,
    target_amount,
    collected_amount,
    outstanding_amount,
    outstanding_amount_eur,
    collection_status,
    failure_reason,
    attempted_date
FROM analytics.fct_fee_collections
WHERE collection_status = 'FAILED'
ORDER BY outstanding_amount_eur DESC;
