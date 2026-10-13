-- 06_narrow_terraform_grants.sql
-- Run once in JOPUFPW-EDGAR_13F after 03 has granted TERRAFORM SELECT and
-- INSERT on RAW.PARSED_FILINGS. Idempotent (safe to rerun: a second run of
-- the same input changes nothing).
--
-- Until 2026-10-13, 02 gave TERRAFORM SELECT and INSERT on every future table
-- in RAW and CREATE FILE FORMAT on the schema. The pipe needs only the first
-- on PARSED_FILINGS, and the file formats are inline in the stages. 02 and 03
-- now grant only that; this script takes back what the account already has,
-- and on an account built from the current 02 and 03 it finds nothing to
-- revoke.

use role securityadmin;

revoke select, insert on future tables in schema edgar_13f.raw from role terraform;
revoke select, insert on table edgar_13f.raw.dataset_submission from role terraform;
revoke select, insert on table edgar_13f.raw.dataset_coverpage from role terraform;
revoke select, insert on table edgar_13f.raw.dataset_othermanager from role terraform;
revoke select, insert on table edgar_13f.raw.dataset_othermanager2 from role terraform;
revoke select, insert on table edgar_13f.raw.dataset_infotable from role terraform;
revoke select, insert on table edgar_13f.raw.dataset_signature from role terraform;
revoke select, insert on table edgar_13f.raw.dataset_summarypage from role terraform;
revoke create file format on schema edgar_13f.raw from role terraform;
grant select, insert on table edgar_13f.raw.parsed_filings to role terraform;

-- Check: TERRAFORM keeps USAGE on the database and schema, CREATE STAGE and
-- CREATE PIPE, SELECT and INSERT on PARSED_FILINGS, and owns the integration,
-- stages and pipe. The only future grants in RAW are LOADER's.
show grants to role terraform;
show future grants in schema edgar_13f.raw;
