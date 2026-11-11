-- =============================================================================
-- Model: int_customer_revenue
-- Grain: One row per customer_id, reporting_month, currency, and revenue_category
-- Purpose: Aggregate customer fee assessments, waivers, collections, arrears,
--          reversals, pass-through costs, and net recognized revenue by native
--          currency and explicit EUR reporting value without cross-currency mixing.
-- =============================================================================

with fee_lifecycle as (
    select
        assessment_id,
        transaction_id,
        customer_id,
        customer_name,
        customer_segment,
        account_id,
        fee_type as revenue_category,
        currency,
        assessed_month as reporting_month,
        gross_assessed_amount,
        waived_amount,
        net_collectible_amount,
        collected_amount,
        outstanding_amount,
        gross_collected_revenue,
        reversed_amount,
        pass_through_cost,
        net_recognized_revenue,
        gross_assessed_amount_eur,
        waived_amount_eur,
        net_collectible_amount_eur,
        collected_amount_eur,
        outstanding_amount_eur,
        gross_collected_revenue_eur,
        reversed_amount_eur,
        pass_through_cost_eur,
        net_recognized_revenue_eur,
        total_collection_attempts,
        successful_collection_attempts,
        failed_collection_attempts
    from {{ ref('int_fee_lifecycle') }}
)

select
    customer_id,
    customer_name,
    customer_segment,
    reporting_month,
    currency,
    revenue_category,
    count(assessment_id) as assessment_count,
    count(distinct account_id) as active_fee_account_count,
    sum(total_collection_attempts) as collection_attempt_count,
    sum(successful_collection_attempts) as successful_collection_count,
    sum(failed_collection_attempts) as failed_collection_count,
    -- Native currency metrics (never mixed across currencies)
    cast(sum(gross_assessed_amount) as numeric(18, 4)) as gross_assessed_fee_amount,
    cast(sum(waived_amount) as numeric(18, 4)) as waived_fee_amount,
    cast(sum(net_collectible_amount) as numeric(18, 4)) as net_collectible_fee_amount,
    cast(sum(collected_amount) as numeric(18, 4)) as collected_fee_amount,
    cast(sum(outstanding_amount) as numeric(18, 4)) as outstanding_fee_amount,
    cast(sum(gross_collected_revenue) as numeric(18, 4)) as gross_collected_revenue,
    cast(sum(reversed_amount) as numeric(18, 4)) as reversed_revenue_amount,
    cast(sum(pass_through_cost) as numeric(18, 4)) as pass_through_cost_amount,
    cast(sum(net_recognized_revenue) as numeric(18, 4)) as net_recognized_revenue,
    -- Explicit EUR reporting equivalents (converted at daily ECB mid-rate per assessment)
    cast(sum(gross_assessed_amount_eur) as numeric(18, 4)) as gross_assessed_fee_amount_eur,
    cast(sum(waived_amount_eur) as numeric(18, 4)) as waived_fee_amount_eur,
    cast(sum(net_collectible_amount_eur) as numeric(18, 4)) as net_collectible_fee_amount_eur,
    cast(sum(collected_amount_eur) as numeric(18, 4)) as collected_fee_amount_eur,
    cast(sum(outstanding_amount_eur) as numeric(18, 4)) as outstanding_fee_amount_eur,
    cast(sum(gross_collected_revenue_eur) as numeric(18, 4)) as gross_collected_revenue_eur,
    cast(sum(reversed_amount_eur) as numeric(18, 4)) as reversed_revenue_amount_eur,
    cast(sum(pass_through_cost_eur) as numeric(18, 4)) as pass_through_cost_amount_eur,
    cast(sum(net_recognized_revenue_eur) as numeric(18, 4)) as net_recognized_revenue_eur
from fee_lifecycle
group by
    customer_id,
    customer_name,
    customer_segment,
    reporting_month,
    currency,
    revenue_category
