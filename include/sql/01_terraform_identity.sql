-- 01_terraform_identity.sql
-- Run once in JOPUFPW-EDGAR_13F after 00_cost_guard.sql. The role and the
-- user are idempotent (safe to rerun: a second run of the same input
-- changes nothing); ADD KEY PAIR is not, it fails on an existing name, and
-- a new key goes in with ROTATE KEY PAIR.
--
-- The Terraform Snowflake provider logs in as a SERVICE user, which cannot
-- use a password or MFA, with a key pair whose private half stays in
-- ~/.snowflake/keys/, outside the repository and outside the Astro image.

use role securityadmin;

-- 1. The role Terraform applies with. Granted to SYSADMIN so objects
--    Terraform creates stay inside the system role hierarchy. Grants on the
--    database and schemas come with the RBAC script that creates them.
create role if not exists terraform
    comment = 'Applies the Snowflake side of terraform/: storage integration, stage, pipe';
grant role terraform to role sysadmin;

-- A storage integration is an account-level object.
use role accountadmin;
grant create integration on account to role terraform;
use role securityadmin;

-- 2. The user. TYPE = SERVICE: no password, no SSO, no MFA enrolment.
create user if not exists terraform_svc
    type = service
    default_role = terraform
    comment = 'Terraform Snowflake provider, key-pair login only';
grant role terraform to user terraform_svc;

-- 3. The public key, as a named key pair. ROLE_RESTRICTION makes the key
--    useless with any role but TERRAFORM; DAYS_TO_EXPIRY = 30 ends it with
--    the trial on 2026-11-08. The body is the .pub file without its two
--    delimiter lines, joined onto one line; it is pasted at run time.
alter user terraform_svc add key pair laptop
    public_key = '<public key body>'
    role_restriction = 'TERRAFORM'
    days_to_expiry = 30
    comment = 'Terraform runs from the laptop';

-- 4. The fingerprint must match the one openssl computes from the .pub file.
show user key pairs for user terraform_svc;
