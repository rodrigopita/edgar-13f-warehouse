-- 02_database_and_roles.sql
-- Run once in JOPUFPW-EDGAR_13F after 01_terraform_identity.sql. Idempotent
-- (safe to rerun: a second run of the same input changes nothing).
--
-- SQL owns the warehouse's structure and access: database, schemas, roles,
-- grants and tables. Terraform owns the S3 plumbing: storage integration,
-- file format, stage, pipe and the bucket notification.

-- 1. Structure. SYSADMIN owns the database and schemas, so no functional role
--    can drop them. RAW holds records as loaded from the landing bucket;
--    AUDIT holds the pipeline's own records: walks, parse failures,
--    reconciliations.
use role sysadmin;
create database if not exists edgar_13f
    comment = 'SEC EDGAR 13F holdings warehouse';
create schema if not exists edgar_13f.raw
    comment = 'Records as loaded from the landing bucket';
create schema if not exists edgar_13f.audit
    comment = 'Pipeline records: walks, parse failures, reconciliations';

use role securityadmin;

-- 2. The ingestion role. The backfill COPY and the pipeline's audit rows run
--    under it: it adds rows to RAW and AUDIT and reads them back, nothing more.
create role if not exists loader
    comment = 'Loads RAW and AUDIT: backfill COPY and pipeline audit rows';
grant role loader to role sysadmin;
grant usage on warehouse edgar_wh to role loader;
grant usage on database edgar_13f to role loader;
grant usage on schema edgar_13f.raw to role loader;
grant usage on schema edgar_13f.audit to role loader;
grant select, insert on future tables in schema edgar_13f.raw to role loader;
grant select, insert on future tables in schema edgar_13f.audit to role loader;

-- 3. Terraform creates the file format, stage and pipe in RAW and owns them.
--    Snowpipe loads with the privileges of the pipe's owner, so TERRAFORM
--    also selects from and inserts into RAW tables; that is the only data it
--    can touch.
grant usage on database edgar_13f to role terraform;
grant usage on schema edgar_13f.raw to role terraform;
grant create file format, create stage, create pipe on schema edgar_13f.raw to role terraform;
grant select, insert on future tables in schema edgar_13f.raw to role terraform;

-- 4. Check: both roles hold what sections 2 and 3 grant.
show grants to role loader;
show grants to role terraform;
show future grants in schema edgar_13f.raw;
