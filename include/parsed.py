"""One filing as JSON lines, the shape Snowpipe loads into RAW.PARSED_FILINGS.

The cover page comes first, then each holding in table order. Every line is an
envelope, {accession, record, record_type, source_key}, so the filer's data
stays apart from the pipeline's fields and each row names the XML it was
parsed from. The bytes are deterministic, sorted keys and no timestamps, so a
rerun writes the same file. Nothing here touches S3 or imports Airflow.
"""

import json

from include.edgar_xml import CoverPage, Holding


def filing_lines(
    cover: CoverPage, cover_key: str, holdings: list[Holding], table_key: str | None
) -> bytes:
    """The JSON-lines file for one filing: the cover page, then one line per holding."""
    if holdings and table_key is None:
        raise ValueError(f"{cover.accession}: holdings without the key of their table")
    lines = [_line(cover.accession, "cover", cover_key, cover.model_dump(mode="json"))]
    lines.extend(
        _line(cover.accession, "holding", table_key, h.model_dump(mode="json")) for h in holdings
    )
    return "".join(lines).encode()


def _line(accession: str, record_type: str, source_key: str | None, record: dict) -> str:
    envelope = {
        "accession": accession,
        "record": record,
        "record_type": record_type,
        "source_key": source_key,
    }
    # ensure_ascii=False keeps filer names as written; the file is UTF-8.
    return json.dumps(envelope, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
