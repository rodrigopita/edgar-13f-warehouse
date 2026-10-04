import json
import os
from datetime import UTC, date, datetime
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

from include import walk
from include.edgar_client import EdgarClient
from include.landing import LandingZone, index_key, info_table_key, primary_doc_key
from tests.fakes import FakeResponse

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "edgar"
BUCKET = "landing-under-test"
QTR3 = "https://www.sec.gov/Archives/edgar/daily-index/2026/QTR3"
QTR4 = "https://www.sec.gov/Archives/edgar/daily-index/2026/QTR4"

HEADER = "Form Type   Company Name   CIK   Date Filed  File Name\n" + "-" * 80 + "\n"


def row(form_type: str, company: str, cik: str, filed: str, accession: str) -> str:
    return f"{form_type:<17}{company:<40}{cik:<12}{filed:<12}edgar/data/{cik}/{accession}.txt\n"


def listing(*days: str) -> bytes:
    items = [{"name": f"form.{d}.idx"} for d in days]
    return json.dumps({"directory": {"item": items}}).encode()


def folder(*names: str) -> bytes:
    return json.dumps({"directory": {"item": [{"name": n} for n in names]}}).encode()


@pytest.fixture
def s3():
    os.environ.update(
        AWS_ACCESS_KEY_ID="testing", AWS_SECRET_ACCESS_KEY="testing", AWS_DEFAULT_REGION="us-east-1"
    )
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client


@pytest.fixture
def zone(s3) -> LandingZone:
    return LandingZone(BUCKET, s3_client=s3)


@pytest.fixture
def client(session, clock, sleeper) -> EdgarClient:
    return EdgarClient("someone@example.com", session=session, clock=clock, sleeper=sleeper)


class TestDayFor:
    def test_a_run_at_0600_walks_the_previous_day(self):
        assert walk.day_for(datetime(2026, 9, 23, 6, 0, tzinfo=UTC)) == date(2026, 9, 22)

    def test_a_manual_run_in_the_afternoon_also_walks_yesterday(self):
        assert walk.day_for(datetime(2026, 9, 23, 15, 42, tzinfo=UTC)) == date(2026, 9, 22)

    def test_crosses_month_and_year_boundaries(self):
        assert walk.day_for(datetime(2026, 10, 1, 6, tzinfo=UTC)) == date(2026, 9, 30)
        assert walk.day_for(datetime(2027, 1, 1, 6, tzinfo=UTC)) == date(2026, 12, 31)


class TestBatches:
    def test_splits_into_half_open_ranges(self):
        assert walk.batches(250, size=100) == [(0, 100), (100, 200), (200, 250)]

    def test_exact_multiple_has_no_empty_tail(self):
        assert walk.batches(200, size=100) == [(0, 100), (100, 200)]

    def test_zero_entries_is_one_empty_range(self):
        assert walk.batches(0) == [(0, 0)]

    def test_a_wave_day_stays_far_under_the_map_limit(self):
        assert len(walk.batches(2602)) == 27


class TestPlanDays:
    def test_published_day_with_nothing_to_sweep(self, client, session, zone):
        session.queue(FakeResponse(200, listing("20260921", "20260922")))
        zone.land_index(date(2026, 9, 21), b"landed")

        plan = walk.plan_days(client, zone, date(2026, 9, 22), since=date(2026, 9, 1))

        assert plan == {"day": "2026-09-22", "published": True, "sweep": []}
        assert session.calls == [f"{QTR3}/index.json"]

    def test_unpublished_day_is_reported_not_raised(self, client, session, zone):
        session.queue(FakeResponse(200, listing("20260918")))

        plan = walk.plan_days(client, zone, date(2026, 9, 20), since=date(2026, 9, 1))

        assert plan["published"] is False

    def test_a_listed_day_missing_in_s3_is_swept(self, client, session, zone):
        session.queue(FakeResponse(200, listing("20260921", "20260922")))

        plan = walk.plan_days(client, zone, date(2026, 9, 22), since=date(2026, 9, 1))

        assert plan["sweep"] == ["2026-09-21"]

    def test_sweep_window_is_bounded_and_respects_since(self, client, session, zone):
        session.queue(FakeResponse(200, listing("20260901", "20260910", "20260914", "20260915")))

        plan = walk.plan_days(client, zone, date(2026, 9, 22), since=date(2026, 9, 1))

        # 09-10 is outside the 7-day window, 09-01 too; 09-14 is 8 days back, out.
        assert plan["sweep"] == ["2026-09-15"]

    def test_since_cuts_the_window_short(self, client, session, zone):
        session.queue(FakeResponse(200, listing("20260828", "20260901", "20260902")))

        plan = walk.plan_days(client, zone, date(2026, 9, 3), since=date(2026, 9, 1))

        assert plan["sweep"] == ["2026-09-01", "2026-09-02"]

    def test_window_across_a_quarter_boundary_lists_both_quarters(self, client, session, zone):
        session.queue(FakeResponse(200, listing("20260929", "20260930")))
        session.queue(FakeResponse(200, listing("20261001", "20261002")))

        plan = walk.plan_days(client, zone, date(2026, 10, 2), since=date(2026, 9, 1))

        assert session.calls == [f"{QTR3}/index.json", f"{QTR4}/index.json"]
        assert plan["published"] is True
        assert plan["sweep"] == ["2026-09-29", "2026-09-30", "2026-10-01"]


