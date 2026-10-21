{{ config(materialized='view') }}

-- Pipeline freshness, read from each layer when queried: the day the latest
-- walk run was for and when its audit record was written, the latest
-- filing date and parsed file in RAW, and the latest walk filing date in
-- CORE. RAW behind the audit records means the pipe stalled; CORE behind
-- RAW means dbt has not run since. A view, so it reports the layers and
-- never its own build.
select
    (select max(walk_day) from {{ ref('stg_audit_walk_runs') }}) as last_walk_day,
    (select max(recorded_at) from {{ ref('stg_audit_walk_runs') }}) as last_audit_recorded_at,
    (select max(filing_date) from {{ ref('stg_xml_filing_records') }}) as last_filing_date_in_raw,
    (select max(source_last_modified) from {{ ref('stg_xml_filing_records') }})
        as last_parsed_file_written_at,
    (select max(filing_date) from {{ ref('filings') }} where origin = 'walk')
        as last_filing_date_in_core,
    current_timestamp() as read_at
