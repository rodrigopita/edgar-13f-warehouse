-- The cp3 test filer: Brookfield Corp /ON/, CIK 0001001085, period
-- 2018-06-30, checked against EDGAR on 2026-10-08. The restatement of
-- 2018-11-15 and the addition of 2018-12-14 are in effect; the original and
-- the two-row restatement of 2018-11-14 are superseded. Rows on either side
-- of the difference fail the test.
with expected as (
    select '0000950123-18-008668' as accession_number, 1 as filing_position, 'original' as filing_role, true as is_superseded, false as is_contributing
    union all select '0000950123-18-011987', 2, 'restatement', true, false
    union all select '0000950123-18-012060', 3, 'restatement', false, true
    union all select '0000950123-18-012410', 4, 'addition', false, true
),

actual as (
    select accession_number, filing_position, filing_role, is_superseded, is_contributing
    from {{ ref('lineage_filings') }}
    where cik = '0001001085' and period_of_report = '2018-06-30'::date
)

(select 'missing' as side, * from expected minus select 'missing', * from actual)
union all
(select 'unexpected' as side, * from actual minus select 'unexpected', * from expected)
