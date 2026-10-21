-- Data-quality rows: facts about a filing that the rules resolved without
-- the source settling them, or that the source contradicts. They travel
-- with the data instead of stopping the build. One row per filing and
-- check; the checks are named for the rules in docs/scope.md, Decisions,
-- 2026-10-15 to 2026-10-17.

with filing_state as (
    select
        filings.accession_number,
        filings.cik,
        filings.period_of_report,
        filings.filing_date,
        filings.submission_type,
        filings.is_amendment,
        filings.cover_is_amendment,
        filings.amendment_type,
        filings.amendment_no,
        filings.report_type,
        filings.report_calendar_or_quarter,
        filings.table_entry_total,
        filings.table_value_total_as_filed,
        filings.origin,
        lineage.filing_position,
        lineage.filing_role,
        lineage.effective_position,
        lineage.is_superseded,
        lineage.is_contributing
    from {{ ref('filings') }} as filings
    inner join {{ ref('lineage_filings') }} as lineage
        on lineage.accession_number = filings.accession_number
),

holding_totals as (
    select accession_number, count(*) as holdings_count, sum(value_as_filed) as value_as_filed
    from {{ ref('holdings') }}
    group by accession_number
),

untyped_amendments as (
    select
        'untyped_amendment' as check_name,
        cik,
        period_of_report,
        accession_number,
        origin,
        submission_type || ' names no amendment type on its cover; read as a restatement' as detail
    from filing_state
    where is_amendment and amendment_type is null
),

second_originals as (
    select
        'second_original' as check_name,
        cik,
        period_of_report,
        accession_number,
        origin,
        '13F-HR at position ' || filing_position || ' of its lineage; read as a restatement' as detail
    from filing_state
    where submission_type = '13F-HR' and filing_role = 'restatement'
),

cover_boxes as (
    select
        'cover_box_disagrees_with_submission_type' as check_name,
        cik,
        period_of_report,
        accession_number,
        origin,
        'submission type ' || submission_type || ', amendment box '
            || coalesce(iff(cover_is_amendment, 'Y', 'N'), 'blank') as detail
    from filing_state
    where coalesce(cover_is_amendment, false) <> is_amendment
),

report_types as (
    select
        'report_type_disagrees_with_submission_type' as check_name,
        cik,
        period_of_report,
        accession_number,
        origin,
        'submission type ' || submission_type || ', report type ' || report_type as detail
    from filing_state
    where (submission_type like '13F-NT%') <> (report_type = '13F NOTICE')
),

cover_periods as (
    select
        'period_disagrees_with_cover' as check_name,
        cik,
        period_of_report,
        accession_number,
        origin,
        'cover period ' || coalesce(to_varchar(report_calendar_or_quarter), 'missing') as detail
    from filing_state
    where report_calendar_or_quarter is distinct from period_of_report
),

chain_starts as (
    select
        'lineage_starts_with_amendment' as check_name,
        cik,
        period_of_report,
        accession_number,
        origin,
        'the first holdings filing of the lineage is a ' || filing_role || ' filed as 13F-HR/A' as detail
    from filing_state
    where filing_role <> 'notice'
    qualify row_number() over (partition by cik, period_of_report order by filing_position) = 1
        and submission_type = '13F-HR/A'
),

same_date_submitters as (
    select
        'filings_of_one_date_across_submitters' as check_name,
        cik,
        period_of_report,
        accession_number,
        origin,
        'filed ' || to_varchar(filing_date)
            || ' beside a filing from another submitter; accession order between them is arbitrary' as detail
    from filing_state
    where filing_role <> 'notice'
    qualify min(left(accession_number, 10)) over (partition by cik, period_of_report, filing_date)
        <> max(left(accession_number, 10)) over (partition by cik, period_of_report, filing_date)
),

number_ordered as (
    select
        'filing_order_set_by_amendment_number' as check_name,
        cik,
        period_of_report,
        accession_number,
        origin,
        'amendment ' || coalesce(to_varchar(amendment_no), 'none') || ' takes position ' || filing_position
            || ' among the filings of ' || to_varchar(filing_date) || ', against accession order' as detail
    from filing_state
    where filing_role <> 'notice'
    qualify row_number() over (
        partition by cik, period_of_report order by {{ filing_order() }}
    ) <> row_number() over (
        partition by cik, period_of_report order by filing_date, accession_number
    )
),

