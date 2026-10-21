-- One row per backfill audit record and data set table: the rows the run
-- extracted from the zips, and the rows and files its COPY loaded. A COPY
-- skips the files it loaded in the last 64 days, so a second run of the
-- backfill extracts again and loads none.
with records as (
    select record, source_file
    from {{ source('audit', 'backfill_runs') }}
    qualify row_number() over (partition by source_file order by source_content_key) = 1
)

select
    records.record:run_id::string as run_id,
    records.record:recorded_at::timestamp_tz as recorded_at,
    extracted.key::string as table_name,
    extracted.value::number as extracted_rows,
    get(records.record:rows_loaded, extracted.key)::number as rows_loaded,
    get(records.record:files_loaded, extracted.key)::number as files_loaded,
    records.source_file
from records,
    lateral flatten(input => records.record:extracted_rows) as extracted
