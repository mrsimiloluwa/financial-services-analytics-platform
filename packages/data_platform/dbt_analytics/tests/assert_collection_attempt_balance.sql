-- =============================================================================
-- Singular Test: assert_collection_attempt_balance
-- Invariant: For every collection attempt, target_amount must equal
--            collected_amount + outstanding_amount, and SETTLED attempts
--            must have outstanding_amount = 0.0000.
-- =============================================================================

select
    collection_id,
    assessment_id,
    collection_status,
    target_amount,
    collected_amount,
    outstanding_amount
from {{ ref('fct_fee_collections') }}
where target_amount <= 0.0000
   or collected_amount < 0.0000
   or outstanding_amount < 0.0000
   or abs(target_amount - (collected_amount + outstanding_amount)) > 0.0000
   or (collection_status = 'SETTLED' and outstanding_amount <> 0.0000)
