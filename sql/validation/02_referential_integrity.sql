-- =============================================================================
-- RECONCILIATION QUERY 2: REFERENTIAL INTEGRITY AUDIT
--
-- Data Quality Invariant:
-- No orphan records across customers, bank accounts, and transactions.
-- =============================================================================

-- 1. Accounts without corresponding customer profile
SELECT 
    'ORPHAN_ACCOUNTS' AS issue_type,
    a.account_id,
    a.customer_id
FROM raw.accounts a
LEFT JOIN raw.customers c ON a.customer_id = c.customer_id
WHERE c.customer_id IS NULL;

-- 2. Transactions without corresponding customer bank account
SELECT 
    'ORPHAN_TRANSACTIONS' AS issue_type,
    t.transaction_id,
    t.account_id
FROM raw.transactions t
LEFT JOIN raw.accounts a ON t.account_id = a.account_id
WHERE a.account_id IS NULL;

-- 3. Ledger entries without corresponding journal
SELECT 
    'ORPHAN_LEDGER_ENTRIES' AS issue_type,
    le.entry_id,
    le.journal_id
FROM raw.ledger_entries le
LEFT JOIN raw.journals j ON le.journal_id = j.journal_id
WHERE j.journal_id IS NULL;
