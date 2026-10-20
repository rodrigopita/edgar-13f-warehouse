-- Canonical holdings: for each filer and period of report, the holdings of
-- the contributing filings and nothing else, which is the warehouse's
-- answer to what the filer reported. The marts read this model.
--
-- One more holding leaves: a copied holding. A contributing addition that
-- lists a holding identical to one of an earlier contributing filing of
-- its lineage has resubmitted it, and counting both would count it twice.
-- Identical is the macro is_copied_holding: security, put or call, amount,
-- amount type, discretion and other managers all equal, null-safe, the
-- other managers as filed and in order. Holdings of one filing are never
-- compared with each other, since a filing may hold the same security
-- under several discretions or managers, and an addition that merely adds
-- holdings of securities already held keeps them, as a different manager's
-- book is a different holding. Only lineages with a contributing addition
-- are compared, so the window runs over a small part of the holdings.

with contributing as (
    select
        lineage.cik,
        lineage.period_of_report,
        lineage.filing_position,
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
),

addition_lineages as (
    select distinct cik as addition_cik, period_of_report as addition_period
    from {{ ref('lineage_filings') }}
    where is_contributing and filing_role = 'addition'
),

flagged as (
    select
        contributing.*,
        {{ is_copied_holding() }} as is_copied
    from contributing
    inner join addition_lineages
        on addition_lineages.addition_cik = contributing.cik
        and addition_lineages.addition_period = contributing.period_of_report
    union all
    select
        contributing.*,
        false as is_copied
    from contributing
    left join addition_lineages
        on addition_lineages.addition_cik = contributing.cik
        and addition_lineages.addition_period = contributing.period_of_report
    where addition_lineages.addition_cik is null
)

select
    cik,
    period_of_report,
    accession_number,
    filing_role,
    filing_date,
    origin,
    holding_key,
    name_of_issuer,
    title_of_class,
    cusip,
    figi,
    value_as_filed,
    value_unit,
    value_usd,
    shares_or_principal_amount,
    shares_or_principal_amount_type,
    put_call,
    investment_discretion,
    other_manager_sequence_numbers,
    voting_sole,
    voting_shared,
    voting_none,
    source_file,
    source_row
from flagged
where not (filing_role = 'addition' and is_copied)