summaries as (
    select
        'summary_disagrees_with_holdings' as check_name,
        state.cik,
        state.period_of_report,
        state.accession_number,
        state.origin,
        iff(
            state.table_entry_total is null,
            'no summary page; the table holds ' || coalesce(totals.holdings_count, 0) || ' holdings',
            'summary ' || state.table_entry_total || ' entries worth ' || state.table_value_total_as_filed
                || ' as filed; the table holds ' || coalesce(totals.holdings_count, 0) || ' worth '
                || coalesce(totals.value_as_filed, 0)
        ) as detail
    from filing_state as state
    left join holding_totals as totals
        on totals.accession_number = state.accession_number
    where state.filing_role <> 'notice'
        and (
            state.table_entry_total is distinct from coalesce(totals.holdings_count, 0)
            or state.table_value_total_as_filed is distinct from coalesce(totals.value_as_filed, 0)
        )
),

superseded_additions as (
    select
        additions.accession_number,
        additions.cik,
        additions.period_of_report,
        additions.origin,
        effective.accession_number as effective_accession
    from filing_state as additions
    inner join filing_state as effective
        on effective.cik = additions.cik
        and effective.period_of_report = additions.period_of_report
        and effective.filing_position = additions.effective_position
    where additions.filing_role = 'addition' and additions.is_superseded
),

added_securities as (
    select distinct
        superseded.accession_number,
        superseded.cik,
        superseded.period_of_report,
        superseded.origin,
        superseded.effective_accession,
        holdings.cusip
    from superseded_additions as superseded
    inner join {{ ref('holdings') }} as holdings
        on holdings.accession_number = superseded.accession_number
),

restated_securities as (
    select distinct holdings.accession_number, holdings.cusip
    from {{ ref('holdings') }} as holdings
    inner join (select distinct effective_accession from superseded_additions) as effective
        on effective.effective_accession = holdings.accession_number
),

unrestated_additions as (
    select
        'superseded_addition_not_restated' as check_name,
        added.cik,
        added.period_of_report,
        added.accession_number,
        added.origin,
        count(*) || ' of the securities it added are not in ' || added.effective_accession
            || ', the restatement that supersedes it' as detail
    from added_securities as added
    left join restated_securities as restated
        on restated.accession_number = added.effective_accession
        and restated.cusip = added.cusip
    where restated.cusip is null
    group by added.cik, added.period_of_report, added.accession_number, added.origin, added.effective_accession
),

unit_overrides as (
    select
        'value_unit_overrides_filing_date_rule' as check_name,
        state.cik,
        state.period_of_report,
        state.accession_number,
        state.origin,
        'median value per share as filed is ' || to_varchar(round(units.median_value_per_share, 4))
            || '; read as ' || units.value_unit || ' where the filing date says ' || units.filing_date_unit as detail
    from {{ ref('filing_value_units') }} as units
    inner join filing_state as state
        on state.accession_number = units.accession_number
    where units.value_unit <> units.filing_date_unit
),

share_prices as (
    select
        holdings.accession_number,
        state.period_of_report,
        holdings.cusip,
        holdings.value_usd / holdings.shares_or_principal_amount as usd_per_share
    from {{ ref('holdings') }} as holdings
    inner join filing_state as state
        on state.accession_number = holdings.accession_number
    where holdings.shares_or_principal_amount_type = 'SH'
        and holdings.shares_or_principal_amount > 0
        and holdings.put_call is null
),

yardsticks as (
    select period_of_report, cusip, median(usd_per_share) as yardstick_usd_per_share
    from share_prices
    group by period_of_report, cusip
    having count(*) >= 5 and median(usd_per_share) > 0
),

price_ratios as (
    select
        prices.accession_number,
        median(prices.usd_per_share / yardsticks.yardstick_usd_per_share) as median_ratio
    from share_prices as prices
    inner join yardsticks
        on yardsticks.period_of_report = prices.period_of_report
        and yardsticks.cusip = prices.cusip
    group by prices.accession_number
),

off_yardstick as (
    select
        'value_off_yardstick_by_a_thousand' as check_name,
        state.cik,
        state.period_of_report,
        state.accession_number,
        state.origin,
        'median value per share is ' || to_varchar(round(ratios.median_ratio, 5))
            || ' times the median across filers of the same security and period' as detail
    from price_ratios as ratios
    inner join filing_state as state
        on state.accession_number = ratios.accession_number
    where ratios.median_ratio < 0.01 or ratios.median_ratio > 100
),

