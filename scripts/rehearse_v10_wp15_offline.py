from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from omni_cio.adapters.tinvest_read_v1 import (
    AccountBindingError,
    CursorProgressError,
    FreshnessState,
    TInvestReadAdapter,
    TInvestReadPolicyV1,
)


NOW = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
ACCOUNT_ID = "synthetic-owner-account"
ACCOUNT_FINGERPRINT = hashlib.sha256(ACCOUNT_ID.encode("utf-8")).hexdigest()


def _money(units: str, *, nano: int = 0) -> dict[str, Any]:
    return {
        "units": units,
        "nano": nano,
        "currency": "RUB",
    }


def _account(account_id: str = ACCOUNT_ID) -> dict[str, Any]:
    return {
        "id": account_id,
        "type": "ACCOUNT_TYPE_TINKOFF",
        "status": "ACCOUNT_STATUS_OPEN",
        "access_level": "ACCOUNT_ACCESS_LEVEL_READ_ONLY",
    }


def _portfolio() -> dict[str, Any]:
    return {
        "total_amount_portfolio": _money("12345", nano=500_000_000),
        "positions": [
            {
                "instrument_uid": "uid-synthetic",
                "position_uid": "position-synthetic",
                "figi": "BBG000000001",
                "instrument_type": "share",
                "quantity": {"units": "10", "nano": 0},
                "blocked": {"units": "1", "nano": 0},
                "current_price": _money("300", nano=500_000_000),
            }
        ],
    }


def _instrument() -> dict[str, Any]:
    return {
        "instrument": {
            "uid": "uid-synthetic",
            "position_uid": "position-synthetic",
            "figi": "BBG000000001",
            "isin": "RU0000000001",
            "ticker": "SYNTH",
            "class_code": "TQBR",
            "name": "Synthetic Instrument",
            "instrument_type": "share",
            "currency": "RUB",
            "lot": 10,
        }
    }


def _operation(operation_id: str) -> dict[str, Any]:
    return {
        "id": operation_id,
        "date": "2026-08-10T10:00:00+00:00",
        "type": "OPERATION_TYPE_BUY",
        "state": "OPERATION_STATE_EXECUTED",
        "instrument_uid": "uid-synthetic",
        "position_uid": "position-synthetic",
        "figi": "BBG000000001",
        "payment": _money("-3000"),
        "price": _money("300"),
        "commission": _money("-1"),
        "quantity": 10,
        "quantity_done": 10,
        "name": "Synthetic buy",
        "description": "Synthetic executed operation",
    }


class _Users:
    def __init__(self, accounts: list[dict[str, Any]]) -> None:
        self._accounts = accounts

    def get_accounts(self) -> dict[str, Any]:
        return {"accounts": self._accounts}

    def get_user_tariff(self) -> dict[str, Any]:
        return {
            "unary_limits": [
                {
                    "limit_per_minute": 120,
                    "methods": [],
                }
            ]
        }


