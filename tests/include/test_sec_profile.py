import json
import zipfile
from datetime import date
from pathlib import Path

import pytest

from include import sec_profile
from include.sec_datasets import Dataset

DATASET = Dataset(date(2026, 6, 1), date(2026, 8, 31), "01jun2026-31aug2026_form13f.zip", "/x")

SUBMISSION = ["ACCESSION_NUMBER", "FILING_DATE", "SUBMISSIONTYPE", "CIK", "PERIODOFREPORT"]
COVERPAGE = [
    "ACCESSION_NUMBER",
    "REPORTCALENDARORQUARTER",
    "ISAMENDMENT",
    "AMENDMENTNO",
    "AMENDMENTTYPE",
    "REPORTTYPE",
]
INFOTABLE = [
    "ACCESSION_NUMBER",
    "INFOTABLE_SK",
    "NAMEOFISSUER",
    "CUSIP",
    "FIGI",
    "VALUE",
    "SSHPRNAMT",
    "SSHPRNAMTTYPE",
    "PUTCALL",
]
SUMMARYPAGE = [
    "ACCESSION_NUMBER",
    "OTHERINCLUDEDMANAGERSCOUNT",
    "TABLEENTRYTOTAL",
    "TABLEVALUETOTAL",
    "ISCONFIDENTIALOMITTED",
]
PLAIN = ["ACCESSION_NUMBER", "NAME"]


def tsv(header: list[str], rows: list[list[str]]) -> str:
    return "\n".join(["\t".join(header), *["\t".join(r) for r in rows]]) + "\n"


def build_zip(path: Path, tables: dict[str, str]) -> Path:
    with zipfile.ZipFile(path, "w") as z:
        for name, text in tables.items():
            z.writestr(f"{name}.tsv", text)
        z.writestr("FORM13F_readme.htm", "<html/>")
    return path


def small_dataset(tmp_path: Path) -> Path:
    return build_zip(
        tmp_path / DATASET.name,
        {
            "SUBMISSION": tsv(
                SUBMISSION,
                [
                    ["A-1", "14-AUG-2026", "13F-HR", "0000000001", "30-JUN-2026"],
                    ["A-2", "20-AUG-2026", "13F-HR/A", "0000000001", "30-JUN-2026"],
                    ["A-3", "25-AUG-2026", "13F-HR/A", "0000000001", "30-JUN-2026"],
                    ["B-1", "01-JUN-2026", "13F-NT", "0000000002", "31-MAR-2026"],
                ],
            ),
            "COVERPAGE": tsv(
                COVERPAGE,
                [
                    ["A-1", "30-JUN-2026", "", "", "", "13F HOLDINGS REPORT"],
                    ["A-2", "30-JUN-2026", "Y", "1", "RESTATEMENT", "13F HOLDINGS REPORT"],
                    ["A-3", "30-JUN-2026", "Y", "2", "NEW HOLDINGS", "13F HOLDINGS REPORT"],
                    ["B-1", "31-MAR-2026", "", "", "", "13F NOTICE"],
                ],
            ),
            "INFOTABLE": tsv(
                INFOTABLE,
                [
                    ["A-1", "1", "ACME", "000000000", "", "500", "10", "SH", ""],
                    ["A-1", "2", "BETA", "111111111", "BBG000BLNNH6", "250000", "100", "SH", "Put"],
                    ["A-2", "3", "ACME", "000000000", "", "600", "12", "SH", ""],
                    ["A-3", "4", "GAMMA", "222222222", "", "1000000", "5", "PRN", ""],
                ],
            ),
            "SUMMARYPAGE": tsv(
                SUMMARYPAGE,
                [
                    ["A-1", "0", "2", "250500", "false"],
                    ["A-2", "0", "1", "600", "false"],
                    ["A-3", "0", "1", "1000000", "false"],
                ],
            ),
            "OTHERMANAGER": tsv(PLAIN, [["A-1", "X"]]),
            "OTHERMANAGER2": tsv(PLAIN, []),
            "SIGNATURE": tsv(PLAIN, [["A-1", "S"], ["A-2", "S"], ["A-3", "S"], ["B-1", "S"]]),
        },
    )