class TestLandDayIndex:
    def test_lands_the_file_then_describes_one_batch(self, client, session, zone):
        real_index = (FIXTURES / "form.20260922.idx").read_bytes()
        session.queue(FakeResponse(200, listing("20260922")), FakeResponse(200, real_index))

        descriptors = walk.land_day_index(client, zone, date(2026, 9, 22))

        assert zone.read(index_key(date(2026, 9, 22))) == real_index
        assert descriptors == [
            {
                "day": "2026-09-22",
                "key": "raw/edgar/index/form.20260922.idx",
                "discovered": 20,
                "by_form": {"13F-HR": 14, "13F-HR/A": 6},
                "start": 0,
                "stop": 20,
            }
        ]

    def test_a_day_with_no_13f_filings_still_yields_a_descriptor(self, client, session, zone):
        text = HEADER + row("10-K", "SOME CORP", "1", "20260922", "0000000001-26-000001")
        session.queue(FakeResponse(200, listing("20260922")), FakeResponse(200, text.encode()))

        descriptors = walk.land_day_index(client, zone, date(2026, 9, 22))

        assert descriptors[0]["discovered"] == 0
        assert (descriptors[0]["start"], descriptors[0]["stop"]) == (0, 0)


class TestWalkBatch:
    REPORT = row("13F-HR", "HOLDER LP", "3", "20260922", "0000000003-26-000001")
    NOTICE = row("13F-NT", "NOTICE LLC", "2", "20260922", "0000000002-26-000001")
    KEY = index_key(date(2026, 9, 22))

    def land_index(self, zone, *rows: str) -> None:
        zone.land_index(date(2026, 9, 22), (HEADER + "".join(rows)).encode())

    def test_lands_each_filing_and_reports_the_counts(self, client, session, zone):
        self.land_index(zone, self.REPORT, self.NOTICE)
        session.queue(
            FakeResponse(200, folder("primary_doc.xml", "table.xml")),
            FakeResponse(200, b"<cover-3/>"),
            FakeResponse(200, b"<table-3/>"),
            FakeResponse(200, folder("primary_doc.xml")),
            FakeResponse(200, b"<cover-2/>"),
        )

        result = walk.walk_batch(client, zone, self.KEY, 0, 2)

        assert result["landed"] == ["0000000003-26-000001", "0000000002-26-000001"]
        assert result["present"] == [] and result["failed"] == []
        assert result["client"]["requests_made"] == 5
        assert zone.read(info_table_key(date(2026, 9, 22), "0000000003-26-000001")) == b"<table-3/>"
        assert (
            zone.read(primary_doc_key(date(2026, 9, 22), "0000000002-26-000001")) == b"<cover-2/>"
        )

    def test_a_rerun_makes_no_edgar_request(self, client, session, zone):
        self.land_index(zone, self.REPORT, self.NOTICE)
        session.queue(
            FakeResponse(200, folder("primary_doc.xml", "table.xml")),
            FakeResponse(200, b"<cover-3/>"),
            FakeResponse(200, b"<table-3/>"),
            FakeResponse(200, folder("primary_doc.xml")),
            FakeResponse(200, b"<cover-2/>"),
        )
        walk.walk_batch(client, zone, self.KEY, 0, 2)
        calls_after_first = len(session.calls)

        result = walk.walk_batch(client, zone, self.KEY, 0, 2)

        assert result["present"] == ["0000000003-26-000001", "0000000002-26-000001"]
        assert result["landed"] == []
        assert len(session.calls) == calls_after_first

    def test_a_report_missing_its_table_is_refetched(self, client, session, zone):
        self.land_index(zone, self.REPORT)
        zone._put(
            primary_doc_key(date(2026, 9, 22), "0000000003-26-000001"),
            b"<old/>",
            "application/xml",
            {},
        )
        session.queue(
            FakeResponse(200, folder("primary_doc.xml", "table.xml")),
            FakeResponse(200, b"<cover-3/>"),
            FakeResponse(200, b"<table-3/>"),
        )

        result = walk.walk_batch(client, zone, self.KEY, 0, 1)

        assert result["landed"] == ["0000000003-26-000001"]

    def test_one_bad_filing_is_recorded_and_the_batch_goes_on(self, client, session, zone):
        self.land_index(zone, self.REPORT, self.NOTICE)
        session.queue(
            FakeResponse(200, folder("primary_doc.xml")),  # a report with no table
            FakeResponse(200, folder("primary_doc.xml")),
            FakeResponse(200, b"<cover-2/>"),
        )

        result = walk.walk_batch(client, zone, self.KEY, 0, 2)

        assert result["landed"] == ["0000000002-26-000001"]
        assert len(result["failed"]) == 1
        assert result["failed"][0]["accession"] == "0000000003-26-000001"
        assert result["failed"][0]["error"].startswith("FilingLayoutError: ")

    def test_a_403_on_one_filing_is_recorded_too(self, client, session, zone):
        self.land_index(zone, self.NOTICE)
        session.queue(FakeResponse(403, b"<html>Undeclared Automated Tool</html>"))

        result = walk.walk_batch(client, zone, self.KEY, 0, 1)

        assert result["failed"][0]["error"].startswith("EdgarPermanentError: HTTP 403")

    def test_slices_the_index_by_the_given_range(self, client, session, zone):
        self.land_index(zone, self.REPORT, self.NOTICE)
        session.queue(
            FakeResponse(200, folder("primary_doc.xml")), FakeResponse(200, b"<cover-2/>")
        )

        result = walk.walk_batch(client, zone, self.KEY, 1, 2)

        assert result["landed"] == ["0000000002-26-000001"]


