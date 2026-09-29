"""One filing's documents on sec.gov: which files exist and their raw bytes.

A filing folder always holds `primary_doc.xml`, the cover page. A holdings
report (13F-HR, 13F-HR/A) also holds one information table whose file name the
filer chooses; a notice (13F-NT, 13F-NT/A) holds none. The folder's index.json
says what is there, so nothing is guessed. Bytes are returned unparsed: raw
lands in S3 before any parser runs.
"""

import json
from dataclasses import dataclass

from include.edgar_client import EdgarClient
from include.edgar_index import Form13F, IndexEntry

PRIMARY_DOC = "primary_doc.xml"


class FilingLayoutError(ValueError):
    """The filing folder does not hold the documents its form type implies."""


@dataclass(frozen=True)
class FilingDocuments:
    """File names in one filing folder, as its index.json lists them."""

    accession: str
    folder: str
    primary_doc: str
    info_table: str | None

    @property
    def is_notice(self) -> bool:
        return self.info_table is None


@dataclass(frozen=True)
class FilingBytes:
    """A filing's documents, fetched and unparsed."""

    entry: IndexEntry
    documents: FilingDocuments
    primary_doc: bytes
    info_table: bytes | None


def list_filing_documents(client: EdgarClient, entry: IndexEntry) -> FilingDocuments:
    """Read the folder's index.json and name the cover page and the information table.

    Raises FilingLayoutError when the folder disagrees with the form type: a
    holdings report without exactly one information table, or a notice with one.
    Raises ValueError for an entry that is not a 13F form.
    """
    form = Form13F(entry.form_type)
    names = _document_names(client, entry)
    if PRIMARY_DOC not in names:
        raise FilingLayoutError(f"{entry.accession}: no {PRIMARY_DOC} in {sorted(names)}")
    tables = sorted(n for n in names if n.lower().endswith(".xml") and n != PRIMARY_DOC)
    expects_table = form in (Form13F.HR, Form13F.HR_A)
    if expects_table and len(tables) != 1:
        raise FilingLayoutError(
            f"{entry.accession} ({form}): expected one information table, found {tables}"
        )
    if not expects_table and tables:
        raise FilingLayoutError(f"{entry.accession} ({form}): a notice with XML tables {tables}")
    return FilingDocuments(
        accession=entry.accession,
        folder=entry.filing_folder,
        primary_doc=PRIMARY_DOC,
        info_table=tables[0] if expects_table else None,
    )


def fetch_filing(client: EdgarClient, entry: IndexEntry) -> FilingBytes:
    """Fetch the cover page and, for a holdings report, the information table.

    Two requests for a notice, three for a holdings report: the listing first.
    """
    documents = list_filing_documents(client, entry)
    primary_doc = client.get(f"{documents.folder}{documents.primary_doc}")
    info_table = None
    if documents.info_table is not None:
        info_table = client.get(f"{documents.folder}{documents.info_table}")
    return FilingBytes(
        entry=entry, documents=documents, primary_doc=primary_doc, info_table=info_table
    )


def _document_names(client: EdgarClient, entry: IndexEntry) -> set[str]:
    listing = client.get(f"{entry.filing_folder}index.json")
    try:
        items = json.loads(listing)["directory"]["item"]
        return {item["name"] for item in items}
    except (ValueError, KeyError, TypeError) as exc:
        raise FilingLayoutError(
            f"{entry.accession}: folder listing is not the expected index.json shape"
        ) from exc
