from __future__ import annotations

from collections.abc import Callable, Sequence
from queue import Empty, Full, LifoQueue
import threading
import time
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


class _BufferedCursor:
    def __init__(self, *, rowcount: int, rows: list[Sequence[Any]]) -> None:
        self.rowcount = rowcount
        self._rows = list(rows)
        self._index = 0

    def fetchone(self) -> Sequence[Any] | None:
        if self._index >= len(self._rows):
            return None
        row = self._rows[self._index]
        self._index += 1
        return row

    def fetchall(self) -> list[Sequence[Any]]:
        rows = self._rows[self._index :]
        self._index = len(self._rows)
        return list(rows)


class _PooledTransaction:
    def __init__(self, owner: _BoundedWebConnectionPool) -> None:
        self._owner = owner
        self._connection: Any | None = None
        self._transaction: Any | None = None
        self._owns_connection = False

    def __enter__(self) -> Any:
        connection, owns_connection = self._owner._checkout()
        self._connection = connection
        self._owns_connection = owns_connection
        if owns_connection:
            self._owner._bind_transaction_connection(connection)
        try:
            transaction = connection.transaction()
            self._transaction = transaction
            return transaction.__enter__()
        except BaseException:
            self._transaction = None
            if owns_connection:
                self._owner._unbind_transaction_connection(connection)
                self._owner._discard_connection(connection)
            self._connection = None
            self._owns_connection = False
            raise

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool | None:
        transaction = self._transaction
        connection = self._connection
        if transaction is None or connection is None:
            raise RuntimeError("WEB_RUNTIME_POSTGRES_TRANSACTION_UNAVAILABLE")
        try:
            result = transaction.__exit__(exc_type, exc, traceback)
        except BaseException:
            if self._owns_connection:
                self._owner._unbind_transaction_connection(connection)
                self._owner._discard_connection(connection)
            raise
        else:
            if self._owns_connection:
                self._owner._unbind_transaction_connection(connection)
                self._owner._return_connection(connection)
            return result
        finally:
            self._transaction = None
            self._connection = None
            self._owns_connection = False


class _BoundedWebConnectionPool:
    """Bounded PostgreSQL pool with transaction-local connection affinity."""

    def __init__(
        self,
        initial_connection: Any,
        *,
        connect: Callable[[], Any],
        max_size: int,
        acquire_timeout_seconds: float,
    ) -> None:
        if isinstance(max_size, bool) or not isinstance(max_size, int) or max_size < 1:
            raise ValueError("WEB_RUNTIME_POSTGRES_POOL_SIZE_INVALID")
        if (
            isinstance(acquire_timeout_seconds, bool)
            or not isinstance(acquire_timeout_seconds, (int, float))
            or acquire_timeout_seconds <= 0
        ):
            raise ValueError("WEB_RUNTIME_POSTGRES_POOL_TIMEOUT_INVALID")
        if bool(getattr(initial_connection, "closed", False)):
            raise RuntimeError("WEB_RUNTIME_POSTGRES_POOL_INITIAL_CONNECTION_CLOSED")

        self._connect = connect
        self._max_size = max_size
        self._acquire_timeout_seconds = float(acquire_timeout_seconds)
        self._available: LifoQueue[Any] = LifoQueue(maxsize=max_size)
        self._available.put_nowait(initial_connection)
        self._count_lock = threading.Lock()
        self._created = 1
        self._local = threading.local()

    def _transaction_connection(self) -> Any | None:
        return getattr(self._local, "transaction_connection", None)

    def _bind_transaction_connection(self, connection: Any) -> None:
        if self._transaction_connection() is not None:
            raise RuntimeError("WEB_RUNTIME_POSTGRES_TRANSACTION_AFFINITY_DRIFT")
        self._local.transaction_connection = connection

    def _unbind_transaction_connection(self, connection: Any) -> None:
        if self._transaction_connection() is not connection:
            raise RuntimeError("WEB_RUNTIME_POSTGRES_TRANSACTION_AFFINITY_DRIFT")
        del self._local.transaction_connection

    def _reserve_connection_slot(self) -> bool:
        with self._count_lock:
            if self._created >= self._max_size:
                return False
            self._created += 1
            return True

    def _release_connection_slot(self) -> None:
        with self._count_lock:
            if self._created < 1:
                raise RuntimeError("WEB_RUNTIME_POSTGRES_POOL_STATE_INVALID")
            self._created -= 1

    def _new_connection_for_reserved_slot(self) -> Any:
        try:
            connection = self._connect()
        except BaseException:
            self._release_connection_slot()
            raise
        if bool(getattr(connection, "closed", False)):
            self._release_connection_slot()
            raise RuntimeError("WEB_RUNTIME_POSTGRES_RECONNECT_INVALID")
        return connection

    def _checkout(self) -> tuple[Any, bool]:
        transaction_connection = self._transaction_connection()
        if transaction_connection is not None:
            if bool(getattr(transaction_connection, "closed", False)):
                raise RuntimeError(
                    "WEB_RUNTIME_POSTGRES_TRANSACTION_CONNECTION_CLOSED"
                )
            return transaction_connection, False

        deadline = time.monotonic() + self._acquire_timeout_seconds
        while True:
            try:
                connection = self._available.get_nowait()
            except Empty:
                if self._reserve_connection_slot():
                    return self._new_connection_for_reserved_slot(), True
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeError("WEB_RUNTIME_POSTGRES_POOL_EXHAUSTED")
                try:
                    connection = self._available.get(timeout=remaining)
                except Empty:
                    raise RuntimeError(
                        "WEB_RUNTIME_POSTGRES_POOL_EXHAUSTED"
                    ) from None

            if bool(getattr(connection, "closed", False)):
                self._release_connection_slot()
                continue
            return connection, True

    def _discard_connection(self, connection: Any) -> None:
        close = getattr(connection, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass
        self._release_connection_slot()

    def _return_connection(self, connection: Any) -> None:
        if bool(getattr(connection, "closed", False)):
            self._release_connection_slot()
            return
        try:
            self._available.put_nowait(connection)
        except Full as exc:
            self._discard_connection(connection)
            raise RuntimeError("WEB_RUNTIME_POSTGRES_POOL_STATE_INVALID") from exc

    @staticmethod
    def _buffer_cursor(cursor: Any) -> _BufferedCursor:
        rows: list[Sequence[Any]] = []
        if getattr(cursor, "description", None) is not None:
            rows = list(cursor.fetchall())
        return _BufferedCursor(
            rowcount=int(cursor.rowcount),
            rows=rows,
        )

    def execute(
        self,
        query: Any,
        params: Sequence[Any] | None = None,
        *,
        prepare: bool | None = None,
    ) -> CursorLike:
        connection, owns_connection = self._checkout()
        if not owns_connection:
            return connection.execute(query, params, prepare=prepare)
        try:
            cursor = connection.execute(query, params, prepare=prepare)
            result = self._buffer_cursor(cursor)
        except BaseException:
            self._discard_connection(connection)
            raise
        self._return_connection(connection)
        return result

    def transaction(self) -> TransactionContext:
        return _PooledTransaction(self)
