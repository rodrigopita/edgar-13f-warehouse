-- One row per filing and the stage it failed at.
select accession_number, failure_stage, count(*) as rows_found
from {{ ref('walk_failures') }}
group by accession_number, failure_stage
having count(*) > 1
