from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading
import time
from typing import Any

from apps.api.app import _SerializedWebConnection


ROOT = Path(__file__).resolve().parents[1]


class _Cursor:
    rowcount = 1

    def fetchone(self) -> tuple[int]:
        return (1,)

    def fetchall(self) -> list[tuple[int]]:
        return [(1,)]


class _Transaction:
    def __init__(self, connection: "_Connection") -> None:
        self._connection = connection

    def __enter__(self) -> "_Transaction":
        with self._connection.state_lock:
            self._connection.active_transactions += 1
            self._connection.max_active_transactions = max(
                self._connection.max_active_transactions,
                self._connection.active_transactions,
            )
            if self._connection.active_transactions > 1:
                raise RuntimeError("OVERLAPPING_TRANSACTION_CONTEXTS")
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        del exc_type, exc, traceback
        with self._connection.state_lock:
            self._connection.active_transactions -= 1


class _Connection:
    def __init__(self) -> None:
        self.state_lock = threading.Lock()
        self.active_transactions = 0
        self.max_active_transactions = 0

    def transaction(self) -> _Transaction:
        return _Transaction(self)

    def execute(
        self,
        query: Any,
        params: Any = None,
        *,
        prepare: bool | None = None,
    ) -> _Cursor:
        del query, params, prepare
        time.sleep(0.003)
        return _Cursor()


def _request_transaction(connection: _SerializedWebConnection) -> tuple[int]:
    with connection.transaction():
        row = connection.execute("SELECT 1").fetchone()
        time.sleep(0.005)
        return row


def test_shared_web_connection_serializes_parallel_request_transactions() -> None:
    raw = _Connection()
    connection = _SerializedWebConnection(raw)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: _request_transaction(connection), range(16)))

    assert results == [(1,)] * 16
    assert raw.max_active_transactions == 1
    assert raw.active_transactions == 0


def test_local_private_app_wraps_connection_before_request_repositories() -> None:
    source = (ROOT / "apps" / "api" / "app.py").read_text(encoding="utf-8")

    raw_open = source.index('raw_connection = connect_postgres("")')
    configure = source.index("_configure_long_lived_web_connection(raw_connection)")
    serialize = source.index("connection = _SerializedWebConnection(raw_connection)")
    sessions = source.index("sessions = PostgresWebSessionRegistryV1(connection)")
    brokers = source.index("broker_repository = PostgresBrokerConnectionRepositoryV1(connection)")

    assert raw_open < configure < serialize < sessions < brokers
    assert "threading.RLock()" in source
    assert "WEB_RUNTIME_POSTGRES_TRANSACTION_UNAVAILABLE" in source
