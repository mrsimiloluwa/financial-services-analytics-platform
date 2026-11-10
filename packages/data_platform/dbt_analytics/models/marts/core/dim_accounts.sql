-- =============================================================================
-- Model: dim_accounts
-- Layer: Marts (Core Dimension)
-- Grain: One row per customer bank account (account_id)
-- =============================================================================

with customer_accounts as (
    select
        account_id,
        account_number,
        account_type,
        account_currency,
        opening_balance,
        reserved_funds,
        initial_available_balance,
        account_status,
        opened_at,
        opened_date,
        customer_id,
        legal_entity_id,
        customer_name,
        customer_segment,
        customer_status,
        has_overdraft_facility,
        overdraft_facility_count,
        primary_facility_id,
        authorized_overdraft_limit,
        initial_total_liquidity,
        standard_interest_rate,
        unauthorized_penalty_rate,
        earliest_facility_start_date,
        latest_facility_end_date
    from {{ ref('int_customer_accounts') }}
),

subledger_movements as (
    -- Subledger customer deposit movements in native account currency
    -- For GL_LIAB_CUSTOMER_DEPOSITS (normal_balance = CREDIT):
    -- CREDIT increases customer balance, DEBIT decreases customer balance.
    select
        account_id,
        currency,
        count(entry_id) as subledger_posting_count,
        sum(credit_amount) as total_credits_posted,
        sum(debit_amount) as total_debits_posted,
        sum(credit_amount - debit_amount) as net_subledger_movement
    from {{ ref('stg_ledger_entries') }}
    where account_type_marker = 'CUSTOMER'
    group by
        account_id,
        currency
)

select
    ca.account_id,
    ca.account_number,
    ca.customer_id,
    ca.legal_entity_id,
    ca.customer_name,
    ca.customer_segment,
    ca.customer_status,
    ca.account_type,
    ca.account_currency,
    ca.account_status,
    ca.opening_balance,
    ca.reserved_funds,
    ca.initial_available_balance,
    ca.has_overdraft_facility,
    ca.overdraft_facility_count,
    ca.primary_facility_id,
    ca.authorized_overdraft_limit,
    ca.initial_total_liquidity,
    ca.standard_interest_rate,
    ca.unauthorized_penalty_rate,
    ca.earliest_facility_start_date,
    ca.latest_facility_end_date,
    coalesce(sm.subledger_posting_count, 0) as subledger_posting_count,
    cast(coalesce(sm.total_credits_posted, 0.0000) as numeric(18, 4)) as total_credits_posted,
    cast(coalesce(sm.total_debits_posted, 0.0000) as numeric(18, 4)) as total_debits_posted,
    cast(coalesce(sm.net_subledger_movement, 0.0000) as numeric(18, 4)) as net_subledger_movement,
    cast(
        ca.opening_balance + coalesce(sm.net_subledger_movement, 0.0000)
        as numeric(18, 4)
    ) as closing_ledger_balance,
    ca.opened_at,
    ca.opened_date
from customer_accounts ca
left join subledger_movements sm
    on ca.account_id = sm.account_id
    and ca.account_currency = sm.currency
