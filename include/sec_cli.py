"""Command line for the SEC 13F data sets: list, download, profile.

Run from the repo root with the contact address in the environment:
`uv run --env-file .env python -m include.sec_cli <command>`.
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from include import sec_profile
from include.edgar_client import EdgarClient
from include.sec_datasets import DEFAULT_DEST, download, list_datasets

DEFAULT_PROFILE_OUT = Path("data/profile")

logger = logging.getLogger(__name__)


def client_from_env() -> EdgarClient:
    contact = os.environ.get("AIRFLOW_VAR_EDGAR_CONTACT")
    if not contact:
        sys.exit(
            "set AIRFLOW_VAR_EDGAR_CONTACT (see .env.example); run with uv run --env-file .env"
        )
    return EdgarClient(contact)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m include.sec_cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="print the data sets the SEC lists, oldest first")
    dl = sub.add_parser("download", help="fetch every data set not yet complete under --dest")
    dl.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    dl.add_argument("--only", help="substring of a name, to fetch a subset")
    pr = sub.add_parser(
        "profile", help="profile the downloaded zips into --out, then print the report"
    )
    pr.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    pr.add_argument("--out", type=Path, default=DEFAULT_PROFILE_OUT)
    pr.add_argument("--only", help="substring of a name, to profile a subset")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    client = client_from_env()
    datasets = list_datasets(client)
    chosen = [d for d in datasets if not getattr(args, "only", None) or args.only in d.name]

    if args.command == "list":
        for d in datasets:
            print(f"{d.window_start} {d.window_end} {d.name}")
        print(f"{len(datasets)} data sets", file=sys.stderr)
    elif args.command == "download":
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
    elif args.command == "profile":
        profiles = sec_profile.profile_all(chosen, args.dest, args.out)
        candidates = sec_profile.candidate_filers(sec_profile.filer_index(profiles))
        (args.out / "candidates.json").write_text(json.dumps(candidates, indent=1))
        print(sec_profile.render_markdown(profiles, candidates))


if __name__ == "__main__":
    main()
