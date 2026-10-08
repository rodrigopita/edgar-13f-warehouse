"""Profile of the SEC 13F data sets: the row counts cp1 asks to write down.

One streaming pass per zip, no extraction to disk, one JSON per data set so
the pass runs once. The seven tables share one schema since 2013 and carry no
quoting, so lines are split on tabs directly. Two things come out besides the
counts: the VALUE unit boundary (thousands before 2023-01-03, dollars after)
shows as the share of rows under 1,000, and a per-filer index of amendments
feeds the choice of the cp3 test case.
"""

import io
import json
import logging
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

from include.sec_datasets import Dataset

TABLES = (
    "SUBMISSION",
    "COVERPAGE",
    "INFOTABLE",
    "OTHERMANAGER",
    "OTHERMANAGER2",
    "SIGNATURE",
    "SUMMARYPAGE",
)
SAMPLE_ROWS = 3
# Market value was reported in thousands before 2023-01-03 and in dollars after.
# In thousands, most positions are under 1,000; in dollars almost none are.
VALUE_UNIT_CHANGE = date(2023, 1, 3)
SMALL_VALUE = 1000

logger = logging.getLogger(__name__)


class ProfileError(ValueError):
    """A data set does not have the seven tables or a table's header is unexpected."""


def profile(path: Path, dataset: Dataset) -> dict:
    """Counts, ranges and samples for one zip; also the per-filer amendment facts."""
    with zipfile.ZipFile(path) as archive:
        # One data set (01jun2025-31aug2025) packs its tables inside a folder; match by base name.
        members = {
            Path(name).name.removesuffix(".tsv"): name
            for name in archive.namelist()
            if name.endswith(".tsv")
        }
        missing = [t for t in TABLES if t not in members]
        if missing:
            raise ProfileError(f"{path.name}: missing tables {missing}")
        result = {
            "name": dataset.name,
            "window_start": dataset.window_start.isoformat(),
            "window_end": dataset.window_end.isoformat(),
            "zip_bytes": path.stat().st_size,
            "rows": {},
            "samples": {},
        }
        for table in TABLES:
            with archive.open(members[table]) as raw:
                text = io.TextIOWrapper(raw, encoding="utf-8", newline="")
                header = next(text).rstrip("\r\n").split("\t")
                scan = _SCANNERS.get(table, _count_only)
                rows, facts, samples = scan(text, header)
            result["rows"][table] = rows
            result["samples"][table] = samples
            if facts:
                result[table.lower()] = facts
    return result


def _read_rows(text, header):
    width = len(header)
    for line in text:
        fields = line.rstrip("\r\n").split("\t")
        if len(fields) != width:
            raise ProfileError(f"row with {len(fields)} fields, header has {width}: {line[:80]!r}")
        yield fields


def _count_only(text, header):
    rows = 0
    samples = []
    for fields in _read_rows(text, header):
        rows += 1
        if len(samples) < SAMPLE_ROWS:
            samples.append(dict(zip(header, fields, strict=True)))
    return rows, None, samples


def _scan_submission(text, header):
    col = {name: i for i, name in enumerate(header)}
    rows = 0
    samples = []
    types: Counter[str] = Counter()
    ciks: set[str] = set()
    filed_min = filed_max = period_min = period_max = None
    filings: dict[str, dict] = {}
    for fields in _read_rows(text, header):
        rows += 1
        if len(samples) < SAMPLE_ROWS:
            samples.append(dict(zip(header, fields, strict=True)))
        filed = _dmy(fields[col["FILING_DATE"]])
        period = _dmy(fields[col["PERIODOFREPORT"]])
        types[fields[col["SUBMISSIONTYPE"]]] += 1
        ciks.add(fields[col["CIK"]])
        filed_min = filed if filed_min is None or filed < filed_min else filed_min
        filed_max = filed if filed_max is None or filed > filed_max else filed_max
        period_min = period if period_min is None or period < period_min else period_min
        period_max = period if period_max is None or period > period_max else period_max
        filings[fields[col["ACCESSION_NUMBER"]]] = {
            "cik": fields[col["CIK"]],
            "period": period.isoformat(),
            "filed": filed.isoformat(),
            "type": fields[col["SUBMISSIONTYPE"]],
        }
    facts = {
        "filing_date_min": filed_min.isoformat() if filed_min else None,
        "filing_date_max": filed_max.isoformat() if filed_max else None,
        "period_min": period_min.isoformat() if period_min else None,
        "period_max": period_max.isoformat() if period_max else None,
        "submission_types": dict(types),
        "distinct_ciks": len(ciks),
        "_filings": filings,
    }
    return rows, facts, samples


