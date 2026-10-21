-- The walk's audit records, one row per record: what one attempt of a run
-- discovered, landed and parsed. Records written before the walk parsed
-- carry no parse counts, which stay null. A record that 09's bulk COPY and
-- the pipe both loaded sits in AUDIT twice under one path; one is kept.
select
    record:run_id::string as run_id,
    record:day::date as walk_day,
    record:recorded_at::timestamp_tz as recorded_at,
    record:published::boolean as is_index_published,
    record:discovered::number as discovered,
    record:landed::number as landed,
    record:already_present::number as already_present,
    array_size(record:failed) as landing_failures,
    record:parsed::number as parsed,
    record:parsed_already_present::number as parsed_already_present,
    record:not_landed::number as not_landed,
    array_size(record:parse_failed) as parse_failures,
    array_size(record:reconcile_gaps) as reconcile_gaps,
    record:requests_made::number as requests_made,
    record:retries::number as retries,
    source_file,
    source_last_modified
from {{ source('audit', 'walk_runs') }}
qualify row_number() over (partition by source_file order by source_content_key) = 1
