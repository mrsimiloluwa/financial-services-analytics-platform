-- =============================================================================
-- Model: stg_journals
-- Grain: One row per accounting journal header (journal_id)
-- Source: raw.journals
-- =============================================================================

with source as (
    select
        journal_id,
        transaction_id,
        journal_type,
        description,
        created_at
    from {{ source('raw', 'journals') }}
)

select
    cast(journal_id as varchar(64)) as journal_id,
    cast(transaction_id as varchar(64)) as transaction_id,
    upper(trim(cast(journal_type as varchar(32)))) as journal_type,
    cast(description as varchar(255)) as description,
    cast(created_at as timestamptz) as journal_created_at,
    cast(created_at as date) as journal_date
from source
