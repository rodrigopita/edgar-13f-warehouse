"""The SEC 13F data sets into Snowflake: stage every zip, then COPY every table.

A zip lands in S3 as fetched, under raw/sec/datasets/, before anything reads
it. Each of its seven tables is then written as gzip to
extracted/sec/datasets/table=<TABLE>/<data set>.tsv.gz, header and all, with
no name and no time in the gzip header, so a rerun writes the same bytes. Rows
are counted on the way and kept as object metadata; COPY reports what it
loaded, and the audit record sets the two side by side. Nothing here imports
Airflow.
"""

import gzip
import io
import zipfile
from collections import Counter
from pathlib import PurePosixPath
from typing import BinaryIO

from include.edgar_client import EdgarClient
from include.landing import EXTRACTED_SUFFIX, LandingZone, dataset_zip_key, extracted_key
from include.sec_datasets import Dataset, fetch
from include.sec_profile import TABLES

ZIP_SUFFIX = "_form13f.zip"
STAGE = "edgar_13f.raw.datasets_stage"
# Each table's columns, its header in the data sets, the same in all 54 zips
# and in include/sql/04_raw_datasets.sql.
COLUMNS = {
    "SUBMISSION": ("accession_number", "filing_date", "submissiontype", "cik", "periodofreport"),
    "COVERPAGE": (
        "accession_number",
        "reportcalendarorquarter",
        "isamendment",
        "amendmentno",
        "amendmenttype",
        "confdeniedexpired",
        "datedeniedexpired",
        "datereported",
        "reasonfornonconfidentiality",
        "filingmanager_name",
        "filingmanager_street1",
        "filingmanager_street2",
        "filingmanager_city",
        "filingmanager_stateorcountry",
        "filingmanager_zipcode",
        "reporttype",
        "form13ffilenumber",
        "crdnumber",
        "secfilenumber",
        "provideinfoforinstruction5",
        "additionalinformation",
    ),
    "INFOTABLE": (
        "accession_number",
        "infotable_sk",
        "nameofissuer",
        "titleofclass",
        "cusip",
        "figi",
        "value",
        "sshprnamt",
        "sshprnamttype",
        "putcall",
        "investmentdiscretion",
        "othermanager",
        "voting_auth_sole",
        "voting_auth_shared",
        "voting_auth_none",
    ),
    "OTHERMANAGER": (
        "accession_number",
        "othermanager_sk",
        "cik",
        "form13ffilenumber",
        "crdnumber",
        "secfilenumber",
        "name",
    ),
    "OTHERMANAGER2": (
        "accession_number",
        "sequencenumber",
        "cik",
        "form13ffilenumber",
        "crdnumber",
        "secfilenumber",
        "name",
    ),
    "SIGNATURE": (
        "accession_number",
        "name",
        "title",
        "phone",
        "signature",
        "city",
        "stateorcountry",
        "signaturedate",
    ),
    "SUMMARYPAGE": (
        "accession_number",
        "otherincludedmanagerscount",
        "tableentrytotal",
        "tablevaluetotal",
        "isconfidentialomitted",
    ),
}
SOURCE_COLUMNS = ("source_file", "source_row", "source_content_key", "source_last_modified")
_METADATA = (
    "metadata$filename",
    "metadata$file_row_number",
    "metadata$file_content_key",
    "metadata$file_last_modified",
)
# zlib level 6, the gzip command's default: as deterministic as 9 and much
# quicker over 12.6 GB of text.
COMPRESS_LEVEL = 6
CHUNK = 1 << 20


class DatasetLayoutError(ValueError):
    """A zip lacks one of the seven tables, or a table's header is not the expected one."""


def dataset_id(zip_name: str) -> str:
    """2013q2 for 2013q2_form13f.zip: the name a zip's extracted files carry."""
    return zip_name.removesuffix(ZIP_SUFFIX)


