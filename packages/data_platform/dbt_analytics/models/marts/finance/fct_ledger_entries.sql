-- =============================================================================
-- Model: fct_ledger_entries
-- Layer: Marts (Finance Fact)
-- Grain: One row per double-entry general ledger posting line (entry_id)
-- =============================================================================

with ledger_entries as (
    select
        entry_id,
        journal_id,
        transaction_id,
        account_id,
        account_type_marker,
        gl_account_id,
        entry_type,
        amount,
        debit_amount,
        credit_amount,
        signed_debit_minus_credit,
        currency,
        original_entry_id,
        posting_status,
        posted_at,
        posting_date
    from {{ ref('stg_ledger_entries') }}
),

journals as (
    select
        journal_id,
        journal_type,
        description as journal_description,
        journal_created_at,
        journal_date
    from {{ ref('stg_journals') }}
),

gl_accounts as (
    select
        gl_account_id,
        gl_account_number,
        account_name as gl_account_name,
        account_category as gl_account_category,
        normal_balance as gl_normal_balance
    from {{ ref('stg_gl_accounts') }}
),

customer_accounts as (
    select
        account_id,
        customer_id,
        customer_name,
        customer_segment,
        account_type as customer_account_type
    from {{ ref('int_customer_accounts') }}
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
    le.entry_id,
    le.journal_id,
    j.journal_type,
    j.journal_description,
    le.transaction_id,
    le.account_id,
    le.account_type_marker,
    ca.customer_id,
    ca.customer_name,
    ca.customer_segment,
    ca.customer_account_type,
    le.gl_account_id,
    gl.gl_account_number,
    gl.gl_account_name,
    gl.gl_account_category,
    gl.gl_normal_balance,
    le.entry_type,
    -- Separate debit and credit amounts in native posting currency
    le.currency,
    le.amount,
    le.debit_amount,
    le.credit_amount,
    le.signed_debit_minus_credit,
    -- Explicit EUR reporting conversion via daily ECB mid-rate on posting_date
    'EUR' as reporting_currency,
    fx.eur_fx_rate,
    fx.eur_fx_rate_source,
    cast(round(le.amount * fx.eur_fx_rate, 4) as numeric(18, 4)) as amount_eur,
    cast(round(le.debit_amount * fx.eur_fx_rate, 4) as numeric(18, 4)) as debit_amount_eur,
    cast(round(le.credit_amount * fx.eur_fx_rate, 4) as numeric(18, 4)) as credit_amount_eur,
    le.original_entry_id,
    le.posting_status,
    le.posting_date,
    cast(date_trunc('month', le.posting_date) as date) as posting_month,
    le.posted_at,
    j.journal_created_at
from ledger_entries le
inner join journals j
    on le.journal_id = j.journal_id
inner join gl_accounts gl
    on le.gl_account_id = gl.gl_account_id
left join customer_accounts ca
    on le.account_id = ca.account_id
    and le.account_type_marker = 'CUSTOMER'
left join fx_to_eur fx
    on le.posting_date = fx.rate_date
    and le.currency = fx.from_currency
