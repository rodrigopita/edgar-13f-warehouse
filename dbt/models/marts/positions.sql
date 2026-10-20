-- One row per position, in the terms of CONTEXT.md: a filer's canonical
-- holdings of one security in one period, keyed by cik, period, CUSIP and
-- put or call. The holdings of a position are summed whatever discretion,
-- other manager or contributing filing each comes from, as the position
-- decision in docs/scope.md (2026-10-19) has it. A put or a call on a
-- security is a position of its own, apart from the security, since its
-- value is the underlying's; is_option says which.
--
-- The amount is summed only when every holding of the position states it
-- the same way. On 2026-10-19, 6,373 positions mixed shares and principal,
-- and a sum of the two means nothing, so they keep their value and carry
-- no amount and no amount type.

select
    cik,
    period_of_report,
    cusip,
    put_call,
    put_call is not null as is_option,
    count(*) as holding_count,
    count(distinct accession_number) as filing_count,
    sum(value_usd) as value_usd,
    case
        when count(distinct shares_or_principal_amount_type) = 1
            and count(shares_or_principal_amount_type) = count(*)
            then min(shares_or_principal_amount_type)
    end as shares_or_principal_amount_type,
    case
        when count(distinct shares_or_principal_amount_type) = 1
            and count(shares_or_principal_amount_type) = count(*)
            then sum(shares_or_principal_amount)
    end as shares_or_principal_amount
from {{ ref('canonical_holdings') }}
group by cik, period_of_report, cusip, put_call
