-- Amendment resolution, one row per data-quality check and path: the
-- filings and lineages it flags. A data-quality row never stops the build,
-- so this is where an operator reads how many there are.
-- data_quality_counts_match_the_lineage_profile pins the data-set counts of
-- ten checks to the pass over the 54 zips.
with flagged_lineages as (
    select distinct check_name, origin, cik, period_of_report
    from {{ ref('data_quality_rows') }}
),

lineage_counts as (
    select check_name, origin, count(*) as lineages
    from flagged_lineages
    group by check_name, origin
),

filing_counts as (
    select check_name, origin, count(*) as filings
    from {{ ref('data_quality_rows') }}
    group by check_name, origin
)

select
    filing_counts.check_name,
    filing_counts.origin,
    filing_counts.filings,
    lineage_counts.lineages
from filing_counts
inner join lineage_counts
    on lineage_counts.check_name = filing_counts.check_name
    and lineage_counts.origin = filing_counts.origin
