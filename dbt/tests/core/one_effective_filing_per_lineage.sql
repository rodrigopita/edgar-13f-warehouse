-- Supersedence: a lineage with an original or a restatement has exactly one
-- of them in effect, and a lineage with neither has none.
select
    cik,
    period_of_report,
    count_if(filing_role in ('original', 'restatement')) as bases,
    count_if(filing_role in ('original', 'restatement') and is_contributing) as bases_in_effect
from {{ ref('lineage_filings') }}
group by cik, period_of_report
having count_if(filing_role in ('original', 'restatement') and is_contributing)
    <> iff(count_if(filing_role in ('original', 'restatement')) > 0, 1, 0)
