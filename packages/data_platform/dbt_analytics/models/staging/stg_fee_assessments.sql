-- =============================================================================
-- Model: stg_fee_assessments
-- Grain: One row per transaction fee assessment (assessment_id)
-- Source: raw.fee_assessments
-- =============================================================================

with source as (
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
        created_at
    from {{ source('raw', 'fee_assessments') }}
)

select
    cast(assessment_id as varchar(64)) as assessment_id,
    cast(transaction_id as varchar(64)) as transaction_id,
    cast(account_id as varchar(64)) as account_id,
    cast(gross_assessed_amount as numeric(18, 4)) as gross_assessed_amount,
    cast(waived_amount as numeric(18, 4)) as waived_amount,
    cast(waiver_reason as varchar(255)) as waiver_reason,
    cast(net_collectible_amount as numeric(18, 4)) as net_collectible_amount,
    upper(trim(cast(assessment_status as varchar(32)))) as assessment_status,
    cast(assessed_at as timestamptz) as assessed_at,
    cast(assessed_at as date) as assessed_date,
    cast(created_at as timestamptz) as created_at
from source
