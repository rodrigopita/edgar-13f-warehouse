# EDGAR 13F Warehouse

Small Snowflake warehouse that answers who holds what, and how institutional positions changed quarter over quarter, from SEC 13F filings. Historical volume comes from the SEC's first-party 13F datasets. Newly discovered filings arrive as XML through an Airflow index walker, land in S3, and Snowpipe loads them into VARIANT raw tables. dbt resolves amendments once in a core layer and builds the marts from that canonical state.

This is a case study for separating historical backfill from incremental ingestion, resolving 13F amendments, and using Snowflake and dbt features for a reason. The scope, decisions and checkpoints are in [docs/scope.md](docs/scope.md).

**Identifiers:** holdings are keyed by CUSIP, the only identifier the SEC data carries for the history; FIGI appears on 7 to 12 percent of rows from 2023 on and never before. No CUSIP-to-ticker mapping is scraped; the numbers are in [docs/2026-10-07-cp1-tsv-profile.md](docs/2026-10-07-cp1-tsv-profile.md).

**Status:** checkpoint 2, Snowflake ingests without hands. The daily walk parses each filing it lands, and Snowpipe loads it into the raw table in under two minutes; the 54 SEC data sets, 125.9 million rows, reconcile with the cp1 profile to the row. The proofs are in [docs/2026-10-11-cp2-xml-path-proof.md](docs/2026-10-11-cp2-xml-path-proof.md) and [docs/2026-10-13-cp2-backfill-proof.md](docs/2026-10-13-cp2-backfill-proof.md).

**Trial window:** the Snowflake trial ends on 2026-11-08, before the mid-November wave of Q3 filings, so the XML path is proven on late filers and amendments, up to 160 filings a day, not on a wave day of about 2,600.
