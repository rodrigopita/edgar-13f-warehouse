import re
from datetime import date
from pathlib import Path

import pytest

from include.edgar_xml import (
    CoverPage,
    Holding,
    XmlParseError,
    XmlRecordError,
    parse_cover_page,
    parse_information_table,
    reconcile,
)

XML = Path(__file__).resolve().parents[1] / "fixtures" / "edgar" / "xml"


def fixture(name: str) -> bytes:
    return (XML / name).read_bytes()


def accession_of(name: str) -> str:
    return re.search(r"\d{10}-\d{2}-\d{6}", name).group()


def cover(name: str) -> CoverPage:
    return parse_cover_page(fixture(name), accession_of(name))


def table(name: str) -> list[Holding]:
    return parse_information_table(fixture(name), accession_of(name))


COVER_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<edgarSubmission xmlns="http://www.sec.gov/edgar/thirteenffiler" xmlns:ns1="http://www.sec.gov/edgar/common">
  <schemaVersion>X0202</schemaVersion>
  <headerData>
    <submissionType>{submission_type}</submissionType>
    <filerInfo>
      <filer><credentials><cik>0000000007</cik></credentials></filer>
      <periodOfReport>06-30-2026</periodOfReport>
    </filerInfo>
  </headerData>
  <formData>
    <coverPage>
      <reportCalendarOrQuarter>06-30-2026</reportCalendarOrQuarter>
      {amendment}
      <filingManager>
        <name>BUILT FIXTURE LP</name>
        <address><ns1:street1>1 MAIN</ns1:street1><ns1:city>X</ns1:city>
          <ns1:stateOrCountry>NY</ns1:stateOrCountry><ns1:zipCode>10001</ns1:zipCode></address>
      </filingManager>
      <reportType>{report_type}</reportType>
      <form13FFileNumber>028-00001</form13FFileNumber>
      <provideInfoForInstruction5>N</provideInfoForInstruction5>
    </coverPage>
    {summary}
  </formData>
</edgarSubmission>
"""
SUMMARY = (
    "<summaryPage><otherIncludedManagersCount>0</otherIncludedManagersCount>"
    "<tableEntryTotal>{entries}</tableEntryTotal><tableValueTotal>{value}</tableValueTotal></summaryPage>"
)


def built_cover(
    submission_type="13F-HR", report_type="13F HOLDINGS REPORT", amendment="", summary=None
) -> bytes:
    summary = SUMMARY.format(entries=2, value=300) if summary is None else summary
    return COVER_TEMPLATE.format(
        submission_type=submission_type,
        report_type=report_type,
        amendment=amendment,
        summary=summary,
    ).encode()


ROW_TEMPLATE = """<infoTable>
  <nameOfIssuer>{issuer}</nameOfIssuer><titleOfClass>COM</titleOfClass>
  <cusip>{cusip}</cusip>{figi}<value>{value}</value>
  <shrsOrPrnAmt><sshPrnamt>{shares}</sshPrnamt><sshPrnamtType>{kind}</sshPrnamtType></shrsOrPrnAmt>
  {put_call}<investmentDiscretion>SOLE</investmentDiscretion>{other}
  <votingAuthority><Sole>{shares}</Sole><Shared>0</Shared><None>0</None></votingAuthority>
