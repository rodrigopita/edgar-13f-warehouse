import logging

import pytest

from include.edgar_client import LOG_EVERY, EdgarClient
from tests.fakes import FakeResponse

URL = "https://www.sec.gov/Archives/edgar/daily-index/2026/QTR3/index.json"


@pytest.fixture
def client(session, clock, sleeper) -> EdgarClient:
    return EdgarClient("someone@example.com", session=session, clock=clock, sleeper=sleeper)


class TestStats:
    def test_zero_before_any_request(self, client):
        assert client.stats() == {
            "requests_made": 0,
            "retries": 0,
            "elapsed_seconds": 0.0,
            "requests_per_second": 0.0,
        }

    def test_reports_the_observed_rate(self, client, session, clock):
        session.queue(*[FakeResponse(200, b"x")] * 20)
        for _ in range(20):
            client.get(URL)
        # 20 requests span 19 limiter gaps of 0.125 s = 2.375 s. Advance to 10 s total.
        clock.advance(10.0 - 2.375)

        stats = client.stats()

        assert stats["requests_made"] == 20
        assert stats["elapsed_seconds"] == pytest.approx(10.0)
        assert stats["requests_per_second"] == pytest.approx(2.0)

    def test_back_to_back_requests_never_exceed_the_ceiling(self, client, session):
        session.queue(*[FakeResponse(200, b"x")] * 200)

        for _ in range(200):
            client.get(URL)

        # 200 requests over 199 gaps: the average is 8 * 200 / 199, never above 8.05.
        assert client.stats()["requests_per_second"] == pytest.approx(8 * 200 / 199)

    def test_counts_retries_and_attempts_separately(self, client, session):
        session.queue(FakeResponse(429), FakeResponse(503), FakeResponse(200, b"ok"))

        client.get(URL)

        stats = client.stats()
        assert stats["requests_made"] == 3
        assert stats["retries"] == 2


class TestLogging:
    def test_warns_before_each_backoff(self, client, session, caplog):
        session.queue(FakeResponse(429), FakeResponse(200, b"ok"))
        caplog.set_level(logging.WARNING, logger="include.edgar_client")

        client.get(URL)

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        assert "attempt 1 failed" in warnings[0].getMessage()
        assert "HTTP 429" in warnings[0].getMessage()
        assert "retrying in 1 s" in warnings[0].getMessage()

    def test_head_requests_count_toward_the_rate_log(self, client, session, caplog):
        session.queue(*[FakeResponse(200, headers={"Content-Length": "1"})] * LOG_EVERY)
        caplog.set_level(logging.INFO, logger="include.edgar_client")

        for _ in range(LOG_EVERY):
            client.head(URL)

        assert client.stats()["requests_made"] == LOG_EVERY
        assert sum(r.getMessage().startswith("edgar rate") for r in caplog.records) == 1

    def test_logs_the_rate_every_hundred_requests(self, client, session, caplog):
        session.queue(*[FakeResponse(200, b"x")] * (2 * LOG_EVERY))
        caplog.set_level(logging.INFO, logger="include.edgar_client")

        for _ in range(2 * LOG_EVERY):
            client.get(URL)

        rate_lines = [
            r.getMessage() for r in caplog.records if r.getMessage().startswith("edgar rate")
        ]
        assert len(rate_lines) == 2
        assert rate_lines[0].startswith("edgar rate: 100 requests, 0 retries")
        assert "req/s" in rate_lines[1]
