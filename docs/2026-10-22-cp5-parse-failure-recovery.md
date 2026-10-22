# cp5: a parse failure, found and recovered

Written 2026-10-22 from the four queries in this document, run before and after one step in Airflow. It is the first part of the cp5 failure demo: a failure the pipeline recorded about itself, found in the observability models, recovered without a request to EDGAR, and checked by the same queries.

## What the numbers say

- **Nine filings had failed to parse, and the warehouse said which.** Before the recovery, `walk_failures` listed nine parse failures and none loaded since: eight notices the parser refused for carrying a summary page, on the runs of 2026-10-14 and 2026-10-17, before `7759cbe` accepted one late on 2026-10-17, and one holdings report. `walk_days` counted 2,562 filings discovered over 36 days and 2,553 loaded, nine short on four days.
- **One step recovered eight.** Clearing `parse_batch` with `record_audit` downstream in the two runs parsed the eight notices from the XML already in S3. No task that calls EDGAR ran: `plan_walk`, `land_indexes` and `walk_batch` were not cleared, and `parse_batch` reads only what was landed.
- **Each rerun wrote an audit record of its own.** The first record of each day stays as written; the rerun added one under its own key, `day=2026-10-13/scheduled__2026-10-14T06-00-00-00-00/2026-10-22T11-39-57.488143-00-00.json` and its twin for 2026-10-16, reading `parsed` 2 and 6, `parsed_already_present` 342 and 244, and no parse failures. `walk_days` reads the latest record of a day, so the rerun's count stands.
- **The pipes loaded both without hands.** The eight notices are in `RAW.PARSED_FILINGS`, one cover page each, written to S3 between 11:39:39 and 11:40:24 UTC, and the two audit records are in `AUDIT.WALK_RUNS`. Each is one cover page, so they add no holdings.
- **One filing is left, and the day that reads minus one is two late filings.** After the recovery 2,561 of 2,562 are loaded. 2026-10-13 reads one more loaded than discovered and 2026-10-15 one fewer because two filings were posted to a later day's index: the index of 2026-10-14 lists `0002079652-26-000005`, dated 2026-10-13, and the index of 2026-10-15 lists `0001172661-26-004529`, Porter White Investment Advisors, dated 2026-10-14. Each counts on its own filing date; across all 36 indexes these are the only two.
- **The filing left is a placeholder table.** The information table of `0001643792-26-000012`, a 13F-HR of 2026-10-19, has one entry: a blank `nameOfIssuer`, CUSIP `000000000`, value 0, 0 shares. The parser refuses a blank issuer name ("name_of_issuer: Input should be a valid string"), so the filing stays out, cover page and all. Data-set staging reads a blank field as null and keeps such a row, so the two paths treat it differently; `walk_failures` keeps showing it until that is settled.
- **2026-08-31 was never a failure.** The walk's first day is the last day of the last data set. Its five 13F-HR are in that data set, filed 31-AUG-2026, and the data set holds no other filing of that date; the cp2 proof of 2026-10-11 left them unparsed for that reason. `walk_days` counts them from the data sets since `ae53137`.

## How it was run

On 2026-10-22, at `ae53137`:

1. A full `dbt build`, 268 of 268, then the four queries below: the before.
2. In the Airflow UI, `parse_batch` cleared with Downstream in run `scheduled__2026-10-14T06:00:00+00:00`, which walks 2026-10-13: four `parse_batch` instances and `record_audit`. The same in run `scheduled__2026-10-17T06:00:00+00:00`, which walks 2026-10-16: three and `record_audit`. Each preview listed only those tasks.
3. Once both runs were green and the pipes had loaded, a second full `dbt build`, 268 of 268, then the queries again: the after.

The queries ran as SYSADMIN in `JOPUFPW-EDGAR_13F`, and `EDGAR_WH` was suspended after them.

## The queries, before and after

The audit records of the two days:

