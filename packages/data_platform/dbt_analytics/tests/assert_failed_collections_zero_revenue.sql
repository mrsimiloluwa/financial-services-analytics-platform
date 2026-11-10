-- =============================================================================
-- Singular Test: assert_failed_collections_zero_revenue
-- Invariant: Failed fee collection attempts (collection_status = 'FAILED')
--            must never record collected_amount > 0, gross_collected_revenue > 0,
--            net_recognized_revenue > 0, or a linked ledger entry.
-- =============================================================================

select
    collection_id,
    assessment_id,
    collection_status,
    collected_amount,
    gross_collected_revenue,
    net_recognized_revenue,
    linked_ledger_entry_id,
    recognition_id
from {{ ref('fct_fee_collections') }}
where collection_status = 'FAILED'
  and (
      collected_amount <> 0.0000
      or gross_collected_revenue <> 0.0000
      or net_recognized_revenue <> 0.0000
      or linked_ledger_entry_id is not null
      or recognition_id is not null
  )
