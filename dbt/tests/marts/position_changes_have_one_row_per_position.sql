-- Each filer period compares each position once: one row per cik, period,
-- CUSIP and put or call, the security itself, whose put_call is null,
-- counted apart from its options.
select cik, period_of_report, cusip, coalesce(put_call, 'none') as put_call_key, count(*) as rows_found
from {{ ref('position_changes') }}
group by cik, period_of_report, cusip, coalesce(put_call, 'none')
having count(*) > 1
