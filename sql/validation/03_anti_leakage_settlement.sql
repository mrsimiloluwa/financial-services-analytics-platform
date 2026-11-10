-- =============================================================================
-- RECONCILIATION QUERY 3: ANTI-LEAKAGE SETTLEMENT INVARIANT
--
-- Financial Invariant:
-- Transactions with status FAILED or PENDING must NEVER generate general ledger postings.
-- Ledger postings represent legally binding accounting movements; phantom postings
-- on unsettled payments constitute financial misstatement.
-- =============================================================================

SELECT 
    t.transaction_id,
    t.status,
    t.transaction_amount,
    t.transaction_currency,
    COUNT(le.entry_id) AS illegal_posting_count
FROM raw.transactions t
JOIN raw.ledger_entries le ON t.transaction_id = le.transaction_id
WHERE t.status IN ('FAILED', 'PENDING')
GROUP BY t.transaction_id, t.status, t.transaction_amount, t.transaction_currency;
