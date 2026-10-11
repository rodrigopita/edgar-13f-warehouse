-- 03_raw_parsed_filings.sql
-- Run once in JOPUFPW-EDGAR_13F after 02_database_and_roles.sql and before
-- Terraform creates the pipe that loads it. Idempotent (safe to rerun: a
-- second run of the same input changes nothing).
--
-- One row per JSON line that include/edgar_xml.py writes under parsed/: the
-- cover page of a filing or one of its holdings, as an envelope with
-- record_type, accession, source_key and the parsed record. Rows are kept as
-- loaded; the core layer types them and resolves duplicates.

use role sysadmin;

-- The four source columns come from Snowpipe's METADATA$ columns, so every
-- row names the file and line it came from. Load time is the row timestamp
-- (METADATA$ROW_LAST_COMMIT_TIME), not a CURRENT_TIMESTAMP default: the pipe
-- docs say such defaults record when the load compiles, not when it commits.
create table if not exists edgar_13f.raw.parsed_filings (
    record variant not null
        comment 'One JSON line: {record_type, accession, source_key, record}',
    source_file varchar not null
        comment 'METADATA$FILENAME: path of the JSON-lines file under the stage',
    source_row number not null
        comment 'METADATA$FILE_ROW_NUMBER: line of the record in that file',
    source_content_key varchar not null
        comment 'METADATA$FILE_CONTENT_KEY: checksum of the file',
    source_last_modified timestamp_ntz not null
        comment 'METADATA$FILE_LAST_MODIFIED: when the file was written to S3'
)
row_timestamp = true
comment = 'Cover pages and holdings parsed from EDGAR 13F XML, one JSON line per row';

-- Check: LOADER and TERRAFORM hold SELECT and INSERT through the future grants.
show grants on table edgar_13f.raw.parsed_filings;
