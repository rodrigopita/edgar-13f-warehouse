-- Supersedence: a superseded filing contributes nothing, a notice neither
-- supersedes nor contributes, and an addition after the effective filing
-- contributes.
select accession_number, filing_role, filing_position, effective_position, is_superseded, is_contributing
from {{ ref('lineage_filings') }}
where (is_superseded and is_contributing)
    or (filing_role = 'notice' and (is_superseded or is_contributing))
    or (filing_role = 'addition'
        and filing_position > coalesce(effective_position, 0)
        and not is_contributing)
