-- =============================================================================
-- Singular Test: assert_revenue_recognition_equation
-- Invariant: Across all fee assessments, collections, and customer revenue marts:
--            net_recognized_revenue = gross_collected_revenue
--                                   - reversed_revenue_amount
--                                   - pass_through_cost
--            and gross_collected_revenue = collected_amount for settled collections.
-- =============================================================================

with invalid_assessments as (
    select
        'fct_fee_assessments' as model_name,
        assessment_id as record_id,
        gross_collected_revenue,
        reversed_amount as reversed_revenue_amount,
        pass_through_cost,
        net_recognized_revenue
    from {{ ref('fct_fee_assessments') }}
    where abs(
        net_recognized_revenue
        - (gross_collected_revenue - reversed_amount - pass_through_cost)
    ) > 0.0000
       or abs(gross_collected_revenue - collected_amount) > 0.0000
),

invalid_collections as (
    select
        'fct_fee_collections' as model_name,
        collection_id as record_id,
        gross_collected_revenue,
        reversed_revenue_amount,
        pass_through_cost,
        net_recognized_revenue
    from {{ ref('fct_fee_collections') }}
    where abs(
        net_recognized_revenue
        - (gross_collected_revenue - reversed_revenue_amount - pass_through_cost)
    ) > 0.0000
       or (collection_status in ('SETTLED', 'PARTIAL') and abs(gross_collected_revenue - collected_amount) > 0.0000)
),

invalid_customer_revenue as (
    select
        'fct_customer_revenue' as model_name,
        customer_revenue_id as record_id,
        gross_collected_revenue,
        reversed_revenue_amount,
        pass_through_cost_amount as pass_through_cost,
        net_recognized_revenue
    from {{ ref('fct_customer_revenue') }}
    where abs(
        net_recognized_revenue
        - (gross_collected_revenue - reversed_revenue_amount - pass_through_cost_amount)
    ) > 0.0000
)

select * from invalid_assessments
union all
select * from invalid_collections
union all
select * from invalid_customer_revenue
