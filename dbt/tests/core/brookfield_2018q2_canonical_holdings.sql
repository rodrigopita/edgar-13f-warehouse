-- The cp3 done-criterion: Brookfield Corp /ON/, CIK 0001001085, period
-- 2018-06-30, shows correct canonical holdings. Expected rows and dollars
-- per contributing filing come from a separate Python pass over the raw
-- 2018q4 zip on 2026-10-17: the restatement of 2018-11-15 with 191 holdings
-- and the addition of 2018-12-14 with one, 192 in all. Both read as
-- thousands, which their median value per share as filed shows and their
-- filing dates agree with.
with expected as (
    select '0000950123-18-012060' as accession_number, 191 as holdings, 26744707000 as value_usd
    union all select '0000950123-18-012410', 1, 4751670000
),

actual as (
    select accession_number, count(*) as holdings, sum(value_usd) as value_usd
    from {{ ref('canonical_holdings') }}
    where cik = '0001001085' and period_of_report = '2018-06-30'::date
    group by accession_number
)

(select 'missing' as side, * from expected minus select 'missing', * from actual)
union all
(select 'unexpected' as side, * from actual minus select 'unexpected', * from expected)
