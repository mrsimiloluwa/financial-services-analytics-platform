-- =============================================================================
-- RECONCILIATION QUERY 4: FEE LIFECYCLE & CEILING AUDIT
--
-- Revenue Invariants:
-- 1. Assessment Decomposition: gross_assessed_amount = waived_amount + net_collectible_amount.
-- 2. Collection Ceiling: Cumulative collected_amount across retries must not exceed net_collectible_amount.
-- =============================================================================

-- Part 1: Fee Assessment Mathematical Discrepancies
SELECT 
    'INVALID_FEE_ASSESSMENT_MATH' AS check_name,
    assessment_id,
    gross_assessed_amount,
    waived_amount,
    net_collectible_amount,
    (gross_assessed_amount - (waived_amount + net_collectible_amount)) AS variance
FROM raw.fee_assessments
WHERE gross_assessed_amount <> (waived_amount + net_collectible_amount);

-- Part 2: Fee Collections Exceeding Collectible Ceiling
WITH coll_totals AS (
    SELECT 
        assessment_id,
        SUM(collected_amount) AS total_collected
    FROM raw.fee_collections
    WHERE collection_status IN ('SETTLED', 'PARTIAL')
    GROUP BY assessment_id
)
SELECT 
    'COLLECTION_CEILING_EXCEEDED' AS check_name,
    ct.assessment_id,
    ct.total_collected,
    fa.net_collectible_amount,
    (ct.total_collected - fa.net_collectible_amount) AS excess_amount
FROM coll_totals ct
JOIN raw.fee_assessments fa ON ct.assessment_id = fa.assessment_id
WHERE ct.total_collected > fa.net_collectible_amount;
