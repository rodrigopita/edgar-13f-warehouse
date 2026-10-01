import os
from datetime import date

import boto3
import pytest
from moto import mock_aws

from include.edgar_filing import PRIMARY_DOC, FilingBytes, FilingDocuments
from include.edgar_index import IndexEntry
from include.landing import (
    LandingZone,
    filing_prefix,
    index_key,
    info_table_key,
    primary_doc_key,
)

BUCKET = "landing-under-test"

REPORT = IndexEntry(
    form_type="13F-HR",
    company_name="Andra AP-fonden",
    cik=1535452,
    filed=date(2026, 9, 22),
    accession="0001535452-26-000006",
    path="edgar/data/1535452/0001535452-26-000006.txt",
)
REPORT_DOCS = FilingDocuments(
    accession=REPORT.accession,
    folder=REPORT.filing_folder,
    primary_doc=PRIMARY_DOC,
    info_table="AP2ReportQ22026.xml",
)
NOTICE = IndexEntry(
    form_type="13F-NT",
    company_name="140 Summer Partners Master Fund LP",
    cik=1844084,
    filed=date(2026, 8, 14),
    accession="0000919574-26-005166",
    path="edgar/data/1844084/0000919574-26-005166.txt",
)
NOTICE_DOCS = FilingDocuments(
    accession=NOTICE.accession,
    folder=NOTICE.filing_folder,
    primary_doc=PRIMARY_DOC,
    info_table=None,
)


class TestKeys:
    def test_index_key_is_the_sec_file_name_under_the_index_prefix(self):
        assert index_key(date(2026, 9, 22)) == "raw/edgar/index/form.20260922.idx"

    def test_filing_keys_partition_by_filing_date_then_accession(self):
        prefix = filing_prefix(date(2026, 9, 22), "0001535452-26-000006")

        assert prefix == "raw/edgar/filings/filed=2026-09-22/0001535452-26-000006/"
        assert (
            primary_doc_key(date(2026, 9, 22), "0001535452-26-000006") == prefix + "primary_doc.xml"
        )
        assert info_table_key(date(2026, 9, 22), "0001535452-26-000006") == prefix + "infotable.xml"


@pytest.fixture
def s3():
    # moto answers boto3 in-process; the credentials only need to exist.
    os.environ.update(
        AWS_ACCESS_KEY_ID="testing",
        AWS_SECRET_ACCESS_KEY="testing",
        AWS_DEFAULT_REGION="us-east-1",
    )
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        client.put_bucket_versioning(Bucket=BUCKET, VersioningConfiguration={"Status": "Enabled"})
        yield client


@pytest.fixture
def zone(s3) -> LandingZone:
    return LandingZone(BUCKET, s3_client=s3)


def stored(s3, key: str) -> dict:
    obj = s3.get_object(Bucket=BUCKET, Key=key)
    return {"body": obj["Body"].read(), "type": obj["ContentType"], "meta": obj["Metadata"]}


def test_land_index_writes_the_bytes_unchanged_as_text(zone, s3):
    data = b"Description: Daily Index\n----\n13F-HR  X  1  20260922  edgar/data/1/a.txt\n"

    landed = zone.land_index(date(2026, 9, 22), data)

    assert landed.key == "raw/edgar/index/form.20260922.idx"
    assert landed.size == len(data)
    assert landed.version_id
    assert stored(s3, landed.key) == {
        "body": data,
        "type": "text/plain",
        "meta": {"source": "form.20260922.idx"},
    }


class TestLandFiling:
    def test_holdings_report_lands_two_objects_with_a_fixed_table_name(self, zone, s3):
        filing = FilingBytes(REPORT, REPORT_DOCS, b"<edgarSubmission/>", b"<informationTable/>")

        landed = zone.land_filing(filing)

        assert [item.key for item in landed] == [
            "raw/edgar/filings/filed=2026-09-22/0001535452-26-000006/primary_doc.xml",
            "raw/edgar/filings/filed=2026-09-22/0001535452-26-000006/infotable.xml",
        ]
        table = stored(s3, landed[1].key)
        assert table["body"] == b"<informationTable/>"
        assert table["type"] == "application/xml"
        assert table["meta"] == {
            "accession": "0001535452-26-000006",
            "cik": "1535452",
            "form-type": "13F-HR",
            "filed": "2026-09-22",
            "original-name": "AP2ReportQ22026.xml",
        }

    def test_notice_lands_the_cover_page_only(self, zone, s3):
        filing = FilingBytes(NOTICE, NOTICE_DOCS, b"<edgarSubmission/>", None)

        landed = zone.land_filing(filing)

        assert [item.key for item in landed] == [
            "raw/edgar/filings/filed=2026-08-14/0000919574-26-005166/primary_doc.xml"
        ]
        keys = [o["Key"] for o in s3.list_objects_v2(Bucket=BUCKET)["Contents"]]
        assert keys == [landed[0].key]

    def test_the_partition_comes_from_the_row_not_the_walk_day(self, zone):
        # A late filer found in the 2026-09-22 index but filed 2026-03-31 lands
        # under its own filing date.
        late = IndexEntry("13F-HR", "Late LP", 7, date(2026, 3, 31), "0000000007-26-000001", "x")
        docs = FilingDocuments(late.accession, late.filing_folder, PRIMARY_DOC, "t.xml")

        landed = zone.land_filing(FilingBytes(late, docs, b"<a/>", b"<b/>"))

        assert all(item.key.startswith("raw/edgar/filings/filed=2026-03-31/") for item in landed)


class TestIdempotency:
    def test_a_second_run_of_the_same_input_changes_nothing_visible(self, zone, s3):
        filing = FilingBytes(REPORT, REPORT_DOCS, b"<edgarSubmission/>", b"<informationTable/>")

        first = zone.land_filing(filing)
        second = zone.land_filing(filing)

        assert [i.key for i in first] == [i.key for i in second]
        # Still two keys, each current version holding the input bytes, and each
        # key carrying two versions: the rerun rewrote, it did not add or alter.
        listing = s3.list_objects_v2(Bucket=BUCKET)["Contents"]
        assert len(listing) == 2
        assert stored(s3, second[0].key)["body"] == b"<edgarSubmission/>"
        assert stored(s3, second[1].key)["body"] == b"<informationTable/>"
        for item in second:
            versions = s3.list_object_versions(Bucket=BUCKET, Prefix=item.key)["Versions"]
            assert len(versions) == 2

    def test_versioning_keeps_the_overwritten_object(self, zone, s3):
        key = index_key(date(2026, 9, 22))
        zone.land_index(date(2026, 9, 22), b"first")
        zone.land_index(date(2026, 9, 22), b"second")

        versions = s3.list_object_versions(Bucket=BUCKET, Prefix=key)["Versions"]

        assert len(versions) == 2
        assert stored(s3, key)["body"] == b"second"


def test_exists_is_false_before_and_true_after_landing(zone):
    key = index_key(date(2026, 9, 22))

    assert not zone.exists(key)
    zone.land_index(date(2026, 9, 22), b"x")
    assert zone.exists(key)
