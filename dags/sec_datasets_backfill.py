"""Load the SEC 13F data sets into Snowflake: the historical path, run by hand.

Lists the zips on the SEC's datasets page and stages each one in S3: the zip
as fetched, then its seven tables as gzip. Staging fetches from the SEC, so it
sits in the one-slot `edgar` pool. Once every zip is staged, one COPY per
table loads them into RAW.DATASET_<TABLE> as AIRFLOW_SVC with role LOADER.
Idempotent (safe to rerun: a second run of the same input changes nothing):
staged zips are skipped and COPY skips files it loaded in the last 64 days.
The audit record sets the rows each file held beside the rows Snowflake
loaded from it.
"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.snowflake.hooks.snowflake import SnowflakeHook
from airflow.sdk import Variable, dag, task

from include import sec_backfill, sec_datasets
from include.edgar_client import EdgarClient
from include.landing import LandingZone
from include.sec_profile import TABLES

AWS_CONN_ID = "aws_default"
SNOWFLAKE_CONN_ID = "snowflake_default"


def edgar_client() -> EdgarClient:
    """Built per task from the contact Variable (AIRFLOW_VAR_EDGAR_CONTACT in .env)."""
    return EdgarClient(Variable.get("edgar_contact"))


def landing_zone() -> LandingZone:
    """Bucket from the raw_bucket Variable, boto3 client from the aws_default connection."""
    return LandingZone(Variable.get("raw_bucket"), S3Hook(aws_conn_id=AWS_CONN_ID).get_conn())


@dag(
    dag_id="sec_datasets_backfill",
    schedule=None,
    start_date=datetime(2026, 10, 12, tzinfo=UTC),
    catchup=False,
    max_active_runs=1,
    dagrun_timeout=timedelta(hours=4),
    default_args={"retries": 1, "retry_delay": timedelta(minutes=5)},
    description=(
        "Stages every SEC 13F data set zip in S3 and COPYs its seven tables into "
        "RAW.DATASET_<TABLE>. Run by hand. Idempotent (safe to rerun: a second run "
        "of the same input changes nothing)."
    ),
    tags=["sec", "backfill"],
)
def sec_datasets_backfill():
    @task(pool="edgar")
    def list_datasets() -> list[dict]:
        """Name and URL of every zip, oldest first; the task rebuilds the dates."""
        return [{"name": d.name, "url": d.url} for d in sec_datasets.list_datasets(edgar_client())]

    @task(pool="edgar")
    def stage_dataset(dataset: dict) -> dict:
        """Fetches from the SEC only when the zip is in neither form in S3."""
        parsed = sec_datasets.parse_dataset(dataset["name"], dataset["url"])
        return sec_backfill.stage_dataset(edgar_client(), landing_zone(), parsed)

    @task(retries=0)
    def copy_table(table: str) -> dict:
        """A failed COPY loads nothing (ON_ERROR = ABORT_STATEMENT): look, fix, rerun."""
        hook = SnowflakeHook(snowflake_conn_id=SNOWFLAKE_CONN_ID)
        with hook.get_conn() as connection, connection.cursor() as cursor:
            cursor.execute(sec_backfill.copy_statement(table))
            names = [column[0] for column in cursor.description]
            results = sec_backfill.copy_results(names, cursor.fetchall())
        return {"table": table, "results": results}

    @task(trigger_rule="all_done")
    def record_audit(
        staged: Sequence[dict] | None, copied: Sequence[dict] | None, run_id: str
    ) -> str:
        """Written whatever happened upstream; a failed upstream shows as None here."""
        record = sec_backfill.audit_record(
            list(staged) if staged is not None else [],
            list(copied) if copied is not None else [],
            run_id,
            datetime.now(UTC).isoformat(),
        )
        return landing_zone().land_backfill_audit(run_id, record).key

    staged = stage_dataset.expand(dataset=list_datasets())
    copied = copy_table.expand(table=list(TABLES))
    staged >> copied
    record_audit(staged, copied)


sec_datasets_backfill()
