-- The unit each filing reports market value in, one row per filing with
-- holdings. The SEC's readme says values are in thousands of dollars before
-- 2023-01-03 and in dollars from that day, by filing date; filers did not
-- all follow it, so the unit is read from the filing itself. A filing whose
-- median value per share as filed is under 1 reports thousands, and 1 or
-- more reports dollars: a dollar price under 1 is a penny stock, a price in
-- thousands over 1 is a share worth more than $1,000. A filing with no
-- share row keeps the filing-date rule. Graded on 2026-10-17 against the
-- 316 late restatements whose original settles their unit: 315 right.

with holding_prices as (
    select accession_number, value_as_filed, shares_or_principal_amount, shares_or_principal_amount_type
    from {{ ref('stg_dataset_infotable') }}
    union all
    select accession_number, value_as_filed, shares_or_principal_amount, shares_or_principal_amount_type
    from {{ ref('stg_xml_holdings') }}
),

per_filing as (
    select
        accession_number,
        median(
            iff(
                shares_or_principal_amount_type = 'SH' and shares_or_principal_amount > 0,
                value_as_filed / shares_or_principal_amount,
                null
            )
        ) as median_value_per_share
    from holding_prices
    group by accession_number
),

ruled as (
    select
        per_filing.accession_number,
        filings.filing_date,
        per_filing.median_value_per_share,
        iff(filings.filing_date < '2023-01-03'::date, 'thousands', 'dollars') as filing_date_unit
    from per_filing
    inner join {{ ref('filings') }} as filings
        on filings.accession_number = per_filing.accession_number
),

read_units as (
    select
        *,
        case
            when median_value_per_share is null then filing_date_unit
            when median_value_per_share < 1 then 'thousands'
            else 'dollars'
        end as value_unit
    from ruled
)

select
    accession_number,
    filing_date,
    median_value_per_share,
    filing_date_unit,
    value_unit,
    iff(value_unit = 'thousands', 1000, 1) as value_multiplier
from read_units
