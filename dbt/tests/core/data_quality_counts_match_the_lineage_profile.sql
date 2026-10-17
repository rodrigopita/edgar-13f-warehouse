-- The data-set rows of each check against the count a separate Python pass
-- over the 54 zips found on 2026-10-16 and 2026-10-17, so the SQL and the
-- profile check each other. The data sets are fixed history until the next
-- one is loaded, which moves these numbers on purpose. The summary,
-- repeated-security and yardstick checks have no independent count yet and
-- are left out.
with expected as (
    select 'untyped_amendment' as check_name, 55 as filings
    union all select 'second_original', 28
    union all select 'cover_box_disagrees_with_submission_type', 93
    union all select 'report_type_disagrees_with_submission_type', 11
    union all select 'period_disagrees_with_cover', 5
    union all select 'lineage_starts_with_amendment', 421
    union all select 'filings_of_one_date_across_submitters', 57
    union all select 'filing_order_set_by_amendment_number', 88
    union all select 'superseded_addition_not_restated', 67
    union all select 'value_unit_overrides_filing_date_rule', 13500
),

actual as (
    select check_name, count(*) as filings
    from {{ ref('data_quality_rows') }}
    where origin = 'data_set'
    group by check_name
)

select expected.check_name, expected.filings as expected_filings, coalesce(actual.filings, 0) as actual_filings
from expected
left join actual
    on actual.check_name = expected.check_name
where expected.filings <> coalesce(actual.filings, 0)
