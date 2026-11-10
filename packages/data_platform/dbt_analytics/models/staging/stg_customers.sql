-- =============================================================================
-- Model: stg_customers
-- Grain: One row per customer (customer_id)
-- Source: raw.customers
-- =============================================================================

with source as (
    select
        customer_id,
        legal_entity_id,
        customer_name,
        customer_segment,
        status,
        onboarding_date,
        created_at
    from {{ source('raw', 'customers') }}
)

select
    cast(customer_id as varchar(64)) as customer_id,
    cast(legal_entity_id as varchar(64)) as legal_entity_id,
    cast(customer_name as varchar(255)) as customer_name,
    upper(trim(cast(customer_segment as varchar(32)))) as customer_segment,
    upper(trim(cast(status as varchar(32)))) as customer_status,
    cast(onboarding_date as date) as onboarding_date,
    cast(created_at as timestamptz) as created_at
from source
