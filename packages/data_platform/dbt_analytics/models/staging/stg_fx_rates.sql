-- =============================================================================
-- Model: stg_fx_rates
-- Grain: One row per daily currency pair quote (rate_id; unique on rate_date + from_currency + to_currency)
-- Source: raw.fx_rates
-- =============================================================================

with source as (
    select
        rate_id,
        rate_date,
        from_currency,
        to_currency,
        mid_rate,
        bid_rate,
        ask_rate,
        rate_source,
        rate_type,
        rate_timestamp,
        created_at
    from {{ source('raw', 'fx_rates') }}
)

select
    cast(rate_id as varchar(64)) as rate_id,
    cast(rate_date as date) as rate_date,
    upper(trim(cast(from_currency as varchar(3)))) as from_currency,
    upper(trim(cast(to_currency as varchar(3)))) as to_currency,
    cast(mid_rate as numeric(18, 6)) as mid_rate,
    cast(bid_rate as numeric(18, 6)) as bid_rate,
    cast(ask_rate as numeric(18, 6)) as ask_rate,
    cast(ask_rate - bid_rate as numeric(18, 6)) as bid_ask_spread,
    cast(rate_source as varchar(64)) as rate_source,
    upper(trim(cast(rate_type as varchar(32)))) as rate_type,
    cast(rate_timestamp as timestamptz) as rate_timestamp,
    cast(created_at as timestamptz) as created_at
from source
