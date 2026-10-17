-- Every filing in its lineage, with its position and its supersedence state.
-- A lineage is one filer's filings for one period of report, in filing
-- order: filing date; within a date the cover's amendment number, an
-- original first since it has none; then the accession number, whose last
-- six digits count the submitter's filings. The terms are those of
-- CONTEXT.md and the rules those of docs/scope.md, Decisions, 2026-10-15
-- to 2026-10-17.
--
-- The submission type decides original, amendment or notice; the cover's
-- amendment type decides restatement or addition. The first 13F-HR is the
-- original and a later one counts as a restatement; an amendment with no
-- type counts as a restatement. The latest original or restatement is the
-- effective one: it and every addition after it contribute, and every
-- holdings report before it is superseded. With none present, every
-- addition contributes. Notices take a position and do neither.
--
-- Plain SQL on purpose: the unit tests beside this model ran red and green
-- in DuckDB before they ran in Snowflake.

with ordered as (
    select
        accession_number,
        cik,
        period_of_report,
        submission_type,
        amendment_type,
        amendment_no,
        row_number() over (
            partition by cik, period_of_report
            order by filing_date, amendment_no nulls first, accession_number
        ) as filing_position
    from {{ ref('filings') }}
),

roled as (
    select
        *,
        case
            when submission_type like '13F-NT%' then 'notice'
            when submission_type = '13F-HR' and filing_position = min(
                case when submission_type = '13F-HR' then filing_position end
            ) over (partition by cik, period_of_report) then 'original'
            when amendment_type = 'NEW HOLDINGS' then 'addition'
            else 'restatement'
        end as filing_role
    from ordered
),

effective as (
    select
        *,
        max(case when filing_role in ('original', 'restatement') then filing_position end) over (
            partition by cik, period_of_report
        ) as effective_position
    from roled
)

select
    accession_number,
    cik,
    period_of_report,
    filing_position,
    filing_role,
    effective_position,
    filing_role <> 'notice' and filing_position < coalesce(effective_position, 0) as is_superseded,
    filing_position = coalesce(effective_position, 0)
        or (filing_role = 'addition' and filing_position > coalesce(effective_position, 0))
        as is_contributing
from effective
