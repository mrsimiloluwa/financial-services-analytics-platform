-- =============================================================================
-- Model: int_fee_lifecycle
-- Grain: One row per fee assessment (assessment_id)
-- Purpose: Reconcile the end-to-end fee lifecycle from assessment through
--          collection attempts and revenue recognition without join fan-out.
--          Clearly separates gross assessed, waived, net collectible,
--          collected, outstanding, reversed, pass-through costs, and net revenue.
-- =============================================================================

with assessments as (
    select
        assessment_id,
        transaction_id,
        account_id,
        gross_assessed_amount,
        waived_amount,
        waiver_reason,
        net_collectible_amount,
        assessment_status,
        assessed_at,
        assessed_date
    from {{ ref('stg_fee_assessments') }}
),

-- Pre-aggregate collection attempts + revenue recognitions at collection_id level first,
-- then roll up to assessment_id to prevent fan-out when an assessment has multiple attempts.
collections_with_rev as (
    select
        fc.collection_id,
        fc.assessment_id,
        fc.account_id,
        fc.collection_attempt_number,
        fc.target_amount,
        fc.collected_amount,
        fc.outstanding_amount,
        fc.collection_status,
        fc.failure_reason,
        fc.attempted_at,
        fc.settled_at,
        fc.linked_ledger_entry_id,
        rr.recognition_id,
        coalesce(rr.gross_collected_revenue, 0.0000) as gross_collected_revenue,
        coalesce(rr.reversed_revenue_amount, 0.0000) as reversed_revenue_amount,
        coalesce(rr.pass_through_cost, 0.0000) as pass_through_cost,
        coalesce(rr.net_recognized_revenue, 0.0000) as net_recognized_revenue,
        rr.recognized_at
    from {{ ref('stg_fee_collections') }} fc
    left join {{ ref('stg_revenue_recognitions') }} rr
        on fc.collection_id = rr.collection_id
),

