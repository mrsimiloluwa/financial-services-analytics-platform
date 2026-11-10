-- =============================================================================
-- Model: stg_transactions
-- Grain: One row per commercial transaction (transaction_id)
-- Source: raw.transactions
-- =============================================================================

with source as (
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
        status,
        original_transaction_id,
        journal_id,
        initiated_at,
        settled_at,
        created_at
    from {{ source('raw', 'transactions') }}
)

select
    cast(transaction_id as varchar(64)) as transaction_id,
    cast(account_id as varchar(64)) as account_id,
    cast(counterparty_account_id as varchar(64)) as counterparty_account_id,
    upper(trim(cast(transaction_type as varchar(32)))) as transaction_type,
    upper(trim(cast(channel as varchar(32)))) as channel,
    upper(trim(cast(direction as varchar(16)))) as direction,
    cast(transaction_amount as numeric(18, 4)) as transaction_amount,
    upper(trim(cast(transaction_currency as varchar(3)))) as transaction_currency,
    upper(trim(cast(settlement_currency as varchar(3)))) as settlement_currency,
    cast(customer_fx_rate as numeric(18, 6)) as customer_fx_rate,
    cast(base_currency_amount as numeric(18, 4)) as base_currency_amount,
    upper(trim(cast(status as varchar(32)))) as transaction_status,
    cast(original_transaction_id as varchar(64)) as original_transaction_id,
    cast(journal_id as varchar(64)) as journal_id,
    cast(initiated_at as timestamptz) as initiated_at,
    cast(initiated_at as date) as transaction_date,
    cast(settled_at as timestamptz) as settled_at,
    cast(settled_at as date) as settlement_date,
    case
        when upper(trim(status)) in ('SETTLED', 'REVERSED') then true
        else false
    end as is_settled_or_reversed,
    case
        when original_transaction_id is not null or upper(trim(status)) = 'REVERSED' then true
        else false
    end as is_reversal_related,
    cast(created_at as timestamptz) as created_at
from source
