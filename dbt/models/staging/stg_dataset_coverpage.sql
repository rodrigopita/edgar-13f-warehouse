-- The cover page of each filing in the data sets: the amendment fields as
-- the filer ticked them, the filing manager and the report type.
select
    accession_number,
    {{ dataset_date('reportcalendarorquarter') }} as report_calendar_or_quarter,
    {{ dataset_flag('isamendment') }} as is_amendment,
    {{ dataset_number('amendmentno') }} as amendment_no,
    {{ dataset_text('amendmenttype') }} as amendment_type,
    {{ dataset_flag('confdeniedexpired') }} as conf_denied_expired,
    {{ dataset_date('datedeniedexpired') }} as date_denied_expired,
    {{ dataset_date('datereported') }} as date_reported,
    {{ dataset_text('reasonfornonconfidentiality') }} as reason_for_non_confidentiality,
    {{ dataset_text('filingmanager_name') }} as filing_manager_name,
    {{ dataset_text('filingmanager_street1') }} as filing_manager_street1,
    {{ dataset_text('filingmanager_street2') }} as filing_manager_street2,
    {{ dataset_text('filingmanager_city') }} as filing_manager_city,
    {{ dataset_text('filingmanager_stateorcountry') }} as filing_manager_state_or_country,
    {{ dataset_text('filingmanager_zipcode') }} as filing_manager_zip_code,
    {{ dataset_text('reporttype') }} as report_type,
    {{ dataset_text('form13ffilenumber') }} as form_13f_file_number,
    {{ dataset_text('crdnumber') }} as crd_number,
    {{ dataset_text('secfilenumber') }} as sec_file_number,
    {{ dataset_flag('provideinfoforinstruction5') }} as provide_info_for_instruction5,
    {{ dataset_text('additionalinformation') }} as additional_information,
    source_file,
    source_row,
    source_content_key,
    source_last_modified
from {{ source('raw', 'dataset_coverpage') }}
