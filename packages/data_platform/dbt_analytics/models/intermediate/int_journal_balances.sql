-- =============================================================================
-- Model: int_journal_balances
-- Grain: One row per accounting journal and currency leg (journal_id + currency)
-- Purpose: Verify double-entry accounting balance per journal and currency leg,
--          tracking total debits, total credits, net imbalance, and entry counts.
-- =============================================================================

with journals as (
    select
        journal_id,
        transaction_id,
        journal_type,
        description,
        journal_created_at,
        journal_date
    from {{ ref('stg_journals') }}
),

ledger_legs as (
    select
        journal_id,
        currency,
        count(entry_id) as entry_count,
        sum(debit_amount) as total_debit_amount,
        sum(credit_amount) as total_credit_amount,
        sum(signed_debit_minus_credit) as net_imbalance_amount,
        min(posted_at) as first_posted_at,
        max(posted_at) as last_posted_at
    from {{ ref('stg_ledger_entries') }}
    group by
        journal_id,
        currency
)

select
    j.journal_id,
    l.currency,
    j.transaction_id,
    j.journal_type,
    j.description,
    j.journal_created_at,
    j.journal_date,
    l.entry_count,
    cast(l.total_debit_amount as numeric(18, 4)) as total_debit_amount,
    cast(l.total_credit_amount as numeric(18, 4)) as total_credit_amount,
    cast(l.net_imbalance_amount as numeric(18, 4)) as net_imbalance_amount,
    abs(l.net_imbalance_amount) = 0.0000 as is_balanced,
    l.first_posted_at,
    l.last_posted_at
from journals j
inner join ledger_legs l
    on j.journal_id = l.journal_id
