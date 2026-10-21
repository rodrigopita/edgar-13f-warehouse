-- The backfill reconciled, one row per data set table: the rows extracted
-- from the zips as the latest audit record counts them, the rows and files
-- its COPY loaded summed over every run, and the rows in RAW now. A COPY
-- skips the files it loaded in the last 64 days, so the loads of every run
-- add up to the table.
with extracted as (
    select
        table_name,
        extracted_rows,
        row_number() over (partition by table_name order by recorded_at desc) as recency
    from {{ ref('stg_audit_backfill_tables') }}
),

loads as (
    select
        table_name,
        sum(rows_loaded) as rows_loaded,
        sum(files_loaded) as files_loaded,
        count(*) as backfill_runs
    from {{ ref('stg_audit_backfill_tables') }}
    group by table_name
),

raw_tables as (
    select 'COVERPAGE' as table_name, count(*) as raw_rows
    from {{ source('raw', 'dataset_coverpage') }}
    union all
    select 'INFOTABLE', count(*) from {{ source('raw', 'dataset_infotable') }}
    union all
    select 'OTHERMANAGER', count(*) from {{ source('raw', 'dataset_othermanager') }}
    union all
    select 'OTHERMANAGER2', count(*) from {{ source('raw', 'dataset_othermanager2') }}
    union all
    select 'SIGNATURE', count(*) from {{ source('raw', 'dataset_signature') }}
    union all
    select 'SUBMISSION', count(*) from {{ source('raw', 'dataset_submission') }}
    union all
    select 'SUMMARYPAGE', count(*) from {{ source('raw', 'dataset_summarypage') }}
)

select
    extracted.table_name,
    extracted.extracted_rows,
    loads.rows_loaded,
    loads.files_loaded,
    loads.backfill_runs,
    raw_tables.raw_rows
from extracted
inner join loads
    on loads.table_name = extracted.table_name
left join raw_tables
    on raw_tables.table_name = extracted.table_name
where extracted.recency = 1