class TestProfile:
    def test_counts_every_table_and_keeps_samples(self, tmp_path):
        prof = sec_profile.profile(small_dataset(tmp_path), DATASET)

        assert prof["rows"] == {
            "SUBMISSION": 4,
            "COVERPAGE": 4,
            "INFOTABLE": 4,
            "OTHERMANAGER": 1,
            "OTHERMANAGER2": 0,
            "SIGNATURE": 4,
            "SUMMARYPAGE": 3,
        }
        assert prof["name"] == DATASET.name and prof["window_end"] == "2026-08-31"
        assert len(prof["samples"]["INFOTABLE"]) == 3
        assert prof["samples"]["INFOTABLE"][1]["FIGI"] == "BBG000BLNNH6"
        assert prof["samples"]["OTHERMANAGER2"] == []

    def test_submission_facts(self, tmp_path):
        sub = sec_profile.profile(small_dataset(tmp_path), DATASET)["submission"]

        assert (sub["filing_date_min"], sub["filing_date_max"]) == ("2026-06-01", "2026-08-25")
        assert (sub["period_min"], sub["period_max"]) == ("2026-03-31", "2026-06-30")
        assert sub["submission_types"] == {"13F-HR": 1, "13F-HR/A": 2, "13F-NT": 1}
        assert sub["distinct_ciks"] == 2

    def test_coverpage_amendment_facts(self, tmp_path):
        cover = sec_profile.profile(small_dataset(tmp_path), DATASET)["coverpage"]

        assert cover["amendment_types"] == {"RESTATEMENT": 1, "NEW HOLDINGS": 1}
        assert cover["is_amendment"] == {"<blank>": 2, "Y": 2}
        assert cover["report_types"] == {"13F HOLDINGS REPORT": 3, "13F NOTICE": 1}

    def test_infotable_facts_including_the_unit_boundary_share(self, tmp_path):
        it = sec_profile.profile(small_dataset(tmp_path), DATASET)["infotable"]

        assert it["value_sum"] == 500 + 250000 + 600 + 1000000
        assert (it["value_min"], it["value_max"]) == (500, 1000000)
        assert it["value_median"] == 250000
        assert (
            it["share_value_under_1000"] == 0.5
        )  # two of four rows look like thousands-era values
        assert it["figi_filled"] == 1 and it["figi_share"] == 0.25
        assert it["amount_types"] == {"SH": 3, "PRN": 1}
        assert it["put_call"] == {"<none>": 3, "Put": 1}

    def test_tables_inside_a_folder_are_found_by_base_name(self, tmp_path):
        # 01jun2025-31aug2025_form13f.zip is packed this way; the other 53 are flat.
        tables = {t: tsv(PLAIN, [["A-1", "X"]]) for t in sec_profile.TABLES}
        tables["SUBMISSION"] = tsv(
            SUBMISSION, [["A-1", "14-AUG-2026", "13F-HR", "1", "30-JUN-2026"]]
        )
        tables["COVERPAGE"] = tsv(
            COVERPAGE, [["A-1", "30-JUN-2026", "", "", "", "13F HOLDINGS REPORT"]]
        )
        tables["INFOTABLE"] = tsv(
            INFOTABLE, [["A-1", "1", "ACME", "000000000", "", "500", "10", "SH", ""]]
        )
        tables["SUMMARYPAGE"] = tsv(SUMMARYPAGE, [["A-1", "0", "1", "500", "false"]])
        nested = {f"01JUN2025-31AUG2025_form13f/{k}": v for k, v in tables.items()}

        prof = sec_profile.profile(build_zip(tmp_path / DATASET.name, nested), DATASET)

        assert prof["rows"]["INFOTABLE"] == 1 and prof["rows"]["SIGNATURE"] == 1

    def test_missing_table_is_an_error(self, tmp_path):
        path = build_zip(tmp_path / DATASET.name, {"SUBMISSION": tsv(SUBMISSION, [])})

        with pytest.raises(sec_profile.ProfileError, match="missing tables"):
            sec_profile.profile(path, DATASET)

    def test_ragged_row_is_an_error(self, tmp_path):
        tables = {t: tsv(PLAIN, []) for t in sec_profile.TABLES}
        tables["SUBMISSION"] = tsv(SUBMISSION, [["A-1", "14-AUG-2026", "13F-HR", "1"]])
        path = build_zip(tmp_path / DATASET.name, tables)

        with pytest.raises(sec_profile.ProfileError, match="row with 4 fields, header has 5"):
            sec_profile.profile(path, DATASET)

    def test_public_view_drops_the_per_accession_parts(self, tmp_path):
        prof = sec_profile.profile(small_dataset(tmp_path), DATASET)

        assert "_filings" in prof["submission"]
        assert "_filings" not in sec_profile.public(prof)["submission"]
        json.dumps(sec_profile.public(prof))


