-- 08_audit_and_observability.sql
-- Run once in JOPUFPW-EDGAR_13F after 07_dbt_identity.sql and before
-- Terraform creates the pipes that load AUDIT. Idempotent (safe to rerun: a
-- second run of the same input changes nothing).
--
-- AUDIT holds what the pipeline wrote about itself. The walk and the backfill
-- each land one JSON record per attempt of a run, under raw/edgar/audit/walk/
-- and raw/sec/audit/backfill/, and a pipe loads each record into a table here
-- as PARSED_FILINGS_PIPE loads RAW. OBSERVABILITY holds what dbt derives from
-- AUDIT, RAW and CORE: filings discovered against loaded, failures, row
-- counts and data-quality counts. dbt reads AUDIT and cannot write to it, so
-- the record of what happened stays apart from what is computed from it.

-- 1. Structure. SYSADMIN owns OBSERVABILITY as it owns the other schemas.
use role sysadmin;
create schema if not exists edgar_13f.observability
    comment = 'Pipeline health derived by dbt from AUDIT, RAW and CORE';

-- 2. One row per audit record file. The source columns come from Snowpipe's
--    METADATA$ columns as in 03, without the line number: each file is one
--    JSON object. Load time is the row timestamp, for the reason 03 gives.
create table if not exists edgar_13f.audit.walk_runs (
    record variant not null
        comment 'One walk audit record: days walked, discovered, landed, parsed, failures',
    source_file varchar not null
        comment 'METADATA$FILENAME: path of the record under the stage',
    source_content_key varchar not null
        comment 'METADATA$FILE_CONTENT_KEY: checksum of the file',
    source_last_modified timestamp_ntz not null
        comment 'METADATA$FILE_LAST_MODIFIED: when the record was written to S3'
)
row_timestamp = true
comment = 'Audit records of the daily walk, one per attempt of a run';

create table if not exists edgar_13f.audit.backfill_runs (
    record variant not null
        comment 'One backfill audit record: rows extracted and loaded per table',
    source_file varchar not null
        comment 'METADATA$FILENAME: path of the record under the stage',
    source_content_key varchar not null
        comment 'METADATA$FILE_CONTENT_KEY: checksum of the file',
    source_last_modified timestamp_ntz not null
        comment 'METADATA$FILE_LAST_MODIFIED: when the record was written to S3'
)
row_timestamp = true
comment = 'Audit records of the data set backfill, one per attempt of a run';

use role securityadmin;

-- 3. Terraform creates the stages and pipes in AUDIT and owns them. A pipe
--    loads with its owner's privileges, so TERRAFORM gets SELECT and INSERT
--    on the two tables its pipes load, as 03 grants on PARSED_FILINGS.
grant usage on schema edgar_13f.audit to role terraform;
grant create stage, create pipe on schema edgar_13f.audit to role terraform;
grant select, insert on table edgar_13f.audit.walk_runs to role terraform;
grant select, insert on table edgar_13f.audit.backfill_runs to role terraform;

-- 4. dbt builds in OBSERVABILITY. TRANSFORMER already reads every table in
--    AUDIT through the future grant in 07.
grant usage, create table, create view on schema edgar_13f.observability
    to role transformer;

-- 5. Checks: TERRAFORM holds what section 3 grants; TRANSFORMER can build in
--    OBSERVABILITY and read both tables.
show grants to role terraform;
show grants on table edgar_13f.audit.walk_runs;
show grants on table edgar_13f.audit.backfill_runs;
show grants on schema edgar_13f.observability;
