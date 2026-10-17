-- Canonical holdings: for each filer and period of report, the holdings of
-- the contributing filings and nothing else, which is the warehouse's
-- answer to what the filer reported. The marts read this model.

select
    lineage.cik,
    lineage.period_of_report,
    holdings.accession_number,
    lineage.filing_role,
    filings.filing_date,
    holdings.origin,
    holdings.holding_key,
    holdings.name_of_issuer,
    holdings.title_of_class,
    holdings.cusip,
    holdings.figi,
    holdings.value_as_filed,
    holdings.value_unit,
    holdings.value_usd,
    holdings.shares_or_principal_amount,
    holdings.shares_or_principal_amount_type,
    holdings.put_call,
    holdings.investment_discretion,
    holdings.other_manager_sequence_numbers,
    holdings.voting_sole,
    holdings.voting_shared,
    holdings.voting_none,
    holdings.source_file,
    holdings.source_row
from {{ ref('holdings') }} as holdings
inner join {{ ref('lineage_filings') }} as lineage
    on lineage.accession_number = holdings.accession_number
inner join {{ ref('filings') }} as filings
    on filings.accession_number = holdings.accession_number
where lineage.is_contributing
