-- 04_raw_datasets.sql
-- Run once in JOPUFPW-EDGAR_13F after 03_raw_parsed_filings.sql. Idempotent
-- (safe to rerun: a second run of the same input changes nothing).
--
-- The seven tables of the SEC 13F data sets, one raw table each, loaded by
-- COPY from the extracted TSVs under extracted/sec/datasets/. Columns keep
-- the data sets' own names and stay text: the header is the same in all 54
-- zips from 2013q2 to 01jun2026-31aug2026, and typing belongs to the core
-- layer, where dates written DD-MON-YYYY are parsed and VALUE, in thousands
-- of dollars before 2023-01-03, is put on one unit. Every table ends with the
-- same four source columns as RAW.PARSED_FILINGS, and load time is the row
-- timestamp.

use role sysadmin;

create table if not exists edgar_13f.raw.dataset_submission (
    accession_number varchar,
    filing_date varchar,
    submissiontype varchar,
    cik varchar,
    periodofreport varchar,
    source_file varchar not null,
    source_row number not null,
    source_content_key varchar not null,
    source_last_modified timestamp_ntz not null
)
row_timestamp = true
comment = 'SUBMISSION.tsv from the SEC 13F data sets, as loaded';

create table if not exists edgar_13f.raw.dataset_coverpage (
    accession_number varchar,
    reportcalendarorquarter varchar,
    isamendment varchar,
    amendmentno varchar,
    amendmenttype varchar,
    confdeniedexpired varchar,
    datedeniedexpired varchar,
    datereported varchar,
    reasonfornonconfidentiality varchar,
    filingmanager_name varchar,
    filingmanager_street1 varchar,
    filingmanager_street2 varchar,
    filingmanager_city varchar,
    filingmanager_stateorcountry varchar,
    filingmanager_zipcode varchar,
    reporttype varchar,
    form13ffilenumber varchar,
    crdnumber varchar,
    secfilenumber varchar,
    provideinfoforinstruction5 varchar,
    additionalinformation varchar,
    source_file varchar not null,
    source_row number not null,
    source_content_key varchar not null,
    source_last_modified timestamp_ntz not null
)
row_timestamp = true
comment = 'COVERPAGE.tsv from the SEC 13F data sets, as loaded';

create table if not exists edgar_13f.raw.dataset_othermanager (
    accession_number varchar,
    othermanager_sk varchar,
    cik varchar,
    form13ffilenumber varchar,
    crdnumber varchar,
    secfilenumber varchar,
    name varchar,
    source_file varchar not null,
    source_row number not null,
    source_content_key varchar not null,
    source_last_modified timestamp_ntz not null
)
row_timestamp = true
comment = 'OTHERMANAGER.tsv from the SEC 13F data sets, as loaded';

create table if not exists edgar_13f.raw.dataset_othermanager2 (
    accession_number varchar,
    sequencenumber varchar,
    cik varchar,
    form13ffilenumber varchar,
    crdnumber varchar,
    secfilenumber varchar,
    name varchar,
    source_file varchar not null,
    source_row number not null,
    source_content_key varchar not null,
    source_last_modified timestamp_ntz not null
)
row_timestamp = true
comment = 'OTHERMANAGER2.tsv from the SEC 13F data sets, as loaded';

create table if not exists edgar_13f.raw.dataset_infotable (
    accession_number varchar,
    infotable_sk varchar,
    nameofissuer varchar,
    titleofclass varchar,
    cusip varchar,
    figi varchar,
    value varchar,
    sshprnamt varchar,
    sshprnamttype varchar,
    putcall varchar,
    investmentdiscretion varchar,
    othermanager varchar,
    voting_auth_sole varchar,
    voting_auth_shared varchar,
    voting_auth_none varchar,
    source_file varchar not null,
    source_row number not null,
    source_content_key varchar not null,
    source_last_modified timestamp_ntz not null
)
row_timestamp = true
comment = 'INFOTABLE.tsv from the SEC 13F data sets, as loaded';

create table if not exists edgar_13f.raw.dataset_signature (
    accession_number varchar,
    name varchar,
    title varchar,
    phone varchar,
    signature varchar,
    city varchar,
    stateorcountry varchar,
    signaturedate varchar,
    source_file varchar not null,
    source_row number not null,
    source_content_key varchar not null,
    source_last_modified timestamp_ntz not null
)
row_timestamp = true
comment = 'SIGNATURE.tsv from the SEC 13F data sets, as loaded';

create table if not exists edgar_13f.raw.dataset_summarypage (
    accession_number varchar,
    otherincludedmanagerscount varchar,
    tableentrytotal varchar,
    tablevaluetotal varchar,
    isconfidentialomitted varchar,
    source_file varchar not null,
    source_row number not null,
    source_content_key varchar not null,
    source_last_modified timestamp_ntz not null
)
row_timestamp = true
comment = 'SUMMARYPAGE.tsv from the SEC 13F data sets, as loaded';

-- The backfill COPY runs as LOADER and reads the extracted files through a
-- stage Terraform creates and owns. An external stage needs only USAGE; the
-- future grant is in place before the stage exists.
use role securityadmin;
grant usage on future stages in schema edgar_13f.raw to role loader;

-- Check: seven tables, each with LOADER and TERRAFORM holding SELECT and
-- INSERT through the future grants from 02.
show tables like 'DATASET_%' in schema edgar_13f.raw;
show grants on table edgar_13f.raw.dataset_infotable;