assessment_collections_agg as (
    select
        assessment_id,
        count(collection_id) as total_collection_attempts,
        count(case when collection_status in ('SETTLED', 'PARTIAL') then 1 end) as successful_collection_attempts,
        count(case when collection_status = 'FAILED' then 1 end) as failed_collection_attempts,
        max(collection_id) as latest_collection_id,
        max(recognition_id) as latest_recognition_id,
        max(linked_ledger_entry_id) as linked_ledger_entry_id,
        sum(
            case
                when collection_status in ('SETTLED', 'PARTIAL', 'REVERSED') then collected_amount
                else 0.0000
            end
        ) as total_collected_amount,
        sum(gross_collected_revenue) as total_gross_collected_revenue,
        sum(reversed_revenue_amount) as total_reversed_amount,
        sum(pass_through_cost) as total_pass_through_cost,
        sum(net_recognized_revenue) as total_net_recognized_revenue,
        max(collection_status) as latest_collection_status,
        max(failure_reason) as latest_failure_reason,
        min(attempted_at) as first_attempted_at,
        max(attempted_at) as last_attempted_at,
        max(settled_at) as settled_at,
        max(recognized_at) as recognized_at
    from collections_with_rev
    group by assessment_id
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
        transaction_type,
        channel,
        transaction_amount,
        transaction_currency,
        transaction_status,
        transaction_date
    from {{ ref('int_transactions_enriched') }}
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
    a.assessment_id,
    a.transaction_id,
    tc.customer_id,
    tc.customer_name,
    tc.customer_segment,
    a.account_id,
    tc.account_number,
    tc.account_type,
    -- Fee type corresponds to the underlying transaction product schedule
    tc.transaction_type as fee_type,
    tc.channel,
    tc.transaction_status,
    -- Fee is assessed and swept in the account/transaction denomination currency
    tc.account_currency as currency,
    -- Original currency measures (NUMERIC(18,4))
    cast(a.gross_assessed_amount as numeric(18, 4)) as gross_assessed_amount,
    cast(a.waived_amount as numeric(18, 4)) as waived_amount,
    a.waiver_reason,
    cast(a.net_collectible_amount as numeric(18, 4)) as net_collectible_amount,
    cast(coalesce(ac.total_collected_amount, 0.0000) as numeric(18, 4)) as collected_amount,
    cast(
        a.net_collectible_amount - coalesce(ac.total_collected_amount, 0.0000)
        as numeric(18, 4)
    ) as outstanding_amount,
    cast(coalesce(ac.total_gross_collected_revenue, 0.0000) as numeric(18, 4)) as gross_collected_revenue,
    cast(coalesce(ac.total_reversed_amount, 0.0000) as numeric(18, 4)) as reversed_amount,
    cast(coalesce(ac.total_pass_through_cost, 0.0000) as numeric(18, 4)) as pass_through_cost,
    cast(coalesce(ac.total_net_recognized_revenue, 0.0000) as numeric(18, 4)) as net_recognized_revenue,
    -- Explicit EUR reporting conversion via stg_fx_rates on assessed_date
    fx.eur_fx_rate,
    fx.eur_fx_rate_source,
    cast(round(a.gross_assessed_amount * fx.eur_fx_rate, 4) as numeric(18, 4)) as gross_assessed_amount_eur,
    cast(round(a.waived_amount * fx.eur_fx_rate, 4) as numeric(18, 4)) as waived_amount_eur,
    cast(round(a.net_collectible_amount * fx.eur_fx_rate, 4) as numeric(18, 4)) as net_collectible_amount_eur,
    cast(
        round(coalesce(ac.total_collected_amount, 0.0000) * fx.eur_fx_rate, 4)
        as numeric(18, 4)
    ) as collected_amount_eur,
    cast(
        round(
            (a.net_collectible_amount - coalesce(ac.total_collected_amount, 0.0000)) * fx.eur_fx_rate,
            4
        )
        as numeric(18, 4)
    ) as outstanding_amount_eur,
    cast(
        round(coalesce(ac.total_reversed_amount, 0.0000) * fx.eur_fx_rate, 4)
        as numeric(18, 4)
    ) as reversed_amount_eur,
    cast(
        round(coalesce(ac.total_pass_through_cost, 0.0000) * fx.eur_fx_rate, 4)
        as numeric(18, 4)
    ) as pass_through_cost_eur,
    cast(
        round(coalesce(ac.total_net_recognized_revenue, 0.0000) * fx.eur_fx_rate, 4)
        as numeric(18, 4)
    ) as net_recognized_revenue_eur,
    -- Collection attempt metadata & statuses
    coalesce(ac.total_collection_attempts, 0) as total_collection_attempts,
    coalesce(ac.successful_collection_attempts, 0) as successful_collection_attempts,
    coalesce(ac.failed_collection_attempts, 0) as failed_collection_attempts,
    ac.latest_collection_id,
    ac.latest_recognition_id,
    ac.linked_ledger_entry_id,
    a.assessment_status,
    coalesce(ac.latest_collection_status, 'UNATTEMPTED') as collection_status,
    ac.latest_failure_reason as failure_reason,
    case
        when a.assessment_status = 'WAIVED_IN_FULL' then 'WAIVED_IN_FULL'
        when coalesce(ac.total_reversed_amount, 0.0000) > 0.0000 then 'REVERSED'
        when coalesce(ac.total_collected_amount, 0.0000) = a.net_collectible_amount
            and a.net_collectible_amount > 0.0000 then 'COLLECTED_IN_FULL'
        when coalesce(ac.total_collected_amount, 0.0000) > 0.0000
            and coalesce(ac.total_collected_amount, 0.0000) < a.net_collectible_amount then 'PARTIALLY_COLLECTED'
        when coalesce(ac.failed_collection_attempts, 0) > 0 then 'COLLECTION_FAILED_ARREARS'
        else 'PENDING_COLLECTION'
    end as lifecycle_status,
    a.assessed_at,
    a.assessed_date,
    cast(date_trunc('month', a.assessed_date) as date) as assessed_month,
    ac.first_attempted_at,
    ac.last_attempted_at,
    ac.settled_at,
    ac.recognized_at
from assessments a
inner join transactions_context tc
    on a.transaction_id = tc.transaction_id
left join assessment_collections_agg ac
    on a.assessment_id = ac.assessment_id
left join fx_to_eur fx
    on a.assessed_date = fx.rate_date
    and tc.account_currency = fx.from_currency
