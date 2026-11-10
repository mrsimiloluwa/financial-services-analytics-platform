-- =============================================================================
-- Model: stg_fee_collections
-- Grain: One row per fee collection attempt (collection_id)
-- Source: raw.fee_collections
-- =============================================================================

with source as (
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
        settled_at,
        linked_ledger_entry_id,
        created_at
    from {{ source('raw', 'fee_collections') }}
)

select
    cast(collection_id as varchar(64)) as collection_id,
    cast(assessment_id as varchar(64)) as assessment_id,
    cast(account_id as varchar(64)) as account_id,
    cast(collection_attempt_number as integer) as collection_attempt_number,
    cast(target_amount as numeric(18, 4)) as target_amount,
    cast(collected_amount as numeric(18, 4)) as collected_amount,
    cast(outstanding_amount as numeric(18, 4)) as outstanding_amount,
    upper(trim(cast(collection_status as varchar(32)))) as collection_status,
    cast(failure_reason as varchar(255)) as failure_reason,
    cast(attempted_at as timestamptz) as attempted_at,
    cast(attempted_at as date) as attempted_date,
    cast(settled_at as timestamptz) as settled_at,
    cast(settled_at as date) as settled_date,
    cast(linked_ledger_entry_id as varchar(64)) as linked_ledger_entry_id,
    cast(created_at as timestamptz) as created_at
from source
