-- Brookfield Corp /ON/, CIK 0001001085, period 2017-12-31. Expected rows and
-- dollars per contributing filing come from a separate Python pass over the
-- raw 2018q1, 2018q2 and 2018q4 zips on 2026-10-19, each filing read as
-- thousands by its median value per share: the restatement's 152 holdings
-- and the additions' 2, 1 and 2, 157 in all.
with expected as (
    select '0000950123-18-002599' as accession_number, 152 as holdings, 21378784000 as value_usd
    union all select '0000950123-18-002831', 2, 575841000
    union all select '0000950123-18-005836', 1, 124982000
    union all select '0000950123-18-011980', 2, 46028000
),

actual as (
    select accession_number, count(*) as holdings, sum(value_usd) as value_usd
    from {{ ref('canonical_holdings') }}
    where cik = '0001001085' and period_of_report = '2017-12-31'::date
    group by accession_number
)

(select 'missing' as side, * from expected minus select 'missing', * from actual)
union all
(select 'unexpected' as side, * from actual minus select 'unexpected', * from expected)
