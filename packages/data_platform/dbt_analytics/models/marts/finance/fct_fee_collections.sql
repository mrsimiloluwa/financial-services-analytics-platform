-- =============================================================================
-- Model: fct_fee_collections
-- Layer: Marts (Finance Fact)
-- Grain: One row per fee collection attempt (collection_id)
-- =============================================================================

with collections as (
    select
        collection_id,
        assessment_id,
        account_id,
        collection_attempt_number,
        target_amount,
        collected_amount,
        outstanding_amount,
        collection_status,
        failure_reason,
        attempted_at,
        attempted_date,
        settled_at,
        settled_date,
        linked_ledger_entry_id
    from {{ ref('stg_fee_collections') }}
),

assessments as (
    select
        assessment_id,
        transaction_id,
        gross_assessed_amount,
        waived_amount,
        net_collectible_amount,
        assessment_status
    from {{ ref('stg_fee_assessments') }}
),

transactions_context as (
    select
        transaction_id,
        customer_id,
        customer_name,
        customer_segment,
        account_number,
        account_type,
        account_currency,
        transaction_type as fee_type,
        channel
    from {{ ref('int_transactions_enriched') }}
),

recognitions_agg as (
    -- Pure financial aggregation by collection_id (1:0..1 enforced by unique_stg_revenue_recognitions_collection_id)
    select
        collection_id,
        sum(gross_collected_revenue) as gross_collected_revenue,
        sum(reversed_revenue_amount) as reversed_revenue_amount,
        sum(pass_through_cost) as pass_through_cost,
        sum(net_recognized_revenue) as net_recognized_revenue,
        max(recognized_at) as recognized_at,
        max(recognized_date) as recognized_date
    from {{ ref('stg_revenue_recognitions') }}
    group by collection_id
),

ranked_recognitions as (
    select
        collection_id,
        recognition_id,
        row_number() over (
            partition by collection_id
            order by
                recognized_at desc,
                recognition_id desc
        ) as recognition_rank_desc
    from {{ ref('stg_revenue_recognitions') }}
),

recognitions as (
    select
        ra.collection_id,
        rr.recognition_id,
        ra.gross_collected_revenue,
        ra.reversed_revenue_amount,
        ra.pass_through_cost,
        ra.net_recognized_revenue,
        ra.recognized_at,
        ra.recognized_date
    from recognitions_agg ra
    left join ranked_recognitions rr
        on ra.collection_id = rr.collection_id
        and rr.recognition_rank_desc = 1
),

fx_to_eur as (
    select
        rate_date,
        from_currency,
        mid_rate as eur_fx_rate,
        rate_source as eur_fx_rate_source
    from {{ ref('stg_fx_rates') }}
    where to_currency = 'EUR'
)

select
    c.collection_id,
    c.assessment_id,
    a.transaction_id,
    tc.customer_id,
    tc.customer_name,
    tc.customer_segment,
    c.account_id,
    tc.account_number,
    tc.account_type,
    tc.fee_type,
    tc.channel,
    c.collection_attempt_number,
    -- Native currency collection attempt and revenue recognition amounts
    tc.account_currency as currency,
    c.target_amount,
    c.collected_amount,
    c.outstanding_amount,
    r.recognition_id,
    cast(coalesce(r.gross_collected_revenue, 0.0000) as numeric(18, 4)) as gross_collected_revenue,
    cast(coalesce(r.reversed_revenue_amount, 0.0000) as numeric(18, 4)) as reversed_revenue_amount,
    cast(coalesce(r.pass_through_cost, 0.0000) as numeric(18, 4)) as pass_through_cost,
    cast(coalesce(r.net_recognized_revenue, 0.0000) as numeric(18, 4)) as net_recognized_revenue,
    -- Explicit EUR reporting conversion on attempted_date
    'EUR' as reporting_currency,
    fx.eur_fx_rate,
    fx.eur_fx_rate_source,
    cast(round(c.target_amount * fx.eur_fx_rate, 4) as numeric(18, 4)) as target_amount_eur,
    cast(round(c.collected_amount * fx.eur_fx_rate, 4) as numeric(18, 4)) as collected_amount_eur,
    cast(round(c.outstanding_amount * fx.eur_fx_rate, 4) as numeric(18, 4)) as outstanding_amount_eur,
    cast(
        round(coalesce(r.gross_collected_revenue, 0.0000) * fx.eur_fx_rate, 4)
        as numeric(18, 4)
    ) as gross_collected_revenue_eur,
    cast(
        round(coalesce(r.reversed_revenue_amount, 0.0000) * fx.eur_fx_rate, 4)
        as numeric(18, 4)
    ) as reversed_revenue_amount_eur,
    cast(
        round(coalesce(r.pass_through_cost, 0.0000) * fx.eur_fx_rate, 4)
        as numeric(18, 4)
    ) as pass_through_cost_eur,
    cast(
        round(coalesce(r.net_recognized_revenue, 0.0000) * fx.eur_fx_rate, 4)
        as numeric(18, 4)
    ) as net_recognized_revenue_eur,
    -- Statuses, links, and dates
    a.assessment_status,
    c.collection_status,
    c.failure_reason,
    c.linked_ledger_entry_id,
    c.attempted_date,
    cast(date_trunc('month', c.attempted_date) as date) as attempted_month,
    c.settled_date,
    r.recognized_date,
    c.attempted_at,
    c.settled_at,
    r.recognized_at
from collections c
inner join assessments a
    on c.assessment_id = a.assessment_id
inner join transactions_context tc
    on a.transaction_id = tc.transaction_id
left join recognitions r
    on c.collection_id = r.collection_id
left join fx_to_eur fx
    on c.attempted_date = fx.rate_date
    and tc.account_currency = fx.from_currency
