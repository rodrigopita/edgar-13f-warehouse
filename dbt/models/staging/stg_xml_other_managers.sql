-- The other managers a cover page names, from both of its lists: the
-- managers reporting for the filer (the data sets' OTHERMANAGER) and the
-- managers included in the filing (OTHERMANAGER2), told apart by listed_on.
with covers as (
    select accession_number, parsed, source_file, source_row, source_content_key, source_last_modified
    from {{ ref('stg_xml_filing_records') }}
    where record_type = 'cover'
),

listed as (
    select covers.*, 'cover' as listed_on, managers.value as manager
    from covers, lateral flatten(input => covers.parsed:other_managers) as managers
    union all
    select covers.*, 'summary' as listed_on, managers.value as manager
    from covers, lateral flatten(input => covers.parsed:summary:other_managers) as managers
)

select
    accession_number,
    listed_on,
    manager:sequence_number::number as sequence_number,
    lpad(manager:cik::string, 10, '0') as cik,
    manager:form_13f_file_number::string as form_13f_file_number,
    manager:crd_number::string as crd_number,
    manager:sec_file_number::string as sec_file_number,
    manager:name::string as name,
    source_file,
    source_row,
    source_content_key,
    source_last_modified
from listed
