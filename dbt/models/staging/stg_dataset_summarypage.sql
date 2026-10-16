-- The totals a holdings report declares for itself. The value total is in
-- the unit of the filing date, like the holdings it sums.
select
    summaries.accession_number,
    {{ dataset_number('summaries.otherincludedmanagerscount') }} as other_included_managers_count,
    {{ dataset_number('summaries.tableentrytotal') }} as table_entry_total,
    {{ dataset_usd('summaries.tablevaluetotal', 'submissions.filing_date') }} as table_value_total_usd,
    {{ dataset_flag('summaries.isconfidentialomitted') }} as is_confidential_omitted,
    summaries.source_file,
    summaries.source_row,
    summaries.source_content_key,
    summaries.source_last_modified
from {{ source('raw', 'dataset_summarypage') }} as summaries
left join {{ ref('stg_dataset_submission') }} as submissions
    on submissions.accession_number = summaries.accession_number
