-- =============================================================================
-- Model: fct_customer_revenue
-- Layer: Marts (Finance Fact)
-- Grain: One row per customer_id, reporting_month, currency, and revenue_category
-- Purpose: Governed customer profitability and fee revenue mart preserving
--          native currencies alongside explicit EUR reporting values.
-- =============================================================================

with customer_revenue as (
    select
        customer_id,
        customer_name,
        customer_segment,
        reporting_month,
        currency,
        revenue_category,
        assessment_count,
        active_fee_account_count,
        collection_attempt_count,
        successful_collection_count,
        failed_collection_count,
        gross_assessed_fee_amount,
        waived_fee_amount,
        net_collectible_fee_amount,
        collected_fee_amount,
        outstanding_fee_amount,
        gross_collected_revenue,
        reversed_revenue_amount,
        pass_through_cost_amount,
        net_recognized_revenue,
        gross_assessed_fee_amount_eur,
        waived_fee_amount_eur,
        net_collectible_fee_amount_eur,
        collected_fee_amount_eur,
        outstanding_fee_amount_eur,
        gross_collected_revenue_eur,
        reversed_revenue_amount_eur,
        pass_through_cost_amount_eur,
        net_recognized_revenue_eur
    from {{ ref('int_customer_revenue') }}
)

select
    -- Deterministic composite grain identifier
    concat(
        customer_id,
        '|',
        to_char(reporting_month, 'YYYY-MM'),
        '|',
        currency,
        '|',
        revenue_category
    ) as customer_revenue_id,
    customer_id,
    customer_name,
    customer_segment,
    reporting_month,
    to_char(reporting_month, 'YYYY-MM') as year_month,
    currency,
    revenue_category,
    assessment_count,
    active_fee_account_count,
    collection_attempt_count,
    successful_collection_count,
    failed_collection_count,
    -- Native currency metrics (NUMERIC(18,4))
    gross_assessed_fee_amount,
    waived_fee_amount,
    net_collectible_fee_amount,
    collected_fee_amount,
    outstanding_fee_amount,
    gross_collected_revenue,
    reversed_revenue_amount,
    pass_through_cost_amount,
    net_recognized_revenue,
    -- Explicit EUR reporting metrics (NUMERIC(18,4))
    'EUR' as reporting_currency,
    gross_assessed_fee_amount_eur,
    waived_fee_amount_eur,
    net_collectible_fee_amount_eur,
    collected_fee_amount_eur,
    outstanding_fee_amount_eur,
    gross_collected_revenue_eur,
    reversed_revenue_amount_eur,
    pass_through_cost_amount_eur,
    net_recognized_revenue_eur,
    -- Governed ratios
    cast(
        case
            when net_collectible_fee_amount > 0.0000
                then round(collected_fee_amount / net_collectible_fee_amount, 4)
            else 0.0000
        end
        as numeric(7, 4)
    ) as fee_collection_rate,
    cast(
        case
            when gross_assessed_fee_amount > 0.0000
                then round(waived_fee_amount / gross_assessed_fee_amount, 4)
            else 0.0000
        end
        as numeric(7, 4)
    ) as fee_waiver_rate,
    cast(
        case
            when gross_assessed_fee_amount > 0.0000
                then round((waived_fee_amount + outstanding_fee_amount) / gross_assessed_fee_amount, 4)
            else 0.0000
        end
        as numeric(7, 4)
    ) as total_fee_leakage_rate
from customer_revenue
