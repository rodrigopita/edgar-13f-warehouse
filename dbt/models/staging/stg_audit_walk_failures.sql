-- One row per filing an audit record names as failed: to land, when its
-- XML could not be fetched, or to parse, when the XML would not read as a
-- 13F. Records written before the walk parsed list no parse failures.
with records as (
    select record, source_file
    from {{ source('audit', 'walk_runs') }}
    qualify row_number() over (partition by source_file order by source_content_key) = 1
)

select
    records.record:run_id::string as run_id,
    records.record:recorded_at::timestamp_tz as recorded_at,
    records.record:day::date as walk_day,
    'land' as failure_stage,
    failures.value:accession::string as accession_number,
    failures.value:form_type::string as submission_type,
    failures.value:error::string as error,
    records.source_file
from records,
    lateral flatten(input => records.record:failed) as failures

union all

select
    records.record:run_id::string,
    records.record:recorded_at::timestamp_tz,
    records.record:day::date,
    'parse',
    failures.value:accession::string,
    failures.value:form_type::string,
    failures.value:error::string,
    records.source_file
from records,
    lateral flatten(input => records.record:parse_failed) as failures
