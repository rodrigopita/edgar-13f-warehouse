-- Filings discovered against filings loaded, one row per day the walk
-- covered: the 13F filings the day's index listed, as the latest audit
-- record covering the day counts them, against the filings in CORE with
-- that filing date. A rerun or a later run's sweep can cover a day again,
-- and the latest record stands. The walk's first day, 2026-08-31, is also
-- the last day of the last data set, so its filings load from the data
-- sets, and loaded_from_data_sets says so. A filing posted to a later
-- day's index keeps its own filing date, so it counts on that date and not
-- on its index day; the totals over all days are unaffected.
with day_records as (
    select
        walk_day,
        discovered,
        holdings_reports,
        holdings_report_amendments,
        notices,
        notice_amendments,
        run_id,
        recorded_at,
        count(*) over (partition by walk_day) as audit_records,
        row_number() over (
            partition by walk_day order by recorded_at desc, source_file desc
        ) as recency
    from {{ ref('stg_audit_walk_days') }}
),

loaded_filings as (
    select
        filing_date,
        count(distinct accession_number) as loaded,
        count(distinct case when origin = 'data_set' then accession_number end)
            as loaded_from_data_sets
    from {{ ref('filings') }}
    group by filing_date
)

select
    day_records.walk_day,
    day_records.discovered,
    day_records.holdings_reports,
    day_records.holdings_report_amendments,
    day_records.notices,
    day_records.notice_amendments,
    coalesce(loaded_filings.loaded, 0) as loaded,
    coalesce(loaded_filings.loaded_from_data_sets, 0) as loaded_from_data_sets,
    day_records.discovered - coalesce(loaded_filings.loaded, 0) as not_loaded,
    day_records.audit_records,
    day_records.run_id,
    day_records.recorded_at
from day_records
left join loaded_filings
    on loaded_filings.filing_date = day_records.walk_day
where day_records.recency = 1