```sql
select walk_day, run_id, recorded_at, parsed, parsed_already_present,
       parse_failures, source_file
from edgar_13f.core.stg_audit_walk_runs
where walk_day in ('2026-10-13', '2026-10-16')
order by walk_day, recorded_at;
```

| walk_day   | recorded_at (UTC)   | parsed | parsed_already_present | parse_failures | in the results   |
| ---------- | ------------------- | -----: | ---------------------: | -------------: | ---------------- |
| 2026-10-13 | 2026-10-14 11:05:34 |    342 |                      0 |              2 | before and after |
| 2026-10-13 | 2026-10-22 11:39:57 |      2 |                    342 |              0 | after only |
| 2026-10-16 | 2026-10-17 06:09:19 |    244 |                      0 |              6 | before and after |
| 2026-10-16 | 2026-10-22 11:40:26 |      6 |                    244 |              0 | after only |

The eight notices in RAW:

```sql
select record:accession::string as accession_number,
       count(*) as rows_loaded,
       min(source_last_modified) as written_to_s3_at
from edgar_13f.raw.parsed_filings
where record:accession::string in (
    '0001510483-26-000007', '0001758171-26-000005',
    '0000928633-26-000004', '0001263005-26-000005', '0001352469-26-000006',
    '0001844756-26-000005', '0001844757-26-000005', '0001915577-26-000005'
)
group by 1
order by 1;
```

Before: no rows. After: eight rows, one each, written between 11:39:39 and 11:40:24 UTC on 2026-10-22.

The parse failures:

```sql
select accession_number, submission_type, walk_day, failed_attempts,
       last_run_id, is_loaded
from edgar_13f.observability.walk_failures
order by walk_day, accession_number;
```

| accession_number     | submission_type | walk_day   | is_loaded before | is_loaded after |
| -------------------- | --------------- | ---------- | ---------------- | --------------- |
| 0001510483-26-000007 | 13F-NT          | 2026-10-13 | false            | true            |
| 0001758171-26-000005 | 13F-NT          | 2026-10-13 | false            | true            |
| 0000928633-26-000004 | 13F-NT          | 2026-10-16 | false            | true            |
| 0001263005-26-000005 | 13F-NT          | 2026-10-16 | false            | true            |
| 0001352469-26-000006 | 13F-NT          | 2026-10-16 | false            | true            |
| 0001844756-26-000005 | 13F-NT          | 2026-10-16 | false            | true            |
| 0001844757-26-000005 | 13F-NT          | 2026-10-16 | false            | true            |
| 0001915577-26-000005 | 13F-NT          | 2026-10-16 | false            | true            |
| 0001643792-26-000012 | 13F-HR          | 2026-10-19 | false            | false           |

Each failed once; a rerun that parses a filing records no failure, so `failed_attempts` and `last_run_id` do not change.

The days that do not reconcile, and the totals:

```sql
select walk_day, discovered, loaded, loaded_from_data_sets, not_loaded,
       audit_records
from edgar_13f.observability.walk_days
where not_loaded <> 0 or loaded_from_data_sets <> 0
order by walk_day;

select count(*) as walk_days, sum(discovered) as discovered,
       sum(loaded) as loaded, sum(not_loaded) as not_loaded
from edgar_13f.observability.walk_days;
```

| walk_day   | discovered | loaded before | loaded after | from data sets | not_loaded before | not_loaded after |
| ---------- | ---------: | ------------: | -----------: | -------------: | ----------------: | ---------------: |
| 2026-08-31 |          5 |             5 |            5 |              5 |                 0 |                0 |
| 2026-10-13 |        344 |           343 |          345 |              0 |                 1 |               -1 |
| 2026-10-15 |        203 |           202 |          202 |              0 |                 1 |                1 |
| 2026-10-16 |        250 |           244 |          250 |              0 |                 6 |                0 |
| 2026-10-19 |        233 |           232 |          232 |              0 |                 1 |                1 |
| all 36     |      2,562 |         2,553 |        2,561 |              5 |                 9 |                1 |
