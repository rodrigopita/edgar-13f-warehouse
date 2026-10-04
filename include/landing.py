"""The S3 landing zone: bytes from EDGAR, unchanged, under deterministic keys.

Keys are derived from what the filing is (accession, filing date) and never
from when it was fetched, so a rerun of the same day writes the same objects
with the same bytes: idempotent (safe to rerun: a second run of the same input
changes nothing). The bucket is versioned, so an overwrite keeps the prior
version. The module imports nothing from Airflow; the DAG hands it a boto3
client built from the Airflow connection.
"""

import json
import re
from dataclasses import dataclass
from datetime import date

import boto3
from botocore.exceptions import ClientError

from include.edgar_filing import FilingBytes

INDEX_PREFIX = "raw/edgar/index"
FILINGS_PREFIX = "raw/edgar/filings"
AUDIT_PREFIX = "raw/edgar/audit/walk"
PRIMARY_DOC_NAME = "primary_doc.xml"
# The filer chooses the information table's file name. It is stored under one
# fixed name, and the original is kept as object metadata.
INFO_TABLE_NAME = "infotable.xml"


def index_key(day: date) -> str:
    return f"{INDEX_PREFIX}/form.{day:%Y%m%d}.idx"


def filing_prefix(filed: date, accession: str) -> str:
    return f"{FILINGS_PREFIX}/filed={filed.isoformat()}/{accession}/"


def primary_doc_key(filed: date, accession: str) -> str:
    return filing_prefix(filed, accession) + PRIMARY_DOC_NAME


def info_table_key(filed: date, accession: str) -> str:
    return filing_prefix(filed, accession) + INFO_TABLE_NAME


def audit_key(day: date, run_id: str) -> str:
    """One audit record per DAG run, under the day the run was for."""
    safe_run_id = re.sub(r"[^A-Za-z0-9_.-]", "-", run_id)
    return f"{AUDIT_PREFIX}/day={day.isoformat()}/{safe_run_id}.json"


@dataclass(frozen=True)
class Landed:
    """One object written: where, how many bytes, and which version S3 assigned."""

    key: str
    size: int
    version_id: str | None


class LandingZone:
    """Writes to one bucket through a boto3 S3 client."""

    def __init__(self, bucket: str, s3_client=None) -> None:
        self.bucket = bucket
        self._s3 = s3_client if s3_client is not None else boto3.client("s3")

    def land_index(self, day: date, data: bytes) -> Landed:
        """Store a daily form index as fetched."""
        return self._put(index_key(day), data, "text/plain", {"source": f"form.{day:%Y%m%d}.idx"})

    def land_filing(self, filing: FilingBytes) -> list[Landed]:
        """Store a filing's cover page and, for a holdings report, its information table."""
        entry, documents = filing.entry, filing.documents
        metadata = {
            "accession": entry.accession,
            "cik": str(entry.cik),
            "form-type": entry.form_type,
            "filed": entry.filed.isoformat(),
        }
        landed = [
            self._put(
                primary_doc_key(entry.filed, entry.accession),
                filing.primary_doc,
                "application/xml",
                metadata | {"original-name": documents.primary_doc},
            )
        ]
        if filing.info_table is not None and documents.info_table is not None:
            landed.append(
                self._put(
                    info_table_key(entry.filed, entry.accession),
                    filing.info_table,
                    "application/xml",
                    metadata | {"original-name": documents.info_table},
                )
            )
        return landed

    def land_audit(self, day: date, run_id: str, record: dict) -> Landed:
        """Store one run's audit record as JSON. The pipeline writes its own audit."""
        data = json.dumps(record, sort_keys=True, default=str).encode()
        return self._put(audit_key(day, run_id), data, "application/json", {"run-id": run_id})

    def read(self, key: str) -> bytes:
        """Bytes of a landed object. Needs only s3:GetObject."""
        return self._s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def exists(self, key: str) -> bool:
        """Whether the key has a current version. Needs only s3:GetObject."""
        try:
            self._s3.head_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                return False
            raise
        return True

    def _put(self, key: str, data: bytes, content_type: str, metadata: dict[str, str]) -> Landed:
        response = self._s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            Metadata=metadata,
        )
        return Landed(key=key, size=len(data), version_id=response.get("VersionId"))
