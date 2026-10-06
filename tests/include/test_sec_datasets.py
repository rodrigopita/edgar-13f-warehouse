from datetime import date
from itertools import pairwise
from pathlib import Path

import pytest

from include.edgar_client import EdgarClient
from include.sec_datasets import Dataset, DatasetNameError, download, list_datasets, parse_dataset
from tests.fakes import FakeResponse

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "edgar"
PAGE = "https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets"
OLD = "/files/structureddata/data/form-13f-data-sets/2013q2_form13f.zip"
NEW = "/files/datastandardsinnovation/data/form-13f-data-sets/01jun2026-31aug2026_form13f.zip"


@pytest.fixture
def client(session, clock, sleeper) -> EdgarClient:
    return EdgarClient("someone@example.com", session=session, clock=clock, sleeper=sleeper)


class TestParseDataset:
    @pytest.mark.parametrize(
        ("name", "start", "end"),
        [
            pytest.param("2013q2_form13f.zip", date(2013, 4, 1), date(2013, 6, 30), id="q2"),
            pytest.param("2023q4_form13f.zip", date(2023, 10, 1), date(2023, 12, 31), id="q4"),
            pytest.param("2020q1_form13f.zip", date(2020, 1, 1), date(2020, 3, 31), id="q1"),
            pytest.param(
                "01jan2024-29feb2024_form13f.zip", date(2024, 1, 1), date(2024, 2, 29), id="bridge"
            ),
            pytest.param(
                "01dec2025-28feb2026_form13f.zip",
                date(2025, 12, 1),
                date(2026, 2, 28),
                id="year-end",
            ),
            pytest.param(
                "01jun2026-31aug2026_form13f.zip", date(2026, 6, 1), date(2026, 8, 31), id="latest"
            ),
        ],
    )
    def test_dates_both_name_styles(self, name, start, end):
        d = parse_dataset(name, f"/x/{name}")

        assert (d.window_start, d.window_end) == (start, end)
        assert d.quarter_style == ("q" in name[:6])

    def test_unknown_name_is_an_error(self):
        with pytest.raises(DatasetNameError, match="unrecognized"):
            parse_dataset("form13f_everything.zip", "/x")

    def test_impossible_date_is_an_error(self):
        with pytest.raises(DatasetNameError, match="cannot date"):
            parse_dataset("31feb2024-31may2024_form13f.zip", "/x")


class TestListDatasets:
    def test_reads_all_54_from_the_real_page_oldest_first(self, client, session):
        session.queue(FakeResponse(200, (FIXTURES / "form-13f-data-sets.html").read_bytes()))

        datasets = list_datasets(client)

        assert session.calls == [PAGE]
        assert len(datasets) == 54
        assert datasets[0].name == "2013q2_form13f.zip"
        assert datasets[-1].name == "01jun2026-31aug2026_form13f.zip"
        assert sum(d.quarter_style for d in datasets) == 43
        assert datasets[0].url == OLD and datasets[-1].url == NEW

    def test_windows_tile_the_timeline_without_gaps_or_overlaps(self, client, session):
        session.queue(FakeResponse(200, (FIXTURES / "form-13f-data-sets.html").read_bytes()))

        datasets = list_datasets(client)

        for earlier, later in pairwise(datasets):
            assert (later.window_start - earlier.window_end).days == 1, (earlier.name, later.name)

    def test_the_xml_walk_starts_the_day_after_the_newest_window(self, client, session):
        session.queue(FakeResponse(200, (FIXTURES / "form-13f-data-sets.html").read_bytes()))

        assert list_datasets(client)[-1].window_end == date(2026, 8, 31)


class TestDownload:
    DATASET = Dataset(date(2013, 4, 1), date(2013, 6, 30), "2013q2_form13f.zip", OLD)
    URL = "https://www.sec.gov" + OLD

    def test_fetches_when_absent_and_writes_atomically(self, client, session, tmp_path):
        session.queue(
            FakeResponse(200, headers={"Content-Length": "5"}), FakeResponse(200, b"zip!!")
        )

        path = download(client, self.DATASET, tmp_path)

        assert path == tmp_path / "2013q2_form13f.zip"
        assert path.read_bytes() == b"zip!!"
        assert session.calls == [f"HEAD {self.URL}", self.URL]
        assert not (tmp_path / "2013q2_form13f.part").exists()

    def test_a_complete_local_copy_costs_one_head_and_no_get(self, client, session, tmp_path):
        (tmp_path / "2013q2_form13f.zip").write_bytes(b"zip!!")
        session.queue(FakeResponse(200, headers={"Content-Length": "5"}))

        download(client, self.DATASET, tmp_path)

        assert session.calls == [f"HEAD {self.URL}"]
        assert client.requests_made == 1

    def test_a_short_local_copy_is_refetched(self, client, session, tmp_path):
        (tmp_path / "2013q2_form13f.zip").write_bytes(b"zi")
        session.queue(
            FakeResponse(200, headers={"Content-Length": "5"}), FakeResponse(200, b"zip!!")
        )

        download(client, self.DATASET, tmp_path)

        assert (tmp_path / "2013q2_form13f.zip").read_bytes() == b"zip!!"

    def test_a_truncated_body_is_refused_and_leaves_no_file(self, client, session, tmp_path):
        session.queue(FakeResponse(200, headers={"Content-Length": "5"}), FakeResponse(200, b"zi"))

        with pytest.raises(OSError, match="got 2 bytes, Content-Length said 5"):
            download(client, self.DATASET, tmp_path)

        assert list(tmp_path.iterdir()) == []
