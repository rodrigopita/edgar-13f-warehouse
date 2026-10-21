-- One row per audit record and day it walked: the run's own day, when its
-- index was published, and each earlier day its sweep found unlanded. The
-- counts are the 13F filings the day's index listed, by submission type.
with records as (
    select record, source_file
    from {{ source('audit', 'walk_runs') }}
    qualify row_number() over (partition by source_file order by source_content_key) = 1
)

select
    records.record:run_id::string as run_id,
    records.record:recorded_at::timestamp_tz as recorded_at,
    days.key::date as walk_day,
    days.value:discovered::number as discovered,
    coalesce(days.value:by_form['13F-HR']::number, 0) as holdings_reports,
    coalesce(days.value:by_form['13F-HR/A']::number, 0) as holdings_report_amendments,
    coalesce(days.value:by_form['13F-NT']::number, 0) as notices,
    coalesce(days.value:by_form['13F-NT/A']::number, 0) as notice_amendments,
    days.value:key::string as index_key,
    records.source_file
from records,
    lateral flatten(input => records.record:days) as days