def _scan_coverpage(text, header):
    col = {name: i for i, name in enumerate(header)}
    rows = 0
    samples = []
    amendment = Counter()
    amendment_type = Counter()
    report_type = Counter()
    amendment_by_accession: dict[str, str] = {}
    for fields in _read_rows(text, header):
        rows += 1
        if len(samples) < SAMPLE_ROWS:
            samples.append(dict(zip(header, fields, strict=True)))
        amendment[fields[col["ISAMENDMENT"]] or "<blank>"] += 1
        kind = fields[col["AMENDMENTTYPE"]]
        if kind:
            amendment_type[kind] += 1
            amendment_by_accession[fields[col["ACCESSION_NUMBER"]]] = kind
        report_type[fields[col["REPORTTYPE"]]] += 1
    facts = {
        "is_amendment": dict(amendment),
        "amendment_types": dict(amendment_type),
        "report_types": dict(report_type),
        "_amendment_by_accession": amendment_by_accession,
    }
    return rows, facts, samples


def _scan_infotable(text, header):
    col = {name: i for i, name in enumerate(header)}
    rows = 0
    samples = []
    values: list[int] = []
    figi = 0
    small = 0
    amount_type = Counter()
    put_call = Counter()
    bad_values = 0
    for fields in _read_rows(text, header):
        rows += 1
        if len(samples) < SAMPLE_ROWS:
            samples.append(dict(zip(header, fields, strict=True)))
        try:
            value = int(fields[col["VALUE"]])
        except ValueError:
            bad_values += 1
        else:
            values.append(value)
            small += value < SMALL_VALUE
        figi += bool(fields[col["FIGI"]])
        amount_type[fields[col["SSHPRNAMTTYPE"]]] += 1
        put_call[fields[col["PUTCALL"]] or "<none>"] += 1
    values.sort()
    facts = {
        "value_sum": sum(values),
        "value_min": values[0] if values else None,
        "value_median": values[len(values) // 2] if values else None,
        "value_max": values[-1] if values else None,
        "share_value_under_1000": round(small / len(values), 4) if values else None,
        "bad_values": bad_values,
        "figi_filled": figi,
        "figi_share": round(figi / rows, 4) if rows else None,
        "amount_types": dict(amount_type),
        "put_call": dict(put_call),
    }
    return rows, facts, samples


def _scan_summarypage(text, header):
    col = {name: i for i, name in enumerate(header)}
    rows = 0
    samples = []
    entries_by_accession: dict[str, int] = {}
    for fields in _read_rows(text, header):
        rows += 1
        if len(samples) < SAMPLE_ROWS:
            samples.append(dict(zip(header, fields, strict=True)))
        try:
            entries_by_accession[fields[col["ACCESSION_NUMBER"]]] = int(
                fields[col["TABLEENTRYTOTAL"]]
            )
        except ValueError:
            pass
    return rows, {"_entries_by_accession": entries_by_accession}, samples


_SCANNERS = {
    "SUBMISSION": _scan_submission,
    "COVERPAGE": _scan_coverpage,
    "INFOTABLE": _scan_infotable,
    "SUMMARYPAGE": _scan_summarypage,
}


def _dmy(text: str) -> date:
    """The data sets write dates as 31-JUL-2026."""
    return datetime.strptime(text, "%d-%b-%Y").date()  # noqa: DTZ007


# --- the filer index and the cp3 candidate ----------------------------------------


def filer_index(profiles: list[dict]) -> dict[str, dict]:
    """Per CIK: every (period) with its filings, from the private parts of the profiles."""
    index: dict[str, dict] = defaultdict(lambda: {"periods": defaultdict(list)})
    for prof in profiles:
        filings = prof["submission"]["_filings"]
        kinds = prof["coverpage"]["_amendment_by_accession"]
        entries = prof["summarypage"]["_entries_by_accession"]
        for accession, f in filings.items():
            index[f["cik"]]["periods"][f["period"]].append(
                {
                    "accession": accession,
                    "filed": f["filed"],
                    "type": f["type"],
                    "amendment_type": kinds.get(accession),
                    "entries": entries.get(accession),
                }
            )
    return index


def candidate_filers(index: dict[str, dict], top: int = 10) -> list[dict]:
    """CIKs with the messiest amendment histories, for the cp3 test case.

    Scored by periods with two or more holdings-report amendments, bonus for
    having both amendment types, and kept to a hand-checkable size: largest
    table between 50 and 3,000 entries.
    """
    scored = []
    for cik, data in index.items():
        periods = data["periods"]
        messy = 0
        restatements = additions = 0
        largest = 0
        for filings in periods.values():
            amendments = [f for f in filings if f["type"] == "13F-HR/A"]
            messy += len(amendments) >= 2
            restatements += sum(f["amendment_type"] == "RESTATEMENT" for f in amendments)
            additions += sum(f["amendment_type"] == "NEW HOLDINGS" for f in amendments)
            largest = max([largest, *[f["entries"] or 0 for f in filings]])
        if messy == 0 or not (50 <= largest <= 3000):
            continue
        scored.append(
            {
                "cik": cik,
                "periods_with_two_or_more_amendments": messy,
                "restatements": restatements,
                "new_holdings": additions,
                "both_types": restatements > 0 and additions > 0,
                "largest_table": largest,
                "periods": len(periods),
                "score": messy * 10 + 5 * (restatements > 0 and additions > 0),
            }
        )
    scored.sort(key=lambda c: (-c["score"], -c["periods"], c["cik"]))
    return scored[:top]


# --- running and reporting -------------------------------------------------------


def public(prof: dict) -> dict:
    """The profile without the per-accession parts that only the filer index needs."""
    return {
        k: (
            {kk: vv for kk, vv in v.items() if not kk.startswith("_")} if isinstance(v, dict) else v
        )
        for k, v in prof.items()
    }


def profile_all(datasets: list[Dataset], source: Path, out: Path) -> list[dict]:
    """Profile every zip into out/<name>.json, skipping ones already profiled."""
    out.mkdir(parents=True, exist_ok=True)
    profiles = []
    for dataset in datasets:
        target = out / (dataset.name.removesuffix(".zip") + ".json")
        if target.exists():
            profiles.append(json.loads(target.read_text()))
            continue
        prof = profile(source / dataset.name, dataset)
        target.write_text(json.dumps(prof, indent=1, sort_keys=True))
        logger.info(
            "%s: %s rows in INFOTABLE, %s filings",
            dataset.name,
            f"{prof['rows']['INFOTABLE']:,}",
            prof["rows"]["SUBMISSION"],
        )
        profiles.append(prof)
    return profiles


def render_markdown(profiles: list[dict], candidates: list[dict]) -> str:
    """The tables for docs/<date>-cp1-tsv-profile.md."""
    lines = [
        "| data set | window | zip MB | filings | holdings rows | value sum | under 1,000 | FIGI |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for p in profiles:
        it = p["infotable"]
        lines.append(
            f"| {p['name'].removesuffix('_form13f.zip')} | {p['window_start']} to {p['window_end']} | "
            f"{p['zip_bytes'] / 1e6:.0f} | {p['rows']['SUBMISSION']:,} | {p['rows']['INFOTABLE']:,} | "
            f"{it['value_sum']:,} | {it['share_value_under_1000']:.1%} | {it['figi_share']:.1%} |"
        )
    total_rows = {t: sum(p["rows"][t] for p in profiles) for t in TABLES}
    lines += ["", "| table | rows across all data sets |", "|---|---:|"]
    lines += [f"| {t} | {n:,} |" for t, n in total_rows.items()]
    types = Counter()
    for p in profiles:
        types.update(p["submission"]["submission_types"])
    lines += ["", "| submission type | filings |", "|---|---:|"]
    lines += [f"| {t} | {n:,} |" for t, n in sorted(types.items())]
    kinds = Counter()
    for p in profiles:
        kinds.update(p["coverpage"]["amendment_types"])
    lines += ["", "| amendment type | filings |", "|---|---:|"]
    lines += [f"| {t} | {n:,} |" for t, n in sorted(kinds.items())]
    lines += [
        "",
        "| CIK | periods with 2+ amendments | restatements | new holdings | both | largest table | periods |",
        "|---|---:|---:|---:|---|---:|---:|",
    ]
    lines += [
        f"| {c['cik']} | {c['periods_with_two_or_more_amendments']} | {c['restatements']} | {c['new_holdings']} | "
        f"{'yes' if c['both_types'] else 'no'} | {c['largest_table']:,} | {c['periods']} |"
        for c in candidates
    ]
    return "\n".join(lines) + "\n"
