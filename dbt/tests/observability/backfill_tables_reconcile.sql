-- Each data set table holds in RAW the rows the backfill extracted from the
-- zips, and its COPY loaded each row once.
select *
from {{ ref('backfill_tables') }}
where extracted_rows <> rows_loaded
    or rows_loaded <> raw_rows
    or raw_rows is null
