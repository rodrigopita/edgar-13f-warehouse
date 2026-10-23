-- 05_airflow_identity.sql
-- Run once in JOPUFPW-EDGAR_13F after 04_raw_datasets.sql. The user is
-- idempotent (safe to rerun: a second run of the same input changes
-- nothing); ADD KEY PAIR is not, it fails on an existing name, and a new key
-- goes in with ROTATE KEY PAIR.
--
-- Airflow runs the backfill COPY as AIRFLOW_SVC, a SERVICE user in LOADER,
-- with its own key pair: Terraform's key cannot load data and this one
-- cannot create objects, so each can be revoked alone.

use role securityadmin;

-- 1. The user. TYPE = SERVICE: no password, no SSO, no MFA enrolment.
--    EDGAR_WH is its default so a COPY needs no USE WAREHOUSE.
create user if not exists airflow_svc
    type = service
    default_role = loader
    default_warehouse = edgar_wh
    comment = 'Airflow on the laptop: backfill COPY, key-pair login only';
grant role loader to user airflow_svc;

-- 2. The public key, as a named key pair restricted to LOADER. DAYS_TO_EXPIRY
--    = 28 ends it with the trial on 2026-11-08. The body is the .pub file
--    without its two delimiter lines, joined onto one line; it is pasted at
--    run time.
alter user airflow_svc add key pair astro_local
    public_key = '<public key body>'
    role_restriction = 'LOADER'
    days_to_expiry = 28
    comment = 'Airflow in the local Astro stack';

-- 3. The fingerprint must match the one openssl computes from the .pub file.
show user key pairs for user airflow_svc;
