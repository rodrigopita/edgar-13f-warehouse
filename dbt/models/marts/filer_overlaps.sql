-- Portfolio overlap between the largest filers of each period: every pair
-- of the filers ranked first to the overlap_filers var (100 by default) by
-- value, ties broken by CIK, once, with how many securities both hold and
-- how much of their portfolios those make up. The terms are those of
-- CONTEXT.md.
--
-- Every pair of all filers would be some 40 million rows a period, so the
-- mart keeps the largest filers, about 5,000 pairs a period; any other two
-- filers compare by the same join over positions. A filer worth nothing is
-- never ranked. Options stay out, as in filer_periods, since a put or a
-- call is stated at the value of the underlying.
--
-- weight_overlap sums, over the securities both hold, the smaller of the
-- two filers' weights, a weight being the position's share of the filer
-- period's value: 1 for identical portfolios, 0 for disjoint ones. The
-- weights divide in floating point, since Snowflake rounds a division of
-- integers to six decimals. Pairs that share nothing are kept with zeros.

with ranked_filers as (
    select
        cik,
        filer_name,
        period_of_report,
        value_usd
    from {{ ref('filer_periods') }}
    where value_usd > 0
    qualify row_number() over (
        partition by period_of_report
        order by value_usd desc, cik
    ) <= {{ var('overlap_filers', 100) }}
),

weights as (
    select
        positions.cik,
        positions.period_of_report,
        positions.cusip,
        cast(positions.value_usd as double) / cast(ranked.value_usd as double) as weight
    from {{ ref('positions') }} as positions
    inner join ranked_filers as ranked
        on ranked.cik = positions.cik
        and ranked.period_of_report = positions.period_of_report
    where not positions.is_option
),

pairs as (
    select
        ranked.period_of_report,
        ranked.cik,
        ranked.filer_name,
        other.cik as other_cik,
        other.filer_name as other_filer_name
    from ranked_filers as ranked
    inner join ranked_filers as other
        on other.period_of_report = ranked.period_of_report
        and other.cik > ranked.cik
),

shared as (
    select
        held.period_of_report,
        held.cik,
        other.cik as other_cik,
        count(*) as shared_securities,
        sum(least(held.weight, other.weight)) as weight_overlap
    from weights as held
    inner join weights as other
        on other.period_of_report = held.period_of_report
        and other.cusip = held.cusip
        and other.cik > held.cik
    group by held.period_of_report, held.cik, other.cik
)

select
    pairs.period_of_report,
    pairs.cik,
    pairs.filer_name,
    pairs.other_cik,
    pairs.other_filer_name,
    coalesce(shared.shared_securities, 0) as shared_securities,
    coalesce(shared.weight_overlap, 0) as weight_overlap
from pairs
left join shared
    on shared.period_of_report = pairs.period_of_report
    and shared.cik = pairs.cik
    and shared.other_cik = pairs.other_cik
