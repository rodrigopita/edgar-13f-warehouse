-- Brookfield Corp /ON/, CIK 0001001085, period 2017-12-31, the second case
-- named in docs/scope.md. Read from the raw zips on 2026-10-19: the original
-- of 2018-02-14 is superseded by the restatement of the next day, and three
-- additions follow it, all in effect. Rows on either side of the difference
-- fail the test.
with expected as (
    select '0000950123-18-001865' as accession_number, 1 as filing_position, 'original' as filing_role, true as is_superseded, false as is_contributing
    union all select '0000950123-18-002599', 2, 'restatement', false, true
    union all select '0000950123-18-002831', 3, 'addition', false, true
    union all select '0000950123-18-005836', 4, 'addition', false, true
    union all select '0000950123-18-011980', 5, 'addition', false, true
),

actual as (
    select accession_number, filing_position, filing_role, is_superseded, is_contributing
    from {{ ref('lineage_filings') }}
    where cik = '0001001085' and period_of_report = '2017-12-31'::date
)

(select 'missing' as side, * from expected minus select 'missing', * from actual)
union all
(select 'unexpected' as side, * from actual minus select 'unexpected', * from expected)
