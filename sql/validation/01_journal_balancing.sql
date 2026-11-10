-- =============================================================================
-- RECONCILIATION QUERY 1: DOUBLE-ENTRY GENERAL LEDGER BALANCING
--
-- Accounting Invariant:
-- In a multi-currency double-entry ledger, every completed journal must balance
-- strictly per currency leg: SUM(DEBITS) - SUM(CREDITS) = 0.0000.
-- =============================================================================

WITH leg_balances AS (
    SELECT 
        journal_id,
        currency,
        SUM(CASE WHEN entry_type = 'DEBIT' THEN amount ELSE -amount END) AS currency_leg_imbalance,
        COUNT(entry_id) AS entries_in_leg
    FROM raw.ledger_entries
    GROUP BY journal_id, currency
)
SELECT 
    journal_id,
    currency,
    currency_leg_imbalance,
    entries_in_leg
FROM leg_balances
WHERE currency_leg_imbalance <> 0.0000;
