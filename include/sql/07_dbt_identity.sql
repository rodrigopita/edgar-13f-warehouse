-- 07_dbt_identity.sql
-- Run once in JOPUFPW-EDGAR_13F after 06_narrow_terraform_grants.sql. The
-- schemas, the role, its grants and the user are idempotent (safe to rerun:
-- a second run of the same input changes nothing); ADD KEY PAIR is not, it
-- fails on an existing name, and a new key goes in with ROTATE KEY PAIR.
--
-- dbt runs as DBT_SVC, a SERVICE user in TRANSFORMER, with the third key
-- pair: Terraform's key cannot read data, Airflow's cannot create objects
-- outside RAW and AUDIT, and this one cannot load or write back to either,
-- so each can be revoked alone. From this script on, the future grants in
-- RAW list TRANSFORMER's SELECT beside LOADER's.

-- 1. Structure. SYSADMIN owns CORE and MARTS as it owns RAW and AUDIT, so
--    dbt can create and replace what lives inside them and cannot drop the
--    schemas themselves. CORE holds the typed layer and the canonical
--    holdings; MARTS holds the question-shaped tables of cp4.
use role sysadmin;
create schema if not exists edgar_13f.core
    comment = 'Typed filings and holdings, amendments resolved into canonical state';
create schema if not exists edgar_13f.marts
    comment = 'Question-shaped tables built from CORE';

use role securityadmin;

-- 2. The transformation role. It reads RAW and AUDIT, every table there now
--    and any added later, and builds in CORE and MARTS. No INSERT on RAW or
--    AUDIT: a model cannot write back to the loaded record.
create role if not exists transformer
    comment = 'dbt: reads RAW and AUDIT, creates tables and views in CORE and MARTS';
grant role transformer to role sysadmin;
grant usage on warehouse edgar_wh to role transformer;
grant usage on database edgar_13f to role transformer;
grant usage on schema edgar_13f.raw to role transformer;
grant usage on schema edgar_13f.audit to role transformer;
grant select on all tables in schema edgar_13f.raw to role transformer;
grant select on all tables in schema edgar_13f.audit to role transformer;
grant select on future tables in schema edgar_13f.raw to role transformer;
grant select on future tables in schema edgar_13f.audit to role transformer;
grant usage, create table, create view on schema edgar_13f.core to role transformer;
grant usage, create table, create view on schema edgar_13f.marts to role transformer;

-- 3. The user. TYPE = SERVICE: no password, no SSO, no MFA enrolment.
--    EDGAR_WH is its default so a run needs no USE WAREHOUSE.
create user if not exists dbt_svc
    type = service
    default_role = transformer
    default_warehouse = edgar_wh
    comment = 'dbt on the laptop: builds CORE and MARTS, key-pair login only';
grant role transformer to user dbt_svc;

-- 4. The public key, as a named key pair restricted to TRANSFORMER.
--    DAYS_TO_EXPIRY = 24 ends it with the trial on 2026-11-08. The body is
--    the .pub file without its two delimiter lines, joined onto one line;
--    it is pasted at run time.
alter user dbt_svc add key pair laptop
    public_key = '<public key body>'
    role_restriction = 'TRANSFORMER'
    days_to_expiry = 24
    comment = 'dbt runs from the laptop';

-- 5. Checks: the fingerprint must match the one openssl computes from the
--    .pub file; TRANSFORMER holds what section 2 grants and nothing on the
--    stages or the pipe; RAW's future grants are LOADER's and TRANSFORMER's.
show user key pairs for user dbt_svc;
show grants to role transformer;
show future grants in schema edgar_13f.raw;
