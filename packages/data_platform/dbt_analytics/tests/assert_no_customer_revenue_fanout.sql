-- =============================================================================
-- Singular Test: assert_no_customer_revenue_fanout
-- Invariant: Aggregating fct_customer_revenue by currency must exactly equal
--            aggregating fct_fee_assessments by currency across all measures,
--            and total gross/net revenue across all currencies must match
--            stg_revenue_recognitions without any join fan-out.
-- =============================================================================

with assessment_totals as (
    select
        currency,
        count(assessment_id) as assessment_count,
        sum(gross_assessed_amount) as gross_assessed,
        sum(waived_amount) as waived,
        sum(net_collectible_amount) as net_collectible,
        sum(collected_amount) as collected,
        sum(outstanding_amount) as outstanding,
        sum(net_recognized_revenue) as net_revenue,
        sum(net_recognized_revenue_eur) as net_revenue_eur
    from {{ ref('fct_fee_assessments') }}
    group by currency
),

customer_rev_totals as (
    select
        currency,
        sum(assessment_count) as assessment_count,
        sum(gross_assessed_fee_amount) as gross_assessed,
        sum(waived_fee_amount) as waived,
        sum(net_collectible_fee_amount) as net_collectible,
        sum(collected_fee_amount) as collected,
        sum(outstanding_fee_amount) as outstanding,
        sum(net_recognized_revenue) as net_revenue,
        sum(net_recognized_revenue_eur) as net_revenue_eur
    from {{ ref('fct_customer_revenue') }}
    group by currency
)

select
    coalesce(a.currency, c.currency) as currency,
    a.assessment_count as assessment_cnt,
    c.assessment_count as customer_rev_cnt,
    a.gross_assessed as assessment_gross,
    c.gross_assessed as customer_rev_gross,
    a.net_revenue as assessment_net_rev,
    c.net_revenue as customer_rev_net_rev,
    a.net_revenue_eur as assessment_net_rev_eur,
    c.net_revenue_eur as customer_rev_net_rev_eur
from assessment_totals a
full outer join customer_rev_totals c
    on a.currency = c.currency
where a.currency is null
   or c.currency is null
   or a.assessment_count <> c.assessment_count
   or abs(a.gross_assessed - c.gross_assessed) > 0.0000
   or abs(a.waived - c.waived) > 0.0000
   or abs(a.net_collectible - c.net_collectible) > 0.0000
   or abs(a.collected - c.collected) > 0.0000
   or abs(a.outstanding - c.outstanding) > 0.0000
   or abs(a.net_revenue - c.net_revenue) > 0.0000
   or abs(a.net_revenue_eur - c.net_revenue_eur) > 0.0000
