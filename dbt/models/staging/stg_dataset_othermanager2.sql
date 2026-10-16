-- The other managers included in the filing, from the summary page. The
-- sequence number is what a holding's other-manager field refers to.
select
    accession_number,
    {{ dataset_number('sequencenumber') }} as sequence_number,
    {{ dataset_text('cik') }} as cik,
    {{ dataset_text('form13ffilenumber') }} as form_13f_file_number,
    {{ dataset_text('crdnumber') }} as crd_number,
    {{ dataset_text('secfilenumber') }} as sec_file_number,
    {{ dataset_text('name') }} as name,
    source_file,
    source_row,
    source_content_key,
    source_last_modified
from {{ source('raw', 'dataset_othermanager2') }}
