from __future__ import annotations

from collections.abc import Callable, Sequence
import threading
from typing import Any

from omni_cio.persistence.migration import CursorLike, TransactionContext


class _SerializedCursor:
    def __init__(self, cursor: Any, lock: Any) -> None:
        self._cursor = cursor
        self._lock = lock
        self.rowcount = int(cursor.rowcount)

    def fetchone(self) -> Sequence[Any] | None:
        with self._lock:
            return self._cursor.fetchone()

    def fetchall(self) -> list[Sequence[Any]]:
        with self._lock:
            return list(self._cursor.fetchall())


class _SerializedTransaction:
    def __init__(self, owner: _SerializedWebConnection, lock: Any) -> None:
        self._owner = owner
        self._lock = lock
        self._transaction: Any | None = None

    def __enter__(self) -> Any:
        self._lock.acquire()
        try:
            connection = self._owner._connection_for_use_locked()
            self._transaction = connection.transaction()
            return self._transaction.__enter__()
        except BaseException:
            self._transaction = None
            self._lock.release()
            raise

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool | None:
        transaction = self._transaction
        if transaction is None:
            raise RuntimeError("WEB_RUNTIME_POSTGRES_TRANSACTION_UNAVAILABLE")
        try:
            return transaction.__exit__(exc_type, exc, traceback)
        finally:
            self._transaction = None
            self._lock.release()


class _SerializedWebConnection:
    """Serialize one PostgreSQL session and recover before a later operation."""

    def __init__(
        self,
        connection: Any,
        *,
        reconnect: Callable[[], Any] | None = None,
    ) -> None:
        self._connection = connection
        self._reconnect = reconnect
        self._lock = threading.RLock()

    def _connection_for_use_locked(self) -> Any:
        if not bool(getattr(self._connection, "closed", False)):
            return self._connection
        if self._reconnect is None:
            raise RuntimeError("WEB_RUNTIME_POSTGRES_CONNECTION_CLOSED")
        replacement = self._reconnect()
        if bool(getattr(replacement, "closed", False)):
            raise RuntimeError("WEB_RUNTIME_POSTGRES_RECONNECT_INVALID")
        self._connection = replacement
        return replacement

    def execute(
        self,
        query: Any,
        params: Sequence[Any] | None = None,
        *,
        prepare: bool | None = None,
    ) -> CursorLike:
        with self._lock:
            connection = self._connection_for_use_locked()
            cursor = connection.execute(query, params, prepare=prepare)
            return _SerializedCursor(cursor, self._lock)

    def transaction(self) -> TransactionContext:
        return _SerializedTransaction(self, self._lock)


def _configure_long_lived_web_connection(connection: Any) -> None:
    """Keep request transactions explicit instead of nesting under startup SELECTs."""

    try:
        connection.autocommit = True
    except Exception as exc:
        raise RuntimeError("WEB_RUNTIME_POSTGRES_AUTOCOMMIT_REQUIRED") from exc
    if getattr(connection, "autocommit", None) is not True:
        raise RuntimeError("WEB_RUNTIME_POSTGRES_AUTOCOMMIT_REQUIRED")
