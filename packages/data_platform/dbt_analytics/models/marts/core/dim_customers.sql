-- =============================================================================
-- Model: dim_customers
-- Layer: Marts (Core Dimension)
-- Grain: One row per customer (customer_id)
-- =============================================================================

with customers as (
    select
        customer_id,
        legal_entity_id,
        customer_name,
        customer_segment,
        customer_status,
        onboarding_date,
        created_at
    from {{ ref('stg_customers') }}
),

account_summary as (
    select
        customer_id,
        count(account_id) as total_accounts,
        count(case when account_status = 'ACTIVE' then 1 end) as active_accounts,
        count(distinct account_currency) as distinct_currencies_count,
        string_agg(distinct account_currency, ', ' order by account_currency) as currencies_held,
        sum(case when has_overdraft_facility then 1 else 0 end) as accounts_with_overdraft_count
    from {{ ref('int_customer_accounts') }}
    group by customer_id
),

transaction_summary as (
    select
        customer_id,
        count(transaction_id) as total_transactions_initiated,
        count(case when transaction_status = 'SETTLED' then 1 end) as settled_transactions_count,
        min(transaction_date) as first_transaction_date,
        max(transaction_date) as last_transaction_date
    from {{ ref('int_transactions_enriched') }}
    group by customer_id
)

select
    c.customer_id,
    c.legal_entity_id,
    c.customer_name,
    c.customer_segment,
    c.customer_status,
    c.onboarding_date,
    coalesce(a.total_accounts, 0) as total_accounts,
    coalesce(a.active_accounts, 0) as active_accounts,
    coalesce(a.distinct_currencies_count, 0) as distinct_currencies_count,
    a.currencies_held,
    coalesce(a.accounts_with_overdraft_count, 0) as accounts_with_overdraft_count,
    coalesce(t.total_transactions_initiated, 0) as total_transactions_initiated,
    coalesce(t.settled_transactions_count, 0) as settled_transactions_count,
    t.first_transaction_date,
    t.last_transaction_date,
    c.created_at
from customers c
left join account_summary a
    on c.customer_id = a.customer_id
left join transaction_summary t
    on c.customer_id = t.customer_id
