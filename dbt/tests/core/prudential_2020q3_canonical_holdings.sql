-- Prudential Financial, CIK 0001137774, period 2020-09-30: the NEW HOLDINGS
-- amendment 0001137774-21-000108 adds an omitted other manager's book. It
-- repeats 1148 of the 2239 securities of the original
-- 0001137774-20-000125, about half, so it stays an addition, and none of
-- its holdings is an exact copy, so every one sums: 3973 holdings of the
-- original and 1368 of the addition. A third filing, the addition
-- 0001137774-24-000098 of 2024-06-14, repeats almost nothing and adds 5
-- holdings, in dollars. The first two come from the filings on sec.gov,
-- fetched 2026-10-20; the third, and the lineage as a whole, from a
-- separate Python pass over the 54 zips the same day, which agrees on the
-- first two.
with expected as (
    select '0001137774-20-000125' as accession_number, 3973 as holdings, 53012762000 as value_usd
    union all select '0001137774-21-000108', 1368, 691963000
    union all select '0001137774-24-000098', 5, 46308698
),

actual as (
    select accession_number, count(*) as holdings, sum(value_usd) as value_usd
    from {{ ref('canonical_holdings') }}
    where cik = '0001137774' and period_of_report = '2020-09-30'::date
    group by accession_number
)

(select 'missing' as side, * from expected minus select 'missing', * from actual)
union all
(select 'unexpected' as side, * from actual minus select 'unexpected', * from expected)
