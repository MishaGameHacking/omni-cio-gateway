"""Bounded lock holders leave shared database connections available for reads."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, nullcontext
from threading import Barrier, BoundedSemaphore, Lock
from uuid import UUID

import pytest

from omnicio import db as persistence


class _Cursor:
    def __init__(self) -> None:
        self.result = None

    def execute(self, query, params=()):
        if "pg_try_advisory_lock" in query:
            self.result = {"locked": True}
        elif "pg_advisory_unlock" in query:
            self.result = {"unlocked": True}
        elif "RETURNING user_id" in query:
            self.result = {"user_id": params[0]}
        else:
            self.result = None

    def fetchone(self):
        return self.result


class _Connection:
    def transaction(self):
        return nullcontext()

    def cursor(self):
        return nullcontext(_Cursor())

    def close(self):
        pass


class _BoundedPool:
    def __init__(self, *, max_size, **kwargs):
        self.max_size = max_size
        self.capacity = BoundedSemaphore(max_size)
        self.mutex = Lock()
        self.active = 0
        self.peak = 0

    @contextmanager
    def connection(self):
        if not self.capacity.acquire(timeout=0.5):
            raise TimeoutError("nested read exhausted shared pool")
        with self.mutex:
            self.active += 1
            self.peak = max(self.peak, self.active)
        try:
            yield _Connection()
        finally:
            with self.mutex:
                self.active -= 1
            self.capacity.release()


def test_eight_concurrent_owners_keep_capacity_for_nested_reads(monkeypatch):
    monkeypatch.setattr(persistence, "ConnectionPool", _BoundedPool)
    database = persistence.Database("unused-synthetic-dsn")
    all_admission_attempts = Barrier(8, timeout=5)

    def assess(index):
        with database.strategy_assessment_slot(UUID(int=index + 1)) as admitted:
            # All eight requests must reach admission before any owner performs
            # the nested database read required by the real broker service.
            all_admission_attempts.wait()
            if admitted:
                with database.pool.connection():
                    pass
            return admitted

    with ThreadPoolExecutor(max_workers=8) as executor:
        outcomes = list(executor.map(assess, range(8)))
    assert outcomes.count(True) == 2
    assert outcomes.count(False) == 6
    assert database.pool.max_size == 8
    assert database.pool.active == 0
    assert database.pool.peak <= 4
    # Returned capacity remains usable after all concurrent contexts close.
    with database.strategy_assessment_slot(UUID(int=100)) as admitted:
        assert admitted


@pytest.mark.parametrize("failure", [RuntimeError, persistence.DatabaseError])
def test_admission_capacity_is_released_on_body_error(monkeypatch, failure):
    monkeypatch.setattr(persistence, "ConnectionPool", _BoundedPool)
    database = persistence.Database("unused-synthetic-dsn")
    for index in range(5):
        with (
            pytest.raises(failure, match="synthetic failure"),
            database.strategy_assessment_slot(UUID(int=index + 1)) as admitted,
        ):
            assert admitted
            raise failure("synthetic failure")
    assert database.pool.active == 0
    with (
        database.strategy_assessment_slot(UUID(int=100)) as first,
        database.strategy_assessment_slot(UUID(int=101)) as second,
        database.strategy_assessment_slot(UUID(int=102)) as overflow,
    ):
        assert first and second
        assert not overflow


def test_admission_capacity_is_released_when_pool_acquisition_fails(monkeypatch):
    class UnavailablePool:
        def __init__(self, **kwargs):
            pass

        def connection(self):
            raise TimeoutError("synthetic pool unavailable")

    monkeypatch.setattr(persistence, "ConnectionPool", UnavailablePool)
    database = persistence.Database("unused-synthetic-dsn")
    for index in range(5):
        with (
            pytest.raises(TimeoutError, match="synthetic pool unavailable"),
            database.strategy_assessment_slot(UUID(int=index + 1)),
        ):
            pytest.fail("Unavailable pool cannot admit an assessment")
