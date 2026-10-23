# EDGAR 13F Warehouse

A Snowflake warehouse that answers who holds what, and how institutional positions changed quarter over quarter, from SEC Form 13F filings. History comes from the SEC's own 13F data sets; every filing after them comes from a daily walk of EDGAR's index, parsed from XML, landed in S3 and loaded by Snowpipe. dbt resolves amendments once into canonical holdings and builds the marts from them.

The scope, every decision with its reason and date, and the checkpoints are in [docs/scope.md](docs/scope.md); the words the models and this README use are defined in [CONTEXT.md](CONTEXT.md).

**The trial ends before the November wave.** The Snowflake trial ends on 2026-11-08, before the mid-November wave of filings for 2026-09-30. The XML path is proven on late filers and amendments, up to 344 filings a day, and not on a wave day of about 2,600.

## Quickstart

**What it needs.** An AWS account with an admin profile, and a bucket name of your own. A Snowflake account; this one is a Standard trial in AWS us-east-1, the bucket's region. The [Astro CLI](https://www.astronomer.io/docs/astro/cli/overview) for Airflow, Terraform 1.5 or later, and [uv](https://docs.astral.sh/uv/), which brings Python 3.14 and every dependency. Three Snowflake key pairs, one each for Terraform, Airflow and dbt, encrypted with a real passphrase and kept outside the repository under `~/.snowflake/keys/`. The SEC asks automated clients to declare a contact address and stay under 10 requests a second: [Accessing EDGAR data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data), [Form 13F data sets](https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets).

1. **Local checks**, what CI runs on every push:
   ```bash
   uv sync --all-groups
   uv run ruff check . && uv run ruff format --check .
   uv run pytest            # tests that call sec.gov are marked live; -m live runs them
   ```
2. **Snowflake structure.** Run `include/sql/00` to `08` in order in Snowsight. `00` puts the resource monitor and the X-Small warehouse in place before anything spends a credit. `01`, `05` and `07` create the three service users and take their public keys, and `03` and `08` create the tables the pipes load. Each file's header names what must run before it, and its last statements show whether it worked.
3. **Terraform**, from `terraform/`, then the rest of the SQL:
   ```bash
   cp terraform.tfvars.example terraform.tfvars     # bucket, owner, AWS profile, Snowflake account
   read -rs TF_VAR_snowflake_private_key_passphrase && export TF_VAR_snowflake_private_key_passphrase
   terraform init && terraform apply                # bucket, IAM, storage integration, stages, pipes, notification
   terraform plan                                   # should read: No changes
   ```
   Then `include/sql/09` to `11`: the audit records written before the pipes, LOADER's narrowed grants and the analyst role.
4. **Airflow.** Copy `.env.example` to `.env` and fill it in. Build the Snowflake line from the key, never by hand:
   ```bash
   uv run python -I scripts/snowflake_conn_line.py ~/.snowflake/keys/<airflow key>.p8 >> .env
   astro dev start
   ```
   `sec_datasets_backfill` runs once by hand and loads the 54 data sets, about half an hour on 2026-10-13. `edgar_daily_index_walk` runs daily at 06:00 UTC with catchup, so the scheduler walks a day the laptop slept through once it wakes. Never run anything with `uv run --env-file .env`. uv cannot parse the Snowflake line, and it prints the line, key and passphrase included. To use the data set command line, pass only the contact address: `AIRFLOW_VAR_EDGAR_CONTACT=<address> uv run python -m include.sec_cli list`.
5. **dbt.** The connection lives in `~/.dbt/profiles.yml`, outside the repository, with two targets: `dev`, the default, on the development clone, and `prod` on the warehouse.
   ```yaml
   edgar_13f_warehouse:
     target: dev
     outputs:
       dev:
         type: snowflake
         account: <organization>-<account>
         user: DBT_SVC
         role: TRANSFORMER
         warehouse: EDGAR_WH
         database: EDGAR_13F_DEV
         schema: CORE
         threads: 4
         private_key_path: ~/.snowflake/keys/<dbt key>.p8
         private_key_passphrase: "{{ env_var('DBT_SNOWFLAKE_PRIVATE_KEY_PASSPHRASE') }}"
       prod:
         type: snowflake
         account: <organization>-<account>
         user: DBT_SVC
         role: TRANSFORMER
         warehouse: EDGAR_WH
         database: EDGAR_13F
         schema: CORE
         threads: 4
         private_key_path: ~/.snowflake/keys/<dbt key>.p8
         private_key_passphrase: "{{ env_var('DBT_SNOWFLAKE_PRIVATE_KEY_PASSPHRASE') }}"
   ```
   From `dbt/`, `dbt build --target prod` builds and tests everything, about 12 minutes on the X-Small, and `dbt source freshness --target prod` says whether the walk and the pipes are current. To change a model, refresh the clone with `include/sql/12_dev_clone.sql`, run `dbt run --select config.materialized:view` so its views read the clone, then `dbt build --select <model>+`.
