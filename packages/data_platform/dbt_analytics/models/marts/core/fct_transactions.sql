-- =============================================================================
-- Model: fct_transactions
-- Layer: Marts (Core Fact)
-- Grain: One row per commercial transaction (transaction_id)
-- =============================================================================

with transactions as (
    select
        transaction_id,
        account_id,
        account_number,
        account_type,
        account_currency,
        customer_id,
        customer_name,
        customer_segment,
        counterparty_account_id,
        transaction_type,
        channel,
        direction,
        transaction_amount,
        transaction_currency,
        settlement_currency,
        customer_fx_rate,
        base_currency_amount,
        reporting_eur_fx_rate,
        reporting_fx_rate_source,
        transaction_amount_eur,
        transaction_status,
        original_transaction_id,
        journal_id,
        initiated_at,
        transaction_date,
        transaction_month,
        settled_at,
        settlement_date,
        is_settled_or_reversed,
        is_reversal_related,
        is_cross_currency
    from {{ ref('int_transactions_enriched') }}
)

select
    transaction_id,
    customer_id,
    customer_name,
    customer_segment,
    account_id,
    account_number,
    account_type,
    account_currency,
    counterparty_account_id,
    transaction_type,
    channel,
    direction,
    transaction_status,
    -- Original transaction currency and amount (never mixed across currencies)
    transaction_currency,
    transaction_amount,
    -- Settlement currency and amount
    settlement_currency,
    customer_fx_rate,
    base_currency_amount,
    -- Explicit EUR reporting conversion
    'EUR' as reporting_currency,
    reporting_eur_fx_rate,
    reporting_fx_rate_source,
    transaction_amount_eur,
    -- Lineage and lifecycle metadata
    original_transaction_id,
    journal_id,
    is_settled_or_reversed,
    is_reversal_related,
    is_cross_currency,
    transaction_date,
    transaction_month,
    settlement_date,
    initiated_at,
    settled_at
from transactions
