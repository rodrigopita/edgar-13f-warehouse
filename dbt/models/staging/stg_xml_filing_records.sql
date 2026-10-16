-- The JSON lines of the XML path, one file version per filing. Snowpipe
-- loads a path again once 14 days have passed, so a reparsed filing can
-- sit in RAW twice under two content keys; the file written last is the
-- one that counts, whole, and the earlier one is left out whole.
select
    record:accession::string as accession_number,
    record:record_type::string as record_type,
    record:source_key::string as source_key,
    record:record as parsed,
    regexp_substr(source_file, 'filed=(\\d{4}-\\d{2}-\\d{2})', 1, 1, 'e', 1)::date as filing_date,
    source_file,
    source_row,
    source_content_key,
    source_last_modified
from {{ source('raw', 'parsed_filings') }}
qualify source_content_key = first_value(source_content_key) over (
    partition by record:accession::string
    order by source_last_modified desc, source_content_key desc
)