6. **Check it.** `select * from edgar_13f.observability.walk_days where not_loaded <> 0` lists the days the walk discovered more than loaded, and `select * from edgar_13f.observability.pipeline_freshness` how current each layer is. End every session with `show warehouses` reading `SUSPENDED`.

## 1. Why this architecture?

```mermaid
flowchart LR
    DS[SEC 13F data sets] --> BF[backfill DAG]
    IX[EDGAR daily index and XML] --> WK[walk DAG: land and parse]
    BF --> S3[(S3 landing bucket)]
    WK --> S3
    S3 -- COPY --> RAW
    S3 -- Snowpipe --> RAW
    S3 -- Snowpipe --> AUDIT
    RAW --> DBT[dbt]
    AUDIT --> DBT
    DBT --> CORE[CORE: lineages, canonical holdings, data-quality rows]
    CORE --> MARTS[MARTS: positions, changes, concentration, overlap]
    DBT --> OBS[OBSERVABILITY]
```

- **History comes from the SEC's data sets, and everything after from a daily walk of EDGAR's index.** The data sets are the SEC's own flattening of the 13F XML, so the history needs no parser of its own, and the walk begins where the last data set ends. The 54 data sets hold 124,012,468 holdings filed from April 2013 to August 2026; from 2026-08-31 to 2026-10-21 the walk found 2,562 filings, and all of them are in the warehouse. The five from its first day came in through the last data set, which ends that day.
- **S3 is the record, and the warehouse rebuilds from it.** Every byte from the SEC lands unchanged in a versioned bucket, under keys derived from what it is, so a rerun writes the same object again. The pipeline's IAM user may put, get and list and nothing else, and Snowflake reads through a role of its own that cannot write.
- **The XML is parsed in Python before it reaches Snowflake.** A parser with pydantic types the filer's XML where it enters and writes one JSON-lines file per filing beside it; a filing it cannot read goes into the run's audit record instead of loading in part. Nine filings failed this way from 2026-10-13 to 2026-10-19, and all nine loaded on 2026-10-22 from the XML already in S3 ([the record](docs/2026-10-22-cp5-parse-failure-recovery.md)).
- **Loading runs without hands.** A bucket notification tells Snowpipe of each new file, so a parsed filing reaches `RAW.PARSED_FILINGS` with nobody running anything, 52 seconds at the median from the S3 write to the commit ([the record](docs/2026-10-11-cp2-xml-path-proof.md)).
- **dbt resolves amendments once, into canonical holdings, and the marts read nothing else.** A filer's filings for one period form a lineage, and one model decides which of them contribute. 1,040 additions in the data sets resubmit a whole list; reading them as restatements took $26.5 trillion of double counting out. The result matches a separate pass over the 54 zips to the row, 115,478,173 data-set holdings. "What did Lone Pine Capital buy and sell last quarter" is one select on `position_changes`, and its 49 rows match the filings on sec.gov.
- **The pipeline records itself, and the warehouse reads the record.** Each attempt of a walk or a backfill writes an audit record to S3, a pipe loads it into `AUDIT`, and dbt derives `OBSERVABILITY` from `AUDIT`, `RAW` and `CORE`, so whether the pipeline is whole is a query.
- **Each layer has its own schema and each job its own role.** `RAW` holds the record as loaded, `CORE` the typed filings and canonical holdings, `MARTS` the question-shaped tables; LOADER adds rows to `RAW`, TRANSFORMER builds, TERRAFORM owns the plumbing and ANALYST reads `MARTS` alone ([the probes](docs/2026-10-23-cp5-rbac-proof.md)).
- **Every model rebuilds in full, and development runs in a clone.** A full build takes 11 to 12 minutes and about a fifth of a credit. One statement makes `EDGAR_13F_DEV`, a zero-copy clone that holds the whole warehouse for development ([the record](docs/2026-10-23-cp5-dev-clone.md)).
