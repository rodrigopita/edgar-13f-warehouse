-- One row per period that a filing in lineage_filings names, in the terms
-- of CONTEXT.md: the calendar quarter end a filing reports on, as EDGAR
-- records it. The grain is the period itself, so a period named by many
-- filings is one row.
--
-- A period is whatever EDGAR recorded with the submission, so one that is
-- no quarter end stays a row: a filing names it, and the relationships
-- test from lineage_filings holds only while it is here. is_quarter_end
-- says which rows are quarter ends; on 2026-10-19 every period in the
-- lineages was one.
--
-- previous_period is the quarter end three months before, and only a
-- quarter end has one: a period off the quarter end has no previous
-- period, and a mart comparing periods skips it rather than guess. It
-- is the last day of the month three months back, not the same day, since
-- 2024-06-30 less three months is 2024-03-30 and the quarter end is the
-- 31st.
--
-- Plain SQL on purpose, like lineage_filings: the dateadd, date_trunc and
-- last_day of dbt's cross-database macros, extract, and no adapter
-- function beside them.

with named as (
    select distinct period_of_report
    from {{ ref('lineage_filings') }}
),

typed as (
    select
        period_of_report,
        period_of_report = {{ dbt.last_day('period_of_report', 'month') }}
            and extract(month from period_of_report) in (3, 6, 9, 12) as is_quarter_end
    from named
)

select
    period_of_report,
    is_quarter_end,
    case
        when is_quarter_end
            then {{ dbt.last_day(dbt.dateadd('month', -3, 'period_of_report'), 'month') }}
    end as previous_period,
    extract(year from period_of_report) as calendar_year,
    extract(quarter from period_of_report) as calendar_quarter
from typed
