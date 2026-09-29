import json
from datetime import date
from pathlib import Path

import pytest

from include.edgar_client import EdgarClient
from include.edgar_filing import (
    PRIMARY_DOC,
    FilingDocuments,
    FilingLayoutError,
    fetch_filing,
    list_filing_documents,
)
from include.edgar_index import IndexEntry
from tests.fakes import FakeResponse

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "edgar"
SEC = "https://www.sec.gov"

HOLDINGS_REPORT = IndexEntry(
    form_type="13F-HR",
    company_name="Andra AP-fonden",
    cik=1535452,
    filed=date(2026, 9, 22),
    accession="0001535452-26-000006",
    path="edgar/data/1535452/0001535452-26-000006.txt",
)
NOTICE = IndexEntry(
    form_type="13F-NT",
    company_name="140 Summer Partners Master Fund LP",
    cik=1844084,
    filed=date(2026, 8, 14),
    accession="0000919574-26-005166",
    path="edgar/data/1844084/0000919574-26-005166.txt",
)
HR_FOLDER = f"{SEC}/Archives/edgar/data/1535452/000153545226000006/"
NT_FOLDER = f"{SEC}/Archives/edgar/data/1844084/000091957426005166/"


def listing(*names: str) -> bytes:
    return json.dumps({"directory": {"item": [{"name": n} for n in names]}}).encode()


@pytest.fixture
def client(session, clock, sleeper) -> EdgarClient:
    return EdgarClient("someone@example.com", session=session, clock=clock, sleeper=sleeper)


class TestListFilingDocuments:
    def test_holdings_report_names_its_filer_chosen_table(self, client, session):
        session.queue(
            FakeResponse(200, (FIXTURES / "filing-0001535452-26-000006-index.json").read_bytes())
        )

        documents = list_filing_documents(client, HOLDINGS_REPORT)

        assert session.calls == [f"{HR_FOLDER}index.json"]
        assert documents == FilingDocuments(
            accession="0001535452-26-000006",
            folder="/Archives/edgar/data/1535452/000153545226000006/",
            primary_doc=PRIMARY_DOC,
            info_table="AP2ReportQ22026.xml",
        )
        assert not documents.is_notice

    def test_notice_has_a_cover_page_and_no_table(self, client, session):
        session.queue(
            FakeResponse(200, (FIXTURES / "filing-0000919574-26-005166-index.json").read_bytes())
        )

        documents = list_filing_documents(client, NOTICE)

        assert documents.info_table is None
        assert documents.is_notice
        assert documents.primary_doc == PRIMARY_DOC

    def test_the_filer_name_is_taken_whatever_it_is(self, client, session):
        session.queue(FakeResponse(200, listing(PRIMARY_DOC, "infotable.xml", "0001-index.html")))

        assert list_filing_documents(client, HOLDINGS_REPORT).info_table == "infotable.xml"

    def test_table_match_is_case_insensitive_on_the_extension(self, client, session):
        session.queue(FakeResponse(200, listing(PRIMARY_DOC, "Holdings.XML")))

        assert list_filing_documents(client, HOLDINGS_REPORT).info_table == "Holdings.XML"

    def test_holdings_report_without_a_table_is_a_layout_error(self, client, session):
        session.queue(FakeResponse(200, listing(PRIMARY_DOC, "0001-index.html")))

        with pytest.raises(FilingLayoutError, match="expected one information table, found \\[\\]"):
            list_filing_documents(client, HOLDINGS_REPORT)

    def test_holdings_report_with_two_tables_is_a_layout_error(self, client, session):
        session.queue(FakeResponse(200, listing(PRIMARY_DOC, "a.xml", "b.xml")))

        with pytest.raises(FilingLayoutError, match="found \\['a.xml', 'b.xml'\\]"):
            list_filing_documents(client, HOLDINGS_REPORT)

    def test_notice_with_a_table_is_a_layout_error(self, client, session):
        session.queue(FakeResponse(200, listing(PRIMARY_DOC, "infotable.xml")))

        with pytest.raises(FilingLayoutError, match="a notice with XML tables"):
            list_filing_documents(client, NOTICE)

    def test_missing_cover_page_is_a_layout_error(self, client, session):
        session.queue(FakeResponse(200, listing("infotable.xml")))

        with pytest.raises(FilingLayoutError, match="no primary_doc.xml"):
            list_filing_documents(client, HOLDINGS_REPORT)

    def test_listing_that_is_not_json_is_a_layout_error(self, client, session):
        session.queue(FakeResponse(200, b"<html>Undeclared Automated Tool</html>"))

        with pytest.raises(FilingLayoutError, match="not the expected index.json shape"):
            list_filing_documents(client, HOLDINGS_REPORT)

    def test_a_non_13f_entry_is_refused_before_any_request(self, client, session):
        other = IndexEntry("10-K", "SOME CORP", 1, date(2026, 9, 22), "0000000001-26-000001", "x")

        with pytest.raises(ValueError, match="10-K"):
            list_filing_documents(client, other)

        assert session.calls == []


class TestFetchFiling:
    def test_holdings_report_takes_three_requests_in_order(self, client, session):
        session.queue(
            FakeResponse(200, (FIXTURES / "filing-0001535452-26-000006-index.json").read_bytes()),
            FakeResponse(200, b"<edgarSubmission/>"),
            FakeResponse(200, b"<informationTable/>"),
        )

        filing = fetch_filing(client, HOLDINGS_REPORT)

        assert session.calls == [
            f"{HR_FOLDER}index.json",
            f"{HR_FOLDER}primary_doc.xml",
            f"{HR_FOLDER}AP2ReportQ22026.xml",
        ]
        assert filing.entry is HOLDINGS_REPORT
        assert filing.primary_doc == b"<edgarSubmission/>"
        assert filing.info_table == b"<informationTable/>"

    def test_notice_takes_two_requests(self, client, session):
        session.queue(
            FakeResponse(200, (FIXTURES / "filing-0000919574-26-005166-index.json").read_bytes()),
            FakeResponse(200, b"<edgarSubmission/>"),
        )

        filing = fetch_filing(client, NOTICE)

        assert session.calls == [f"{NT_FOLDER}index.json", f"{NT_FOLDER}primary_doc.xml"]
        assert filing.info_table is None
        assert filing.documents.is_notice

    def test_bytes_are_returned_unparsed(self, client, session):
        session.queue(
            FakeResponse(200, listing(PRIMARY_DOC, "t.xml")),
            FakeResponse(200, b"not even xml"),
            FakeResponse(200, b"\x00\x01 binary junk"),
        )

        filing = fetch_filing(client, HOLDINGS_REPORT)

        assert filing.primary_doc == b"not even xml"
        assert filing.info_table == b"\x00\x01 binary junk"
