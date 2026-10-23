-- 11_analyst_role.sql
-- Run once in JOPUFPW-EDGAR_13F after 10_narrow_loader_grants.sql.
-- Idempotent (safe to rerun: a second run of the same input changes
-- nothing).
--
-- ANALYST reads the marts and nothing else: the question-shaped tables of
-- cp4, not the loaded record in RAW, the typed layer in CORE, or the
-- pipeline's own records in AUDIT and OBSERVABILITY. With LOADER, TRANSFORMER
-- and TERRAFORM it completes the separation the scope asks for: ingestion,
-- transformation and analytics each hold what their work needs. The role
-- has no user; a person is granted it, and in this account SYSADMIN holds
-- it as it holds the other three.

use role securityadmin;

create role if not exists analyst
    comment = 'Reads MARTS: the question-shaped tables, nothing upstream';
grant role analyst to role sysadmin;
grant usage on warehouse edgar_wh to role analyst;
grant usage on database edgar_13f to role analyst;
grant usage on schema edgar_13f.marts to role analyst;

-- dbt replaces every mart on each build, and a replaced table is a new
-- object, so the future grant is what keeps ANALYST reading them; the grant
-- on all tables covers the ones built before this script.
grant select on all tables in schema edgar_13f.marts to role analyst;
grant select on future tables in schema edgar_13f.marts to role analyst;

-- Check: ANALYST holds USAGE on the warehouse, the database and MARTS, and
-- SELECT on the four marts; MARTS has one future grant, ANALYST's.
show grants to role analyst;
show future grants in schema edgar_13f.marts;
