"""Typed records from a 13F filing's two XML documents.

The cover page (primary_doc.xml) becomes a CoverPage; each row of the
information table becomes a Holding. Pydantic marks this boundary: the data is
filer-authored, so values are coerced and checked here and nowhere else. The
parsers match elements by local name with the namespace stripped, which rides
over the two spellings of the instruction-5 flag and over the common-namespace
address fields. Nothing here imports Airflow.
"""

import re
import xml.etree.ElementTree as ET
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from include.edgar_index import Form13F

AmendmentType = Literal["RESTATEMENT", "NEW HOLDINGS"]
ReportType = Literal["13F HOLDINGS REPORT", "13F NOTICE", "13F COMBINATION REPORT"]

_CUSIP = re.compile(r"^[0-9A-Z]{9}$")
_FIGI = re.compile(r"^[0-9A-Z]{12}$")
_SEQUENCE = re.compile(r"\d+")


class XmlParseError(ValueError):
    """The document is not the XML it should be: malformed, wrong root, no rows."""


class XmlRecordError(ValueError):
    """A record did not validate. `row_index` is set for a holding, None for a cover page."""

    def __init__(self, accession: str, row_index: int | None, error: ValidationError) -> None:
        self.accession = accession
        self.row_index = row_index
        self.error = error
        where = f"row {row_index}" if row_index is not None else "cover page"
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in error.errors()
        )
        super().__init__(f"{accession} {where}: {problems}")


class Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Address(Strict):
    street1: str
    street2: str | None = None
    city: str
    state_or_country: str
    zip_code: str


class OtherManager(Strict):
    """A manager the filer reports on behalf of, on the cover page or the summary page."""

    sequence_number: int | None = None
    cik: int | None = None
    crd_number: str | None = None
    form_13f_file_number: str | None = None
    sec_file_number: str | None = None
    name: str


class SummaryPage(Strict):
    other_included_managers_count: int = Field(ge=0)
    table_entry_total: int = Field(ge=0)
    table_value_total: int = Field(ge=0)
    is_confidential_omitted: bool | None = None
    other_managers: list[OtherManager] = []


class CoverPage(Strict):
    """primary_doc.xml, typed. The accession is supplied by the caller; the XML has none."""

    accession: str
    namespace: str | None
    schema_version: str | None
    cik: int
    submission_type: Form13F
    period_of_report: date
    report_calendar_or_quarter: date
    is_amendment: bool = False
    amendment_no: int | None = None
    amendment_type: AmendmentType | None = None
    conf_denied_expired: bool | None = None
    filing_manager_name: str
    filing_manager_address: Address
    report_type: ReportType
    form_13f_file_number: str
    crd_number: str | None = None
    sec_file_number: str | None = None
    provide_info_for_instruction5: bool | None = None
    additional_information: str | None = None
    other_managers: list[OtherManager] = []
    summary: SummaryPage | None = None

    @model_validator(mode="after")
    def _consistent(self) -> CoverPage:
        if self.is_amendment and self.amendment_type is None:
            raise ValueError("isAmendment is true but amendmentType is missing")
        if not self.is_amendment and (self.amendment_type or self.amendment_no):
            raise ValueError("amendment fields present on a filing that is not an amendment")
        if self.submission_type.is_amendment != self.is_amendment:
            raise ValueError(
                f"submissionType {self.submission_type} disagrees with isAmendment={self.is_amendment}"
            )
        if self.report_type == "13F NOTICE" and self.summary is not None:
            raise ValueError("a notice has no summary page")
        return self


class Holding(Strict):
    """One infoTable row. row_index is 1-based, for lineage back to the raw file."""

    row_index: int = Field(ge=1)
    name_of_issuer: str
    title_of_class: str
    cusip: str = Field(pattern=_CUSIP.pattern)
    figi: str | None = Field(default=None, pattern=_FIGI.pattern)
    value: int = Field(ge=0)
    shares_or_principal: int = Field(ge=0)
    shares_or_principal_type: Literal["SH", "PRN"]
    put_call: Literal["Put", "Call"] | None = None
    investment_discretion: Literal["SOLE", "DFND", "OTR"]
    other_managers: list[int] = []
    voting_sole: int = Field(ge=0)
    voting_shared: int = Field(ge=0)
    voting_none: int = Field(ge=0)

    @field_validator("cusip", "figi", mode="before")
    @classmethod
    def _upper(cls, value: object) -> object:
        """Identifiers are case-insensitive; filers type them both ways (46625h100 seen)."""
        return value.strip().upper() if isinstance(value, str) else value


