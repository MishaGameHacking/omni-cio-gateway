"""Deterministic cache concurrency checks; no external calls or production data."""
from collections import OrderedDict
from threading import Barrier, Event, Lock, RLock, Thread, local

import pytest

from backend import portfolio_details as details


class StripeKey(tuple):
    """Choose a lock stripe deterministically instead of depending on hash seed."""
    def __new__(cls, label, stripe):
        value = super().__new__(cls, (label,))
        value.stripe = stripe
        return value

    def __hash__(self):
        return self.stripe


class TrackedLock:
    def __init__(self):
        self.lock = RLock()
        self.counter_lock = Lock()
        self.attempts = 0
        self.second_attempt = Event()

    def __enter__(self):
        with self.counter_lock:
            self.attempts += 1
            if self.attempts == 2:
                self.second_attempt.set()
        self.lock.acquire()
        return self

    def __exit__(self, *_):
        self.lock.release()


@pytest.fixture
def isolated_cache(monkeypatch):
    monkeypatch.setattr(details, "_cache", OrderedDict())
    monkeypatch.setattr(details, "_request_locks", [RLock(), RLock()])
    monkeypatch.setattr(details, "_cache_context", local())


def start_worker(operation, values, errors):
    def run():
        try:
            values.append(operation())
        except BaseException as error:
            errors.append(error)
    thread = Thread(target=run, daemon=True)
    thread.start()
    return thread


def join_workers(*threads):
    for thread in threads:
        thread.join(timeout=5)
    assert not any(thread.is_alive() for thread in threads), "Cache workers deadlocked"


def test_inverse_nested_stripes_finish_without_ab_ba_deadlock(isolated_cache):
    barrier = Barrier(2)
    values, errors = [], []
    def operation(index):
        def outer_load():
            barrier.wait(timeout=5)
            return details.cached(StripeKey(f"inner-{index}", 1 - index), 60, lambda: index)
        return details.cached(StripeKey(f"outer-{index}", index), 60, outer_load)
    first = start_worker(lambda: operation(0), values, errors)
    second = start_worker(lambda: operation(1), values, errors)
    join_workers(first, second)
    assert errors == []
    assert sorted(values) == [0, 1]


def test_top_level_same_key_still_coalesces_one_loader(isolated_cache, monkeypatch):
    tracked = TrackedLock()
    monkeypatch.setattr(details, "_request_locks", [tracked])
    entered, release = Event(), Event()
    values, errors, calls = [], [], []
    def load():
        calls.append(1)
        entered.set()
        assert release.wait(timeout=5)
        return {"value": 7}
    first = start_worker(lambda: details.cached(("same-key",), 60, load), values, errors)
    assert entered.wait(timeout=5)
    second = start_worker(lambda: details.cached(("same-key",), 60, load), values, errors)
    try:
        assert tracked.second_attempt.wait(timeout=5)
    finally:
        release.set()
    join_workers(first, second)
    assert errors == []
    assert calls == [1]
    assert values == [{"value": 7}, {"value": 7}]


def test_loader_exception_clears_thread_local_nesting(isolated_cache, monkeypatch):
    tracked = TrackedLock()
    monkeypatch.setattr(details, "_request_locks", [tracked])
    def fail():
        raise ValueError("synthetic failure")
    with pytest.raises(ValueError, match="synthetic failure"):
        details.cached(("failed",), 60, fail)
    assert details._cache_context.loading is False
    assert details.cached(("next",), 60, lambda: 3) == 3
    assert tracked.attempts == 2


def test_cache_keeps_identity_expiry_and_copy_isolation(isolated_cache, monkeypatch):
    clock = [0]
    monkeypatch.setattr(details.time, "monotonic", lambda: clock[0])
    first_key = ("dashboard", "database", 1, "connection-one", "RUB")
    second_key = ("dashboard", "database", 1, "connection-two", "RUB")
    first = details.cached(first_key, 10, lambda: {"rows": [1]})
    first["rows"].append(99)
    cached = details.cached(first_key, 10, lambda: pytest.fail("unexpected reload"))
    assert cached == {"rows": [1]}
    cached["rows"].append(88)
    assert details.cached(first_key, 10, lambda: None) == {"rows": [1]}
    assert details.cached(second_key, 10, lambda: {"rows": [2]}) == {"rows": [2]}
    clock[0] = 11
    assert details.cached(first_key, 10, lambda: {"rows": [3]}) == {"rows": [3]}


def test_late_nested_load_does_not_overwrite_value_published_during_load(isolated_cache):
    entered, release = Event(), Event()
    values, errors = [], []
    shared = StripeKey("shared-inner", 0)
    def slow_inner():
        entered.set()
        assert release.wait(timeout=5)
        return {"source": "older"}
    def first_load():
        return details.cached(shared, 60, slow_inner)
    def second_load():
        return details.cached(shared, 60, lambda: {"source": "newer"})
    first = start_worker(lambda: details.cached(StripeKey("first-outer", 0), 60, first_load), values, errors)
    assert entered.wait(timeout=5)
    second = start_worker(lambda: details.cached(StripeKey("second-outer", 1), 60, second_load), values, errors)
    try:
        second.join(timeout=5)
        assert not second.is_alive(), "Nested cache read waited on another loader's stripe"
    finally:
        release.set()
    join_workers(first, second)
    assert errors == []
    assert details.cached(shared, 60, lambda: None) == {"source": "newer"}


def test_cache_remains_bounded(isolated_cache):
    for index in range(300):
        details.cached(("bounded", index), 60, lambda: {"synthetic": True})
    assert len(details._cache) == 256
