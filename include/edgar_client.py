"""HTTP client for sec.gov: declared User-Agent, request ceiling, retry policy.

Every request to EDGAR in this project goes through EdgarClient. The module
imports nothing from Airflow so it parses fast and tests without it.
"""

import logging
import time
from collections.abc import Callable

import requests
from tenacity import (
    RetryCallState,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

BASE_URL = "https://www.sec.gov"
# The SEC's published maximum is 10 requests per second. The ceiling stays below it.
DEFAULT_MAX_RPS = 8
USER_AGENT_TEMPLATE = "edgar-13f-warehouse {contact}"
# Seconds to connect, seconds to wait for the first byte.
REQUEST_TIMEOUT = (5, 30)
# Five attempts with waits of 1, 2, 4 and 8 seconds between them, 15 seconds in
# all. That covers a transient error, not a rate block: sec.gov lifts a block only
# after ten minutes under the limit, which is left to the task retry (5 minutes in
# the DAG) rather than to a client that would hold a pool slot while sleeping.
RETRY_ATTEMPTS = 5
RETRY_WAIT_MIN = 1.0
RETRY_WAIT_MAX = 30.0
# One rate line in the task log per this many requests.
LOG_EVERY = 100

logger = logging.getLogger(__name__)

Clock = Callable[[], float]
Sleeper = Callable[[float], None]


class EdgarError(Exception):
    """Base class for failures talking to sec.gov."""

    def __init__(self, status: int, url: str, message: str | None = None) -> None:
        self.status = status
        self.url = url
        super().__init__(message or f"HTTP {status} for {url}")


class EdgarRetryableError(EdgarError):
    """429, 5xx, or a transport failure: the same request may succeed after a wait."""


class EdgarPermanentError(EdgarError):
    """403, 404 and any other status a retry cannot fix.

    sec.gov answers 403 both to an undeclared User-Agent and to a file that
    does not exist, so this error never triggers a retry and carries the URL.
    """


class RateLimiter:
    """Minimum spacing between calls: at most max_rps calls per second.

    The clock and the sleeper are injected so tests run without waiting.
    """

    def __init__(
        self,
        max_rps: float,
        clock: Clock = time.monotonic,
        sleeper: Sleeper = time.sleep,
    ) -> None:
        if max_rps <= 0:
            raise ValueError("max_rps must be positive")
        self.min_interval = 1.0 / max_rps
        self._clock = clock
        self._sleep = sleeper
        self._last: float | None = None

    def wait(self) -> float:
        """Block until the next call is allowed. Returns the seconds slept."""
        now = self._clock()
        slept = 0.0
        if self._last is not None:
            remaining = self.min_interval - (now - self._last)
            if remaining > 0:
                self._sleep(remaining)
                slept = remaining
        self._last = now + slept
        return slept


class EdgarClient:
    """Fetches bytes from sec.gov under the declared User-Agent and the rate ceiling."""

    def __init__(
        self,
        contact: str,
        max_rps: float = DEFAULT_MAX_RPS,
        session: requests.Session | None = None,
        clock: Clock = time.monotonic,
        sleeper: Sleeper = time.sleep,
    ) -> None:
        if "@" not in contact:
            raise ValueError(
                "contact must be an email address; the SEC asks for a reachable "
                "contact in the User-Agent"
            )
        self.user_agent = USER_AGENT_TEMPLATE.format(contact=contact)
        self.session = session if session is not None else requests.Session()
        self.session.headers.update(
            {"User-Agent": self.user_agent, "Accept-Encoding": "gzip, deflate"}
        )
        self._limiter = RateLimiter(max_rps, clock=clock, sleeper=sleeper)
        self._clock = clock
        self._sleep = sleeper
        self.requests_made = 0
        self.retries = 0
        self.started_at = clock()
        # The same injected sleeper serves the limiter and the backoff, so a test
        # that fakes one fakes both. reraise=True surfaces the last EdgarRetryableError
        # instead of tenacity's own RetryError.
        self._retrying = Retrying(
            retry=retry_if_exception_type(EdgarRetryableError),
            wait=wait_exponential(multiplier=1, min=RETRY_WAIT_MIN, max=RETRY_WAIT_MAX),
            stop=stop_after_attempt(RETRY_ATTEMPTS),
            before_sleep=self._note_retry,
            reraise=True,
            sleep=sleeper,
        )

    def get(self, url: str) -> bytes:
        """Fetch a URL, or a path under sec.gov, with the retry policy applied.

        Raises EdgarRetryableError after the last failed attempt and
        EdgarPermanentError at once, without a retry.
        """
        return self._retrying(self._fetch, self._absolute(url))

    def head(self, url: str) -> dict[str, str]:
        """Response headers of a HEAD request, under the same limiter and retry policy.

        Used to learn a file's Content-Length before deciding to download it.
        """
        return self._retrying(self._fetch_head, self._absolute(url))

    def stats(self) -> dict[str, float | int]:
        """Counters since construction, for the task log and the audit record.

        requests_per_second is the observed average, attempts included, so the
        README can quote the rate the walker held against the SEC's limit.
        """
        elapsed = self._clock() - self.started_at
        return {
            "requests_made": self.requests_made,
            "retries": self.retries,
            "elapsed_seconds": elapsed,
            "requests_per_second": self.requests_made / elapsed if elapsed > 0 else 0.0,
        }

    def _fetch(self, url: str) -> bytes:
        """One attempt: wait for the limiter, request, map the status to a result."""
        self._before_request()
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as exc:
            raise EdgarRetryableError(0, url, f"{type(exc).__name__} for {url}") from exc
        self._raise_unless_ok(response.status_code, url)
        return response.content

    def _fetch_head(self, url: str) -> dict[str, str]:
        self._before_request()
        try:
            response = self.session.head(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        except requests.RequestException as exc:
            raise EdgarRetryableError(0, url, f"{type(exc).__name__} for {url}") from exc
        self._raise_unless_ok(response.status_code, url)
        return dict(response.headers)

    def _before_request(self) -> None:
        """Every attempt, GET or HEAD, waits for the limiter and counts toward the rate."""
        self._limiter.wait()
        self.requests_made += 1
        if self.requests_made % LOG_EVERY == 0:
            self._log_rate()

    @staticmethod
    def _raise_unless_ok(status: int, url: str) -> None:
        if status == 200:
            return
        if status == 429 or 500 <= status < 600:
            raise EdgarRetryableError(status, url)
        raise EdgarPermanentError(status, url)

    def _note_retry(self, retry_state: RetryCallState) -> None:
        """tenacity hook, called before each backoff sleep."""
        self.retries += 1
        outcome = retry_state.outcome
        error = outcome.exception() if outcome is not None else None
        wait = retry_state.next_action.sleep if retry_state.next_action is not None else 0.0
        logger.warning(
            "edgar attempt %d failed (%s), retrying in %.0f s",
            retry_state.attempt_number,
            error,
            wait,
        )

    def _log_rate(self) -> None:
        s = self.stats()
        logger.info(
            "edgar rate: %d requests, %d retries, %.1f s elapsed, %.2f req/s",
            s["requests_made"],
            s["retries"],
            s["elapsed_seconds"],
            s["requests_per_second"],
        )

    @staticmethod
    def _absolute(url: str) -> str:
        if url.startswith(("https://", "http://")):
            return url
        return f"{BASE_URL}/{url.lstrip('/')}"