class Reconciliation(Strict):
    """The filer's own totals against what the table holds. Deltas, never a raise."""

    table_entry_total: int
    holdings_count: int
    table_value_total: int
    value_sum: int

    @property
    def entries_match(self) -> bool:
        return self.table_entry_total == self.holdings_count

    @property
    def values_match(self) -> bool:
        return self.table_value_total == self.value_sum


def parse_cover_page(data: bytes, accession: str) -> CoverPage:
    root = _root(data, "edgarSubmission", accession)
    cover = _child(root, "formData", "coverPage")
    if cover is None:
        raise XmlParseError(f"{accession}: no formData/coverPage")
    manager = _child(cover, "filingManager")
    summary = _child(root, "formData", "summaryPage")
    # Some notices carry <summaryPage/> with three empty totals. Nothing is summarized
    # there, so it is treated as absent rather than as three invalid integers.
    if summary is not None and not any(
        _text(summary, name)
        for name in ("otherIncludedManagersCount", "tableEntryTotal", "tableValueTotal")
    ):
        summary = None
    fields = {
        "accession": accession,
        "namespace": _namespace(root),
        "schema_version": _text(root, "schemaVersion"),
        "cik": _text(root, "headerData", "filerInfo", "filer", "credentials", "cik"),
        "submission_type": _text(root, "headerData", "submissionType"),
        "period_of_report": _mdy(_text(root, "headerData", "filerInfo", "periodOfReport")),
        "report_calendar_or_quarter": _mdy(_text(cover, "reportCalendarOrQuarter")),
        "is_amendment": _flag(_text(cover, "isAmendment")) or False,
        "amendment_no": _text(cover, "amendmentNo"),
        "amendment_type": _text(cover, "amendmentInfo", "amendmentType"),
        "conf_denied_expired": _flag(_text(cover, "amendmentInfo", "confDeniedExpired")),
        "filing_manager_name": _text(manager, "name"),
        "filing_manager_address": {
            "street1": _text(manager, "address", "street1"),
            "street2": _text(manager, "address", "street2"),
            "city": _text(manager, "address", "city"),
            "state_or_country": _text(manager, "address", "stateOrCountry"),
            "zip_code": _text(manager, "address", "zipCode"),
        },
        "report_type": _text(cover, "reportType"),
        "form_13f_file_number": _text(cover, "form13FFileNumber"),
        "crd_number": _text(cover, "crdNumber"),
        "sec_file_number": _text(cover, "secFileNumber"),
        # Two spellings in the wild: the schema says ...Instruction5, many filers omit the 5.
        "provide_info_for_instruction5": _yes_no(
            _text(cover, "provideInfoForInstruction5") or _text(cover, "provideInfoForInstruction")
        ),
        "additional_information": _text(cover, "additionalInformation"),
        "other_managers": [
            _other_manager(m) for m in _children(cover, "otherManagersInfo", "otherManager")
        ],
        "summary": None
        if summary is None
        else {
            "other_included_managers_count": _text(summary, "otherIncludedManagersCount"),
            "table_entry_total": _text(summary, "tableEntryTotal"),
            "table_value_total": _text(summary, "tableValueTotal"),
            "is_confidential_omitted": _flag(_text(summary, "isConfidentialOmitted")),
            "other_managers": [
                _other_manager(_child(m2, "otherManager"), _text(m2, "sequenceNumber"))
                for m2 in _children(summary, "otherManagers2Info", "otherManager2")
            ],
        },
    }
    try:
        return CoverPage.model_validate(fields)
    except ValidationError as exc:
        raise XmlRecordError(accession, None, exc) from exc


