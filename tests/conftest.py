import pytest

from tests.fakes import FakeClock, FakeSession, FakeSleeper


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def sleeper(clock: FakeClock) -> FakeSleeper:
    return FakeSleeper(clock)


@pytest.fixture
def session() -> FakeSession:
    return FakeSession()
