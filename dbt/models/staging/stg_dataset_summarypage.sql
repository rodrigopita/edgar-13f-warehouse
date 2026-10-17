-- The totals a holdings report declares for itself, typed. The value total
-- stays as filed, in the unit of the holdings it sums.
select
    summaries.accession_number,
    {{ dataset_number('summaries.otherincludedmanagerscount') }} as other_included_managers_count,
    {{ dataset_number('summaries.tableentrytotal') }} as table_entry_total,
    {{ dataset_number('summaries.tablevaluetotal') }} as table_value_total_as_filed,
    {{ dataset_flag('summaries.isconfidentialomitted') }} as is_confidential_omitted,
    summaries.source_file,
    summaries.source_row,
    summaries.source_content_key,
    summaries.source_last_modified
from {{ source('raw', 'dataset_summarypage') }} as summaries