def parse_information_table(data: bytes, accession: str) -> list[Holding]:
    """Every infoTable row, typed, in file order. Raises on the first bad row."""
    root = _root(data, "informationTable", accession)
    rows = _children(root, "infoTable")
    holdings = []
    for index, row in enumerate(rows, start=1):
        fields = {
            "row_index": index,
            "name_of_issuer": _text(row, "nameOfIssuer"),
            "title_of_class": _text(row, "titleOfClass"),
            "cusip": _text(row, "cusip"),
            "figi": _text(row, "figi"),
            "value": _text(row, "value"),
            "shares_or_principal": _text(row, "shrsOrPrnAmt", "sshPrnamt"),
            "shares_or_principal_type": _text(row, "shrsOrPrnAmt", "sshPrnamtType"),
            "put_call": _text(row, "putCall"),
            "investment_discretion": _text(row, "investmentDiscretion"),
            "other_managers": _sequence_numbers(_text(row, "otherManager")),
            "voting_sole": _text(row, "votingAuthority", "Sole"),
            "voting_shared": _text(row, "votingAuthority", "Shared"),
            "voting_none": _text(row, "votingAuthority", "None"),
        }
        try:
            holdings.append(Holding.model_validate(fields))
        except ValidationError as exc:
            raise XmlRecordError(accession, index, exc) from exc
    return holdings


def reconcile(cover: CoverPage, holdings: list[Holding]) -> Reconciliation | None:
    """Compare the cover page's totals with the table. None for a filing without a summary."""
    if cover.summary is None:
        return None
    return Reconciliation(
        table_entry_total=cover.summary.table_entry_total,
        holdings_count=len(holdings),
        table_value_total=cover.summary.table_value_total,
        value_sum=sum(h.value for h in holdings),
    )


# --- element access by local name -------------------------------------------------


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _namespace(element: ET.Element) -> str | None:
    return element.tag[1:].split("}", 1)[0] if element.tag.startswith("{") else None


def _root(data: bytes, expected: str, accession: str) -> ET.Element:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise XmlParseError(f"{accession}: not well-formed XML ({exc})") from exc
    if _local(root.tag) != expected:
        raise XmlParseError(f"{accession}: root is <{_local(root.tag)}>, expected <{expected}>")
    return root


def _child(element: ET.Element | None, *path: str) -> ET.Element | None:
    for name in path:
        if element is None:
            return None
        element = next((c for c in element if _local(c.tag) == name), None)
    return element


def _children(element: ET.Element | None, *path: str) -> list[ET.Element]:
    parent = _child(element, *path[:-1]) if len(path) > 1 else element
    if parent is None:
        return []
    return [c for c in parent if _local(c.tag) == path[-1]]


def _text(element: ET.Element | None, *path: str) -> str | None:
    found = _child(element, *path)
    if found is None or found.text is None:
        return None
    text = found.text.strip()
    return text or None


def _mdy(text: str | None) -> date | None:
    """EDGAR writes dates as MM-DD-YYYY."""
    if text is None:
        return None
    month, day, year = text.split("-")
    return date(int(year), int(month), int(day))


def _flag(text: str | None) -> bool | None:
    if text is None:
        return None
    return text.lower() in ("true", "1", "y", "yes")


def _yes_no(text: str | None) -> bool | None:
    if text is None:
        return None
    return text.upper() == "Y"


def _sequence_numbers(text: str | None) -> list[int]:
    """otherManager is free text such as "1", "1, 2" or "01 02"."""
    return [int(n) for n in _SEQUENCE.findall(text)] if text else []


def _other_manager(element: ET.Element | None, sequence_number: str | None = None) -> dict:
    return {
        "sequence_number": sequence_number,
        "cik": _text(element, "cik"),
        "crd_number": _text(element, "crdNumber"),
        "form_13f_file_number": _text(element, "form13FFileNumber"),
        "sec_file_number": _text(element, "secFileNumber"),
        "name": _text(element, "name"),
    }