class TestFilerIndexAndCandidates:
    def test_index_groups_filings_by_cik_and_period(self, tmp_path):
        prof = sec_profile.profile(small_dataset(tmp_path), DATASET)

        index = sec_profile.filer_index([prof])

        periods = index["0000000001"]["periods"]
        assert list(periods) == ["2026-06-30"]
        assert [f["type"] for f in periods["2026-06-30"]] == ["13F-HR", "13F-HR/A", "13F-HR/A"]
        assert [f["amendment_type"] for f in periods["2026-06-30"]] == [
            None,
            "RESTATEMENT",
            "NEW HOLDINGS",
        ]
        assert [f["entries"] for f in periods["2026-06-30"]] == [2, 1, 1]

    def test_candidates_need_two_amendments_and_a_hand_checkable_size(self):
        def filing(kind, amendment=None, entries=100):
            return {
                "accession": "x",
                "filed": "d",
                "type": kind,
                "amendment_type": amendment,
                "entries": entries,
            }

        index = {
            "messy": {
                "periods": {
                    "p1": [
                        filing("13F-HR"),
                        filing("13F-HR/A", "RESTATEMENT"),
                        filing("13F-HR/A", "NEW HOLDINGS"),
                    ],
                    "p2": [
                        filing("13F-HR"),
                        filing("13F-HR/A", "RESTATEMENT"),
                        filing("13F-HR/A", "RESTATEMENT"),
                    ],
                }
            },
            "one_amendment": {
                "periods": {"p1": [filing("13F-HR"), filing("13F-HR/A", "RESTATEMENT")]}
            },
            "huge": {
                "periods": {
                    "p1": [
                        filing("13F-HR", entries=9000),
                        filing("13F-HR/A", "RESTATEMENT"),
                        filing("13F-HR/A", "RESTATEMENT"),
                    ]
                }
            },
            "tiny": {
                "periods": {
                    "p1": [
                        filing("13F-HR", entries=3),
                        filing("13F-HR/A", "RESTATEMENT", entries=3),
                        filing("13F-HR/A", "RESTATEMENT", entries=3),
                    ]
                }
            },
        }

        candidates = sec_profile.candidate_filers(index)

        assert [c["cik"] for c in candidates] == ["messy"]
        assert candidates[0]["periods_with_two_or_more_amendments"] == 2
        assert candidates[0]["both_types"] is True
        assert candidates[0]["score"] == 25


class TestProfileAllAndReport:
    def test_profile_all_writes_json_once_and_reuses_it(self, tmp_path):
        source = tmp_path / "src"
        source.mkdir()
        small_dataset(source)
        out = tmp_path / "out"

        first = sec_profile.profile_all([DATASET], source, out)
        (source / DATASET.name).unlink()  # a second pass must not need the zip
        second = sec_profile.profile_all([DATASET], source, out)

        assert first[0]["rows"] == second[0]["rows"]
        assert (out / "01jun2026-31aug2026_form13f.json").exists()

    def test_report_renders_tables(self, tmp_path):
        prof = sec_profile.profile(small_dataset(tmp_path), DATASET)
        candidates = sec_profile.candidate_filers(sec_profile.filer_index([prof]))

        report = sec_profile.render_markdown([prof], candidates)

        assert "| 01jun2026-31aug2026 | 2026-06-01 to 2026-08-31 |" in report
        assert "| INFOTABLE | 4 |" in report
        assert "| 13F-HR/A | 2 |" in report
        assert "| RESTATEMENT | 1 |" in report
        # The only filer has a two-row table, under the hand-checkable floor, so no candidate row.
        assert candidates == []
        assert "| 0000000001 |" not in report
