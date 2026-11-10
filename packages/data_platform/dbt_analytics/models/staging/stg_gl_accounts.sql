-- =============================================================================
-- Model: stg_gl_accounts
-- Grain: One row per General Ledger account (gl_account_id)
-- Source: raw.gl_accounts
-- =============================================================================

with source as (
    select
        gl_account_id,
        gl_account_number,
        account_name,
        account_category,
        normal_balance,
        currency,
        description,
        created_at
    from {{ source('raw', 'gl_accounts') }}
)

select
    cast(gl_account_id as varchar(64)) as gl_account_id,
    cast(gl_account_number as varchar(16)) as gl_account_number,
    cast(account_name as varchar(255)) as account_name,
    upper(trim(cast(account_category as varchar(32)))) as account_category,
    upper(trim(cast(normal_balance as varchar(16)))) as normal_balance,
    upper(trim(cast(currency as varchar(3)))) as currency,
    cast(description as text) as description,
    cast(created_at as timestamptz) as created_at
from source
