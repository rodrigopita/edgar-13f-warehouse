import gzip
import io
import os
import re
import zipfile
from datetime import date
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

from include import sec_backfill
from include.edgar_client import EdgarClient
from include.landing import LandingZone, dataset_zip_key, extracted_key
from include.sec_datasets import Dataset
from include.sec_profile import TABLES
from tests.fakes import FakeResponse

BUCKET = "landing-under-test"
SQL_04 = Path(__file__).resolve().parents[2] / "include" / "sql" / "04_raw_datasets.sql"
URL = "https://www.sec.gov/files/structureddata/data/form-13f-data-sets/2013q2_form13f.zip"
DATASET = Dataset(date(2013, 4, 1), date(2013, 6, 30), "2013q2_form13f.zip", URL)


def header(table: str) -> str:
    return "\t".join(c.upper() for c in sec_backfill.COLUMNS[table]) + "\n"


def row(table: str, n: int) -> str:
    return "\t".join(f"{table[:3]}{n}-{i}" for i in range(len(sec_backfill.COLUMNS[table]))) + "\n"


def tsv(table: str, rows: int) -> bytes:
    return (header(table) + "".join(row(table, n) for n in range(rows))).encode()


def build_zip(rows: int = 3, folder: str = "", skip: str | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for table in TABLES:
            if table != skip:
                archive.writestr(f"{folder}{table}.tsv", tsv(table, rows))
        archive.writestr(f"{folder}FORM13F_readme.htm", "<html/>")
    return buffer.getvalue()


@pytest.fixture
def s3():
    os.environ.update(
        AWS_ACCESS_KEY_ID="testing", AWS_SECRET_ACCESS_KEY="testing", AWS_DEFAULT_REGION="us-east-1"
    )
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        client.put_bucket_versioning(Bucket=BUCKET, VersioningConfiguration={"Status": "Enabled"})
        yield client


@pytest.fixture
def zone(s3) -> LandingZone:
    return LandingZone(BUCKET, s3_client=s3)


@pytest.fixture
def client(session, clock, sleeper) -> EdgarClient:
    return EdgarClient("someone@example.com", session=session, clock=clock, sleeper=sleeper)


def queue_zip(session, data: bytes) -> None:
    session.queue(
        FakeResponse(200, headers={"Content-Length": str(len(data))}), FakeResponse(200, data)
    )


class TestStageDataset:
    def test_lands_the_zip_and_one_gzip_per_table_with_its_rows(self, client, session, zone):
        data = build_zip(rows=3)
        queue_zip(session, data)

        result = sec_backfill.stage_dataset(client, zone, DATASET)

        assert result == {
            "dataset": "2013q2_form13f.zip",
            "source": "sec",
            "rows": dict.fromkeys(TABLES, 3),
        }
        assert zone.read(dataset_zip_key("2013q2_form13f.zip")) == data
        for table in TABLES:
            key = extracted_key(table, "2013q2")
            assert gzip.decompress(zone.read(key)) == tsv(table, 3)
            assert zone.metadata(key) == {"dataset": "2013q2", "table": table, "rows": "3"}

    def test_a_rerun_fetches_nothing_and_reads_the_counts_back(self, client, session, zone, s3):
        queue_zip(session, build_zip(rows=3))
        sec_backfill.stage_dataset(client, zone, DATASET)
        calls_after_first = len(session.calls)

        result = sec_backfill.stage_dataset(client, zone, DATASET)

        assert result["source"] == "extracted"
        assert result["rows"] == dict.fromkeys(TABLES, 3)
        assert len(session.calls) == calls_after_first
        for table in TABLES:
            key = extracted_key(table, "2013q2")
            assert len(s3.list_object_versions(Bucket=BUCKET, Prefix=key)["Versions"]) == 1

    def test_a_landed_zip_is_read_from_s3_not_fetched(self, client, session, zone):
        zone.land_dataset_zip("2013q2_form13f.zip", build_zip(rows=2))

        result = sec_backfill.stage_dataset(client, zone, DATASET)

        assert result["source"] == "s3"
        assert result["rows"] == dict.fromkeys(TABLES, 2)
        assert session.calls == []

    def test_tables_nested_in_a_folder_are_found_by_name(self, client, session, zone):
        queue_zip(session, build_zip(rows=1, folder="01jun2025-31aug2025_form13f/"))

        result = sec_backfill.stage_dataset(client, zone, DATASET)

        assert result["rows"] == dict.fromkeys(TABLES, 1)

    def test_a_missing_table_is_a_layout_error_and_extracts_nothing(self, client, session, zone):
        queue_zip(session, build_zip(skip="SIGNATURE"))

        with pytest.raises(sec_backfill.DatasetLayoutError, match="no SIGNATURE.tsv"):
            sec_backfill.stage_dataset(client, zone, DATASET)

        assert not zone.exists(extracted_key("SIGNATURE", "2013q2"))


class TestGzipTable:
    def test_counts_data_rows_not_the_header(self):
        _, rows = sec_backfill.gzip_table(io.BytesIO(tsv("SUBMISSION", 5)), "SUBMISSION", "z")

        assert rows == 5

    def test_a_last_row_without_its_newline_still_counts(self):
        data = tsv("SUBMISSION", 2).rstrip(b"\n")

        compressed, rows = sec_backfill.gzip_table(io.BytesIO(data), "SUBMISSION", "z")

        assert rows == 2
        assert gzip.decompress(compressed) == data

    def test_a_header_only_table_has_no_rows(self):
        _, rows = sec_backfill.gzip_table(
            io.BytesIO(header("SUMMARYPAGE").encode()), "SUMMARYPAGE", "z"
        )

        assert rows == 0

    def test_the_same_table_gives_the_same_bytes_with_no_time_in_the_header(self):
        first, _ = sec_backfill.gzip_table(io.BytesIO(tsv("INFOTABLE", 50)), "INFOTABLE", "z")
        second, _ = sec_backfill.gzip_table(io.BytesIO(tsv("INFOTABLE", 50)), "INFOTABLE", "z")

        assert first == second
        assert first[4:8] == b"\x00\x00\x00\x00"

    def test_an_unexpected_header_is_a_layout_error(self):
        data = b"ACCESSION_NUMBER\tSOMETHING_ELSE\n1\t2\n"

        with pytest.raises(sec_backfill.DatasetLayoutError, match="z SUBMISSION: header"):
            sec_backfill.gzip_table(io.BytesIO(data), "SUBMISSION", "z")


def raw_table_columns() -> dict[str, tuple[str, ...]]:
    """Column names of each RAW.DATASET_<TABLE> as include/sql/04 creates it."""
    text = SQL_04.read_text()
    tables = {}
    for name, body in re.findall(r"edgar_13f\.raw\.dataset_(\w+) \((.*?)\n\)", text, re.DOTALL):
        tables[name.upper()] = tuple(re.findall(r"^\s{4}(\w+) ", body, re.MULTILINE))
    return tables


class TestCopyStatement:
    def test_the_columns_are_exactly_those_of_the_raw_table(self):
        tables = raw_table_columns()

        assert set(tables) == set(TABLES)
        for table in TABLES:
            assert tables[table] == sec_backfill.COLUMNS[table] + sec_backfill.SOURCE_COLUMNS

    def test_selects_one_position_per_column_from_the_table_folder(self):
        statement = sec_backfill.copy_statement("INFOTABLE")

        assert statement.startswith("copy into edgar_13f.raw.dataset_infotable (")
        assert "$15, metadata$filename" in statement and "$16" not in statement
        assert "from @edgar_13f.raw.datasets_stage/table=INFOTABLE/" in statement
        assert statement.endswith("on_error = abort_statement")


class TestCopyResults:
    NAMES = ("file", "status", "rows_parsed", "rows_loaded", "error_limit", "errors_seen")

    def test_one_dict_per_file_with_lower_case_keys(self):
        rows = [
            ("s3://b/extracted/sec/datasets/table=SUBMISSION/2013q2.tsv.gz", "LOADED", 3, 3, 1, 0)
        ]

        results = sec_backfill.copy_results([n.upper() for n in self.NAMES], rows)

        assert results == [dict(zip(self.NAMES, rows[0], strict=True))]

    def test_nothing_new_to_load_is_an_empty_list(self):
        results = sec_backfill.copy_results(
            ["status"], [("Copy executed with 0 files processed.",)]
        )

        assert results == []


class TestAuditRecord:
    STAGED = (
        {"dataset": "2013q2_form13f.zip", "source": "sec", "rows": dict.fromkeys(TABLES, 3)},
        {"dataset": "2013q3_form13f.zip", "source": "extracted", "rows": dict.fromkeys(TABLES, 4)},
    )

    def result(self, table: str, ident: str, loaded: int, status: str = "LOADED") -> dict:
        file = f"s3://b/extracted/sec/datasets/table={table}/{ident}.tsv.gz"
        return {"file": file, "status": status, "rows_parsed": loaded, "rows_loaded": loaded}

    def test_sums_extracted_and_loaded_rows_per_table(self):
        copies = [
            {"table": t, "results": [self.result(t, "2013q2", 3), self.result(t, "2013q3", 4)]}
            for t in TABLES
        ]

        record = sec_backfill.audit_record(list(self.STAGED), copies, "manual__x", "now")

        assert record["datasets"] == 2
        assert record["sources"] == {"sec": 1, "extracted": 1}
        assert record["extracted_rows"] == dict.fromkeys(TABLES, 7)
        assert record["rows_loaded"] == dict.fromkeys(TABLES, 7)
        assert record["files_loaded"] == dict.fromkeys(TABLES, 2)
        assert record["mismatches"] == [] and record["not_loaded"] == []

    def test_a_file_that_loaded_fewer_rows_than_it_held_is_a_mismatch(self):
        copies = [{"table": "INFOTABLE", "results": [self.result("INFOTABLE", "2013q2", 2)]}]

        record = sec_backfill.audit_record(list(self.STAGED), copies, "manual__x", "now")

        assert record["mismatches"] == [
            {"dataset": "2013q2_form13f.zip", "table": "INFOTABLE", "extracted": 3, "loaded": 2}
        ]

    def test_files_loaded_by_an_earlier_run_are_not_compared(self):
        record = sec_backfill.audit_record(list(self.STAGED), [], "manual__x", "now")

        assert record["mismatches"] == []
        assert record["rows_loaded"] == dict.fromkeys(TABLES, 0)

    def test_a_file_not_loaded_is_listed(self):
        failed = self.result("SIGNATURE", "2013q2", 0, status="LOAD_FAILED")

        record = sec_backfill.audit_record(
            list(self.STAGED), [{"table": "SIGNATURE", "results": [failed]}], "manual__x", "now"
        )

        assert record["not_loaded"] == [failed]


class TestReconcileSql:
    PROFILES = (
        {"name": "2013q3_form13f.zip", "rows": dict.fromkeys(TABLES, 4)},
        {"name": "2013q2_form13f.zip", "rows": dict.fromkeys(TABLES, 3) | {"INFOTABLE": 87715}},
    )

    def test_expects_every_table_of_every_profile_oldest_first(self):
        sql = sec_backfill.reconcile_sql(list(self.PROFILES))

        assert "('2013q2', 'INFOTABLE', 87715)" in sql
        assert "('2013q3', 'SUMMARYPAGE', 4)" in sql
        assert sql.index("('2013q2', 'SUBMISSION'") < sql.index("('2013q3', 'SUBMISSION'")
        # Each of the two queries carries its own list: two profiles, seven tables each.
        assert sql.count("        ('2013q") == 2 * 2 * len(TABLES)

    def test_counts_every_raw_table_by_file_and_returns_only_differences(self):
        sql = sec_backfill.reconcile_sql(list(self.PROFILES))

        for table in TABLES:
            assert f"from edgar_13f.raw.dataset_{table.lower()} group by file_name" in sql
        assert "full outer join loaded l" in sql
        assert "where expected_rows is distinct from loaded_rows" in sql
        assert sql.count(";") == 2
