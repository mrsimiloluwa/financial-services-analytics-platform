-- =============================================================================
-- Singular Test: assert_no_missing_fx_rates_in_marts
-- Invariant: Every row in fct_transactions, fct_ledger_entries,
--            fct_fee_assessments, and fct_fee_collections must have a valid,
--            non-null, positive EUR conversion rate from stg_fx_rates.
-- =============================================================================

with missing_txn_fx as (
    select
        'fct_transactions' as model_name,
        transaction_id as record_id,
        transaction_currency as currency,
        transaction_date as effective_date,
        reporting_eur_fx_rate as fx_rate
    from {{ ref('fct_transactions') }}
    where reporting_eur_fx_rate is null
       or reporting_eur_fx_rate <= 0.000000
       or (transaction_currency <> 'EUR' and reporting_eur_fx_rate = 1.000000)
),

missing_ledger_fx as (
    select
        'fct_ledger_entries' as model_name,
        entry_id as record_id,
        currency,
        posting_date as effective_date,
        eur_fx_rate as fx_rate
    from {{ ref('fct_ledger_entries') }}
    where eur_fx_rate is null
       or eur_fx_rate <= 0.000000
       or (currency <> 'EUR' and eur_fx_rate = 1.000000)
),

missing_assessment_fx as (
    select
        'fct_fee_assessments' as model_name,
        assessment_id as record_id,
        currency,
        assessed_date as effective_date,
        eur_fx_rate as fx_rate
    from {{ ref('fct_fee_assessments') }}
    where eur_fx_rate is null
       or eur_fx_rate <= 0.000000
       or (currency <> 'EUR' and eur_fx_rate = 1.000000)
),

missing_collection_fx as (
    select
        'fct_fee_collections' as model_name,
        collection_id as record_id,
        currency,
        attempted_date as effective_date,
        eur_fx_rate as fx_rate
    from {{ ref('fct_fee_collections') }}
    where eur_fx_rate is null
       or eur_fx_rate <= 0.000000
       or (currency <> 'EUR' and eur_fx_rate = 1.000000)
)

select * from missing_txn_fx
union all
select * from missing_ledger_fx
union all
select * from missing_assessment_fx
union all
select * from missing_collection_fx