def stage_dataset(client: EdgarClient, zone: LandingZone, dataset: Dataset) -> dict:
    """Land one zip and its seven tables as gzip, and report the rows each holds.

    Idempotent (safe to rerun: a second run of the same input changes nothing).
    A data set whose seven files are all in S3 costs seven HEADs and no download;
    the row counts come back from the files' metadata. A zip already landed is
    read from S3 rather than fetched again.
    """
    set_id = dataset_id(dataset.name)
    found = {table: zone.metadata(extracted_key(table, set_id)) for table in TABLES}
    if all(meta is not None for meta in found.values()):
        rows = {table: int(meta["rows"]) for table, meta in found.items()}
        return {"dataset": dataset.name, "source": "extracted", "rows": rows}
    if zone.exists(dataset_zip_key(dataset.name)):
        data, source = zone.read(dataset_zip_key(dataset.name)), "s3"
    else:
        data, source = fetch(client, dataset), "sec"
        zone.land_dataset_zip(dataset.name, data)
    rows = {}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        # One zip, 01jun2025-31aug2025, nests its tables in a folder: match by base name.
        members = {PurePosixPath(i.filename).name: i for i in archive.infolist() if not i.is_dir()}
        for table in TABLES:
            member = members.get(f"{table}.tsv")
            if member is None:
                raise DatasetLayoutError(f"{dataset.name}: no {table}.tsv")
            with archive.open(member) as stream:
                compressed, count = gzip_table(stream, table, dataset.name)
            zone.land_extracted(table, set_id, compressed, count)
            rows[table] = count
    return {"dataset": dataset.name, "source": source, "rows": rows}


def gzip_table(stream: BinaryIO, table: str, name: str) -> tuple[bytes, int]:
    """One table as deterministic gzip bytes and its data rows, the header not counted.

    The header must be the one the raw table's columns follow, or COPY would put
    values under the wrong names.
    """
    header = stream.readline()
    expected = "\t".join(column.upper() for column in COLUMNS[table]).encode()
    if header.rstrip(b"\n") != expected:
        raise DatasetLayoutError(f"{name} {table}: header {header[:120]!r} is not {expected!r}")
    buffer = io.BytesIO()
    newlines = 0
    last = b"\n"
    with gzip.GzipFile(
        filename="", mode="wb", fileobj=buffer, compresslevel=COMPRESS_LEVEL, mtime=0
    ) as out:
        out.write(header)
        while chunk := stream.read(CHUNK):
            out.write(chunk)
            newlines += chunk.count(b"\n")
            last = chunk[-1:]
    # A last row without its newline is still a row.
    return buffer.getvalue(), newlines + (last != b"\n")


def copy_statement(table: str) -> str:
    """COPY every extracted file of one table, with the source columns from METADATA$.

    The stage carries the TSV format. ON_ERROR = ABORT_STATEMENT, the bulk
    default, written out: one bad row loads nothing, so a table is whole or
    absent. COPY skips a file it loaded in the last 64 days.
    """
    columns = ", ".join(COLUMNS[table] + SOURCE_COLUMNS)
    positions = ", ".join(f"${i}" for i in range(1, len(COLUMNS[table]) + 1))
    return (
        f"copy into edgar_13f.raw.dataset_{table.lower()} ({columns})\n"
        f"from (\n"
        f"    select {positions}, {', '.join(_METADATA)}\n"
        f"    from @{STAGE}/table={table}/\n"
        f")\n"
        f"on_error = abort_statement"
    )


def copy_results(names: list[str], rows: list[tuple]) -> list[dict]:
    """COPY's output as one dict per file, keys in lower case.

    When every file was loaded before, COPY answers with a single status row and
    no file column: that is no file loaded, an empty list.
    """
    keys = [name.lower() for name in names]
    if "file" not in keys:
        return []
    return [dict(zip(keys, row, strict=True)) for row in rows]


