-- =============================================================================
-- Model: dim_date
-- Layer: Marts (Core Dimension)
-- Grain: One row per calendar date (date_day)
-- =============================================================================

with calendar_dates as (
    select distinct
        rate_date as date_day
    from {{ ref('stg_fx_rates') }}
)

select
    date_day,
    cast(extract(year from date_day) as integer) as calendar_year,
    cast(extract(quarter from date_day) as integer) as calendar_quarter,
    cast(extract(month from date_day) as integer) as calendar_month,
    to_char(date_day, 'YYYY-MM') as year_month,
    cast(date_trunc('month', date_day) as date) as first_day_of_month,
    cast(extract(day from date_day) as integer) as day_of_month,
    cast(extract(isodow from date_day) as integer) as iso_day_of_week,
    trim(to_char(date_day, 'Day')) as day_name,
    case
        when extract(isodow from date_day) in (6, 7) then true
        else false
    end as is_weekend
from calendar_dates
