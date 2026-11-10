-- =============================================================================
-- Model: stg_ledger_entries
-- Grain: One row per double-entry general ledger posting line (entry_id)
-- Source: raw.ledger_entries
-- =============================================================================

with source as (
    select
        entry_id,
        journal_id,
        transaction_id,
        account_id,
        account_type_marker,
        gl_account_id,
        entry_type,
        amount,
        currency,
        original_entry_id,
        posting_status,
        posted_at,
        created_at
    from {{ source('raw', 'ledger_entries') }}
)

select
    cast(entry_id as varchar(64)) as entry_id,
    cast(journal_id as varchar(64)) as journal_id,
    cast(transaction_id as varchar(64)) as transaction_id,
    cast(account_id as varchar(64)) as account_id,
    upper(trim(cast(account_type_marker as varchar(16)))) as account_type_marker,
    cast(gl_account_id as varchar(64)) as gl_account_id,
    upper(trim(cast(entry_type as varchar(16)))) as entry_type,
    cast(amount as numeric(18, 4)) as amount,
    cast(
        case when upper(trim(entry_type)) = 'DEBIT' then amount else 0.0000 end
        as numeric(18, 4)
    ) as debit_amount,
    cast(
        case when upper(trim(entry_type)) = 'CREDIT' then amount else 0.0000 end
        as numeric(18, 4)
    ) as credit_amount,
    cast(
        case when upper(trim(entry_type)) = 'DEBIT' then amount else -amount end
        as numeric(18, 4)
    ) as signed_debit_minus_credit,
    upper(trim(cast(currency as varchar(3)))) as currency,
    cast(original_entry_id as varchar(64)) as original_entry_id,
    upper(trim(cast(posting_status as varchar(32)))) as posting_status,
    cast(posted_at as timestamptz) as posted_at,
    cast(posted_at as date) as posting_date,
    cast(created_at as timestamptz) as created_at
from source
