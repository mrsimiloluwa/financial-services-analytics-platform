-- =============================================================================
-- RECONCILIATION QUERY 5: BATCH SUMMARY AUDIT & ROW COUNTS
--
-- Audit Lineage:
-- Verify total row counts across all raw tables compared to ingestion manifest.
-- =============================================================================

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
UNION ALL SELECT 'ingestion_batch_manifests', COUNT(*) FROM raw.ingestion_batch_manifests
ORDER BY table_name;
