from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from typing import Any

import pytest

from omni_cio.adapters.tinvest_read_v1 import (
    CursorProgressError,
    TInvestReadAdapter,
    TInvestReadPolicyV1,
)


ACCOUNT_ID = "synthetic-owner-account"
ACCOUNT_FINGERPRINT = hashlib.sha256(ACCOUNT_ID.encode("utf-8")).hexdigest()
NOW = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)


class _Users:
    def get_accounts(self) -> dict[str, Any]:
        return {
            "accounts": [
                {
                    "id": ACCOUNT_ID,
                    "type": "ACCOUNT_TYPE_TINKOFF",
                    "status": "ACCOUNT_STATUS_OPEN",
                    "access_level": "ACCOUNT_ACCESS_LEVEL_READ_ONLY",
                }
            ]
        }

    def get_user_tariff(self) -> dict[str, Any]:
        return {"unary_limits": [{"limit_per_minute": 120, "methods": []}]}


class _Operations:
    def __init__(self) -> None:
        self.cursors: list[str] = []

    def get_operations_by_cursor(self, request: Any) -> dict[str, Any]:
        self.cursors.append(request.cursor)
        if request.cursor == "":
            return {
                "items": [],
                "has_next": True,
                "next_cursor": "cursor-2",
            }
        if request.cursor == "cursor-2":
            return {
                "items": [],
                "has_next": False,
                "next_cursor": "",
            }
        raise AssertionError("unexpected cursor")


class _Client:
    def __init__(self, operations: _Operations) -> None:
        self.users = _Users()
        self.operations = operations

    def __enter__(self) -> _Client:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        del exc_type, exc, tb


def _adapter(operations: _Operations) -> TInvestReadAdapter:
    return TInvestReadAdapter(
        client_factory=lambda: _Client(operations),
        expected_account_fingerprint_sha256=ACCOUNT_FINGERPRINT,
        policy=TInvestReadPolicyV1(max_operation_pages=1),
        clock=lambda: NOW,
        monotonic=lambda: 0.0,
        sleeper=lambda _: None,
        random_unit=lambda: 0.0,
    )


def test_bounded_poll_returns_resume_cursor_and_next_cycle_continues() -> None:
    operations = _Operations()
    reader = _adapter(operations)

    first = reader.read_operations()
    second = reader.read_operations(start_cursor=first.next_cursor or "")

    assert first.truncated is True
    assert first.next_cursor == "cursor-2"
    assert second.truncated is False
    assert second.next_cursor is None
    assert operations.cursors == ["", "cursor-2"]


def test_resume_cursor_length_is_fail_closed() -> None:
    with pytest.raises(CursorProgressError, match="OPERATIONS_START_CURSOR_TOO_LONG"):
        _adapter(_Operations()).read_operations(start_cursor="x" * 2049)