</infoTable>"""


def built_row(
    issuer="ACME CORP",
    cusip="000000000",
    value="100",
    shares="10",
    kind="SH",
    put_call="",
    other="",
    figi="",
) -> str:
    return ROW_TEMPLATE.format(
        issuer=issuer,
        cusip=cusip,
        figi=figi,
        value=value,
        shares=shares,
        kind=kind,
        put_call=put_call,
        other=other,
    )


def built_table(*rows: str) -> bytes:
    body = "".join(rows)
    return (
        '<?xml version="1.0"?><informationTable '
        'xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">'
        f"{body}</informationTable>"
    ).encode()


class TestRealCoverPages:
    def test_holdings_report_fields(self):
        c = cover("hr-0001214659-26-011275-primary_doc.xml")

        assert c.accession == "0001214659-26-011275"
        assert c.cik == 2104502
        assert c.submission_type == "13F-HR"
        assert c.period_of_report == date(2025, 9, 30)  # a late filer: filed in 2026
        assert c.report_calendar_or_quarter == date(2025, 9, 30)
        assert c.is_amendment is False and c.amendment_type is None
        assert c.filing_manager_name.startswith("Davis Wealth Advisors")
        assert c.filing_manager_address.state_or_country == "NH"
        assert c.report_type == "13F HOLDINGS REPORT"
        assert c.form_13f_file_number == "028-26531"
        assert c.provide_info_for_instruction5 is False
        assert c.summary.table_entry_total == 91
        assert c.summary.table_value_total == 111375990
        assert c.summary.other_managers[0].name == "JPMORGAN CHASE & CO"
        assert c.summary.other_managers[0].sequence_number == 1
        assert c.namespace == "http://www.sec.gov/edgar/thirteenffiler"

    def test_restatement_amendment(self):
        c = cover("hr_a_restatement-0001908612-26-000004-primary_doc.xml")

        assert c.submission_type == "13F-HR/A"
        assert c.is_amendment is True
        assert c.amendment_no == 1
        assert c.amendment_type == "RESTATEMENT"

    def test_new_holdings_amendment(self):
        c = cover("hr_a_new_holdings-0001259261-26-000014-primary_doc.xml")

        assert c.is_amendment is True
        assert c.amendment_type == "NEW HOLDINGS"

    def test_notice_has_no_summary(self):
        c = cover("nt-0001451086-26-000003-primary_doc.xml")

        assert c.submission_type == "13F-NT"
        assert c.report_type == "13F NOTICE"
        assert c.summary is None
        assert len(c.other_managers) >= 1

    def test_notice_amendment(self):
        c = cover("nt_a-0001193125-26-379727-primary_doc.xml")

        assert c.submission_type == "13F-NT/A" and c.is_amendment is True

    def test_combination_report(self):
        c = cover("combination-0001990467-26-000004-primary_doc.xml")

        assert c.report_type == "13F COMBINATION REPORT"
        assert len(c.other_managers) == 2

    def test_confidential_omitted_flag(self):
        c = cover("confidential_omitted-0000897423-26-000120-primary_doc.xml")

        assert c.summary.is_confidential_omitted is True

    def test_old_spelling_of_the_instruction_flag_maps_to_the_same_field(self):
        old = cover("instruction_old_spelling-0001214659-26-011668-primary_doc.xml")
        new = cover("hr-0001214659-26-011275-primary_doc.xml")

        assert old.provide_info_for_instruction5 is not None
        assert new.provide_info_for_instruction5 is not None


class TestRealTables:
    def test_rows_are_typed_and_indexed(self):
        rows = table("hr-0001214659-26-011275-infotable.xml")

        assert len(rows) == 91
        first = rows[0]
        assert first.row_index == 1
        assert first.name_of_issuer == "AB ACTIVE ETFS INC"
        assert first.cusip == "00039J103"
        assert first.value == 758909
        assert first.shares_or_principal == 14976
        assert first.shares_or_principal_type == "SH"
        assert first.put_call is None
        assert first.investment_discretion == "SOLE"
        assert first.voting_sole == 14976 and first.voting_shared == 0 and first.voting_none == 0
        assert [r.row_index for r in rows] == list(range(1, 92))

    def test_lowercase_cusip_in_a_real_filing_is_normalized(self):
        rows = table("hr_a_restatement-0001908612-26-000004-infotable.xml")

        assert rows[61].cusip == "46625H100"

    @pytest.mark.parametrize(
        "name",
        [
            "hr-0001214659-26-011275",
            "hr_a_restatement-0001908612-26-000004",
            "hr_a_new_holdings-0001259261-26-000014",
        ],
    )
    def test_real_filings_reconcile_with_their_own_totals(self, name):
        c = cover(f"{name}-primary_doc.xml")
        rows = table(f"{name}-infotable.xml")

        r = reconcile(c, rows)

        assert r.entries_match and r.values_match
        assert r.holdings_count == len(rows) == c.summary.table_entry_total


class TestBuiltCoverPages:
    def test_amendment_without_a_type_is_rejected(self):
        data = built_cover("13F-HR/A", amendment="<isAmendment>true</isAmendment>")

        with pytest.raises(XmlRecordError, match="amendmentType is missing"):
            parse_cover_page(data, "0000000007-26-000001")

    def test_amendment_fields_on_an_original_are_rejected(self):
        data = built_cover(
            "13F-HR",
            amendment="<isAmendment>false</isAmendment><amendmentNo>1</amendmentNo>"
            "<amendmentInfo><amendmentType>RESTATEMENT</amendmentType></amendmentInfo>",
        )

        with pytest.raises(XmlRecordError, match="not an amendment"):
            parse_cover_page(data, "0000000007-26-000001")

    def test_submission_type_must_agree_with_the_flag(self):
        data = built_cover("13F-HR/A", amendment="<isAmendment>false</isAmendment>")

        with pytest.raises(XmlRecordError, match="disagrees with isAmendment"):
            parse_cover_page(data, "0000000007-26-000001")

    def test_unknown_amendment_type_is_rejected(self):
        data = built_cover(
            "13F-HR/A",
            amendment="<isAmendment>true</isAmendment>"
            "<amendmentInfo><amendmentType>CORRECTION</amendmentType></amendmentInfo>",
        )

        with pytest.raises(XmlRecordError, match="amendment_type"):
            parse_cover_page(data, "0000000007-26-000001")

    def test_unknown_report_type_is_rejected(self):
        with pytest.raises(XmlRecordError, match="report_type"):
            parse_cover_page(built_cover(report_type="13F SOMETHING"), "0000000007-26-000001")

    def test_absent_isamendment_means_false(self):
        c = parse_cover_page(built_cover(amendment=""), "0000000007-26-000001")

        assert c.is_amendment is False

    def test_empty_summary_page_counts_as_absent(self):
        empty = "<summaryPage><otherIncludedManagersCount/><tableEntryTotal/><tableValueTotal/></summaryPage>"
        c = parse_cover_page(
            built_cover("13F-NT", "13F NOTICE", summary=empty), "0000000007-26-000001"
        )

        assert c.summary is None

    def test_notice_with_a_real_summary_is_rejected(self):
        with pytest.raises(XmlRecordError, match="notice has no summary"):
            parse_cover_page(built_cover("13F-NT", "13F NOTICE"), "0000000007-26-000001")

    def test_truncated_xml_is_a_parse_error(self):
        with pytest.raises(XmlParseError, match="not well-formed"):
            parse_cover_page(built_cover()[:300], "0000000007-26-000001")

    def test_wrong_root_is_a_parse_error(self):
        with pytest.raises(XmlParseError, match="root is <html>"):
            parse_cover_page(b"<html>Undeclared Automated Tool</html>", "0000000007-26-000001")

    def test_missing_cover_page_is_a_parse_error(self):
        data = b'<edgarSubmission xmlns="x"><headerData/><formData/></edgarSubmission>'

        with pytest.raises(XmlParseError, match="no formData/coverPage"):
            parse_cover_page(data, "0000000007-26-000001")


class TestBuiltTables:
    def test_optional_fields_and_free_text_sequence_numbers(self):
        rows = parse_information_table(
            built_table(
                built_row(
                    put_call="<putCall>Put</putCall>", other="<otherManager>1, 2</otherManager>"
                ),
                built_row(
                    kind="PRN",
                    figi="<figi>BBG000BLNNH6</figi>",
                    other="<otherManager>01 03</otherManager>",
                ),
            ),
            "0000000007-26-000001",
        )

        assert rows[0].put_call == "Put" and rows[0].other_managers == [1, 2]
        assert rows[1].shares_or_principal_type == "PRN"
        assert rows[1].figi == "BBG000BLNNH6" and rows[1].other_managers == [1, 3]

    def test_a_bad_row_names_its_index_and_field(self):
        data = built_table(built_row(), built_row(value="12.5"), built_row())

        with pytest.raises(XmlRecordError, match="row 2: value") as excinfo:
            parse_information_table(data, "0000000007-26-000001")

        assert excinfo.value.row_index == 2
        assert excinfo.value.accession == "0000000007-26-000001"

    @pytest.mark.parametrize(
        ("row", "field"),
        [
            pytest.param(built_row(cusip="12345678"), "cusip", id="cusip-too-short"),
            pytest.param(built_row(cusip="1234567-9"), "cusip", id="cusip-bad-character"),
            pytest.param(built_row(value="-5"), "value", id="negative-value"),
            pytest.param(built_row(shares="ten"), "shares_or_principal", id="non-numeric-shares"),
            pytest.param(
                built_row(kind="UNITS"), "shares_or_principal_type", id="unknown-amount-type"
            ),
            pytest.param(
                built_row(put_call="<putCall>Short</putCall>"), "put_call", id="unknown-put-call"
            ),
            pytest.param(built_row(figi="<figi>TOOSHORT</figi>"), "figi", id="figi-not-twelve"),
            pytest.param(
                built_row().replace("<cusip>000000000</cusip>", ""), "cusip", id="missing-cusip"
            ),
        ],
    )
    def test_malformed_rows_are_rejected_with_the_field_named(self, row, field):
        with pytest.raises(XmlRecordError, match=f"row 1: {field}"):
            parse_information_table(built_table(row), "0000000007-26-000001")

    def test_empty_table_yields_no_rows(self):
        assert parse_information_table(built_table(), "0000000007-26-000001") == []

    def test_wrong_root_is_a_parse_error(self):
        with pytest.raises(XmlParseError, match="expected <informationTable>"):
            parse_information_table(built_cover(), "0000000007-26-000001")


class TestReconcile:
    def test_reports_deltas_without_raising(self):
        c = parse_cover_page(built_cover(summary=SUMMARY.format(entries=3, value=999)), "a")
        rows = parse_information_table(
            built_table(built_row(value="100"), built_row(value="200")), "a"
        )

        r = reconcile(c, rows)

        assert not r.entries_match and r.table_entry_total == 3 and r.holdings_count == 2
        assert not r.values_match and r.table_value_total == 999 and r.value_sum == 300

    def test_none_for_a_filing_without_a_summary(self):
        c = cover("nt-0001451086-26-000003-primary_doc.xml")

        assert reconcile(c, []) is None
