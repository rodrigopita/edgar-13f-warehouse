-- One row per filer: a CIK that any filing in filings carries, with the
-- name it filed under last and the first and last periods it filed for.
--
-- The name is filing_manager_name from the cover. A filer can rename
-- itself: on 2026-10-19, 2,470 of 16,591 filers had filed under more
-- than one name, and no filing lacked one. The name is the one on the
-- latest filing that has one: latest by filing date, then by accession
-- number, both descending, since the accession's last six digits count
-- the submitter's filings within a date. The latest filing by date is
-- not the latest period: a late filing for an old period is the filer's
-- latest word. A filer with no name on any filing is still a row, with a
-- null name.
--
-- first_period and last_period span every filing of the filer, notices and
-- superseded filings included, since the model says when the filer was
-- there, not what it held.

with latest_named_filing as (
    select
        cik,
        filing_manager_name
    from {{ ref('filings') }}
    where filing_manager_name is not null
    qualify row_number() over (
        partition by cik
        order by filing_date desc, accession_number desc
    ) = 1
),

spans as (
    select
        cik,
        min(period_of_report) as first_period,
        max(period_of_report) as last_period
    from {{ ref('filings') }}
    group by cik
)

select
    spans.cik,
    latest_named_filing.filing_manager_name as filer_name,
    spans.first_period,
    spans.last_period
from spans
left join latest_named_filing
    on latest_named_filing.cik = spans.cik
