-- The signature block of each filing in the data sets.
select
    accession_number,
    {{ dataset_text('name') }} as name,
    {{ dataset_text('title') }} as title,
    {{ dataset_text('phone') }} as phone,
    {{ dataset_text('signature') }} as signature,
    {{ dataset_text('city') }} as city,
    {{ dataset_text('stateorcountry') }} as state_or_country,
    {{ dataset_date('signaturedate') }} as signature_date,
    source_file,
    source_row,
    source_content_key,
    source_last_modified
from {{ source('raw', 'dataset_signature') }}
