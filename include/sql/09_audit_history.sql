-- 09_audit_history.sql
-- Run once in JOPUFPW-EDGAR_13F after Terraform has created the audit stages
-- and pipes. A rerun within 64 days loads nothing: a bulk COPY skips the
-- files it loaded in that window.
--
-- A pipe loads only the files its bucket notification reports, so the audit
-- records written before the pipes existed need one bulk COPY: 87 walk
-- records from 2026-08-31 on and 2 backfill records, as listed on 2026-10-21.
-- Bulk COPY and Snowpipe keep separate load metadata and neither skips what
-- the other loaded, so a record the pipe loaded before this ran is loaded
-- again; the staging views keep one row per file. SYSADMIN inherits the
-- stages from TERRAFORM and the warehouse from LOADER.

use role sysadmin;
use warehouse edgar_wh;

-- 1. The files each stage holds now: the counts the loads must match.
list @edgar_13f.audit.walk_runs_stage;
list @edgar_13f.audit.backfill_runs_stage;

-- 2. The loads, with the pipes' column mapping. ON_ERROR stays at the bulk
--    default, ABORT_STATEMENT: a record that does not load stops the COPY
--    and names the file.
copy into edgar_13f.audit.walk_runs
    (record, source_file, source_content_key, source_last_modified)
from (
    select $1, metadata$filename,
           metadata$file_content_key, metadata$file_last_modified
    from @edgar_13f.audit.walk_runs_stage
);

copy into edgar_13f.audit.backfill_runs
    (record, source_file, source_content_key, source_last_modified)
from (
    select $1, metadata$filename,
           metadata$file_content_key, metadata$file_last_modified
    from @edgar_13f.audit.backfill_runs_stage
);

-- 3. Check: one row per listed file in each table, no file twice, and the
--    pipes running.
select 'walk_runs' as audit_table, count(*) as rows_loaded,
       count(distinct source_file) as files
from edgar_13f.audit.walk_runs
union all
select 'backfill_runs', count(*), count(distinct source_file)
from edgar_13f.audit.backfill_runs;

select system$pipe_status('edgar_13f.audit.walk_runs_pipe');
select system$pipe_status('edgar_13f.audit.backfill_runs_pipe');
