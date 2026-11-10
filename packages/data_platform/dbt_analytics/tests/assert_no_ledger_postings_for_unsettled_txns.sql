-- =============================================================================
-- Singular Test: assert_no_ledger_postings_for_unsettled_txns
-- Invariant: FAILED or PENDING transactions must never generate general ledger
--            postings.
-- =============================================================================

select
    t.transaction_id,
    t.transaction_status,
    count(le.entry_id) as illegal_ledger_entry_count
from {{ ref('fct_transactions') }} t
inner join {{ ref('fct_ledger_entries') }} le
    on t.transaction_id = le.transaction_id
where t.transaction_status in ('FAILED', 'PENDING')
group by
    t.transaction_id,
    t.transaction_status
