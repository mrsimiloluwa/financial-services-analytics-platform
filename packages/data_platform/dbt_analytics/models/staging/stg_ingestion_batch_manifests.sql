-- =============================================================================
-- Model: stg_ingestion_batch_manifests
-- Grain: One row per ingestion batch manifest (batch_id)
-- Source: raw.ingestion_batch_manifests
-- =============================================================================

with source as (
    select
        batch_id,
        generator_version,
        random_seed,
        profile_name,
        reporting_base_currency,
        total_records,
        entity_counts,
        started_at,
        completed_at,
        status,
        created_at
    from {{ source('raw', 'ingestion_batch_manifests') }}
)

select
    cast(batch_id as uuid) as batch_id,
    cast(generator_version as varchar(32)) as generator_version,
    cast(random_seed as integer) as random_seed,
    upper(trim(cast(profile_name as varchar(32)))) as profile_name,
    upper(trim(cast(reporting_base_currency as varchar(3)))) as reporting_base_currency,
    cast(total_records as integer) as total_records,
    entity_counts,
    cast(started_at as timestamptz) as started_at,
    cast(completed_at as timestamptz) as completed_at,
    upper(trim(cast(status as varchar(32)))) as batch_status,
    cast(created_at as timestamptz) as created_at
from source
