# cp2: the historical backfill reconciles with the cp1 profile

Written 2026-10-13 from two runs of `sec_datasets_backfill` and the reconciliation `python -m include.sec_cli reconcile-sql` writes. It is the record of the second cp2 done-criterion: the backfill row counts reconcile against the checkpoint 1 profile.

## What the numbers say

- **54 zips, 378 files, 125,937,801 rows.** The first run fetched all 54 data sets from the SEC, landed each zip under `raw/sec/datasets/` and its seven tables as gzip under `extracted/sec/datasets/`, and seven COPYs loaded all 378 files into `RAW.DATASET_<TABLE>`.
- **No difference from the cp1 profile.** The reconciliation compares, for each of the 54 data sets and seven tables, the rows the cp1 profile counted in the zip with the rows `RAW.DATASET_<TABLE>` holds from that data set's file. It returned no row: all 378 pairs agree.
- **Three counts, one number per file.** The run's audit record holds, for every file, the rows extraction counted and the rows COPY reported loading; they are equal for all 378. The reconciliation then matches the loaded rows against the profile, which was written on 2026-10-07 from the laptop's copies of the same zips.
- **Run twice, changed nothing.** The second run downloaded nothing (all 54 data sets read their counts back from the extracted files' metadata), and every COPY reported zero files processed. A zip and an extracted file sampled afterwards each still had one S3 version.
- **30 minutes and a fraction of a credit.** Staging took 26 minutes, one zip at a time in the `edgar` pool. Six tables loaded in about 30 seconds each and `INFOTABLE` in 4 minutes 7 seconds. The resource monitor read 0.34 credits used since the trial began on 2026-10-09, this load included.

| table         | cp1 profile |      loaded |
| ------------- | ----------: | ----------: |
| SUBMISSION    |     409,685 |     409,685 |
| COVERPAGE     |     409,685 |     409,685 |
| INFOTABLE     | 124,012,468 | 124,012,468 |
| OTHERMANAGER  |     207,051 |     207,051 |
| OTHERMANAGER2 |     163,101 |     163,101 |
| SIGNATURE     |     409,685 |     409,685 |
| SUMMARYPAGE   |     326,126 |     326,126 |

## How it was run

- **First run**, `manual-r202610130922`, triggered by hand at 12:22 UTC with the code at `562f63f`; success at 12:52. Audit record `raw/sec/audit/backfill/manual-r202610130922.json`: `sources: {"sec": 54}`, 54 files loaded per table, `mismatches: []`.
- **Second run**, `manual-r202610131007`, at 13:07 UTC; success at 13:10. Audit record `raw/sec/audit/backfill/manual-r202610131007.json`: `sources: {"extracted": 54}`, zero files and zero rows loaded per table.
- **Reconciliation**, from `uv run python -m include.sec_cli reconcile-sql`, run as ACCOUNTADMIN on `EDGAR_WH` after the first run: the first query, the differences, returned no row; the second, the totals, is the table above.

## What it does not show

- **Typed data.** The raw tables hold text as the data sets write it: dates as `DD-MON-YYYY`, VALUE in thousands of dollars before 2023-01-03 and in dollars after. Typing and the unit belong to the core layer in cp3.
- **The overlap with the XML path.** The newest data set ends on 2026-08-31 and the walk starts on 2026-09-01, so the two paths share no filing yet. When the SEC publishes the next data set, the overlap becomes a reconciliation test between them.
