-- =============================================================================
-- Model: int_transactions_enriched
-- Grain: One row per commercial transaction (transaction_id)
-- Purpose: Enrich transactions with customer/account context and explicit
--          EUR reporting conversion from stg_fx_rates without default-to-1 fallbacks.
-- =============================================================================

with transactions as (
    select
        transaction_id,
        account_id,
        counterparty_account_id,
        transaction_type,
        channel,
        direction,
        transaction_amount,
        transaction_currency,
        settlement_currency,
        customer_fx_rate,
        base_currency_amount,
        transaction_status,
        original_transaction_id,
        journal_id,
        initiated_at,
        transaction_date,
        settled_at,
        settlement_date,
        is_settled_or_reversed,
        is_reversal_related
    from {{ ref('stg_transactions') }}
),

customer_accounts as (
    select
        account_id,
        account_number,
        account_type,
        account_currency,
        customer_id,
        customer_name,
        customer_segment
    from {{ ref('int_customer_accounts') }}
),

fx_to_eur as (
    select
        rate_date,
        from_currency,
        to_currency,
        mid_rate as eur_mid_rate,
        bid_rate as eur_bid_rate,
        ask_rate as eur_ask_rate,
        rate_source as eur_rate_source
    from {{ ref('stg_fx_rates') }}
    where to_currency = 'EUR'
)

select
    t.transaction_id,
    t.account_id,
    ca.account_number,
    ca.account_type,
    ca.account_currency,
    ca.customer_id,
    ca.customer_name,
    ca.customer_segment,
    t.counterparty_account_id,
    t.transaction_type,
    t.channel,
    t.direction,
    t.transaction_amount,
    t.transaction_currency,
    t.settlement_currency,
    t.customer_fx_rate,
    t.base_currency_amount,
    -- Explicit conversion of transaction_amount from transaction_currency to EUR
    fx.eur_mid_rate as reporting_eur_fx_rate,
    fx.eur_rate_source as reporting_fx_rate_source,
    cast(
        round(t.transaction_amount * fx.eur_mid_rate, 4)
        as numeric(18, 4)
    ) as transaction_amount_eur,
    t.transaction_status,
    t.original_transaction_id,
    t.journal_id,
    t.initiated_at,
    t.transaction_date,
    cast(date_trunc('month', t.transaction_date) as date) as transaction_month,
    t.settled_at,
    t.settlement_date,
    t.is_settled_or_reversed,
    t.is_reversal_related,
    t.transaction_currency <> t.settlement_currency as is_cross_currency
from transactions t
inner join customer_accounts ca
    on t.account_id = ca.account_id
left join fx_to_eur fx
    on t.transaction_date = fx.rate_date
    and t.transaction_currency = fx.from_currency
