-- Lineage: every filing takes a position in exactly one lineage. The
-- relationships test on lineage_filings checks the other direction.
select filings.accession_number
from {{ ref('filings') }} as filings
left join {{ ref('lineage_filings') }} as lineage
    on lineage.accession_number = filings.accession_number
where lineage.accession_number is null
