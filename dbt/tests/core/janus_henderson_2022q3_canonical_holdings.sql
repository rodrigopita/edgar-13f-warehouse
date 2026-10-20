-- Janus Henderson, CIK 0001274173, period 2022-09-30: the NEW HOLDINGS
-- amendment 0001085146-23-000116 repeats 86 percent of the securities of
-- the original 0001085146-22-004110, under the 90 percent threshold, so it
-- stays an addition. 5635 of its 5642 holdings are exact copies of the
-- original's and leave canonical holdings; the 7 that remain add
-- 224772000 dollars. Expected rows and dollars come from the filings on
-- sec.gov, fetched 2026-10-20, and a separate Python pass over the 54
-- zips the same day finds the same filings, rows, units and dollars.
with expected as (
    select '0001085146-22-004110' as accession_number, 6414 as holdings, 133577018000 as value_usd
    union all select '0001085146-23-000116', 7, 224772000
),

actual as (
    select accession_number, count(*) as holdings, sum(value_usd) as value_usd
    from {{ ref('canonical_holdings') }}
    where cik = '0001274173' and period_of_report = '2022-09-30'::date
    group by accession_number
)

(select 'missing' as side, * from expected minus select 'missing', * from actual)
union all
(select 'unexpected' as side, * from actual minus select 'unexpected', * from expected)
