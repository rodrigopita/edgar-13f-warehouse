import json
from pathlib import Path

import pytest

from include.edgar_xml import CoverPage, Holding, parse_cover_page, parse_information_table
from include.parsed import filing_lines

XML = Path(__file__).resolve().parents[1] / "fixtures" / "edgar" / "xml"
REPORT = "0001214659-26-011275"
NOTICE = "0001451086-26-000003"
COVER_KEY = f"raw/edgar/filings/filed=2026-09-22/{REPORT}/primary_doc.xml"
TABLE_KEY = f"raw/edgar/filings/filed=2026-09-22/{REPORT}/infotable.xml"


def report() -> tuple[CoverPage, list[Holding]]:
    cover = parse_cover_page((XML / f"hr-{REPORT}-primary_doc.xml").read_bytes(), REPORT)
    holdings = parse_information_table((XML / f"hr-{REPORT}-infotable.xml").read_bytes(), REPORT)
    return cover, holdings


def rows(data: bytes) -> list[dict]:
    return [json.loads(line) for line in data.decode().splitlines()]


class TestFilingLines:
    def test_the_cover_page_comes_first_then_one_line_per_holding(self):
        cover, holdings = report()

        lines = rows(filing_lines(cover, COVER_KEY, holdings, TABLE_KEY))

        assert len(lines) == 1 + 91
        assert lines[0]["record_type"] == "cover"
        assert {line["record_type"] for line in lines[1:]} == {"holding"}
        assert [line["record"]["row_index"] for line in lines[1:]] == list(range(1, 92))

    def test_every_line_is_the_same_envelope_naming_its_source(self):
        cover, holdings = report()

        lines = rows(filing_lines(cover, COVER_KEY, holdings, TABLE_KEY))

        assert all(
            set(line) == {"accession", "record", "record_type", "source_key"} for line in lines
        )
        assert {line["accession"] for line in lines} == {REPORT}
        assert lines[0]["source_key"] == COVER_KEY
        assert {line["source_key"] for line in lines[1:]} == {TABLE_KEY}

    def test_dates_and_the_form_type_come_out_as_json_strings(self):
        cover, holdings = report()

        record = rows(filing_lines(cover, COVER_KEY, holdings, TABLE_KEY))[0]["record"]

        assert record["submission_type"] == "13F-HR"
        assert record["period_of_report"] == cover.period_of_report.isoformat()

    def test_parsing_the_same_filing_twice_gives_the_same_bytes(self):
        first_cover, first_holdings = report()
        second_cover, second_holdings = report()

        first = filing_lines(first_cover, COVER_KEY, first_holdings, TABLE_KEY)
        second = filing_lines(second_cover, COVER_KEY, second_holdings, TABLE_KEY)

        assert first == second

    def test_a_notice_is_one_line(self):
        cover = parse_cover_page((XML / f"nt-{NOTICE}-primary_doc.xml").read_bytes(), NOTICE)

        lines = rows(filing_lines(cover, "raw/k/primary_doc.xml", [], None))

        assert len(lines) == 1
        assert lines[0]["record_type"] == "cover"

    def test_one_line_per_record_each_ending_in_a_newline(self):
        cover, holdings = report()

        data = filing_lines(cover, COVER_KEY, holdings, TABLE_KEY)

        assert data.endswith(b"\n")
        assert data.count(b"\n") == 1 + len(holdings)

    def test_non_ascii_names_stay_as_written_in_utf8(self):
        cover = report()[0]
        renamed = cover.model_copy(update={"filing_manager_name": "Société Générale"})

        data = filing_lines(renamed, COVER_KEY, [], None)

        assert "Société Générale".encode() in data

    def test_holdings_need_the_key_of_their_table(self):
        cover, holdings = report()

        with pytest.raises(ValueError, match="holdings without the key of their table"):
            filing_lines(cover, COVER_KEY, holdings, None)
