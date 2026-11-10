-- =============================================================================
-- TRANSACTIONAL MERGE STATEMENTS FROM STAGING TO RAW TABLES
-- Enterprise AI Analytics Platform for Financial Services
-- =============================================================================

-- 1. GL Accounts
INSERT INTO raw.gl_accounts (
    gl_account_id, gl_account_number, account_name, account_category, normal_balance, currency, description
)
SELECT gl_account_id, gl_account_number, account_name, account_category, normal_balance, currency, description
FROM staging.gl_accounts
ON CONFLICT (gl_account_id) DO NOTHING;

-- 2. Customers
INSERT INTO raw.customers (
    customer_id, legal_entity_id, customer_name, customer_segment, status, onboarding_date
)
SELECT customer_id, legal_entity_id, customer_name, customer_segment, status, onboarding_date
FROM staging.customers
ON CONFLICT (customer_id) DO NOTHING;

-- 3. Accounts
INSERT INTO raw.accounts (
    account_id, customer_id, account_number, account_type, currency, opening_balance, reserved_funds, status, opened_at
)
SELECT account_id, customer_id, account_number, account_type, currency, opening_balance, reserved_funds, status, opened_at
FROM staging.accounts
ON CONFLICT (account_id) DO NOTHING;

-- 4. Overdraft Facilities
INSERT INTO raw.overdraft_facilities (
    facility_id, account_id, authorized_limit, standard_interest_rate, unauthorized_penalty_rate, effective_start_date, effective_end_date
)
SELECT facility_id, account_id, authorized_limit, standard_interest_rate, unauthorized_penalty_rate, effective_start_date, effective_end_date
FROM staging.overdraft_facilities
ON CONFLICT (facility_id) DO NOTHING;

-- 5. Foreign Exchange Rates
INSERT INTO raw.fx_rates (
    rate_id, rate_date, from_currency, to_currency, mid_rate, bid_rate, ask_rate, rate_source, rate_type, rate_timestamp
)
SELECT rate_id, rate_date, from_currency, to_currency, mid_rate, bid_rate, ask_rate, rate_source, rate_type, rate_timestamp
FROM staging.fx_rates
ON CONFLICT (rate_date, from_currency, to_currency) DO NOTHING;

-- 6. Commercial Transactions
INSERT INTO raw.transactions (
    transaction_id, account_id, counterparty_account_id, transaction_type, channel, direction,
    transaction_amount, transaction_currency, settlement_currency, customer_fx_rate, base_currency_amount,
    status, original_transaction_id, journal_id, initiated_at, settled_at
)
SELECT transaction_id, account_id, counterparty_account_id, transaction_type, channel, direction,
       transaction_amount, transaction_currency, settlement_currency, customer_fx_rate, base_currency_amount,
       status, original_transaction_id, journal_id, initiated_at, settled_at
FROM staging.transactions
ON CONFLICT (transaction_id) DO NOTHING;

-- 7. Accounting Journals
INSERT INTO raw.journals (
    journal_id, transaction_id, journal_type, description, created_at
)
SELECT journal_id, transaction_id, journal_type, description, created_at
FROM staging.journals
ON CONFLICT (journal_id) DO NOTHING;

-- 8. General Ledger Entries
INSERT INTO raw.ledger_entries (
    entry_id, journal_id, transaction_id, account_id, account_type_marker, gl_account_id,
    entry_type, amount, currency, original_entry_id, posting_status, posted_at
)
SELECT entry_id, journal_id, transaction_id, account_id, account_type_marker, gl_account_id,
       entry_type, amount, currency, original_entry_id, posting_status, posted_at
FROM staging.ledger_entries
ON CONFLICT (entry_id) DO NOTHING;

-- 9. Fee Assessments
INSERT INTO raw.fee_assessments (
    assessment_id, transaction_id, account_id, gross_assessed_amount, waived_amount,
    waiver_reason, net_collectible_amount, assessment_status, assessed_at
)
SELECT assessment_id, transaction_id, account_id, gross_assessed_amount, waived_amount,
       waiver_reason, net_collectible_amount, assessment_status, assessed_at
FROM staging.fee_assessments
ON CONFLICT (assessment_id) DO NOTHING;

-- 10. Fee Collections
INSERT INTO raw.fee_collections (
    collection_id, assessment_id, account_id, collection_attempt_number, target_amount,
    collected_amount, outstanding_amount, collection_status, failure_reason,
    attempted_at, settled_at, linked_ledger_entry_id
)
SELECT collection_id, assessment_id, account_id, collection_attempt_number, target_amount,
       collected_amount, outstanding_amount, collection_status, failure_reason,
       attempted_at, settled_at, linked_ledger_entry_id
FROM staging.fee_collections
ON CONFLICT (collection_id) DO NOTHING;

-- 11. Revenue Recognitions
INSERT INTO raw.revenue_recognitions (
    recognition_id, collection_id, gross_collected_revenue, reversed_revenue_amount,
    pass_through_cost, net_recognized_revenue, recognized_at
)
SELECT recognition_id, collection_id, gross_collected_revenue, reversed_revenue_amount,
       pass_through_cost, net_recognized_revenue, recognized_at
FROM staging.revenue_recognitions
ON CONFLICT (recognition_id) DO NOTHING;
