-- One row per filing, from both paths: the data sets through 2026-08-31 and
-- the walk from 2026-09-01. Accession numbers do not repeat across the 54
-- data sets, and the two paths do not overlap until the next data set, so
-- the accession is the key; the unique test on it is where an overlap
-- would first show, and the precedence rule waits for that day.
--
-- The submission type is EDGAR's record of what was filed and decides
-- is_amendment; cover_is_amendment is the box as the filer ticked it. The
-- XML parser refuses a cover whose box disagrees with the submission type,
-- so on the walk the two are equal by construction.

with data_set_filings as (
    select
        submissions.accession_number,
        submissions.cik,
        submissions.filing_date,
        submissions.period_of_report,
        submissions.submission_type,
        submissions.is_amendment,
        covers.is_amendment as cover_is_amendment,
        covers.amendment_type,
        covers.amendment_no,
        covers.report_type,
        covers.report_calendar_or_quarter,
        covers.filing_manager_name,
        summaries.table_entry_total,
        summaries.table_value_total_as_filed,
        summaries.other_included_managers_count,
        summaries.is_confidential_omitted,
        'data_set' as origin,
        submissions.source_file,
        submissions.source_row
    from {{ ref('stg_dataset_submission') }} as submissions
    inner join {{ ref('stg_dataset_coverpage') }} as covers
        on covers.accession_number = submissions.accession_number
    left join {{ ref('stg_dataset_summarypage') }} as summaries
        on summaries.accession_number = submissions.accession_number
),

walk_filings as (
    select
        accession_number,
        cik,
        filing_date,
        period_of_report,
        submission_type,
        is_amendment,
        is_amendment as cover_is_amendment,
        amendment_type,
        amendment_no,
        report_type,
        report_calendar_or_quarter,
        filing_manager_name,
        table_entry_total,
        table_value_total_as_filed,
        other_included_managers_count,
        is_confidential_omitted,
        'walk' as origin,
        source_file,
        source_row
    from {{ ref('stg_xml_cover_pages') }}
)

select * from data_set_filings
union all
select * from walk_filings
