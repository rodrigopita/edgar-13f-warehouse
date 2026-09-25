import pytest
import requests

from include.edgar_client import (
    DEFAULT_MAX_RPS,
    EdgarClient,
    EdgarPermanentError,
    EdgarRetryableError,
    RateLimiter,
)
from tests.fakes import FakeResponse

INDEX_URL = "https://www.sec.gov/Archives/edgar/daily-index/2026/QTR3/index.json"


class TestRateLimiter:
    def test_first_call_never_waits(self, clock, sleeper):
        limiter = RateLimiter(8, clock=clock, sleeper=sleeper)

        assert limiter.wait() == 0.0
        assert sleeper.calls == []

    def test_back_to_back_calls_sleep_the_full_gap(self, clock, sleeper):
        limiter = RateLimiter(8, clock=clock, sleeper=sleeper)
        limiter.wait()

        slept = limiter.wait()

        assert slept == pytest.approx(0.125)
        assert sleeper.calls == [pytest.approx(0.125)]

    def test_partial_gap_sleeps_only_the_remainder(self, clock, sleeper):
        limiter = RateLimiter(8, clock=clock, sleeper=sleeper)
        limiter.wait()
        clock.advance(0.05)

        assert limiter.wait() == pytest.approx(0.075)

    def test_spaced_calls_do_not_sleep(self, clock, sleeper):
        limiter = RateLimiter(8, clock=clock, sleeper=sleeper)
        limiter.wait()
        clock.advance(1.0)

        assert limiter.wait() == 0.0
        assert sleeper.calls == []

    def test_many_calls_hold_the_ceiling(self, clock, sleeper):
        limiter = RateLimiter(8, clock=clock, sleeper=sleeper)
        start = clock()

        for _ in range(81):
            limiter.wait()

        # 81 calls means 80 gaps of 0.125 s: exactly 8 per second, never more.
        assert clock() - start == pytest.approx(10.0)

    def test_rejects_a_non_positive_rate(self):
        with pytest.raises(ValueError, match="positive"):
            RateLimiter(0)


class TestEdgarClientInit:
    def test_declares_user_agent_and_encoding_on_the_session(self, session, clock, sleeper):
        EdgarClient("someone@example.com", session=session, clock=clock, sleeper=sleeper)

        assert session.headers["User-Agent"] == "edgar-13f-warehouse someone@example.com"
        assert session.headers["Accept-Encoding"] == "gzip, deflate"

    def test_rejects_a_contact_without_an_address(self):
        with pytest.raises(ValueError, match="email"):
            EdgarClient("nobody")

    def test_builds_a_real_session_by_default(self):
        client = EdgarClient("someone@example.com")

        assert client.session.headers["User-Agent"] == "edgar-13f-warehouse someone@example.com"

    def test_starts_with_zero_requests(self, session, clock, sleeper):
        client = EdgarClient("someone@example.com", session=session, clock=clock, sleeper=sleeper)

        assert client.requests_made == 0
        assert client.started_at == clock()

    def test_default_ceiling_is_below_the_sec_limit(self):
        assert DEFAULT_MAX_RPS < 10


@pytest.fixture
def client(session, clock, sleeper) -> EdgarClient:
    return EdgarClient("someone@example.com", session=session, clock=clock, sleeper=sleeper)


class TestEdgarClientGet:
    def test_returns_the_body_on_200(self, client, session):
        session.queue(FakeResponse(200, b'{"directory": {}}'))

        assert client.get(INDEX_URL) == b'{"directory": {}}'
        assert session.calls == [INDEX_URL]
        assert client.requests_made == 1

    def test_joins_a_path_onto_the_base_url(self, client, session):
        session.queue(FakeResponse(200, b"x"))

        client.get("/Archives/edgar/daily-index/2026/QTR3/index.json")

        assert session.calls == [INDEX_URL]

    def test_leaves_an_absolute_url_alone(self, client, session):
        session.queue(FakeResponse(200, b"x"))

        client.get("https://data.sec.gov/submissions/CIK0001535452.json")

        assert session.calls == ["https://data.sec.gov/submissions/CIK0001535452.json"]

    def test_retries_429_with_exponential_backoff(self, client, session, sleeper):
        session.queue(FakeResponse(429), FakeResponse(429), FakeResponse(200, b"ok"))

        assert client.get(INDEX_URL) == b"ok"
        assert len(session.calls) == 3
        assert client.requests_made == 3
        assert sleeper.calls == [1.0, 2.0]

    def test_retries_a_transport_failure(self, client, session, sleeper):
        session.queue(requests.ConnectionError("reset"), FakeResponse(200, b"ok"))

        assert client.get(INDEX_URL) == b"ok"
        assert len(session.calls) == 2
        assert sleeper.calls == [1.0]

    def test_gives_up_after_five_attempts(self, client, session, sleeper):
        session.queue(*[FakeResponse(503)] * 5)

        with pytest.raises(EdgarRetryableError) as excinfo:
            client.get(INDEX_URL)

        assert excinfo.value.status == 503
        assert excinfo.value.url == INDEX_URL
        assert len(session.calls) == 5
        assert sleeper.calls == [1.0, 2.0, 4.0, 8.0]

    def test_403_raises_at_once_without_a_retry(self, client, session, sleeper):
        session.queue(FakeResponse(403, b"<html>Undeclared Automated Tool</html>"))

        with pytest.raises(EdgarPermanentError) as excinfo:
            client.get(INDEX_URL)

        assert excinfo.value.status == 403
        assert INDEX_URL in str(excinfo.value)
        assert len(session.calls) == 1
        assert sleeper.calls == []

    def test_404_is_permanent_too(self, client, session):
        session.queue(FakeResponse(404))

        with pytest.raises(EdgarPermanentError):
            client.get(INDEX_URL)

        assert len(session.calls) == 1

    def test_counts_every_attempt_toward_the_rate(self, client, session):
        session.queue(FakeResponse(500), FakeResponse(200, b"ok"))

        client.get(INDEX_URL)

        assert client.requests_made == 2
