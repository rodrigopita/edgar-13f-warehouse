-- The other managers reporting for the filer, from the cover page: the
-- managers whose filings hold what this filing leaves out.
select
    accession_number,
    {{ dataset_number('othermanager_sk') }} as othermanager_sk,
    {{ dataset_text('cik') }} as cik,
    {{ dataset_text('form13ffilenumber') }} as form_13f_file_number,
    {{ dataset_text('crdnumber') }} as crd_number,
    {{ dataset_text('secfilenumber') }} as sec_file_number,
    {{ dataset_text('name') }} as name,
    source_file,
    source_row,
    source_content_key,
    source_last_modified
from {{ source('raw', 'dataset_othermanager') }}
