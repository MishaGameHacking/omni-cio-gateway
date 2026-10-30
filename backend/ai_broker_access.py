"""Fence paid AI against the current, server-stored broker connection.

Only its non-secret version stamp leaves the database read. No broker request or
decryption is needed. Disconnect/reconnect invalidates even the same ciphertext.
Already dispatched provider work cannot be recalled; its cost remains accounted.
"""
from contextlib import closing
import hmac
import sqlite3

try:
    from .ai_budget import BudgetDenied
except ImportError:
    from ai_budget import BudgetDenied


def broker_binding_in(db: sqlite3.Connection, user_id: int) -> str:
    if type(user_id) is not int or user_id <= 0:
        raise BudgetDenied('ai_broker_connection_required')
    try:
        row = db.execute('''SELECT u.tinvest_token_encrypted, v.stamp
            FROM users AS u LEFT JOIN broker_connection_versions AS v ON v.user_id=u.id
            WHERE u.id=?''', (user_id,)).fetchone()
    except sqlite3.OperationalError:
        raise BudgetDenied('ai_broker_binding_unavailable') from None
    if row is None or not isinstance(row[0], bytes) or not row[0]:
        raise BudgetDenied('ai_broker_connection_required')
    stamp = row[1]
    if not isinstance(stamp, str) or len(stamp) != 64 or any(c not in '0123456789abcdef' for c in stamp):
        raise BudgetDenied('ai_broker_binding_unavailable')
    return stamp


def broker_binding(connect, user_id: int) -> str:
    with closing(connect()) as db:
        return broker_binding_in(db, user_id)


def assert_broker_binding_in(db: sqlite3.Connection, user_id: int, expected: str) -> None:
    if not hmac.compare_digest(broker_binding_in(db, user_id), expected):
        raise BudgetDenied('ai_broker_connection_changed')


def assert_broker_binding(connect, user_id: int, expected: str) -> None:
    with closing(connect()) as db:
        assert_broker_binding_in(db, user_id, expected)
