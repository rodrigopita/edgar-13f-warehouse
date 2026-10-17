-- Lineage: filing order is total within a lineage, one filing per position.
select cik, period_of_report, filing_position, count(*) as filings_at_position
from {{ ref('lineage_filings') }}
group by cik, period_of_report, filing_position
having count(*) > 1
