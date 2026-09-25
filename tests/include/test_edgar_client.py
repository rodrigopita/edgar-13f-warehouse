import pytest

from include.edgar_client import DEFAULT_MAX_RPS, EdgarClient, RateLimiter


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
