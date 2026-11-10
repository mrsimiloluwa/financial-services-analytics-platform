-- =============================================================================
-- Model: stg_overdraft_facilities
-- Grain: One row per overdraft facility agreement (facility_id)
-- Source: raw.overdraft_facilities
-- =============================================================================

with source as (
    select
        facility_id,
        account_id,
        authorized_limit,
        standard_interest_rate,
        unauthorized_penalty_rate,
        effective_start_date,
        effective_end_date,
        created_at
    from {{ source('raw', 'overdraft_facilities') }}
)

select
    cast(facility_id as varchar(64)) as facility_id,
    cast(account_id as varchar(64)) as account_id,
    cast(authorized_limit as numeric(18, 4)) as authorized_limit,
    cast(standard_interest_rate as numeric(7, 4)) as standard_interest_rate,
    cast(unauthorized_penalty_rate as numeric(7, 4)) as unauthorized_penalty_rate,
    cast(effective_start_date as date) as effective_start_date,
    cast(effective_end_date as date) as effective_end_date,
    cast(created_at as timestamptz) as created_at
from source
