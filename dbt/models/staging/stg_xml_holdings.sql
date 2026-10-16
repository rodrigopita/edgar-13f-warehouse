-- One row per holding parsed from XML. Values are in dollars as filed: the
-- XML path starts in 2026, after the unit change. The parser has already
-- upper-cased CUSIP and FIGI and read the other-manager field into a list.
select
    accession_number,
    filing_date,
    parsed:row_index::number as row_index,
    parsed:name_of_issuer::string as name_of_issuer,
    parsed:title_of_class::string as title_of_class,
    parsed:cusip::string as cusip,
    parsed:figi::string as figi,
    parsed:value::number as value_usd,
    parsed:shares_or_principal::number as shares_or_principal_amount,
    parsed:shares_or_principal_type::string as shares_or_principal_amount_type,
    parsed:put_call::string as put_call,
    parsed:investment_discretion::string as investment_discretion,
    parsed:other_managers as other_manager_sequence_numbers,
    parsed:voting_sole::number as voting_sole,
    parsed:voting_shared::number as voting_shared,
    parsed:voting_none::number as voting_none,
    source_key,
    source_file,
    source_row,
    source_content_key,
    source_last_modified
from {{ ref('stg_xml_filing_records') }}
where record_type = 'holding'
