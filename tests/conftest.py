"""Keep independent provider tests separate without bypassing market admission."""

import threading
from collections.abc import Iterator
from time import monotonic

import pytest

from omnicio import tbank


@pytest.fixture(autouse=True)
def isolated_market_request_budget(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    workers_before = set(threading.enumerate())
    monkeypatch.setattr(tbank, "_MARKET_REQUEST_BUDGET", tbank._MarketRequestBudget())
    yield
    # Let already completed work exit, but never close a forgotten runtime or
    # carry its threads silently into the next test's fresh admission budget.
    deadline = monotonic() + 1
    remaining = [worker for worker in threading.enumerate()
                 if worker not in workers_before
                 and worker.name.startswith(("public-market-", "market-enrichment"))]
    for worker in remaining:
        worker.join(timeout=max(0, deadline - monotonic()))
    assert not any(worker.is_alive() for worker in remaining), "market workers outlived their test"
