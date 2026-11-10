-- =============================================================================
-- Singular Test: assert_no_assessment_overcollection
-- Invariant: Cumulative collected_amount for an assessment must never exceed
--            net_collectible_amount, and assessment-level reconciliation
--            net_collectible_amount = collected_amount + outstanding_amount
--            must hold exactly.
-- =============================================================================

select
    assessment_id,
    net_collectible_amount,
    collected_amount,
    outstanding_amount
from {{ ref('fct_fee_assessments') }}
where collected_amount > net_collectible_amount
   or outstanding_amount < 0.0000
   or abs(net_collectible_amount - (collected_amount + outstanding_amount)) > 0.0000
