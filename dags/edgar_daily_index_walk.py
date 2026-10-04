"""Walk EDGAR's daily index for the previous day and land every 13F filing it lists.

Runs at 06:00 UTC and walks the previous calendar day, after the SEC posts
that day's index around 10 PM Eastern. Airflow 3's cron timetable sets
data_interval_start to the trigger time itself, so the day is derived by
walk.day_for rather than read from an interval. A day without an index is a
skip (weekends, holidays, not yet posted); a late posting is swept by a later
run. Everything that talks to EDGAR sits in the `edgar` pool, one slot, so a
single client limiter governs the request rate.

The first run walks 2026-09-01, the day after the last SEC 13F TSV dataset
available when this was written (01jun2026-31aug2026) ended, so the XML path
begins where the historical path stopped.
"""

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta

from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.sdk import Variable, dag, task

from include import walk
from include.edgar_client import EdgarClient
from include.landing import LandingZone

AWS_CONN_ID = "aws_default"
# The first run, at 06:00 UTC on 2026-09-02, walks 2026-09-01.
START = datetime(2026, 9, 2, tzinfo=UTC)


def edgar_client() -> EdgarClient:
    """Built per task from the contact Variable (AIRFLOW_VAR_EDGAR_CONTACT in .env)."""
    return EdgarClient(Variable.get("edgar_contact"))


def landing_zone() -> LandingZone:
    """Bucket from the raw_bucket Variable, boto3 client from the aws_default connection."""
    return LandingZone(Variable.get("raw_bucket"), S3Hook(aws_conn_id=AWS_CONN_ID).get_conn())


@dag(
    dag_id="edgar_daily_index_walk",
    schedule="0 6 * * *",
    start_date=START,
    catchup=True,
    max_active_runs=1,
    dagrun_timeout=timedelta(hours=3),
    default_args={"retries": 1, "retry_delay": timedelta(minutes=5)},
    description=(
        "Lands the previous day's EDGAR form index and every 13F filing it lists, "
        "plus any late-posted day from the last week. Idempotent (safe to rerun: a "
        "second run of the same input changes nothing)."
    ),
    tags=["edgar", "extraction"],
)
def edgar_daily_index_walk():
    @task(pool="edgar")
    def plan_walk(logical_date: datetime | None, data_interval_start: datetime) -> dict:
        """Walks the day before the run time; see walk.run_time and walk.day_for."""
        day = walk.day_for(walk.run_time(logical_date, data_interval_start))
        return walk.plan_days(edgar_client(), landing_zone(), day, since=walk.day_for(START))

    @task(pool="edgar")
    def land_indexes(plan: dict) -> list[dict]:
        """Land each day's index and return one descriptor per batch of filings."""
        days = ([plan["day"]] if plan["published"] else []) + plan["sweep"]
        client, zone = edgar_client(), landing_zone()
        descriptors: list[dict] = []
        for iso in days:
            descriptors.extend(walk.land_day_index(client, zone, date.fromisoformat(iso)))
        return descriptors

    @task(pool="edgar", retries=0)
    def walk_batch(batch: dict) -> dict:
        """Per-filing failures are recorded in the result; a batch failure is a bug."""
        result = walk.walk_batch(
            edgar_client(), landing_zone(), batch["key"], batch["start"], batch["stop"]
        )
        return batch | result

    @task(trigger_rule="all_done")
    def record_audit(
        plan: dict | None,
        results: Sequence[dict] | None,
        run_id: str,
        logical_date: datetime | None,
        data_interval_start: datetime,
    ) -> str:
        """Written whatever happened upstream; a failed upstream shows as None here."""
        day = walk.day_for(walk.run_time(logical_date, data_interval_start))
        materialized = list(results) if results is not None else []
        plan = plan or {"day": day.isoformat(), "published": None, "sweep": []}
        record = walk.audit_record(plan, materialized, run_id, datetime.now(UTC).isoformat())
        return landing_zone().land_audit(day, run_id, record).key

    plan = plan_walk()
    descriptors = land_indexes(plan)
    results = walk_batch.expand(batch=descriptors)
    record_audit(plan, results)


edgar_daily_index_walk()
