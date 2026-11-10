-- =============================================================================
-- Singular Test: assert_reversal_within_original_amount
-- Invariant:
--   1. Reversed fee revenue never exceeds gross collected revenue.
--   2. Reversal ledger postings (where original_entry_id is not null) never
--      exceed the amount of the original ledger posting they reverse.
-- =============================================================================

with invalid_revenue_reversals as (
    select
        recognition_id as record_id,
        'REVENUE_RECOGNITION' as violation_type,
        reversed_revenue_amount as reversal_amount,
        gross_collected_revenue as original_amount
    from {{ ref('stg_revenue_recognitions') }}
    where reversed_revenue_amount < 0.0000
       or reversed_revenue_amount > gross_collected_revenue
),

invalid_ledger_reversals as (
    select
        rev.entry_id as record_id,
        'LEDGER_REVERSAL' as violation_type,
        rev.amount as reversal_amount,
        coalesce(orig.amount, -1.0000) as original_amount
    from {{ ref('fct_ledger_entries') }} rev
    left join {{ ref('fct_ledger_entries') }} orig
        on rev.original_entry_id = orig.entry_id
    where rev.original_entry_id is not null
      and (
          orig.entry_id is null
          or rev.amount > orig.amount
          or rev.currency <> orig.currency
      )
)

select * from invalid_revenue_reversals
union all
select * from invalid_ledger_reversals
