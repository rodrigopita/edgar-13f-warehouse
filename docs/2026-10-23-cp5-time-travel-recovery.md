# cp5: a bad build, undone with Time Travel

Written 2026-10-23 from one run of the statements in this document, in the development clone `EDGAR_13F_DEV`. It is the second part of the cp5 failure demo, after the parse failures of 2026-10-22: a build that replaced a table with the wrong output, undone from Time Travel within the one day Standard edition keeps, and checked against production.

## What the run says

- **The bad build.** At 21:43 UTC on 2026-10-23 (14:43 as Snowflake displays it) a development build replaced the clone's `filer_overlaps`, which pairs the hundred largest filers of each period, with a version for the ten largest: 3,590 pairs where there had been 292,328. dbt builds a table with `CREATE OR REPLACE`, which drops the old table into Time Travel and gives the name a new object, so `AT` and `BEFORE` on the name reach only the new table.
- **Two statements undid it, twelve minutes later.** A rename moved the bad table aside to `filer_overlaps_ten`, and `undrop table edgar_13f_dev.marts.filer_overlaps` brought back the table it had replaced: "Table FILER_OVERLAPS successfully restored."
- **It came back whole, and it is the same table.** It holds 292,328 pairs over 99 periods, and row for row what production's `filer_overlaps` holds: a `MINUS` in each direction finds no row. Its created time is the clone's, 14:41:01, so the table restored is the one the clone made, not a rebuild of it.
- **A day is the window, and a rebuild is the fallback.** Standard edition keeps one day of Time Travel, so this recovery had until 21:43 UTC on 2026-10-24. The marts are transient tables, with no Fail-safe after that day; past it, a mart is rebuilt from `CORE` by dbt, the whole set in about four and a half minutes on the X-Small.

## How it was run

On 2026-10-23, as SYSADMIN in `JOPUFPW-EDGAR_13F`, from about 21:55 UTC. `EDGAR_13F_DEV` was cloned from `EDGAR_13F` at 21:41 by `include/sql/12_dev_clone.sql`, and the bad build was `dbt build --target dev --select filer_overlaps --vars '{overlap_filers: 10}'`.

```sql
-- Before: the bad table under the name.
select count(*) as pairs, count(distinct period_of_report) as periods
from edgar_13f_dev.marts.filer_overlaps;

-- The recovery.
alter table edgar_13f_dev.marts.filer_overlaps
    rename to edgar_13f_dev.marts.filer_overlaps_ten;
undrop table edgar_13f_dev.marts.filer_overlaps;

-- After: the count, the comparison with production, and the history.
select count(*) as pairs, count(distinct period_of_report) as periods
from edgar_13f_dev.marts.filer_overlaps;

select
    (select count(*) from (
        select * from edgar_13f_dev.marts.filer_overlaps
        minus
        select * from edgar_13f.marts.filer_overlaps
    )) as rows_only_in_the_clone,
    (select count(*) from (
        select * from edgar_13f.marts.filer_overlaps
        minus
        select * from edgar_13f_dev.marts.filer_overlaps
    )) as rows_only_in_production;

show tables history like 'FILER_OVERLAPS%' in schema edgar_13f_dev.marts;

-- Tidy up: the ten-filer table goes, and stays recoverable for a day.
drop table edgar_13f_dev.marts.filer_overlaps_ten;
```

| when   | table under the name `FILER_OVERLAPS` |   pairs | periods | created (-0700)     |
| ------ | ------------------------------------- | ------: | ------: | ------------------- |
| before | the dev build's                       |   3,590 |      99 | 2026-10-23 14:43:16 |
| after  | the clone's, restored                 | 292,328 |      99 | 2026-10-23 14:41:01 |

The comparison with production after the recovery: `rows_only_in_the_clone` 0, `rows_only_in_production` 0. The history after it lists two live tables, `FILER_OVERLAPS` with 292,328 rows and `FILER_OVERLAPS_TEN` with 3,590, and neither dropped; the last statement then dropped `FILER_OVERLAPS_TEN`.
