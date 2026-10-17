-- Advisors Asset Management, CIK 0001297376, period 2019-03-31: the
-- addition submitted before its restatement.
-- Expected rows and dollars per contributing filing come from a separate
-- Python pass over the raw 01jun2026-31aug2026 zip on 2026-10-17, each
-- filing read in the unit its median value per share as filed shows.
-- The addition, amendment 2, was submitted before the restatement, amendment
-- 1, on 2026-08-18; ordered by amendment number within the date, it
-- supplements the restatement and its two holdings are in effect. Both
-- report dollars.
with expected as (
    select '0001999371-26-018150' as accession_number, 1716 as holdings, 5488354487 as value_usd
    union all select '0001999371-26-018135', 2, 1956
),

actual as (
    select accession_number, count(*) as holdings, sum(value_usd) as value_usd
    from {{ ref('canonical_holdings') }}
    where cik = '0001297376' and period_of_report = '2019-03-31'::date
    group by accession_number
)

(select 'missing' as side, * from expected minus select 'missing', * from actual)
union all
(select 'unexpected' as side, * from actual minus select 'unexpected', * from expected)
