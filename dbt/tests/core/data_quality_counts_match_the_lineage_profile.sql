-- The data-set rows of each check against the count a separate Python pass
-- over the 54 zips found on 2026-10-16 and 2026-10-17, so the SQL and the
-- profile check each other. The data sets are fixed history until the next
-- one is loaded, which moves these numbers on purpose. The walk lands
-- amendments for old periods every day, and of these checks only the
-- superseded addition depends on a later filing of its lineage, so for that
-- check lineages holding a walk filing are left out. The summary,
-- repeated-security and yardstick checks have no independent count yet and
-- are left out. The unit count divides as Snowflake does, rounding to six
-- decimals, which puts one two-row filing, 0001104659-23-011303, at exactly
-- 1 and so in dollars.
with expected as (
    select 'untyped_amendment' as check_name, 55 as filings
    union all select 'second_original', 28
    union all select 'cover_box_disagrees_with_submission_type', 93
    union all select 'report_type_disagrees_with_submission_type', 11
    union all select 'period_disagrees_with_cover', 5
    union all select 'lineage_starts_with_amendment', 413
    union all select 'filings_of_one_date_across_submitters', 57
    union all select 'filing_order_set_by_amendment_number', 88
    union all select 'superseded_addition_not_restated', 67
    union all select 'value_unit_overrides_filing_date_rule', 13499
),

walk_lineages as (
    select distinct cik, period_of_report
    from {{ ref('filings') }}
    where origin = 'walk'
),

actual as (
    select flagged.check_name, count(*) as filings
    from {{ ref('data_quality_rows') }} as flagged
    left join walk_lineages
        on walk_lineages.cik = flagged.cik
        and walk_lineages.period_of_report = flagged.period_of_report
    where flagged.origin = 'data_set'
        and not (flagged.check_name = 'superseded_addition_not_restated' and walk_lineages.cik is not null)
    group by flagged.check_name
)

select expected.check_name, expected.filings as expected_filings, coalesce(actual.filings, 0) as actual_filings
from expected
left join actual
    on actual.check_name = expected.check_name
where expected.filings <> coalesce(actual.filings, 0)
