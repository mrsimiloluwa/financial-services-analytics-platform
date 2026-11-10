-- =============================================================================
-- Model: stg_revenue_recognitions
-- Grain: One row per accounting revenue recognition entry (recognition_id)
-- Source: raw.revenue_recognitions
-- =============================================================================

with source as (
    select
        recognition_id,
        collection_id,
        gross_collected_revenue,
        reversed_revenue_amount,
        pass_through_cost,
        net_recognized_revenue,
        recognized_at,
        created_at
    from {{ source('raw', 'revenue_recognitions') }}
)

select
    cast(recognition_id as varchar(64)) as recognition_id,
    cast(collection_id as varchar(64)) as collection_id,
    cast(gross_collected_revenue as numeric(18, 4)) as gross_collected_revenue,
    cast(reversed_revenue_amount as numeric(18, 4)) as reversed_revenue_amount,
    cast(pass_through_cost as numeric(18, 4)) as pass_through_cost,
    cast(net_recognized_revenue as numeric(18, 4)) as net_recognized_revenue,
    cast(recognized_at as timestamptz) as recognized_at,
    cast(recognized_at as date) as recognized_date,
    cast(created_at as timestamptz) as created_at
from source
