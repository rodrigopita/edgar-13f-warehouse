# EDGAR 13F Warehouse

Small Snowflake warehouse that answers who holds what, and how institutional positions changed quarter over quarter, from SEC 13F filings. Historical volume comes from the SEC's first-party 13F datasets. Newly discovered filings arrive as XML through an Airflow index walker, land in S3, and Snowpipe loads them into VARIANT raw tables. dbt resolves amendments once in a core layer and builds the marts from that canonical state.

This is a case study for separating historical backfill from incremental ingestion, resolving 13F amendments, and using Snowflake and dbt features for a reason. The scope, decisions and checkpoints are in [docs/scope.md](docs/scope.md).

**Identifiers:** holdings are keyed by CUSIP, the only identifier the SEC data carries for the history; FIGI appears on 7 to 12 percent of rows from 2023 on and never before. No CUSIP-to-ticker mapping is scraped; the numbers are in [docs/2026-10-07-cp1-tsv-profile.md](docs/2026-10-07-cp1-tsv-profile.md).

**Status:** checkpoint 1, extraction. Everything runs locally and the Snowflake trial is untouched.
