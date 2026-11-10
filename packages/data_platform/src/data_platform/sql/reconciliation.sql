-- =============================================================================
-- POST-INGESTION RECONCILIATION & DATA QUALITY AUDIT QUERIES
-- Enterprise AI Analytics Platform for Financial Services
-- =============================================================================

-- 1. Double-Entry General Ledger Balancing per Currency Leg
-- Invariant: For every journal, SUM(DEBITS) must equal SUM(CREDITS) independently per currency.
WITH leg_balances AS (
    SELECT 
        journal_id,
        currency,
        SUM(CASE WHEN entry_type = 'DEBIT' THEN amount ELSE -amount END) AS leg_diff
    FROM raw.ledger_entries
    GROUP BY journal_id, currency
)
SELECT 
    journal_id,
    currency,
    leg_diff
FROM leg_balances
WHERE leg_diff <> 0.0000;

-- 2. Anti-Leakage Invariant: No Ledger Postings for Unsettled Transactions
-- Invariant: FAILED or PENDING transactions must NEVER produce ledger entries.
SELECT 
    t.transaction_id,
    t.status,
    COUNT(le.entry_id) AS illegal_posting_count
FROM raw.transactions t
JOIN raw.ledger_entries le ON t.transaction_id = le.transaction_id
WHERE t.status IN ('FAILED', 'PENDING')
GROUP BY t.transaction_id, t.status;

-- 3. Customer to Account Referential Integrity
-- Invariant: Every bank account must link to a valid customer profile.
SELECT COUNT(*) AS orphan_accounts_count
FROM raw.accounts a
LEFT JOIN raw.customers c ON a.customer_id = c.customer_id
WHERE c.customer_id IS NULL;

-- 4. Transaction to Account Referential Integrity
-- Invariant: Every transaction must originate from a valid bank account.
SELECT COUNT(*) AS orphan_transactions_count
FROM raw.transactions t
LEFT JOIN raw.accounts a ON t.account_id = a.account_id
WHERE a.account_id IS NULL;

-- 5. Fee Assessment Mathematical Decomposition
-- Invariant: gross_assessed_amount = waived_amount + net_collectible_amount.
SELECT COUNT(*) AS invalid_assessments_count
FROM raw.fee_assessments
WHERE gross_assessed_amount <> (waived_amount + net_collectible_amount);

-- 6. Fee Collection Ceiling Enforcement
-- Invariant: Cumulative net collections for an assessment must never exceed net_collectible_amount.
WITH coll_totals AS (
    SELECT 
        assessment_id,
        SUM(collected_amount) AS total_collected
    FROM raw.fee_collections
    WHERE collection_status IN ('SETTLED', 'PARTIAL')
    GROUP BY assessment_id
)
SELECT COUNT(*) AS ceiling_violations_count
FROM coll_totals ct
JOIN raw.fee_assessments fa ON ct.assessment_id = fa.assessment_id
WHERE ct.total_collected > fa.net_collectible_amount;

-- 7. Currency Domains Validity
-- Invariant: All customer accounts must use approved ISO currencies (EUR, USD, GBP, CHF).
SELECT COUNT(*) AS invalid_currencies_count
FROM raw.accounts
WHERE currency NOT IN ('EUR', 'USD', 'GBP', 'CHF');

-- 8. Raw Tables Row Counts Audit
SELECT 'gl_accounts' AS table_name, COUNT(*) AS row_count FROM raw.gl_accounts
UNION ALL SELECT 'customers', COUNT(*) FROM raw.customers
UNION ALL SELECT 'accounts', COUNT(*) FROM raw.accounts
UNION ALL SELECT 'overdraft_facilities', COUNT(*) FROM raw.overdraft_facilities
UNION ALL SELECT 'fx_rates', COUNT(*) FROM raw.fx_rates
UNION ALL SELECT 'transactions', COUNT(*) FROM raw.transactions
UNION ALL SELECT 'journals', COUNT(*) FROM raw.journals
UNION ALL SELECT 'ledger_entries', COUNT(*) FROM raw.ledger_entries
UNION ALL SELECT 'fee_assessments', COUNT(*) FROM raw.fee_assessments
UNION ALL SELECT 'fee_collections', COUNT(*) FROM raw.fee_collections
UNION ALL SELECT 'revenue_recognitions', COUNT(*) FROM raw.revenue_recognitions
UNION ALL SELECT 'ingestion_batch_manifests', COUNT(*) FROM raw.ingestion_batch_manifests;
