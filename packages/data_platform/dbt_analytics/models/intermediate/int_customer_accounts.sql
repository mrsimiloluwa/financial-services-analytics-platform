-- =============================================================================
-- Model: int_customer_accounts
-- Grain: One row per customer bank account (account_id)
-- Purpose: Enrich customer accounts with customer profile, commercial segment,
--          and active overdraft facility terms without fan-out.
-- =============================================================================

with customers as (
    select
        customer_id,
        legal_entity_id,
        customer_name,
        customer_segment,
        customer_status,
        onboarding_date
    from {{ ref('stg_customers') }}
),

accounts as (
    select
        account_id,
        customer_id,
        account_number,
        account_type,
        account_currency,
        opening_balance,
        reserved_funds,
        initial_available_balance,
        account_status,
        opened_at,
        opened_date
    from {{ ref('stg_accounts') }}
),

overdraft_agg as (
    -- Pre-aggregate overdraft facilities per account_id to prevent fan-out
    select
        account_id,
        count(facility_id) as facility_count,
        max(facility_id) as primary_facility_id,
        sum(authorized_limit) as total_authorized_overdraft_limit,
        max(standard_interest_rate) as max_standard_interest_rate,
        max(unauthorized_penalty_rate) as max_unauthorized_penalty_rate,
        min(effective_start_date) as earliest_facility_start_date,
        max(effective_end_date) as latest_facility_end_date
    from {{ ref('stg_overdraft_facilities') }}
    group by account_id
)

select
    a.account_id,
    a.account_number,
    a.account_type,
    a.account_currency,
    a.opening_balance,
    a.reserved_funds,
    a.initial_available_balance,
    a.account_status,
    a.opened_at,
    a.opened_date,
    c.customer_id,
    c.legal_entity_id,
    c.customer_name,
    c.customer_segment,
    c.customer_status,
    c.onboarding_date,
    coalesce(od.facility_count, 0) > 0 as has_overdraft_facility,
    coalesce(od.facility_count, 0) as overdraft_facility_count,
    od.primary_facility_id,
    cast(coalesce(od.total_authorized_overdraft_limit, 0.0000) as numeric(18, 4)) as authorized_overdraft_limit,
    cast(
        a.initial_available_balance + coalesce(od.total_authorized_overdraft_limit, 0.0000)
        as numeric(18, 4)
    ) as initial_total_liquidity,
    od.max_standard_interest_rate as standard_interest_rate,
    od.max_unauthorized_penalty_rate as unauthorized_penalty_rate,
    od.earliest_facility_start_date,
    od.latest_facility_end_date
from accounts a
inner join customers c
    on a.customer_id = c.customer_id
left join overdraft_agg od
    on a.account_id = od.account_id
