-- The tidy control: Advisors Asset Management, CIK 0001297376, period
-- 2018-03-31.
-- Expected rows and dollars per contributing filing come from a separate
-- Python pass over the raw 01jun2026-31aug2026 zip on 2026-10-17, each
-- filing read in the unit its median value per share as filed shows.
-- The restatement of 2026-08-13, amendment 1, stands in for the original of
-- 2018 and the addition, amendment 2, supplements it. Both report thousands
-- although filed in 2026: read by the filing date the restatement would
-- total $5.97 million.
with expected as (
    select '0001999371-26-017794' as accession_number, 1689 as holdings, 5968665000 as value_usd
    union all select '0001999371-26-017796', 4, 8000
),

actual as (
    select accession_number, count(*) as holdings, sum(value_usd) as value_usd
    from {{ ref('canonical_holdings') }}
    where cik = '0001297376' and period_of_report = '2018-03-31'::date
    group by accession_number
)

(select 'missing' as side, * from expected minus select 'missing', * from actual)
union all
(select 'unexpected' as side, * from actual minus select 'unexpected', * from expected)
