-- =============================================================================
-- Singular Test: assert_fee_assessment_decomposition
-- Invariant: For every fee assessment, gross_assessed_amount must equal
--            waived_amount + net_collectible_amount, and all amounts >= 0.
-- =============================================================================

select
    assessment_id,
    gross_assessed_amount,
    waived_amount,
    net_collectible_amount
from {{ ref('fct_fee_assessments') }}
where gross_assessed_amount < 0.0000
   or waived_amount < 0.0000
   or net_collectible_amount < 0.0000
   or abs(gross_assessed_amount - (waived_amount + net_collectible_amount)) > 0.0000
