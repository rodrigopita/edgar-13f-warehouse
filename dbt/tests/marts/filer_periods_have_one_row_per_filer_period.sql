-- One row per filer and period with canonical holdings.
select cik, period_of_report, count(*) as rows_found
from {{ ref('filer_periods') }}
group by cik, period_of_report
having count(*) > 1
