-- =============================================================================
-- Singular Test: assert_journal_balanced_per_currency
-- Invariant: Every accounting journal must balance independently per currency
--            leg: SUM(debit_amount) == SUM(credit_amount).
-- Returns failing (journal_id, currency) pairs where abs(diff) > 0.0000.
-- =============================================================================

select
    journal_id,
    currency,
    sum(debit_amount) as total_debits,
    sum(credit_amount) as total_credits,
    sum(debit_amount) - sum(credit_amount) as imbalance
from {{ ref('fct_ledger_entries') }}
group by
    journal_id,
    currency
having abs(sum(debit_amount) - sum(credit_amount)) > 0.0000
