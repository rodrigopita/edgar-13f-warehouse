# cp5: a zero-copy clone as the development warehouse

Written 2026-10-23 from one run of `include/sql/12_dev_clone.sql`, two dbt commands against the clone and the queries in this document. It is the record of the cp5 done-criterion's zero-copy clone: development gets the whole warehouse in one statement, and a change made there stays there.

## What the run says

- **The whole warehouse, in one statement.** `create or replace database edgar_13f_dev clone edgar_13f` made `EDGAR_13F_DEV`. Read after the dev builds below, both databases hold 115,995,390 canonical holdings, 82,865,105 positions, 90,472,586 position changes and 646,271 rows in `RAW.PARSED_FILINGS`.
- **No pipe survives the clone.** A cloned auto-ingest pipe starts stopped and would load into the production table its COPY names in full if it were resumed. The script drops the three, and `show pipes in database edgar_13f_dev` returns nothing.
- **dbt can rebuild anything in it.** A database clone keeps the grants on everything inside it and none on the database itself. The four marts in the clone are TRANSFORMER's, transient with one day of Time Travel; the database carries SYSADMIN's ownership and the USAGE the script grants TRANSFORMER, and nothing else.
- **The views need one dbt run.** dbt writes every reference with its database, so straight after the clone `stg_xml_holdings` in `EDGAR_13F_DEV` still read `EDGAR_13F.CORE.stg_xml_filing_records`. `dbt run --target dev --select config.materialized:view` rebuilt the 16 views in 10 seconds, and it reads `EDGAR_13F_DEV.CORE.stg_xml_filing_records`.
- **A change in development stays there.** `dbt build --target dev --select filer_overlaps --vars '{overlap_filers: 10}'`, 5 of 5 in 20 seconds, rebuilt the clone's overlap mart for the ten largest filers of each period: 3,590 pairs over 99 periods, created at 14:43:16. Production's kept the hundred largest, 292,328 pairs over the same 99 periods, created at 14:16:00 by the rebuild of the RBAC proof.
- **The clone owns no storage of its own.** Bytes stay billed to the table that first wrote them, so a clone owns only what changes in it. Read as ACCOUNTADMIN at 00:17 UTC on 2026-10-24, past the two hours storage counts can lag, all 29 of the clone's live tables are clones owning 0 active bytes, against 12,238,497,792 bytes, about 12.2 GB, owned by production's 29. The one table dbt rebuilt in the clone, the ten-filer `filer_overlaps`, had been dropped by the Time Travel recovery by then.
- **Production is the target you name.** The dbt profile calls the clone `dev` and makes it the default, and `EDGAR_13F` is `prod`. `sources.yml` reads the target's database, so a dev build reads the clone's `RAW` and `AUDIT` as well as writing its `CORE`, `MARTS` and `OBSERVABILITY`.

## The workflow

1. `include/sql/12_dev_clone.sql` in Snowsight, as written: it replaces `EDGAR_13F_DEV` with a fresh clone, so it is also how the clone catches up with the walk.
2. `dbt run --target dev --select config.materialized:view`, so the views read the clone.
3. `dbt build --select <model>+` to change and test a model; `dev` is the default target.
4. `dbt build --target prod` once the change is committed.

## The queries

The view's source, after `12` and again after the dev run of the views:

```sql
select get_ddl('view', 'edgar_13f_dev.core.stg_xml_holdings');
```

| when                       | the view reads                              |
| -------------------------- | ------------------------------------------- |
| after `12`                 | `EDGAR_13F.CORE.stg_xml_filing_records`     |
| after the dev run of views | `EDGAR_13F_DEV.CORE.stg_xml_filing_records` |

The overlap mart in each database, after the dev build:

```sql
select 'EDGAR_13F' as database_name, count(*) as pairs,
       count(distinct period_of_report) as periods
from edgar_13f.marts.filer_overlaps
union all
select 'EDGAR_13F_DEV', count(*), count(distinct period_of_report)
from edgar_13f_dev.marts.filer_overlaps;
```

| database      |   pairs | periods | created (-0700)     |
| ------------- | ------: | ------: | ------------------- |
| EDGAR_13F     | 292,328 |      99 | 2026-10-23 14:16:00 |
| EDGAR_13F_DEV |   3,590 |      99 | 2026-10-23 14:43:16 |

The tables dbt did not rebuild in the clone:

| table                    |   EDGAR_13F | EDGAR_13F_DEV |
| ------------------------ | ----------: | ------------: |
| CORE.CANONICAL_HOLDINGS  | 115,995,390 |   115,995,390 |
| MARTS.POSITIONS          |  82,865,105 |    82,865,105 |
| MARTS.POSITION_CHANGES   |  90,472,586 |    90,472,586 |
| RAW.PARSED_FILINGS       |     646,271 |       646,271 |

The storage each database's tables own, per schema, read as ACCOUNTADMIN, since `TABLE_STORAGE_METRICS` returns rows to that role only:

```sql
select table_catalog, table_schema, count(*) as tables,
       count_if(id <> clone_group_id) as clones,
       sum(active_bytes) as active_bytes_owned
from edgar_13f_dev.information_schema.table_storage_metrics
where table_catalog in ('EDGAR_13F', 'EDGAR_13F_DEV')
    and table_dropped is null
    and catalog_dropped is null
group by table_catalog, table_schema
order by table_schema, table_catalog;
```

| schema        | tables | EDGAR_13F bytes owned | EDGAR_13F_DEV clones | EDGAR_13F_DEV bytes owned |
| ------------- | -----: | --------------------: | -------------------: | ------------------------: |
| AUDIT         |      2 |                57,856 |                    2 |                         0 |
| CORE          |     10 |         5,874,389,504 |                   10 |                         0 |
| MARTS         |      4 |         3,812,877,824 |                    4 |                         0 |
| OBSERVABILITY |      5 |                35,840 |                    5 |                         0 |
| RAW           |      8 |         2,551,136,768 |                    8 |                         0 |
