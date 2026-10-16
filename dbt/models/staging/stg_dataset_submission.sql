-- One row per filing in the data sets. The submission type is EDGAR's own
-- record of what was filed, so it decides whether a filing is an amendment;
-- the cover page's box, in stg_dataset_coverpage, is what the filer ticked.
select
    accession_number,
    {{ dataset_date('filing_date') }} as filing_date,
    {{ dataset_text('submissiontype') }} as submission_type,
    {{ dataset_text('cik') }} as cik,
    {{ dataset_date('periodofreport') }} as period_of_report,
    {{ dataset_text('submissiontype') }} like '%/A' as is_amendment,
    source_file,
    source_row,
    source_content_key,
    source_last_modified
from {{ source('raw', 'dataset_submission') }}
