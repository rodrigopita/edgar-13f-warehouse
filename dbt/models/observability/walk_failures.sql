-- Ingestion and parse failures, one row per filing and stage the walk
-- failed at: how many attempts failed, the latest one's error and run, and
-- whether the filing has since reached RAW. A later run of the same day
-- parses every landed filing whose JSON lines are missing, so a failure the
-- parser has since learned to read clears when its day is run again.
with attempts as (
    select
        accession_number,
        failure_stage,
        submission_type,
        walk_day,
        error,
        run_id,
        recorded_at,
        count(*) over (partition by accession_number, failure_stage) as failed_attempts,
        min(recorded_at) over (partition by accession_number, failure_stage) as first_failed_at,
        row_number() over (
            partition by accession_number, failure_stage order by recorded_at desc
        ) as recency
    from {{ ref('stg_audit_walk_failures') }}
),

loaded_filings as (
    select distinct accession_number
    from {{ ref('stg_xml_filing_records') }}
)

select
    attempts.accession_number,
    attempts.failure_stage,
    attempts.submission_type,
    attempts.walk_day,
    attempts.failed_attempts,
    attempts.first_failed_at,
    attempts.recorded_at as last_failed_at,
    attempts.error as last_error,
    attempts.run_id as last_run_id,
    loaded_filings.accession_number is not null as is_loaded
from attempts
left join loaded_filings
    on loaded_filings.accession_number = attempts.accession_number
where attempts.recency = 1
