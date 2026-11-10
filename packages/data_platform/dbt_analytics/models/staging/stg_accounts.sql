-- =============================================================================
-- Model: stg_accounts
-- Grain: One row per customer bank account (account_id)
-- Source: raw.accounts
-- =============================================================================

with source as (
    select
        account_id,
        customer_id,
        account_number,
        account_type,
        currency,
        opening_balance,
        reserved_funds,
        status,
        opened_at,
        created_at
    from {{ source('raw', 'accounts') }}
)

select
    cast(account_id as varchar(64)) as account_id,
    cast(customer_id as varchar(64)) as customer_id,
    cast(account_number as varchar(64)) as account_number,
    upper(trim(cast(account_type as varchar(32)))) as account_type,
    upper(trim(cast(currency as varchar(3)))) as account_currency,
    cast(opening_balance as numeric(18, 4)) as opening_balance,
    cast(reserved_funds as numeric(18, 4)) as reserved_funds,
    cast(opening_balance - reserved_funds as numeric(18, 4)) as initial_available_balance,
    upper(trim(cast(status as varchar(32)))) as account_status,
    cast(opened_at as timestamptz) as opened_at,
    cast(opened_at as date) as opened_date,
    cast(created_at as timestamptz) as created_at
from source
