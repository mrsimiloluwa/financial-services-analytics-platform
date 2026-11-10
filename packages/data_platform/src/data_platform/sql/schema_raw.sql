-- =============================================================================
-- RAW FINANCIAL DATA SCHEMA DDL
-- Enterprise AI Analytics Platform for Financial Services
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS raw;

-- 1. GL Accounts (Chart of Accounts Master)
CREATE TABLE IF NOT EXISTS raw.gl_accounts (
    gl_account_id VARCHAR(64) PRIMARY KEY,
    gl_account_number VARCHAR(16) NOT NULL UNIQUE,
    account_name VARCHAR(255) NOT NULL,
    account_category VARCHAR(32) NOT NULL,
    normal_balance VARCHAR(16) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    description TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2. Customers Profile Master
CREATE TABLE IF NOT EXISTS raw.customers (
    customer_id VARCHAR(64) PRIMARY KEY,
    legal_entity_id VARCHAR(64) NOT NULL,
    customer_name VARCHAR(255) NOT NULL,
    customer_segment VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL,
    onboarding_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 3. Customer Bank Accounts Subledger
CREATE TABLE IF NOT EXISTS raw.accounts (
    account_id VARCHAR(64) PRIMARY KEY,
    customer_id VARCHAR(64) NOT NULL REFERENCES raw.customers(customer_id),
    account_number VARCHAR(64) NOT NULL UNIQUE,
    account_type VARCHAR(32) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    opening_balance NUMERIC(18, 4) NOT NULL DEFAULT 0.0000,
    reserved_funds NUMERIC(18, 4) NOT NULL DEFAULT 0.0000,
    status VARCHAR(32) NOT NULL,
    opened_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_accounts_customer_id ON raw.accounts(customer_id);

-- 4. Overdraft Facility Agreements
CREATE TABLE IF NOT EXISTS raw.overdraft_facilities (
    facility_id VARCHAR(64) PRIMARY KEY,
    account_id VARCHAR(64) NOT NULL REFERENCES raw.accounts(account_id),
    authorized_limit NUMERIC(18, 4) NOT NULL DEFAULT 0.0000,
    standard_interest_rate NUMERIC(7, 4) NOT NULL,
    unauthorized_penalty_rate NUMERIC(7, 4) NOT NULL,
    effective_start_date DATE NOT NULL,
    effective_end_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_overdraft_account_id ON raw.overdraft_facilities(account_id);

-- 5. Foreign Exchange Market Rates (Triangulated ECB Historical Daily)
CREATE TABLE IF NOT EXISTS raw.fx_rates (
    rate_id VARCHAR(64) PRIMARY KEY,
    rate_date DATE NOT NULL,
    from_currency VARCHAR(3) NOT NULL,
    to_currency VARCHAR(3) NOT NULL,
    mid_rate NUMERIC(18, 6) NOT NULL,
    bid_rate NUMERIC(18, 6) NOT NULL,
    ask_rate NUMERIC(18, 6) NOT NULL,
    rate_source VARCHAR(64) NOT NULL,
    rate_type VARCHAR(32) NOT NULL,
    rate_timestamp TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_fx_rates_pair_date UNIQUE (rate_date, from_currency, to_currency)
);

CREATE INDEX IF NOT EXISTS idx_fx_rates_date ON raw.fx_rates(rate_date);

-- 6. Commercial Transactions
CREATE TABLE IF NOT EXISTS raw.transactions (
    transaction_id VARCHAR(64) PRIMARY KEY,
    account_id VARCHAR(64) NOT NULL REFERENCES raw.accounts(account_id),
    counterparty_account_id VARCHAR(64),
    transaction_type VARCHAR(32) NOT NULL,
    channel VARCHAR(32) NOT NULL,
    direction VARCHAR(16) NOT NULL,
    transaction_amount NUMERIC(18, 4) NOT NULL,
    transaction_currency VARCHAR(3) NOT NULL,
    settlement_currency VARCHAR(3) NOT NULL,
    customer_fx_rate NUMERIC(18, 6) NOT NULL DEFAULT 1.000000,
    base_currency_amount NUMERIC(18, 4) NOT NULL,
    status VARCHAR(32) NOT NULL,
    original_transaction_id VARCHAR(64),
    journal_id VARCHAR(64),
    initiated_at TIMESTAMPTZ NOT NULL,
    settled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_transactions_account_id ON raw.transactions(account_id);
CREATE INDEX IF NOT EXISTS idx_transactions_status ON raw.transactions(status);
CREATE INDEX IF NOT EXISTS idx_transactions_initiated_at ON raw.transactions(initiated_at);

-- 7. Accounting Journals (Balanced Double-Entry Journal Events)
CREATE TABLE IF NOT EXISTS raw.journals (
    journal_id VARCHAR(64) PRIMARY KEY,
    transaction_id VARCHAR(64),
    journal_type VARCHAR(32) NOT NULL,
    description VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_journals_transaction_id ON raw.journals(transaction_id);

-- 8. Double-Entry General Ledger Postings
CREATE TABLE IF NOT EXISTS raw.ledger_entries (
    entry_id VARCHAR(64) PRIMARY KEY,
    journal_id VARCHAR(64) NOT NULL REFERENCES raw.journals(journal_id),
    transaction_id VARCHAR(64),
    account_id VARCHAR(64) NOT NULL,
    account_type_marker VARCHAR(16) NOT NULL,
    gl_account_id VARCHAR(64) NOT NULL REFERENCES raw.gl_accounts(gl_account_id),
    entry_type VARCHAR(16) NOT NULL,
    amount NUMERIC(18, 4) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    original_entry_id VARCHAR(64),
    posting_status VARCHAR(32) NOT NULL DEFAULT 'POSTED',
    posted_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ledger_journal_id ON raw.ledger_entries(journal_id);
CREATE INDEX IF NOT EXISTS idx_ledger_account_id ON raw.ledger_entries(account_id);
CREATE INDEX IF NOT EXISTS idx_ledger_gl_account_id ON raw.ledger_entries(gl_account_id);

-- 9. Fee Assessments (Contractual and Volume Tier Evaluations)
CREATE TABLE IF NOT EXISTS raw.fee_assessments (
    assessment_id VARCHAR(64) PRIMARY KEY,
    transaction_id VARCHAR(64) NOT NULL REFERENCES raw.transactions(transaction_id),
    account_id VARCHAR(64) NOT NULL REFERENCES raw.accounts(account_id),
    gross_assessed_amount NUMERIC(18, 4) NOT NULL,
    waived_amount NUMERIC(18, 4) NOT NULL DEFAULT 0.0000,
    waiver_reason VARCHAR(255),
    net_collectible_amount NUMERIC(18, 4) NOT NULL,
    assessment_status VARCHAR(32) NOT NULL,
    assessed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_fee_assessments_txn ON raw.fee_assessments(transaction_id);
CREATE INDEX IF NOT EXISTS idx_fee_assessments_acc ON raw.fee_assessments(account_id);

-- 10. Fee Collection Attempts (Sweep Execution Lifecycle)
CREATE TABLE IF NOT EXISTS raw.fee_collections (
    collection_id VARCHAR(64) PRIMARY KEY,
    assessment_id VARCHAR(64) NOT NULL REFERENCES raw.fee_assessments(assessment_id),
    account_id VARCHAR(64) NOT NULL REFERENCES raw.accounts(account_id),
    collection_attempt_number INT NOT NULL DEFAULT 1,
    target_amount NUMERIC(18, 4) NOT NULL,
    collected_amount NUMERIC(18, 4) NOT NULL DEFAULT 0.0000,
    outstanding_amount NUMERIC(18, 4) NOT NULL DEFAULT 0.0000,
    collection_status VARCHAR(32) NOT NULL,
    failure_reason VARCHAR(255),
    attempted_at TIMESTAMPTZ NOT NULL,
    settled_at TIMESTAMPTZ,
    linked_ledger_entry_id VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_fee_collections_assessment ON raw.fee_collections(assessment_id);

-- 11. Accounting Revenue Recognitions
CREATE TABLE IF NOT EXISTS raw.revenue_recognitions (
    recognition_id VARCHAR(64) PRIMARY KEY,
    collection_id VARCHAR(64) NOT NULL REFERENCES raw.fee_collections(collection_id),
    gross_collected_revenue NUMERIC(18, 4) NOT NULL,
    reversed_revenue_amount NUMERIC(18, 4) NOT NULL DEFAULT 0.0000,
    pass_through_cost NUMERIC(18, 4) NOT NULL DEFAULT 0.0000,
    net_recognized_revenue NUMERIC(18, 4) NOT NULL,
    recognized_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rev_rec_collection ON raw.revenue_recognitions(collection_id);

-- 12. Ingestion Batch Manifests (Audit & Lineage Logging)
CREATE TABLE IF NOT EXISTS raw.ingestion_batch_manifests (
    batch_id UUID PRIMARY KEY,
    generator_version VARCHAR(32) NOT NULL,
    random_seed INT NOT NULL,
    profile_name VARCHAR(32) NOT NULL,
    reporting_base_currency VARCHAR(3) NOT NULL,
    total_records INT NOT NULL,
    entity_counts JSONB NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
