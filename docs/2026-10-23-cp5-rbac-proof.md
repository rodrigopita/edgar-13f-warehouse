# cp5: each role does its own work and nothing else

Written 2026-10-23 from one run of the probes in this document, after `10_narrow_loader_grants.sql` and `11_analyst_role.sql`. It is the record of the cp5 done-criterion's RBAC: the scope asks for roles that separate ingestion, transformation and analytics, and here each of the four functional roles is shown doing its work and refused the rest.

## What the probes say

- **ANALYST reads the marts and nothing else.** It counted `position_changes` and `filer_overlaps`, and was refused CORE, RAW, AUDIT and OBSERVABILITY ("does not exist or not authorized"), an INSERT into `positions` and a CREATE TABLE in MARTS.
- **TRANSFORMER reads what was loaded and cannot change it.** It counted `RAW.PARSED_FILINGS`, `AUDIT.WALK_RUNS` and `MARTS.POSITIONS`, and was refused an INSERT into `RAW.PARSED_FILINGS` and into `AUDIT.WALK_RUNS`.
- **LOADER adds rows to RAW and reads nothing downstream.** An INSERT into `RAW.DATASET_SUBMISSION` was allowed, and AUDIT, CORE and MARTS were refused. Until `10` it also held INSERT on AUDIT, for audit rows that arrive by pipe since `08`; `show grants to role loader` now lists the warehouse, the database, RAW, the data set stage and RAW's eight tables, and nothing in AUDIT.
- **TERRAFORM owns the plumbing and sees no data.** It listed `PARSED_FILINGS_PIPE` in RAW and was refused CORE. It holds no warehouse, so it could not run a query even where it can see a table.
- **A rebuilt mart stays readable.** dbt replaces every mart on each build, and a replaced table is a new object. `filer_overlaps` was rebuilt after `11`: its OWNERSHIP grant to TRANSFORMER is dated 14:16:01.955 and ANALYST's SELECT 14:16:01.986, 31 milliseconds later, given by the future grant on MARTS.
- **A person reaches every role through SYSADMIN.** The numbered SQL grants LOADER, TRANSFORMER and TERRAFORM to SYSADMIN and to their service users, ANALYST to SYSADMIN alone, and none of them to a person; the probes ran as the account's own user, and `USE ROLE` switched to each.

## How it was run

On 2026-10-23, in `JOPUFPW-EDGAR_13F`, in Snowsight: `10`, then `11`, then `dbt build --select filer_overlaps` (5 of 5, 39 seconds), then the probes below. Each probe block switches to one role with secondary roles off, so that role alone authorizes every statement, and returns what happened to each. The writes are `INSERT ... WHERE FALSE`, which move no rows. `EDGAR_WH` was suspended after them.

The block, here with ANALYST's statements; TRANSFORMER's and LOADER's differ only in the list:

```sql
use role analyst;
use secondary roles none;
use warehouse edgar_wh;
execute immediate $$
declare
    probes array default array_construct(
        'select count(*) from edgar_13f.marts.position_changes',
        'select count(*) from edgar_13f.marts.filer_overlaps',
        'select count(*) from edgar_13f.core.canonical_holdings',
        'select count(*) from edgar_13f.raw.parsed_filings',
        'select count(*) from edgar_13f.audit.walk_runs',
        'select count(*) from edgar_13f.observability.walk_days',
        'insert into edgar_13f.marts.positions select * from edgar_13f.marts.positions where false',
        'create table edgar_13f.marts.rbac_probe (n integer)'
    );
    outcomes array default array_construct();
    probe varchar;
    outcome varchar;
begin
    for i in 0 to array_size(probes) - 1 do
        probe := probes[i]::varchar;
        begin
            execute immediate probe;
            outcome := 'allowed';
        exception
            when other then
                outcome := 'refused: ' || sqlerrm;
        end;
        outcomes := array_append(outcomes, object_construct('probe', probe, 'outcome', outcome));
    end for;
    return outcomes;
end;
$$;
```

TERRAFORM has no warehouse, so its probes were two SHOW commands: `show pipes in schema edgar_13f.raw` and `show tables in schema edgar_13f.core`.

## The outcomes

| role        | statement                                              | outcome                                                  |
| ----------- | ------------------------------------------------------ | -------------------------------------------------------- |
| ANALYST     | `select` from `MARTS.POSITION_CHANGES`                 | allowed                                                  |
| ANALYST     | `select` from `MARTS.FILER_OVERLAPS`, rebuilt          | allowed                                                  |
| ANALYST     | `select` from `CORE.CANONICAL_HOLDINGS`                | refused: schema does not exist or not authorized         |
| ANALYST     | `select` from `RAW.PARSED_FILINGS`                     | refused: schema does not exist or not authorized         |
| ANALYST     | `select` from `AUDIT.WALK_RUNS`                        | refused: schema does not exist or not authorized         |
| ANALYST     | `select` from `OBSERVABILITY.WALK_DAYS`                | refused: schema does not exist or not authorized         |
| ANALYST     | `insert` into `MARTS.POSITIONS`                        | refused: must have INSERT on the table                   |
| ANALYST     | `create table` in MARTS                                | refused: must have CREATE TABLE on the schema            |
| TRANSFORMER | `select` from `RAW.PARSED_FILINGS`                     | allowed                                                  |
| TRANSFORMER | `select` from `AUDIT.WALK_RUNS`                        | allowed                                                  |
| TRANSFORMER | `select` from `MARTS.POSITIONS`                        | allowed                                                  |
| TRANSFORMER | `insert` into `RAW.PARSED_FILINGS`                     | refused: must have INSERT on the table                   |
| TRANSFORMER | `insert` into `AUDIT.WALK_RUNS`                        | refused: must have INSERT on the table                   |
| LOADER      | `insert` into `RAW.DATASET_SUBMISSION`                 | allowed                                                  |
| LOADER      | `select` from `AUDIT.WALK_RUNS`                        | refused: schema does not exist or not authorized         |
| LOADER      | `select` from `CORE.FILINGS`                           | refused: schema does not exist or not authorized         |
| LOADER      | `select` from `MARTS.POSITIONS`                        | refused: schema does not exist or not authorized         |
| TERRAFORM   | `show pipes in schema edgar_13f.raw`                   | allowed: `PARSED_FILINGS_PIPE`, owner TERRAFORM          |
| TERRAFORM   | `show tables in schema edgar_13f.core`                 | refused: object does not exist, or operation cannot be performed |

Each refusal names the privilege the role lacks, for example: "Your primary role ANALYST must have USAGE or any other privilege granted on SCHEMA EDGAR_13F.CORE."
