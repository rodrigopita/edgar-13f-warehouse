-- A parsed filing has one holding per row index; two would mean the
-- envelope dedupe let two file versions through.
select accession_number, row_index, count(*) as rows_seen
from {{ ref('stg_xml_holdings') }}
group by accession_number, row_index
having count(*) > 1
