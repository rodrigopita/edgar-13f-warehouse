-- One row per filer period with canonical holdings: how the portfolio
-- stands, how concentrated it is, whether it can be compared with the
-- previous period, and what the filings behind it say about themselves.
-- The terms are those of CONTEXT.md and the rules those of the position
-- decision in docs/scope.md (2026-10-19).
--
-- Options stay out of the value and the concentration, since a put or a
-- call is stated at the value of the underlying. top_ten_share is the
-- share of the value in the ten largest positions and hhi the sum of the
-- squared shares of every position; both divide in floating point, since
-- Snowflake rounds a division of integers to six decimals.
--
-- comparison_basis says whether entries and exits mean anything here. They
-- do only when the filer also has canonical holdings for the previous
-- period; otherwise the reason is a column and not a data-quality row,
-- since a skipped period, a notice or a report that lists nothing is a
-- fact of coverage and not a contradiction.
--
-- confidential_omission is true when a contributing filing says holdings
-- were omitted under confidential treatment, false when every one says
-- none were, and null otherwise: the flag is blank on about a third of
-- the filings, and a blank is not a no. The data-quality flags mark a
-- filer period whose contributing filings had their value unit read
-- against the filing date or miss the yardstick by a thousand. They flag
-- and never exclude: the shares here are weights within one filer period,
-- which a unit error across a filing does not change.

with ranked as (
    select
        cik,
        period_of_report,
        is_option,
        value_usd,
        row_number() over (
            partition by cik, period_of_report, is_option
            order by value_usd desc, cusip
        ) as value_rank
    from {{ ref('positions') }}
),

portfolios as (
    select
        cik,
        period_of_report,
        count(case when not is_option then 1 end) as position_count,
        count(case when is_option then 1 end) as option_position_count,
        coalesce(sum(case when not is_option then value_usd end), 0) as value_usd,
        coalesce(sum(case when is_option then value_usd end), 0) as option_value_usd,
        sum(case when not is_option and value_rank <= 10 then value_usd end) as top_ten_value_usd
    from ranked
    group by cik, period_of_report
),

concentrations as (
    select
        portfolios.cik,
        portfolios.period_of_report,
        sum(
            (cast(positions.value_usd as double) / cast(portfolios.value_usd as double))
            * (cast(positions.value_usd as double) / cast(portfolios.value_usd as double))
        ) as hhi
    from {{ ref('positions') }} as positions
    inner join portfolios
        on portfolios.cik = positions.cik
        and portfolios.period_of_report = positions.period_of_report
    where not positions.is_option and portfolios.value_usd > 0
    group by portfolios.cik, portfolios.period_of_report
),

lineages as (
    select
        cik,
        period_of_report,
        count(case when filing_role <> 'notice' then 1 end) as holdings_reports
    from {{ ref('lineage_filings') }}
    group by cik, period_of_report
),

contributing as (
    select
        lineage.cik,
        lineage.period_of_report,
        lineage.accession_number,
        filings.is_confidential_omitted
    from {{ ref('lineage_filings') }} as lineage
    left join {{ ref('filings') }} as filings
        on filings.accession_number = lineage.accession_number
    where lineage.is_contributing
),

confidential as (
    select
        cik,
        period_of_report,
        case
            when count(case when is_confidential_omitted then 1 end) > 0 then true
            when count(case when not is_confidential_omitted then 1 end) = count(*) then false
        end as confidential_omission
    from contributing
    group by cik, period_of_report
),

quality as (
    select
        contributing.cik,
        contributing.period_of_report,
        count(case when flagged.check_name = 'value_unit_overrides_filing_date_rule' then 1 end) > 0
            as has_value_unit_override,
        count(case when flagged.check_name = 'value_off_yardstick_by_a_thousand' then 1 end) > 0
            as has_value_off_yardstick
    from contributing
    inner join {{ ref('data_quality_rows') }} as flagged
        on flagged.accession_number = contributing.accession_number
    group by contributing.cik, contributing.period_of_report
)

select
    portfolios.cik,
    filers.filer_name,
    portfolios.period_of_report,
    periods.previous_period,
    case
        when previous_portfolios.cik is not null then 'previous period'
        when previous_lineages.holdings_reports > 0 then 'previous report lists none'
        when previous_lineages.cik is not null then 'previous notice only'
        else 'no previous filing'
    end as comparison_basis,
    portfolios.position_count,
    portfolios.option_position_count,
    portfolios.value_usd,
    portfolios.option_value_usd,
    case
        when portfolios.value_usd > 0
            then cast(portfolios.top_ten_value_usd as double) / cast(portfolios.value_usd as double)
    end as top_ten_share,
    concentrations.hhi,
    confidential.confidential_omission,
    coalesce(quality.has_value_unit_override, false) as has_value_unit_override,
    coalesce(quality.has_value_off_yardstick, false) as has_value_off_yardstick
from portfolios
left join {{ ref('periods') }} as periods
    on periods.period_of_report = portfolios.period_of_report
left join {{ ref('filers') }} as filers
    on filers.cik = portfolios.cik
left join portfolios as previous_portfolios
    on previous_portfolios.cik = portfolios.cik
    and previous_portfolios.period_of_report = periods.previous_period
left join lineages as previous_lineages
    on previous_lineages.cik = portfolios.cik
    and previous_lineages.period_of_report = periods.previous_period
left join concentrations
    on concentrations.cik = portfolios.cik
    and concentrations.period_of_report = portfolios.period_of_report
left join confidential
    on confidential.cik = portfolios.cik
    and confidential.period_of_report = portfolios.period_of_report
left join quality
    on quality.cik = portfolios.cik
    and quality.period_of_report = portfolios.period_of_report
