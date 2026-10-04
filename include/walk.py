"""One run of the EDGAR walk as functions over the client and the landing zone.

The DAG decides when; this module decides what: which days a run walks, how a
day's filings split into batches, how one batch lands, and what the audit
record says. Nothing here imports Airflow, so all of it runs under pytest with
a scripted HTTP session and an in-process S3.
"""

import logging
from collections import Counter
from datetime import date, datetime, timedelta

from include.edgar_client import EdgarClient, EdgarError
from include.edgar_filing import FilingLayoutError, fetch_filing
from include.edgar_index import (
    Form13F,
    fetch_daily_index,
    list_index_days,
    parse_form_index,
    quarter_path,
)
from include.landing import LandingZone, index_key, info_table_key, primary_doc_key

# Filings per mapped batch. A wave day has about 2,600 filings and Airflow maps at
# most 1,024 instances, so batches keep the map small; under the one-slot pool they
# run one at a time anyway.
BATCH_SIZE = 100
# A late posting seen so far was two days late (form.20260710.idx, posted on the
# 12th). Seven days bounds the S3 checks per run while covering that with room.
SWEEP_DAYS = 7

logger = logging.getLogger(__name__)


def day_for(run_time: datetime) -> date:
    """The day a run walks: the calendar day before the time the run is for.

    Airflow 3's cron timetable sets data_interval_start to the trigger time
    itself, so a run at 06:00 UTC on day D walks D-1, whose index the SEC
    posted around 02:00 UTC that morning.
    """
    return run_time.date() - timedelta(days=1)


def plan_days(client: EdgarClient, zone: LandingZone, day: date, since: date) -> dict:
    """What this run walks: `day` if its index is published, plus swept late days.

    The sweep covers listed days in the last SWEEP_DAYS before `day`, not before
    `since`, whose index is not yet in S3. When that window crosses a quarter
    boundary both quarters are listed, otherwise a late September posting would be
    invisible to every October run.
    """
    window_start = max(since, day - timedelta(days=SWEEP_DAYS))
    listed: set[date] = set()
    for probe in sorted({quarter_path(window_start), quarter_path(day)}):
        listed.update(list_index_days(client, _any_day_in(probe, window_start, day)))
    sweep = [d for d in sorted(listed) if window_start <= d < day and not zone.exists(index_key(d))]
    return {
        "day": day.isoformat(),
        "published": day in listed,
        "sweep": [d.isoformat() for d in sweep],
    }


def _any_day_in(quarter: str, first: date, second: date) -> date:
    return first if quarter_path(first) == quarter else second


def batches(total: int, size: int = BATCH_SIZE) -> list[tuple[int, int]]:
    """Half-open index ranges covering `total` entries; one empty range when total is 0.

    The empty range keeps a day with zero 13F filings visible in the audit.
    """
    if total == 0:
        return [(0, 0)]
    return [(start, min(start + size, total)) for start in range(0, total, size)]


def land_day_index(client: EdgarClient, zone: LandingZone, day: date) -> list[dict]:
    """Fetch and land one day's index, then describe its batches.

    The index is landed before it is parsed: if the parser ever breaks, the file
    is already in the bucket and a rerun is reprocessing, not loss.
    """
    data = fetch_daily_index(client, day)
    landed = zone.land_index(day, data)
    entries = parse_form_index(data)
    by_form = dict(Counter(e.form_type for e in entries))
    logger.info("landed %s: %d 13F filings %s", landed.key, len(entries), by_form)
    return [
        {
            "day": day.isoformat(),
            "key": landed.key,
            "discovered": len(entries),
            "by_form": by_form,
            "start": start,
            "stop": stop,
        }
        for start, stop in batches(len(entries))
    ]


def walk_batch(client: EdgarClient, zone: LandingZone, key: str, start: int, stop: int) -> dict:
    """Land the filings in one slice of a landed index.

    A filing already in S3 costs one or two HEAD requests and no EDGAR request.
    A filing that fails is recorded with its reason and the batch goes on; the
    audit shows it, and a rerun of the day retries only what is missing.
    """
    entries = parse_form_index(zone.read(key))[start:stop]
    landed: list[str] = []
    present: list[str] = []
    failed: list[dict] = []
    for entry in entries:
        if _already_landed(zone, entry):
            present.append(entry.accession)
            continue
        try:
            zone.land_filing(fetch_filing(client, entry))
        except (EdgarError, FilingLayoutError) as exc:
            logger.warning("%s %s failed: %s", entry.form_type, entry.accession, exc)
            failed.append(
                {
                    "accession": entry.accession,
                    "form_type": entry.form_type,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
        else:
            landed.append(entry.accession)
    stats = client.stats()
    logger.info(
        "batch %s[%d:%d]: %d landed, %d present, %d failed, %d requests at %.2f req/s",
        key,
        start,
        stop,
        len(landed),
        len(present),
        len(failed),
        stats["requests_made"],
        stats["requests_per_second"],
    )
    return {"landed": landed, "present": present, "failed": failed, "client": stats}


def _already_landed(zone: LandingZone, entry) -> bool:
    if not zone.exists(primary_doc_key(entry.filed, entry.accession)):
        return False
    needs_table = Form13F(entry.form_type) in (Form13F.HR, Form13F.HR_A)
    return not needs_table or zone.exists(info_table_key(entry.filed, entry.accession))


def audit_record(plan: dict, results: list[dict], run_id: str, recorded_at: str) -> dict:
    """One run's numbers, written by the pipeline: discovered, landed, present, failed."""
    days: dict[str, dict] = {}
    for result in results:
        days.setdefault(
            result["day"],
            {
                "key": result["key"],
                "discovered": result["discovered"],
                "by_form": result["by_form"],
            },
        )
    return {
        "run_id": run_id,
        "recorded_at": recorded_at,
        "day": plan["day"],
        "published": plan["published"],
        "swept_days": plan["sweep"],
        "days": days,
        "discovered": sum(d["discovered"] for d in days.values()),
        "landed": sum(len(r["landed"]) for r in results),
        "already_present": sum(len(r["present"]) for r in results),
        "failed": [f for r in results for f in r["failed"]],
        "requests_made": sum(r["client"]["requests_made"] for r in results),
        "retries": sum(r["client"]["retries"] for r in results),
        "batches": len(results),
    }
