-- Deutsche Bank, CIK 0000948046, period 2018-06-30: the NEW HOLDINGS
-- amendment 0000948046-20-000075 is a corrected full list: it repeats 98
-- percent of the securities of the filing it amends, reads as a
-- restatement and stands alone with its 21882 holdings. Expected rows and dollars come from the filings on
-- sec.gov, fetched 2026-10-20, and a separate Python pass over the 54
-- zips the same day finds the same filings, rows, units and dollars.
with expected as (
    select '0000948046-20-000075' as accession_number, 21882 as holdings, 200800774000 as value_usd
),

actual as (
    select accession_number, count(*) as holdings, sum(value_usd) as value_usd
    from {{ ref('canonical_holdings') }}
    where cik = '0000948046' and period_of_report = '2018-06-30'::date
    group by accession_number
)

(select 'missing' as side, * from expected minus select 'missing', * from actual)
union all
(select 'unexpected' as side, * from actual minus select 'unexpected', * from expected)
