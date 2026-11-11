-- =============================================================================
-- Singular Test: assert_latest_collection_attributes_consistency
-- Invariant: On fct_fee_assessments, latest_collection_id, latest_recognition_id,
--            collection_status, and failure_reason must exactly match the
--            chronologically latest attempt in fct_fee_collections (ordered by
--            attempted_at DESC, collection_attempt_number DESC, collection_id DESC)
--            and latest recognition in stg_revenue_recognitions (ordered by
--            recognized_at DESC, recognition_id DESC), and settled collections
--            must never carry a non-null failure_reason.
-- =============================================================================

with ranked_recognitions as (
    select
        collection_id,
        recognition_id,
        row_number() over (
            partition by collection_id
            order by
                recognized_at desc,
                recognition_id desc
        ) as rn
    from {{ ref('stg_revenue_recognitions') }}
),

ranked_attempts as (
    select
        fc.assessment_id,
        fc.collection_id,
        rr.recognition_id,
        fc.collection_status,
        fc.failure_reason,
        row_number() over (
            partition by fc.assessment_id
            order by
                fc.attempted_at desc,
                fc.collection_attempt_number desc,
                fc.collection_id desc
        ) as rn
    from {{ ref('fct_fee_collections') }} fc
    left join ranked_recognitions rr
        on fc.collection_id = rr.collection_id
        and rr.rn = 1
),

latest_attempt as (
    select
        assessment_id,
        collection_id as expected_collection_id,
        recognition_id as expected_recognition_id,
        collection_status as expected_status,
        failure_reason as expected_failure_reason
    from ranked_attempts
    where rn = 1
)

select
    fa.assessment_id,
    fa.latest_collection_id,
    la.expected_collection_id,
    fa.latest_recognition_id,
    la.expected_recognition_id,
    fa.collection_status,
    la.expected_status,
    fa.failure_reason,
    la.expected_failure_reason
from {{ ref('fct_fee_assessments') }} fa
inner join latest_attempt la
    on fa.assessment_id = la.assessment_id
where fa.latest_collection_id is distinct from la.expected_collection_id
   or fa.latest_recognition_id is distinct from la.expected_recognition_id
   or fa.collection_status is distinct from la.expected_status
   or fa.failure_reason is distinct from la.expected_failure_reason
   or (fa.collection_status = 'SETTLED' and fa.failure_reason is not null)