class TestAuditRecord:
    def test_sums_across_batches_and_keeps_each_day_once(self):
        plan = {"day": "2026-09-22", "published": True, "sweep": ["2026-09-21"]}
        day22 = {"day": "2026-09-22", "key": "k22", "discovered": 150, "by_form": {"13F-HR": 150}}
        day21 = {"day": "2026-09-21", "key": "k21", "discovered": 3, "by_form": {"13F-NT": 3}}
        results = [
            day22
            | {
                "start": 0,
                "stop": 100,
                "landed": ["a"] * 90,
                "present": ["p"] * 9,
                "failed": [{"accession": "x", "form_type": "13F-HR", "error": "e"}],
                "client": {"requests_made": 280, "retries": 1},
            },
            day22
            | {
                "start": 100,
                "stop": 150,
                "landed": ["a"] * 50,
                "present": [],
                "failed": [],
                "client": {"requests_made": 150, "retries": 0},
            },
            day21
            | {
                "start": 0,
                "stop": 3,
                "landed": [],
                "present": ["p"] * 3,
                "failed": [],
                "client": {"requests_made": 0, "retries": 0},
            },
        ]

        record = walk.audit_record(plan, results, "scheduled__2026-09-23T06:00:00+00:00", "now")

        assert record["discovered"] == 153
        assert record["landed"] == 140
        assert record["already_present"] == 12
        assert record["failed"] == [{"accession": "x", "form_type": "13F-HR", "error": "e"}]
        assert record["requests_made"] == 430 and record["retries"] == 1
        assert record["batches"] == 3
        assert set(record["days"]) == {"2026-09-22", "2026-09-21"}
        assert record["swept_days"] == ["2026-09-21"]

    def test_an_empty_run_is_still_a_record(self):
        plan = {"day": "2026-09-20", "published": False, "sweep": []}

        record = walk.audit_record(plan, [], "manual__x", "now")

        assert record["discovered"] == 0 and record["batches"] == 0 and record["days"] == {}
