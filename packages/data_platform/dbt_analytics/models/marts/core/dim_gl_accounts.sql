-- =============================================================================
-- Model: dim_gl_accounts
-- Layer: Marts (Core Dimension)
-- Grain: One row per General Ledger account (gl_account_id)
-- =============================================================================

with gl_accounts as (
    select
        gl_account_id,
        gl_account_number,
        account_name,
        account_category,
        normal_balance,
        currency,
        description,
        created_at
    from {{ ref('stg_gl_accounts') }}
)

select
    gl_account_id,
    gl_account_number,
    account_name,
    account_category,
    normal_balance,
    currency as default_currency,
    description,
    created_at
from gl_accounts