class _Operations:
    def __init__(
        self,
        pages: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self._pages = pages or {
            "": {
                "items": [],
                "has_next": False,
                "next_cursor": "",
            }
        }

    def get_portfolio(self, *, account_id: str) -> dict[str, Any]:
        if account_id != ACCOUNT_ID:
            raise AssertionError("synthetic account binding drift")
        return _portfolio()

    def get_positions(self, *, account_id: str) -> dict[str, Any]:
        if account_id != ACCOUNT_ID:
            raise AssertionError("synthetic account binding drift")
        return {
            "money": [_money("1000")],
            "blocked": [_money("100")],
        }

    def get_operations_by_cursor(self, request: Any) -> dict[str, Any]:
        if request.account_id != ACCOUNT_ID:
            raise AssertionError("synthetic account binding drift")
        return self._pages[request.cursor]


class _Instruments:
    def get_instrument_by(self, *, id_type: Any, id: str) -> dict[str, Any]:
        del id_type
        if id not in {
            "uid-synthetic",
            "position-synthetic",
            "BBG000000001",
        }:
            raise AssertionError("unexpected synthetic instrument lookup")
        return _instrument()


class _Client:
    def __init__(
        self,
        *,
        accounts: list[dict[str, Any]] | None = None,
        pages: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.users = _Users(accounts or [_account()])
        self.operations = _Operations(pages)
        self.instruments = _Instruments()

    def __enter__(self) -> _Client:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        del exc_type, exc, tb


def _adapter(
    client: _Client,
    *,
    expected_fingerprint: str = ACCOUNT_FINGERPRINT,
) -> TInvestReadAdapter:
    return TInvestReadAdapter(
        client_factory=lambda: client,
        expected_account_fingerprint_sha256=expected_fingerprint,
        policy=TInvestReadPolicyV1(
            stale_after_seconds=300,
            max_operation_pages=2,
        ),
        clock=lambda: NOW,
        monotonic=lambda: 0.0,
        sleeper=lambda _: None,
        random_unit=lambda: 0.0,
    )


def _wrong_account_rejected() -> bool:
    wrong = hashlib.sha256(b"wrong-synthetic-account").hexdigest()
    try:
        _adapter(
            _Client(),
            expected_fingerprint=wrong,
        ).read_snapshot()
    except AccountBindingError as exc:
        return str(exc) == "OWNER_ACCOUNT_FINGERPRINT_MISMATCH"
    return False


def _cursor_loop_rejected() -> bool:
    client = _Client(
        pages={
            "": {
                "items": [],
                "has_next": True,
                "next_cursor": "",
            }
        }
    )
    try:
        _adapter(client).read_operations()
    except CursorProgressError:
        return True
    return False


def _read_only_source_guard() -> bool:
    adapter_path = (
        Path(__file__).resolve().parents[1]
        / "omni_cio"
        / "adapters"
        / "tinvest_read_v1.py"
    )
    source = adapter_path.read_text(encoding="utf-8").lower()
    forbidden = (
        "tinvest_trading_token",
        ".orders",
        ".stop_orders",
        "post_order",
        "cancel_order",
        "replace_order",
        "sandbox_client",
    )
    return all(marker not in source for marker in forbidden)


def main() -> int:
    duplicate_a = _operation("synthetic-operation-a")
    duplicate_b = dict(duplicate_a)
    duplicate_b["id"] = "synthetic-operation-b"
    operations_client = _Client(
        pages={
            "": {
                "items": [duplicate_a],
                "has_next": True,
                "next_cursor": "cursor-2",
            },
            "cursor-2": {
                "items": [duplicate_b],
                "has_next": False,
                "next_cursor": "",
            },
        }
    )

    snapshot = _adapter(_Client()).read_snapshot(
        evaluated_at=NOW + timedelta(seconds=301)
    )
    operations = _adapter(operations_client).read_operations()

    checks = {
        "expected_account_binding": (
            snapshot.account.account_fingerprint_sha256 == ACCOUNT_FINGERPRINT
        ),
        "account_masked": ACCOUNT_ID not in snapshot.model_dump_json(),
        "canonical_snapshot": (
            snapshot.normalized_position_count == 1
            and snapshot.unresolved_position_count == 0
            and snapshot.snapshot.positions[0].quantity_units == Decimal("10")
        ),
        "freshness_stale_transition": snapshot.freshness.state
        == FreshnessState.STALE,
        "cursor_deduplication": (
            operations.pages_loaded == 2
            and operations.duplicates_removed == 1
            and len(operations.operations) == 1
        ),
        "wrong_account_rejected": _wrong_account_rejected(),
        "cursor_loop_rejected": _cursor_loop_rejected(),
        "read_only_source_guard": _read_only_source_guard(),
    }
    passed = all(checks.values())

    evidence = {
        "schema_version": "1",
        "work_package": "WP15",
        "audit": "deterministic_offline_tinvest_read",
        "status": "PASS" if passed else "FAIL",
        "synthetic_only": True,
        "real_secret_values_used": False,
        "real_account_identifiers_used": False,
        "private_portfolio_payload_used": False,
        "checks": checks,
        "synthetic_counts": {
            "portfolio_positions": snapshot.normalized_position_count,
            "operation_pages": operations.pages_loaded,
            "operation_duplicates_removed": operations.duplicates_removed,
        },
        "freshness_state": snapshot.freshness.state.value,
        "throttle_source": snapshot.throttle.source,
        "authority": {
            "broker_read": True,
            "broker_write": False,
            "trading_methods": False,
            "real_trading_enabled": False,
        },
    }
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
