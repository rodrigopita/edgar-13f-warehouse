from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from include.edgar_index import (
    FORM_TYPES_13F,
    Form13F,
    IndexEntry,
    IndexParseError,
    parse_form_index,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "edgar"

# The real header, shortened. The dashed line is what the parser looks for.
HEADER = """Description:           Daily Index of EDGAR Dissemination Feed by Form Type
Last Data Received:    Sep 22, 2026
Comments:              webmaster@sec.gov

Form Type   Company Name                                                  CIK
      Date Filed  File Name
---------------------------------------------------------------------------------------------
"""


def row(form_type: str, company: str, cik: str, filed: str, path: str) -> str:
    return f"{form_type:<17}{company:<62}{cik:<12}{filed:<12}{path}\n"


@pytest.fixture(scope="module")
def real_index() -> bytes:
    return (FIXTURES / "form.20260922.idx").read_bytes()


class TestForm13F:
    def test_default_filter_is_the_four_members(self):
        assert FORM_TYPES_13F == {"13F-HR", "13F-HR/A", "13F-NT", "13F-NT/A"}
        assert "13F-HR" in Form13F
        assert "10-K" not in Form13F

    def test_amendments_are_the_slash_a_members(self):
        assert Form13F("13F-HR/A").is_amendment
        assert Form13F.NT_A.is_amendment
        assert not Form13F.HR.is_amendment
        assert not Form13F.NT.is_amendment

    def test_a_parsed_form_type_compares_with_the_enum(self, real_index):
        entry = parse_form_index(real_index)[0]

        assert entry.form_type == Form13F.HR
        assert not Form13F(entry.form_type).is_amendment


class TestRealFile:
    def test_yields_the_13f_rows_only(self, real_index):
        entries = parse_form_index(real_index)

        assert len(entries) == 20
        assert Counter(e.form_type for e in entries) == {"13F-HR": 14, "13F-HR/A": 6}
        assert {e.form_type for e in entries} <= FORM_TYPES_13F

    def test_first_row_is_read_field_by_field(self, real_index):
        first = parse_form_index(real_index)[0]

        assert first == IndexEntry(
            form_type="13F-HR",
            company_name="Andra AP-fonden",
            cik=1535452,
            filed=date(2026, 9, 22),
            accession="0001535452-26-000006",
            path="edgar/data/1535452/0001535452-26-000006.txt",
        )
        assert first.filing_folder == "/Archives/edgar/data/1535452/000153545226000006/"

    def test_an_amendment_is_kept_with_its_form_type(self, real_index):
        amendments = [e for e in parse_form_index(real_index) if e.cik == 93751]

        assert len(amendments) == 1
        assert amendments[0].form_type == "13F-HR/A"
        assert amendments[0].company_name == "STATE STREET CORP"
        assert amendments[0].accession == "0000093751-26-000583"

    def test_unfiltered_parse_reads_every_row(self, real_index):
        everything = parse_form_index(real_index, form_types=None)

        assert len(everything) == 3407
        # A daily index is by dissemination day. Most rows carry that day's filing
        # date, but 148 here are older filings the SEC released on the 22nd, some
        # from 2024. The row's own date is the truth; the file's date is not.
        dates = Counter(e.filed for e in everything)
        assert dates[date(2026, 9, 22)] == 3259
        assert min(dates) == date(2024, 7, 30)

    def test_every_13f_row_in_this_file_was_filed_that_day(self, real_index):
        assert {e.filed for e in parse_form_index(real_index)} == {date(2026, 9, 22)}

    def test_str_and_bytes_parse_the_same(self, real_index):
        assert parse_form_index(real_index) == parse_form_index(real_index.decode("latin-1"))


class TestBuiltRows:
    def test_filter_keeps_notices_and_drops_other_forms(self):
        text = HEADER + "".join(
            [
                row("10-K", "SOME CORP", "1", "20260922", "edgar/data/1/0000000001-26-000001.txt"),
                row(
                    "13F-NT", "NOTICE LLC", "2", "20260922", "edgar/data/2/0000000002-26-000001.txt"
                ),
                row(
                    "13F-NT/A",
                    "NOTICE LLC",
                    "2",
                    "20260922",
                    "edgar/data/2/0000000002-26-000002.txt",
                ),
                row(
                    "13F-HR", "HOLDER LP", "3", "20260922", "edgar/data/3/0000000003-26-000001.txt"
                ),
            ]
        )

        kept = [e.form_type for e in parse_form_index(text)]

        assert kept == ["13F-NT", "13F-NT/A", "13F-HR"]

    def test_company_name_keeps_its_inner_spacing(self):
        text = HEADER + row(
            "13F-HR",
            "ACME  HOLDINGS, L.P.",
            "4",
            "20260922",
            "edgar/data/4/0000000004-26-000001.txt",
        )

        assert parse_form_index(text)[0].company_name == "ACME  HOLDINGS, L.P."

    def test_header_only_yields_nothing(self):
        assert parse_form_index(HEADER) == []

    def test_blank_lines_between_rows_are_ignored(self):
        text = (
            HEADER
            + "\n"
            + row("13F-HR", "HOLDER LP", "3", "20260922", "edgar/data/3/0000000003-26-000001.txt")
            + "\n\n"
        )

        assert len(parse_form_index(text)) == 1


class TestMalformed:
    def test_row_without_a_date_names_its_line(self):
        text = (
            HEADER
            + "13F-HR           HOLDER LP        3           edgar/data/3/0000000003-26-000001.txt\n"
        )

        with pytest.raises(IndexParseError, match="line 8 does not look like an index row"):
            parse_form_index(text)

    def test_impossible_date_is_rejected(self):
        text = HEADER + row(
            "13F-HR",
            "HOLDER LP",
            "3",
            "20261340",
            "edgar/data/3/0000000003-26-000001.txt",
        )

        with pytest.raises(IndexParseError, match="line 8: bad filing date '20261340'"):
            parse_form_index(text)

    def test_file_name_without_an_accession_is_rejected(self):
        text = HEADER + row("13F-HR", "HOLDER LP", "3", "20260922", "edgar/data/3/index.txt")

        with pytest.raises(IndexParseError, match="carries no accession number"):
            parse_form_index(text)

    def test_missing_separator_is_not_an_index_file(self):
        with pytest.raises(IndexParseError, match="no dashed separator"):
            parse_form_index(
                "<html>Your Request Originates from an Undeclared Automated Tool</html>"
            )

    def test_bad_row_in_an_unwanted_form_type_still_fails(self):
        # The row is malformed before the filter can drop it: format problems are
        # never hidden by the form-type filter.
        text = HEADER + "10-K   SOME CORP   1   notadate   edgar/data/1/0000000001-26-000001.txt\n"

        with pytest.raises(IndexParseError):
            parse_form_index(text)
