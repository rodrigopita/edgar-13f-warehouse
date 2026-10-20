-- Entries, exits, increases and decreases, in the terms of CONTEXT.md: for
-- each filer period that can be compared with its previous period, every
-- position of either period side by side, one row per cik, period, CUSIP
-- and put or call. "What did filer X buy and sell last quarter" is one
-- select on this model: its cik and period, change_kind other than
-- unchanged.
--
-- Only a filer period whose comparison_basis is 'previous period' has rows:
-- without canonical holdings in both periods an entry or an exit says
-- nothing, so a filer's first report, a period after a notice or a skipped
-- period has none, and filer_periods says why. A position in the period
-- and not the previous one is an entry, the reverse an exit. A position in
-- both increases, decreases or stays by its amount, not its value, which
-- moves with price, and only when both amounts are stated the same way;
-- a position stated in shares in one period and in principal in the other,
-- or mixing the two, is not comparable. A put matches a put, a call a
-- call, and the security itself, whose put_call is null, only itself.
--
-- A 13F lists holdings and not trades, so an increase may net several
-- trades or be a stock split, and a security whose CUSIP changed exits
-- under one and enters under the other.

with compared_periods as (
    select cik, filer_name, period_of_report, previous_period
    from {{ ref('filer_periods') }}
    where comparison_basis = 'previous period'
),

current_positions as (
    select
        compared.cik,
        compared.filer_name,
        compared.period_of_report,
        compared.previous_period,
        positions.cusip,
        positions.put_call,
        coalesce(positions.put_call, 'none') as put_call_key,
        positions.shares_or_principal_amount_type,
        positions.shares_or_principal_amount,
        positions.value_usd
    from {{ ref('positions') }} as positions
    inner join compared_periods as compared
        on compared.cik = positions.cik
        and compared.period_of_report = positions.period_of_report
),

previous_positions as (
    select
        compared.cik,
        compared.filer_name,
        compared.period_of_report,
        compared.previous_period,
        positions.cusip,
        positions.put_call,
        coalesce(positions.put_call, 'none') as put_call_key,
        positions.shares_or_principal_amount_type,
        positions.shares_or_principal_amount,
        positions.value_usd
    from {{ ref('positions') }} as positions
    inner join compared_periods as compared
        on compared.cik = positions.cik
        and compared.previous_period = positions.period_of_report
),

paired as (
    select
        coalesce(held.cik, was_held.cik) as cik,
        coalesce(held.filer_name, was_held.filer_name) as filer_name,
        coalesce(held.period_of_report, was_held.period_of_report) as period_of_report,
        coalesce(held.previous_period, was_held.previous_period) as previous_period,
        coalesce(held.cusip, was_held.cusip) as cusip,
        coalesce(held.put_call, was_held.put_call) as put_call,
        held.cik is not null as is_held,
        was_held.cik is not null as was_held,
        held.shares_or_principal_amount_type,
        held.shares_or_principal_amount,
        was_held.shares_or_principal_amount_type as previous_shares_or_principal_amount_type,
        was_held.shares_or_principal_amount as previous_shares_or_principal_amount,
        held.value_usd,
        was_held.value_usd as previous_value_usd
    from current_positions as held
    full outer join previous_positions as was_held
        on was_held.cik = held.cik
        and was_held.period_of_report = held.period_of_report
        and was_held.cusip = held.cusip
        and was_held.put_call_key = held.put_call_key
),

classified as (
    select
        *,
        is_held
            and was_held
            and shares_or_principal_amount_type = previous_shares_or_principal_amount_type
            and shares_or_principal_amount is not null
            and previous_shares_or_principal_amount is not null
            as is_comparable
    from paired
)

select
    classified.cik,
    classified.filer_name,
    classified.period_of_report,
    classified.previous_period,
    classified.cusip,
    securities.name_of_issuer,
    securities.title_of_class,
    classified.put_call,
    classified.put_call is not null as is_option,
    case
        when not classified.was_held then 'entry'
        when not classified.is_held then 'exit'
        when not classified.is_comparable then 'not comparable'
        when classified.shares_or_principal_amount > classified.previous_shares_or_principal_amount then 'increase'
        when classified.shares_or_principal_amount < classified.previous_shares_or_principal_amount then 'decrease'
        else 'unchanged'
    end as change_kind,
    classified.shares_or_principal_amount_type,
    classified.shares_or_principal_amount,
    classified.previous_shares_or_principal_amount_type,
    classified.previous_shares_or_principal_amount,
    case
        when classified.is_comparable
            then classified.shares_or_principal_amount - classified.previous_shares_or_principal_amount
    end as amount_change,
    classified.value_usd,
    classified.previous_value_usd
from classified
left join {{ ref('securities') }} as securities
    on securities.cusip = classified.cusip