def audit_record(staged: list[dict], copies: list[dict], run_id: str, recorded_at: str) -> dict:
    """One backfill run's numbers: rows each file held beside rows Snowflake loaded.

    `copies` holds one {"table", "results"} per COPY. A file loaded by an earlier
    run is absent from this run's results; its rows are not compared again.
    """
    loaded: dict[tuple[str, str], dict] = {}
    for copy in copies:
        for result in copy["results"]:
            set_id = PurePosixPath(result["file"]).name.removesuffix(EXTRACTED_SUFFIX)
            loaded[(copy["table"], set_id)] = result
    mismatches = []
    for stage in staged:
        set_id = dataset_id(stage["dataset"])
        for table, extracted in stage["rows"].items():
            result = loaded.get((table, set_id))
            if result is not None and result["rows_loaded"] != extracted:
                mismatches.append(
                    {
                        "dataset": stage["dataset"],
                        "table": table,
                        "extracted": extracted,
                        "loaded": result["rows_loaded"],
                    }
                )
    by_table = {copy["table"]: copy["results"] for copy in copies}
    return {
        "run_id": run_id,
        "recorded_at": recorded_at,
        "datasets": len(staged),
        "sources": dict(Counter(stage["source"] for stage in staged)),
        "extracted_rows": {t: sum(s["rows"].get(t, 0) for s in staged) for t in TABLES},
        "files_loaded": {t: len(by_table.get(t, [])) for t in TABLES},
        "rows_loaded": {t: sum(r["rows_loaded"] for r in by_table.get(t, [])) for t in TABLES},
        "not_loaded": [
            r for results in by_table.values() for r in results if r["status"].upper() != "LOADED"
        ],
        "mismatches": mismatches,
        "staged": staged,
    }


def reconcile_sql(profiles: list[dict]) -> str:
    """Two Snowflake queries that check the loaded raw tables against the cp1 profile.

    The first returns every data set and table whose loaded rows differ from the
    rows the profile counted in the zip, either way; no row back is the cp2
    criterion. The second sums both sides per table. `profiles` are the
    data/profile/<name>.json documents the cp1 profile wrote.
    """
    expected = ",\n".join(
        f"        ('{dataset_id(prof['name'])}', '{table}', {prof['rows'][table]})"
        for prof in sorted(profiles, key=lambda p: p["name"])
        for table in TABLES
    )
    loaded = "\n    union all\n".join(
        f"    select '{table}' as table_name, split_part(source_file, '/', -1) as file_name,"
        f" count(*) as loaded_rows\n"
        f"    from edgar_13f.raw.dataset_{table.lower()} group by file_name"
        for table in TABLES
    )
    common = (
        "with expected (dataset, table_name, expected_rows) as (\n"
        f"    select * from values\n{expected}\n),\n"
        f"loaded as (\n{loaded}\n),\n"
        "compared as (\n"
        f"    select coalesce(e.dataset, replace(l.file_name, '{EXTRACTED_SUFFIX}', '')) as dataset,\n"
        "           coalesce(e.table_name, l.table_name) as table_name,\n"
        "           e.expected_rows, l.loaded_rows\n"
        "    from expected e\n"
        "    full outer join loaded l\n"
        f"        on l.table_name = e.table_name and l.file_name = e.dataset || '{EXTRACTED_SUFFIX}'\n"
        ")\n"
    )
    header = (
        f"-- Generated by `python -m include.sec_cli reconcile-sql` from {len(profiles)}"
        " cp1 profiles.\n"
    )
    return (
        f"{header}"
        "-- 1. Data sets and tables whose loaded rows differ from the profile. Expect no rows.\n"
        f"{common}"
        "select * from compared\n"
        "where expected_rows is distinct from loaded_rows\n"
        "order by dataset, table_name;\n\n"
        "-- 2. Rows per table, profile against Snowflake.\n"
        f"{common}"
        "select table_name, sum(expected_rows) as expected_rows, sum(loaded_rows) as loaded_rows\n"
        "from compared\n"
        "group by table_name\n"
        "order by table_name;\n"
    )