lineages_with_additions as (
    select distinct cik, period_of_report
    from filing_state
    where filing_role = 'addition' and is_contributing
),

contributing_securities as (
    select distinct
        state.accession_number,
        state.cik,
        state.period_of_report,
        state.origin,
        state.filing_position,
        state.filing_role,
        holdings.cusip
    from filing_state as state
    inner join lineages_with_additions as lineages
        on lineages.cik = state.cik
        and lineages.period_of_report = state.period_of_report
    inner join {{ ref('holdings') }} as holdings
        on holdings.accession_number = state.accession_number
    where state.is_contributing
),

repeated_securities as (
    select
        'repeated_security_in_addition' as check_name,
        later.cik,
        later.period_of_report,
        later.accession_number,
        later.origin,
        count(distinct later.cusip) || ' of its securities are already in effect from an earlier filing' as detail
    from contributing_securities as later
    inner join contributing_securities as earlier
        on earlier.cik = later.cik
        and earlier.period_of_report = later.period_of_report
        and earlier.filing_position < later.filing_position
        and earlier.cusip = later.cusip
    where later.filing_role = 'addition'
    group by later.cik, later.period_of_report, later.accession_number, later.origin
),

restated_additions as (
    select
        'addition_read_as_restatement' as check_name,
        state.cik,
        state.period_of_report,
        state.accession_number,
        state.origin,
        'repeats ' || coverage.repeated_securities || ' of the ' || coverage.compared_securities
            || ' securities of ' || coverage.compared_accession_number
            || ', the filing it amends; read as a restatement' as detail
    from {{ ref('addition_coverage') }} as coverage
    inner join filing_state as state
        on state.accession_number = coverage.accession_number
    where coverage.is_read_as_restatement
),

copy_filings as (
    select
        state.accession_number,
        state.cik,
        state.period_of_report,
        state.origin,
        state.filing_position,
        state.filing_role
    from filing_state as state
    inner join lineages_with_additions as lineages
        on lineages.cik = state.cik
        and lineages.period_of_report = state.period_of_report
    where state.is_contributing
),

copy_holdings as (
    select
        filings.accession_number,
        filings.cik,
        filings.period_of_report,
        filings.origin,
        filings.filing_position,
        filings.filing_role,
        holdings.cusip,
        holdings.put_call,
        holdings.shares_or_principal_amount,
        holdings.shares_or_principal_amount_type,
        holdings.investment_discretion,
        holdings.other_manager_sequence_numbers
    from copy_filings as filings
    inner join {{ ref('holdings') }} as holdings
        on holdings.accession_number = filings.accession_number
),

copy_flags as (
    select
        *,
        {{ is_copied_holding() }} as is_copied
    from copy_holdings
),

copied_holdings as (
    select
        'copied_holding_in_addition' as check_name,
        cik,
        period_of_report,
        accession_number,
        origin,
        count(case when is_copied then 1 end) || ' of its ' || count(*)
            || ' holdings copy holdings already in effect; they are left out of canonical holdings' as detail
    from copy_flags
    where filing_role = 'addition'
    group by cik, period_of_report, accession_number, origin
    having count(case when is_copied then 1 end) > 0
),

-- A notice says another manager reports the filer's holdings, so it
-- carries none; the submission type decides, and the holdings a notice
-- lists never count.
notice_holdings as (
    select
        'notice_with_holdings' as check_name,
        state.cik,
        state.period_of_report,
        state.accession_number,
        state.origin,
        'a notice that lists ' || totals.holdings_count
            || ' holdings; they are left out of canonical holdings' as detail
    from filing_state as state
    inner join holding_totals as totals
        on totals.accession_number = state.accession_number
    where state.filing_role = 'notice'
)

select * from untyped_amendments
union all select * from second_originals
union all select * from cover_boxes
union all select * from report_types
union all select * from cover_periods
union all select * from chain_starts
union all select * from same_date_submitters
union all select * from number_ordered
union all select * from summaries
union all select * from unrestated_additions
union all select * from repeated_securities
union all select * from restated_additions
union all select * from copied_holdings
union all select * from unit_overrides
union all select * from off_yardstick
union all select * from notice_holdings
