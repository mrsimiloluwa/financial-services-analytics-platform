-- =============================================================================
-- Singular Test: assert_fx_rate_spread_ordering
-- Invariant: Every FX quote must satisfy 0 < bid_rate <= mid_rate <= ask_rate,
--            and identity pairs (from_currency = to_currency) must equal 1.000000.
-- =============================================================================

select
    rate_id,
    rate_date,
    from_currency,
    to_currency,
    bid_rate,
    mid_rate,
    ask_rate
from {{ ref('stg_fx_rates') }}
where bid_rate <= 0.000000
   or mid_rate <= 0.000000
   or ask_rate <= 0.000000
   or bid_rate > mid_rate
   or mid_rate > ask_rate
   or (from_currency = to_currency and mid_rate <> 1.000000)
