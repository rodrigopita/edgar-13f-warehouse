# cp2: the XML path loads without hands

Written 2026-10-11 from one rerun of `edgar_daily_index_walk` and the queries in this document. It is the record of the first cp2 done-criterion: a new XML filing landed in S3 appears in the VARIANT raw table with no manual step.

## What the numbers say

- **96 filings in, 96 files out, 96 loaded.** The run for 2026-10-08 found its 96 filings (86 `13F-HR`, 10 `13F-NT`) already in S3, parsed all of them and wrote one JSON-lines file each under `parsed/edgar/filings/filed=2026-10-08/`. Snowpipe loaded every file: 96 rows in `COPY_HISTORY`, all `LOADED`, no errors.
- **30,429 rows, counted twice.** `RAW.PARSED_FILINGS` holds 96 cover pages and 30,333 holdings. Read straight from S3, the 96 files hold 30,429 lines, and the first line of every file is its cover page.
- **20 seconds at best, 86 at worst.** From the S3 write (`METADATA$FILE_LAST_MODIFIED`) to the row commit (`METADATA$ROW_LAST_COMMIT_TIME`), the median file took 52 seconds. Nothing between the two steps was run by hand: the bucket notification queued each file and the pipe loaded it.
- **Nothing failed to parse; two filings disagree with themselves.** The run's audit record shows `parsed: 96`, `parse_failed: []` and two reconcile gaps, both loaded as designed. `0001641438-26-000006` reports a table value total of 88,102,691 against rows summing to 870,740,683, about 9.9 times more. `0001722641-26-000006` is 210,847 short of its own total of 4,742,640,775. These are data-quality rows for the core layer, the same kind the cp1 profile found in the data sets.
- **No EDGAR filing was fetched twice.** The audit record reads `landed: 0`, `already_present: 96`: the rerun paid HEAD requests for the filings and only fetched the listing and the index.

## How it was run

The DAG's run for logical date 2026-10-09 06:00 UTC (`scheduled__2026-10-09T06:00:00+00:00`, which walks 2026-10-08) was cleared in the Airflow UI and ran with the code at `7dc53de`. Its `parse_batch` task logged `96 parsed`. The files were written between 18:19:33 and 18:21:34 UTC.

The timing query, run as ACCOUNTADMIN in `JOPUFPW-EDGAR_13F`:

```sql
with per_file as (
    select
        source_file,
        count_if(record:record_type::string = 'cover') as covers,
        count_if(record:record_type::string = 'holding') as holdings,
        min(source_last_modified) as written_utc,
        min(convert_timezone('UTC', metadata$row_last_commit_time))::timestamp_ntz
            as committed_utc
    from edgar_13f.raw.parsed_filings
    group by source_file
)
select
    count(*) as files,
    sum(covers) as covers,
    sum(holdings) as holdings,
    min(datediff('second', written_utc, committed_utc)) as fastest_s,
    median(datediff('second', written_utc, committed_utc)) as median_s,
    max(datediff('second', written_utc, committed_utc)) as slowest_s
from per_file;
```

| files | covers | holdings | fastest_s | median_s | slowest_s |
| ----: | -----: | -------: | --------: | -------: | --------: |
|    96 |     96 |   30,333 |        20 |       52 |        86 |

A second query found no file without exactly one cover page on its first row. `EDGAR_WH` was suspended after the queries.

## The whole walk

The runs that walk 2026-09-01 to 2026-10-09 were then cleared the same way and ran one at a time.

- **719 filings parsed and loaded.** Every filing the walk landed from 2026-09-01 to 2026-10-09 has its JSON-lines file. `RAW.PARSED_FILINGS` holds 719 files, 719 cover pages and 192,129 holdings, and the 719 files in S3 hold the same 192,848 lines.
- **No filing failed to parse.** Every audit record with parse counts reads `parse_failed: []`.
- **23 reconcile gaps, all loaded.** Ten filings report an entry count that differs from their table, six a value total off by 5 or less, three a value total off in no simple pattern, and four a value total 10, 100 or 1,000 times apart from their rows' sum. One of those, `0001439805-26-000006`, states 4,353,137 against rows summing to 4,353: its total is in dollars and its rows in thousands. These are the cases the core layer has to resolve.
- **Two runs needed care.** The run that walks 2026-10-02 is a manual run from the cp1 catchup, not a scheduled one, so it was cleared on its own. A leftover run with logical date 2026-09-01, from before the start date moved, walks 2026-08-31: it landed that day's five filings and, cleared twice, never ran `parse_batch`. 2026-08-31 is before the walk's start and inside the last data set, so those five stay unparsed.

## What it does not show

- **A filing wave.** The trial ends on 2026-11-08, before the mid-November wave of Q3 filings, so the path is proven on a weekday of late filers and amendments, not on the 2,600 filings of a wave day.
- **A scheduled run.** Every run here was a cleared rerun of a past day. The scheduled runs from 2026-10-13 on parse what they land with the same code, and their audit records will show it.
