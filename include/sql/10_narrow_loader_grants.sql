-- 10_narrow_loader_grants.sql
-- Run once in JOPUFPW-EDGAR_13F after 09_audit_history.sql. Idempotent
-- (safe to rerun: a second run of the same input changes nothing).
--
-- Until 2026-10-23, 02 gave LOADER USAGE on AUDIT and SELECT and INSERT on
-- every future table there, for audit rows Airflow was to insert. Since 08
-- the audit records reach AUDIT through pipes Terraform owns, so LOADER
-- needs nothing in AUDIT, and 02 and 05 now say so. This script takes back
-- what the account already has, including what that future grant gave on
-- the two tables 08 created, and corrects the comments stored on the role
-- and the user. On an account built from the current files it finds
-- nothing to revoke.

use role securityadmin;

revoke select, insert on future tables in schema edgar_13f.audit from role loader;
revoke select, insert on table edgar_13f.audit.walk_runs from role loader;
revoke select, insert on table edgar_13f.audit.backfill_runs from role loader;
revoke usage on schema edgar_13f.audit from role loader;

alter role loader set comment = 'Loads RAW: the backfill COPY';
alter user airflow_svc set comment = 'Airflow on the laptop: backfill COPY, key-pair login only';

-- Check: LOADER keeps USAGE on the warehouse, the database and RAW, and
-- SELECT and INSERT on RAW's tables; nothing in AUDIT. AUDIT's only future
-- grant is TRANSFORMER's SELECT.
show grants to role loader;
show future grants in schema edgar_13f.audit;
