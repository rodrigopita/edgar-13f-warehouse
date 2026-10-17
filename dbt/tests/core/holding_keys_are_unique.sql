-- A holding is one row of one filing's information table on one path.
select accession_number, origin, holding_key, count(*) as rows_seen
from {{ ref('holdings') }}
group by accession_number, origin, holding_key
having count(*) > 1
