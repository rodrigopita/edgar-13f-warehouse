"""The SEC's Form 13F data sets: the historical path.

The SEC publishes one zip per filing-date window with seven tab-separated
tables extracted from every 13F submission. This module lists them from the
datasets page, downloads them idempotently, and (in a later step) profiles
them. Historical backfill comes from these files and nothing else; the XML
path begins where the newest of them ends.
"""

import argparse
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from include.edgar_client import EdgarClient

DATASETS_PAGE = "/data-research/sec-markets-data/form-13f-data-sets"
DEFAULT_DEST = Path("data/datasets")

_HREF = re.compile(r'href="([^"]*?/([^"/]*form13f\.zip))"')
_QUARTER_NAME = re.compile(r"^(\d{4})q([1-4])_form13f\.zip$")
_WINDOW_NAME = re.compile(r"^(\d{2})([a-z]{3})(\d{4})-(\d{2})([a-z]{3})(\d{4})_form13f\.zip$")
_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}  # fmt: skip

logger = logging.getLogger(__name__)


@dataclass(frozen=True, order=True)
class Dataset:
    """One zip: filings submitted in [window_start, window_end]."""

    window_start: date
    window_end: date
    name: str
    url: str

    @property
    def quarter_style(self) -> bool:
        """True for the 2013q2 to 2023q4 names; false for 01jan2024-29feb2024 and later."""
        return _QUARTER_NAME.match(self.name) is not None


class DatasetNameError(ValueError):
    """A zip link on the datasets page has a name this module cannot date."""


def list_datasets(client: EdgarClient) -> list[Dataset]:
    """Every 13F data set the SEC lists, oldest first."""
    page = client.get(DATASETS_PAGE).decode("utf-8", "ignore")
    datasets = {parse_dataset(name, url) for url, name in _HREF.findall(page)}
    return sorted(datasets)


def parse_dataset(name: str, url: str) -> Dataset:
    """Date a zip from its name. Two styles exist and they do not overlap.

    `2013q2_form13f.zip` through `2023q4_form13f.zip` cover a calendar quarter of
    filing dates. From `01jan2024-29feb2024_form13f.zip` on, the window is spelled
    out; the first is two months, the rest are three (Mar-May, Jun-Aug, Sep-Nov,
    Dec-Feb), aligned with the 13F deadlines 45 days after quarter end.
    """
    if found := _QUARTER_NAME.match(name):
        year, quarter = int(found.group(1)), int(found.group(2))
        start = date(year, 3 * quarter - 2, 1)
        end_month = 3 * quarter
        end = date(year, end_month, _month_end(year, end_month))
        return Dataset(start, end, name, url)
    if found := _WINDOW_NAME.match(name):
        d1, m1, y1, d2, m2, y2 = found.groups()
        try:
            start = date(int(y1), _MONTHS[m1], int(d1))
            end = date(int(y2), _MONTHS[m2], int(d2))
        except (KeyError, ValueError) as exc:
            raise DatasetNameError(f"cannot date {name!r}: {exc}") from exc
        return Dataset(start, end, name, url)
    raise DatasetNameError(f"unrecognized data set name {name!r}")


def _month_end(year: int, month: int) -> int:
    next_month = date(year + (month == 12), month % 12 + 1, 1)
    return (next_month - date(year, month, 1)).days


def download(client: EdgarClient, dataset: Dataset, dest: Path = DEFAULT_DEST) -> Path:
    """Fetch the zip into `dest` unless a complete copy is already there.

    Idempotent (safe to rerun: a second run of the same input changes nothing):
    one HEAD compares Content-Length with the local size, and only a missing or
    short file is fetched. Writes go to a temporary name and are renamed into
    place, so an interrupted download never looks complete.
    """
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / dataset.name
    expected = int(client.head(dataset.url).get("Content-Length", "0"))
    if target.exists() and expected and target.stat().st_size == expected:
        logger.info("%s already complete (%d bytes), skipping", dataset.name, expected)
        return target
    started = time.monotonic()
    data = client.get(dataset.url)
    if expected and len(data) != expected:
        raise OSError(f"{dataset.name}: got {len(data)} bytes, Content-Length said {expected}")
    partial = target.with_suffix(".part")
    partial.write_bytes(data)
    os.replace(partial, target)
    logger.info("%s: %d bytes in %.1f s", dataset.name, len(data), time.monotonic() - started)
    return target


def _client_from_env() -> EdgarClient:
    contact = os.environ.get("AIRFLOW_VAR_EDGAR_CONTACT")
    if not contact:
        sys.exit(
            "set AIRFLOW_VAR_EDGAR_CONTACT (see .env.example); run with uv run --env-file .env"
        )
    return EdgarClient(contact)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m include.sec_datasets")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="print the data sets the SEC lists, oldest first")
    dl = sub.add_parser("download", help="fetch every data set not yet complete under --dest")
    dl.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    dl.add_argument("--only", help="substring of a name, to fetch a subset")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    client = _client_from_env()
    datasets = list_datasets(client)
    if args.command == "list":
        for d in datasets:
            print(f"{d.window_start} {d.window_end} {d.name}")
        print(f"{len(datasets)} data sets", file=sys.stderr)
        return
    chosen = [d for d in datasets if not args.only or args.only in d.name]
    for d in chosen:
        download(client, d, args.dest)
    stats = client.stats()
    logger.info(
        "%d data sets under %s; %d requests, %d retries, %.2f req/s",
        len(chosen),
        args.dest,
        stats["requests_made"],
        stats["retries"],
        stats["requests_per_second"],
    )


if __name__ == "__main__":
    main()
