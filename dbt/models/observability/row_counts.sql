-- Raw-to-modeled row counts, one row per path. Every raw holding row
-- reaches holdings, which raw_holdings_reach_core_whole tests; each holding
-- then sits in a superseded filing, a contributing one or a notice, and a
-- holding of a contributing filing is canonical unless it is a copied
-- holding. A notice says another manager reports the holdings, so the ones
-- a notice lists never count; on 2026-10-21 eleven data-set notices listed
-- 549. The walk's raw rows count one file version per filing, the one
-- staging keeps.
--
-- set_aside_by_walk automates the reconciliation of 2026-10-20: data-set
-- holdings that would contribute if their lineage held only its data-set
-- filings, and are superseded. Only a restatement supersedes, and none from
-- the data sets follows the latest data-set one, so what supersedes them
-- came from the walk. A pass over the zips alone cannot see those filings,
-- so this is the data-set path's distance from that pass: 64,534 holdings
-- on 2026-10-20.
with raw_rows as (
    select 'data_set' as origin, count(*) as raw_rows
    from {{ source('raw', 'dataset_infotable') }}
    union all
    select 'walk', count(*)
    from {{ ref('stg_xml_filing_records') }}
    where record_type = 'holding'
),

filing_paths as (
    select
        lineage.accession_number,
        lineage.cik,
        lineage.period_of_report,
        lineage.filing_position,
        lineage.filing_role,
        lineage.effective_position,
        lineage.is_superseded,
        lineage.is_contributing,
        filings.origin
    from {{ ref('lineage_filings') }} as lineage
    inner join {{ ref('filings') }} as filings
        on filings.accession_number = lineage.accession_number
),

data_set_effective as (
    select
        cik,
        period_of_report,
        max(case when filing_role in ('original', 'restatement')
            then filing_position end) as effective_position
    from filing_paths
    where origin = 'data_set'
    group by cik, period_of_report
),

set_aside_filings as (
    select filing_paths.accession_number
    from filing_paths
    inner join data_set_effective
        on data_set_effective.cik = filing_paths.cik
        and data_set_effective.period_of_report = filing_paths.period_of_report
    where filing_paths.origin = 'data_set'
        and filing_paths.is_superseded
        and (
            filing_paths.filing_position = data_set_effective.effective_position
            or (
                filing_paths.filing_role = 'addition'
                and (
                    data_set_effective.effective_position is null
                    or filing_paths.filing_position > data_set_effective.effective_position
                )
            )
        )
),

holding_states as (
    select
        holdings.origin,
        count(*) as holdings,
        count(case when filing_paths.is_superseded then 1 end) as superseded_holdings,
        count(case when filing_paths.is_contributing then 1 end) as contributing_holdings,
        count(case when filing_paths.filing_role = 'notice' then 1 end) as notice_holdings,
        count(set_aside_filings.accession_number) as set_aside_by_walk
    from {{ ref('holdings') }} as holdings
    left join filing_paths
        on filing_paths.accession_number = holdings.accession_number
    left join set_aside_filings
        on set_aside_filings.accession_number = holdings.accession_number
    group by holdings.origin
),

canonical as (
    select origin, count(*) as canonical_holdings
    from {{ ref('canonical_holdings') }}
    group by origin
),

filing_states as (
    select
        origin,
        count(*) as filings,
        count(case when is_superseded then 1 end) as superseded_filings
    from filing_paths
    group by origin
)

select
    raw_rows.origin,
    raw_rows.raw_rows,
    holding_states.holdings,
    holding_states.superseded_holdings,
    holding_states.contributing_holdings,
    holding_states.notice_holdings,
    canonical.canonical_holdings,
    holding_states.contributing_holdings - canonical.canonical_holdings as copied_holdings,
    holding_states.holdings - holding_states.superseded_holdings
        - holding_states.contributing_holdings - holding_states.notice_holdings
        as unresolved_holdings,
    holding_states.set_aside_by_walk,
    filing_states.filings,
    filing_states.superseded_filings
from raw_rows
left join holding_states
    on holding_states.origin = raw_rows.origin
left join canonical
    on canonical.origin = raw_rows.origin
left join filing_states
    on filing_states.origin = raw_rows.origin
