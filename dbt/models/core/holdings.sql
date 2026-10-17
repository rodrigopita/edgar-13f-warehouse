-- One row per holding, from both paths, typed, with its value as filed and
-- in dollars by its filing's unit from filing_value_units. The key is the
-- accession with the holding's identity on its own path: INFOTABLE_SK in
-- the data sets, the 1-based row of the information table on the walk.
-- Every holding is here, in effect or not; canonical_holdings keeps the
-- ones the lineage says are in effect.

with data_set_holdings as (
    select
        accession_number,
        'data_set' as origin,
        infotable_sk as holding_key,
        name_of_issuer,
        title_of_class,
        cusip,
        figi,
        value_as_filed,
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
    from {{ ref('stg_dataset_infotable') }}
),

walk_holdings as (
    select
        accession_number,
        'walk' as origin,
        row_index as holding_key,
        name_of_issuer,
        title_of_class,
        cusip,
        figi,
        value_as_filed,
        shares_or_principal_amount,
        shares_or_principal_amount_type,
        put_call,
        investment_discretion,
        other_manager_sequence_numbers::array as other_manager_sequence_numbers,
        voting_sole,
        voting_shared,
        voting_none,
        source_file,
        source_row
    from {{ ref('stg_xml_holdings') }}
),

all_holdings as (
    select * from data_set_holdings
    union all
    select * from walk_holdings
)

select
    all_holdings.accession_number,
    all_holdings.origin,
    all_holdings.holding_key,
    all_holdings.name_of_issuer,
    all_holdings.title_of_class,
    all_holdings.cusip,
    all_holdings.figi,
    all_holdings.value_as_filed,
    units.value_unit,
    all_holdings.value_as_filed * units.value_multiplier as value_usd,
    all_holdings.shares_or_principal_amount,
    all_holdings.shares_or_principal_amount_type,
    all_holdings.put_call,
    all_holdings.investment_discretion,
    all_holdings.other_manager_sequence_numbers,
    all_holdings.voting_sole,
    all_holdings.voting_shared,
    all_holdings.voting_none,
    all_holdings.source_file,
    all_holdings.source_row
from all_holdings
inner join {{ ref('filing_value_units') }} as units
    on units.accession_number = all_holdings.accession_number
