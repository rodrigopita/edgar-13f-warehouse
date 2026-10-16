-- The cover page of each filing parsed from XML, with the summary page the
-- parser attaches to it. The filing date comes from the landing path, since
-- the cover page XML carries none. Columns are named as in the data set
-- models so the core layer can set the two paths side by side.
select
    accession_number,
    filing_date,
    parsed:submission_type::string as submission_type,
    lpad(parsed:cik::string, 10, '0') as cik,
    parsed:period_of_report::date as period_of_report,
    parsed:submission_type::string like '%/A' as is_amendment,
    parsed:report_calendar_or_quarter::date as report_calendar_or_quarter,
    parsed:amendment_no::number as amendment_no,
    parsed:amendment_type::string as amendment_type,
    parsed:conf_denied_expired::boolean as conf_denied_expired,
    parsed:filing_manager_name::string as filing_manager_name,
    parsed:filing_manager_address:street1::string as filing_manager_street1,
    parsed:filing_manager_address:street2::string as filing_manager_street2,
    parsed:filing_manager_address:city::string as filing_manager_city,
    parsed:filing_manager_address:state_or_country::string as filing_manager_state_or_country,
    parsed:filing_manager_address:zip_code::string as filing_manager_zip_code,
    parsed:report_type::string as report_type,
    parsed:form_13f_file_number::string as form_13f_file_number,
    parsed:crd_number::string as crd_number,
    parsed:sec_file_number::string as sec_file_number,
    parsed:provide_info_for_instruction5::boolean as provide_info_for_instruction5,
    parsed:additional_information::string as additional_information,
    parsed:summary:other_included_managers_count::number as other_included_managers_count,
    parsed:summary:table_entry_total::number as table_entry_total,
    parsed:summary:table_value_total::number as table_value_total_usd,
    parsed:summary:is_confidential_omitted::boolean as is_confidential_omitted,
    parsed:namespace::string as xml_namespace,
    parsed:schema_version::string as xml_schema_version,
    source_key,
    source_file,
    source_row,
    source_content_key,
    source_last_modified
from {{ ref('stg_xml_filing_records') }}
where record_type = 'cover'
