-- =============================================================================
-- STAGING UNLOGGED SCHEMA DDL FOR FAST BATCH COPY
-- Enterprise AI Analytics Platform for Financial Services
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS staging;

CREATE UNLOGGED TABLE IF NOT EXISTS staging.gl_accounts (
    gl_account_id VARCHAR(64),
    gl_account_number VARCHAR(16),
    account_name VARCHAR(255),
    account_category VARCHAR(32),
    normal_balance VARCHAR(16),
    currency VARCHAR(3),
    description TEXT
);

CREATE UNLOGGED TABLE IF NOT EXISTS staging.customers (
    customer_id VARCHAR(64),
    legal_entity_id VARCHAR(64),
    customer_name VARCHAR(255),
    customer_segment VARCHAR(32),
    status VARCHAR(32),
    onboarding_date DATE
);

CREATE UNLOGGED TABLE IF NOT EXISTS staging.accounts (
    account_id VARCHAR(64),
    customer_id VARCHAR(64),
    account_number VARCHAR(64),
    account_type VARCHAR(32),
    currency VARCHAR(3),
    opening_balance NUMERIC(18, 4),
    reserved_funds NUMERIC(18, 4),
    status VARCHAR(32),
    opened_at TIMESTAMPTZ
);

CREATE UNLOGGED TABLE IF NOT EXISTS staging.overdraft_facilities (
    facility_id VARCHAR(64),
    account_id VARCHAR(64),
    authorized_limit NUMERIC(18, 4),
    standard_interest_rate NUMERIC(7, 4),
    unauthorized_penalty_rate NUMERIC(7, 4),
    effective_start_date DATE,
    effective_end_date DATE
);

CREATE UNLOGGED TABLE IF NOT EXISTS staging.fx_rates (
    rate_id VARCHAR(64),
    rate_date DATE,
    from_currency VARCHAR(3),
    to_currency VARCHAR(3),
    mid_rate NUMERIC(18, 6),
    bid_rate NUMERIC(18, 6),
    ask_rate NUMERIC(18, 6),
    rate_source VARCHAR(64),
    rate_type VARCHAR(32),
    rate_timestamp TIMESTAMPTZ
);

CREATE UNLOGGED TABLE IF NOT EXISTS staging.transactions (
    transaction_id VARCHAR(64),
    account_id VARCHAR(64),
    counterparty_account_id VARCHAR(64),
    transaction_type VARCHAR(32),
    channel VARCHAR(32),
    direction VARCHAR(16),
    transaction_amount NUMERIC(18, 4),
    transaction_currency VARCHAR(3),
    settlement_currency VARCHAR(3),
    customer_fx_rate NUMERIC(18, 6),
    base_currency_amount NUMERIC(18, 4),
    status VARCHAR(32),
    original_transaction_id VARCHAR(64),
    journal_id VARCHAR(64),
    initiated_at TIMESTAMPTZ,
    settled_at TIMESTAMPTZ
);

CREATE UNLOGGED TABLE IF NOT EXISTS staging.journals (
    journal_id VARCHAR(64),
    transaction_id VARCHAR(64),
    journal_type VARCHAR(32),
    description VARCHAR(255),
    created_at TIMESTAMPTZ
);

CREATE UNLOGGED TABLE IF NOT EXISTS staging.ledger_entries (
    entry_id VARCHAR(64),
    journal_id VARCHAR(64),
    transaction_id VARCHAR(64),
    account_id VARCHAR(64),
    account_type_marker VARCHAR(16),
    gl_account_id VARCHAR(64),
    entry_type VARCHAR(16),
    amount NUMERIC(18, 4),
    currency VARCHAR(3),
    original_entry_id VARCHAR(64),
    posting_status VARCHAR(32),
    posted_at TIMESTAMPTZ
);

CREATE UNLOGGED TABLE IF NOT EXISTS staging.fee_assessments (
    assessment_id VARCHAR(64),
    transaction_id VARCHAR(64),
    account_id VARCHAR(64),
    gross_assessed_amount NUMERIC(18, 4),
    waived_amount NUMERIC(18, 4),
    waiver_reason VARCHAR(255),
    net_collectible_amount NUMERIC(18, 4),
    assessment_status VARCHAR(32),
    assessed_at TIMESTAMPTZ
);

CREATE UNLOGGED TABLE IF NOT EXISTS staging.fee_collections (
    collection_id VARCHAR(64),
    assessment_id VARCHAR(64),
    account_id VARCHAR(64),
    collection_attempt_number INT,
    target_amount NUMERIC(18, 4),
    collected_amount NUMERIC(18, 4),
    outstanding_amount NUMERIC(18, 4),
    collection_status VARCHAR(32),
    failure_reason VARCHAR(255),
    attempted_at TIMESTAMPTZ,
    settled_at TIMESTAMPTZ,
    linked_ledger_entry_id VARCHAR(64)
);

CREATE UNLOGGED TABLE IF NOT EXISTS staging.revenue_recognitions (
    recognition_id VARCHAR(64),
    collection_id VARCHAR(64),
    gross_collected_revenue NUMERIC(18, 4),
    reversed_revenue_amount NUMERIC(18, 4),
    pass_through_cost NUMERIC(18, 4),
    net_recognized_revenue NUMERIC(18, 4),
    recognized_at TIMESTAMPTZ
);
