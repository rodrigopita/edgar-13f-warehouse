"""Tests that talk to sec.gov. Deselected by default; run with `uv run pytest -m live`.

They need the contact address the DAG will use, read from AIRFLOW_VAR_EDGAR_CONTACT,
the same variable `.env` gives the Airflow containers.
"""

import datetime as dt
import json
import logging
import os
from zoneinfo import ZoneInfo

import pytest

from include.edgar_client import DEFAULT_MAX_RPS, EdgarClient, EdgarPermanentError

pytestmark = pytest.mark.live

logger = logging.getLogger(__name__)


def current_quarter_path() -> str:
    # EDGAR files by Eastern time; near a quarter boundary UTC would name the wrong folder.
    today = dt.datetime.now(ZoneInfo("America/New_York")).date()
    quarter = (today.month - 1) // 3 + 1
    return f"/Archives/edgar/daily-index/{today.year}/QTR{quarter}"


@pytest.fixture(scope="module")
def client() -> EdgarClient:
    contact = os.environ.get("AIRFLOW_VAR_EDGAR_CONTACT")
    if not contact:
        pytest.skip("AIRFLOW_VAR_EDGAR_CONTACT is not set; see .env.example")
    return EdgarClient(contact)


def test_quarter_index_lists_daily_form_files(client):
    body = client.get(f"{current_quarter_path()}/index.json")

    names = [item["name"] for item in json.loads(body)["directory"]["item"]]
    assert any(name.startswith("form.") and name.endswith(".idx") for name in names)


def test_missing_file_is_a_403_and_is_not_retried(client):
    before = client.requests_made

    with pytest.raises(EdgarPermanentError) as excinfo:
        client.get(f"{current_quarter_path()}/form.19000101.idx")

    assert excinfo.value.status == 403
    assert client.requests_made == before + 1


def test_twenty_requests_stay_under_the_ceiling(client):
    for _ in range(20):
        client.get(f"{current_quarter_path()}/index.json")

    stats = client.stats()
    logger.info("live edgar stats: %s", stats)
    assert stats["retries"] == 0
    # The invariant is spacing, not the average: n requests need at least n - 1 gaps
    # of 1 / max_rps. The average of n over n - 1 gaps sits slightly above the ceiling
    # when the network is fast, so asserting on it would be flaky.
    minimum_elapsed = (stats["requests_made"] - 1) / DEFAULT_MAX_RPS
    assert stats["elapsed_seconds"] >= minimum_elapsed
