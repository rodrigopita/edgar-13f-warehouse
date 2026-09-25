"""Test doubles for the EDGAR client: a clock, a sleeper and a scripted HTTP session."""


class FakeClock:
    """Monotonic clock under test control. advance() moves it forward."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeSleeper:
    """Records every requested sleep and advances the clock instead of waiting."""

    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)
        self.clock.advance(seconds)


class FakeResponse:
    """The two attributes of requests.Response the client reads."""

    def __init__(self, status_code: int, content: bytes = b"") -> None:
        self.status_code = status_code
        self.content = content


class FakeSession:
    """Returns scripted responses in order and records every URL requested.

    A queued exception is raised instead of returned, which is how a test
    scripts a connection error or a timeout.
    """

    def __init__(self) -> None:
        self.headers: dict[str, str] = {}
        self.calls: list[str] = []
        self._responses: list[FakeResponse | Exception] = []

    def queue(self, *responses: FakeResponse | Exception) -> None:
        self._responses.extend(responses)

    def get(self, url: str, timeout: tuple[float, float] | None = None) -> FakeResponse:
        self.calls.append(url)
        if not self._responses:
            raise AssertionError(f"unexpected request, nothing queued: {url}")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
