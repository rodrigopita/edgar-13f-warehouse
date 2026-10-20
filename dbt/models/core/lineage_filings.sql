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
-- An addition that repeats 90 percent or more of the securities of the
-- filing it amends is a restatement in all but its cover, and counts as
-- one; addition_coverage measures it, and the typed role the rules above
-- describe is the macro typed_filing_role, shared with that model. With
-- two such additions in a row, as Morgan Stanley filed for 2024-03-31, the
-- second is the effective filing and the first and the original are
-- superseded.
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
        filing_date,
        row_number() over (
            partition by cik, period_of_report
            order by {{ filing_order() }}
        ) as filing_position
    from {{ ref('filings') }}
),

typed as (
    select
        *,
        {{ typed_filing_role() }} as typed_role
    from ordered
),

roled as (
    select
        typed.*,
        case
            when typed.typed_role = 'addition' and coalesce(coverage.is_read_as_restatement, false)
                then 'restatement'
            else typed.typed_role
        end as filing_role
    from typed
    left join {{ ref('addition_coverage') }} as coverage
        on coverage.accession_number = typed.accession_number
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
    filing_role <> 'notice'
        and effective_position is not null
        and filing_position < effective_position as is_superseded,
    filing_position is not distinct from effective_position
        or (filing_role = 'addition' and (effective_position is null or filing_position > effective_position))
        as is_contributing
from effective
