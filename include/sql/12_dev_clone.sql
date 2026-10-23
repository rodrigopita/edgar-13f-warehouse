-- 12_dev_clone.sql
-- Run in JOPUFPW-EDGAR_13F whenever development needs a fresh copy of the
-- warehouse: each run replaces EDGAR_13F_DEV with a new clone of EDGAR_13F.
-- Nothing here creates, replaces or drops anything but EDGAR_13F_DEV.
--
-- EDGAR_13F_DEV is a zero-copy clone: it shares EDGAR_13F's storage until a
-- table in it changes, so it costs a metadata operation to make and only
-- what dbt rebuilds in it after. dbt's dev target builds there and its
-- sources follow the target, so a model can be changed and rebuilt against
-- the whole warehouse, 115 million canonical holdings included, without
-- reading or writing EDGAR_13F. The clone is a snapshot: the walk keeps
-- loading EDGAR_13F, and the next run of this script brings the clone up
-- to date.
--
-- After it, `dbt run --target dev --select config.materialized:view`: dbt
-- writes every reference with its database, so until then the cloned views
-- still read EDGAR_13F.

-- 1. The clone. SYSADMIN owns EDGAR_13F and, through TRANSFORMER, LOADER and
--    TERRAFORM, holds what cloning each object needs: SELECT on the tables,
--    USAGE on the stages and OWNERSHIP of the pipes. Every child object
--    keeps its grants, so the tables and views dbt built stay TRANSFORMER's;
--    the database itself keeps none.
use role sysadmin;
use warehouse edgar_wh;
create or replace database edgar_13f_dev clone edgar_13f
    comment = 'Development: a zero-copy clone of EDGAR_13F, built by dbt --target dev';

-- 2. The pipes. Their clones start STOPPED_CLONED, and each COPY names its
--    table in EDGAR_13F in full, so a resumed clone would load production
--    a second time. Dropped, they cannot be resumed.
drop pipe if exists edgar_13f_dev.raw.parsed_filings_pipe;
drop pipe if exists edgar_13f_dev.audit.walk_runs_pipe;
drop pipe if exists edgar_13f_dev.audit.backfill_runs_pipe;

-- 3. The grant a clone does not inherit: USAGE on the database, which dbt's
--    role needs to reach the schemas whose grants were cloned with them.
use role securityadmin;
grant usage on database edgar_13f_dev to role transformer;

-- 4. Checks: no pipes; TRANSFORMER owns the marts; a view still names
--    EDGAR_13F until dbt rebuilds the views in dev.
use role sysadmin;
show pipes in database edgar_13f_dev;
show grants on database edgar_13f_dev;
show tables in schema edgar_13f_dev.marts;
select get_ddl('view', 'edgar_13f_dev.core.stg_xml_holdings');
