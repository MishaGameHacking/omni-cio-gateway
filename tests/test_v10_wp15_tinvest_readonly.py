from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
from pathlib import Path
from typing import Any

import grpc
import pytest

from omni_cio.adapters.tinvest_read_v1 import (
    AccountBindingError,
    BrokerDataError,
    CursorProgressError,
    FreshnessState,
    TInvestReadAdapter,
    TInvestReadAdapterError,
    TInvestReadPolicyV1,
)
from omni_cio.contracts.v1.common import Completeness, DataQuality


NOW = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
ACCOUNT_ID = "account-owner-0001"
ACCOUNT_FINGERPRINT = hashlib.sha256(ACCOUNT_ID.encode("utf-8")).hexdigest()


def account(
    account_id: str = ACCOUNT_ID,
    *,
    status: str = "ACCOUNT_STATUS_OPEN",
    access_level: str = "ACCOUNT_ACCESS_LEVEL_READ_ONLY",
) -> dict[str, Any]:
    return {
        "id": account_id,
        "name": "OWNER",
        "type": "ACCOUNT_TYPE_TINKOFF",
        "status": status,
        "access_level": access_level,
    }


def money(units: str, *, currency: str = "RUB", nano: int = 0) -> dict[str, Any]:
    return {"units": units, "nano": nano, "currency": currency}


def quotation(units: str, *, nano: int = 0) -> dict[str, Any]:
    return {"units": units, "nano": nano}


def instrument(
    *,
    uid: str = "uid-sber",
    position_uid: str = "position-sber",
    figi: str = "BBG004730N88",
) -> dict[str, Any]:
    return {
        "instrument": {
            "uid": uid,
            "position_uid": position_uid,
            "figi": figi,
            "isin": "RU0009029540",
            "ticker": "SBER",
            "class_code": "TQBR",
            "name": "Sberbank",
            "instrument_type": "share",
            "currency": "rub",
            "lot": 10,
        }
    }


def portfolio() -> dict[str, Any]:
    return {
        "total_amount_portfolio": money("12345", nano=500_000_000),
        "positions": [
            {
                "instrument_uid": "uid-sber",
                "position_uid": "position-sber",
                "figi": "BBG004730N88",
                "instrument_type": "share",
                "quantity": quotation("10"),
                "blocked": False,
                "blocked_lots": quotation("1"),
                "current_price": money("300", nano=500_000_000),
            }
        ],
        "virtual_positions": [],
    }


def positions() -> dict[str, Any]:
    return {
        "money": [money("1000")],
        "blocked": [money("100")],
        "securities": [
            {
                "instrument_uid": "uid-sber",
                "balance": 10,
                "blocked": 1,
            }
        ],
        "limits_loading_in_progress": False,
    }


class FakeRpcError(grpc.RpcError):
    def __init__(self, code: grpc.StatusCode) -> None:
        super().__init__()
        self._code = code

    def code(self) -> grpc.StatusCode:
        return self._code


class FakeUsers:
    def __init__(self, accounts: list[dict[str, Any]]) -> None:
        self.accounts = accounts
        self.tariff: dict[str, Any] = {
            "unary_limits": [{"limit_per_minute": 120, "methods": []}]
        }

    def get_accounts(self) -> dict[str, Any]:
        return {"accounts": self.accounts}

    def get_user_tariff(self) -> dict[str, Any]:
        return self.tariff


class FakeOperations:
    def __init__(
        self,
        *,
        portfolio_payload: dict[str, Any] | None = None,
        positions_payload: dict[str, Any] | None = None,
        operation_pages: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.portfolio_payload = portfolio_payload or portfolio()
        self.positions_payload = positions_payload or positions()
        self.operation_pages = operation_pages or {
            "": {"items": [], "has_next": False, "next_cursor": ""}
        }
        self.portfolio_failures: list[BaseException] = []
        self.portfolio_calls = 0
        self.position_calls = 0
        self.operation_calls = 0

    def get_portfolio(self, *, account_id: str) -> dict[str, Any]:
        assert account_id == ACCOUNT_ID
        self.portfolio_calls += 1
        if self.portfolio_failures:
            raise self.portfolio_failures.pop(0)
        return self.portfolio_payload

    def get_positions(self, *, account_id: str) -> dict[str, Any]:
        assert account_id == ACCOUNT_ID
        self.position_calls += 1
        return self.positions_payload

    def get_operations_by_cursor(self, request: Any) -> dict[str, Any]:
        assert request.account_id == ACCOUNT_ID
        self.operation_calls += 1
        return self.operation_pages[request.cursor]


class FakeInstruments:
    def __init__(self, payload: dict[str, Any] | None = None) -> None:
        self.payload = payload or instrument()
        self.calls = 0

    def get_instrument_by(self, *, id_type: Any, id: str) -> dict[str, Any]:
        del id_type
        assert id in {"uid-sber", "position-sber", "BBG004730N88"}
        self.calls += 1
        return self.payload


class FakeClient:
    def __init__(
        self,
        *,
        accounts: list[dict[str, Any]] | None = None,
        operations: FakeOperations | None = None,
        instruments: FakeInstruments | None = None,
    ) -> None:
        self.users = FakeUsers(accounts or [account()])
        self.operations = operations or FakeOperations()
        self.instruments = instruments or FakeInstruments()

    def __enter__(self) -> FakeClient:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        del exc_type, exc, tb


def adapter(
    client: FakeClient,
    *,
    expected_fingerprint: str = ACCOUNT_FINGERPRINT,
    policy: TInvestReadPolicyV1 | None = None,
    clock: Any = None,
    sleeper: Any = None,
) -> TInvestReadAdapter:
    return TInvestReadAdapter(
        client_factory=lambda: client,
        expected_account_fingerprint_sha256=expected_fingerprint,
        policy=policy,
        clock=clock or (lambda: NOW),
        monotonic=lambda: 0.0,
        sleeper=sleeper or (lambda _: None),
        random_unit=lambda: 0.0,
    )


def operation(
    operation_id: str,
    *,
    date: str,
    payment_units: str,
    trades_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "cursor": "operation-cursor-a",
        "broker_account_id": ACCOUNT_ID,
        "id": operation_id,
        "parent_operation_id": "parent-operation-a",
        "date": date,
        "type": "OPERATION_TYPE_BUY",
        "state": "OPERATION_STATE_EXECUTED",
        "instrument_uid": "uid-sber",
        "position_uid": "position-sber",
        "figi": "BBG004730N88",
        "payment": money(payment_units),
        "price": money("300"),
        "commission": money("-1"),
        "quantity": 10,
        "quantity_done": 10,
        "name": "Buy",
        "description": "Executed buy",
        "trades_info": trades_info or {"trades": [{"trade_id": "trade-a"}]},
    }


def test_snapshot_normalizes_exact_decimal_identity_and_cash() -> None:
    client = FakeClient()
    result = adapter(client).read_snapshot()

    assert result.account.masked_label == "***0001"
    assert ACCOUNT_ID not in result.model_dump_json()
    assert result.portfolio_total is not None
    assert result.portfolio_total.amount == Decimal("12345.5")
    assert result.snapshot.metadata.quality.quality == DataQuality.VERIFIED
    assert result.snapshot.metadata.quality.completeness == Completeness.COMPLETE
    assert result.broker_position_count == 1
    assert result.normalized_position_count == 1
    assert result.unresolved_position_count == 0

    position = result.snapshot.positions[0]
    assert position.quantity_units == Decimal("10")
    assert position.blocked_units == Decimal("1")
    assert position.instrument.uid == "uid-sber"
    assert position.instrument.isin == "RU0009029540"
    assert position.instrument.ticker == "SBER"
    assert position.valuation is not None
    assert position.valuation.unit_price == Decimal("300.5")
    assert position.valuation.currency == "RUB"

    cash = result.snapshot.cash_balances[0]
    assert cash.reported.amount == Decimal("1000")
    assert cash.blocked is not None
    assert cash.blocked.amount == Decimal("100")
    assert cash.available is not None
    assert cash.available.amount == Decimal("900")


def test_depositary_blocked_position_is_conservatively_fully_blocked() -> None:
    payload = portfolio()
    payload["positions"][0]["blocked"] = True
    payload["positions"][0]["blocked_lots"] = quotation("0")
    result = adapter(
        FakeClient(operations=FakeOperations(portfolio_payload=payload))
    ).read_snapshot()

    assert result.snapshot.positions[0].quantity_units == Decimal("10")
    assert result.snapshot.positions[0].blocked_units == Decimal("10")


def test_snapshot_is_deterministic_for_same_payload_and_clock() -> None:
    first = adapter(FakeClient()).read_snapshot()
    second = adapter(FakeClient()).read_snapshot()

    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_wrong_account_binding_fails_without_raw_id_in_error() -> None:
    wrong = hashlib.sha256(b"another-account").hexdigest()

    with pytest.raises(AccountBindingError) as exc_info:
        adapter(FakeClient(), expected_fingerprint=wrong).read_snapshot()

    assert str(exc_info.value) == "OWNER_ACCOUNT_FINGERPRINT_MISMATCH"
    assert ACCOUNT_ID not in str(exc_info.value)


def test_multiple_open_accounts_fail_closed() -> None:
    client = FakeClient(
        accounts=[
            account(),
            account("account-owner-0002"),
        ]
    )

    with pytest.raises(AccountBindingError, match="MULTIPLE_ACCESSIBLE_OPEN_ACCOUNTS"):
        adapter(client).read_snapshot()


def test_no_access_account_is_not_selectable() -> None:
    client = FakeClient(
        accounts=[account(access_level="ACCOUNT_ACCESS_LEVEL_NO_ACCESS")]
    )

    with pytest.raises(AccountBindingError, match="NO_ACCESSIBLE_OPEN_ACCOUNT"):
        adapter(client).read_snapshot()


def test_partial_identity_is_explicit_and_strict_mode_rejects() -> None:
    bad_instrument = instrument(uid="different-uid")
    strict_client = FakeClient(instruments=FakeInstruments(bad_instrument))

    with pytest.raises(BrokerDataError, match="PORTFOLIO_NORMALIZATION_INCOMPLETE"):
        adapter(strict_client).read_snapshot()

    partial_client = FakeClient(instruments=FakeInstruments(bad_instrument))
    result = adapter(partial_client).read_snapshot(allow_partial=True)

    assert result.broker_position_count == 1
    assert result.normalized_position_count == 0
    assert result.unresolved_position_count == 1
    assert result.snapshot.metadata.quality.quality == DataQuality.DEGRADED
    assert result.snapshot.metadata.quality.completeness == Completeness.PARTIAL
    assert (
        result.snapshot.metadata.quality.issues[0].code
        == "BROKER_POSITION_UNRESOLVED"
    )


def test_limits_loading_is_never_silently_complete() -> None:
    payload = positions()
    payload["limits_loading_in_progress"] = True
    operations = FakeOperations(positions_payload=payload)

    with pytest.raises(BrokerDataError, match="POSITIONS_LIMITS_LOADING_IN_PROGRESS"):
        adapter(FakeClient(operations=operations)).read_snapshot()

    partial = adapter(
        FakeClient(operations=FakeOperations(positions_payload=payload))
    ).read_snapshot(allow_partial=True)
    assert partial.snapshot.metadata.quality.quality == DataQuality.DEGRADED
    assert partial.snapshot.metadata.quality.completeness == Completeness.PARTIAL
    assert any(
        issue.code == "BROKER_LIMITS_LOADING_IN_PROGRESS"
        for issue in partial.snapshot.metadata.quality.issues
    )


def test_virtual_positions_are_never_silently_omitted() -> None:
    payload = portfolio()
    payload["virtual_positions"] = [
        {
            "instrument_uid": "uid-virtual",
            "position_uid": "position-virtual",
            "figi": "BBG000VIRTUAL",
            "quantity": quotation("2"),
        }
    ]

    with pytest.raises(BrokerDataError, match="PORTFOLIO_VIRTUAL_POSITIONS_UNSUPPORTED"):
        adapter(
            FakeClient(operations=FakeOperations(portfolio_payload=payload))
        ).read_snapshot()

    partial = adapter(
        FakeClient(operations=FakeOperations(portfolio_payload=payload))
    ).read_snapshot(allow_partial=True)
    assert partial.broker_position_count == 2
    assert partial.normalized_position_count == 1
    assert partial.unresolved_position_count == 1
    assert partial.snapshot.metadata.quality.completeness == Completeness.PARTIAL
    assert any(
        issue.code == "BROKER_VIRTUAL_POSITIONS_UNRESOLVED"
        for issue in partial.snapshot.metadata.quality.issues
    )


def test_freshness_transitions_to_stale_deterministically() -> None:
    policy = TInvestReadPolicyV1(stale_after_seconds=300)
    result = adapter(FakeClient(), policy=policy).read_snapshot(
        evaluated_at=NOW + timedelta(seconds=301)
    )

    assert result.freshness.state == FreshnessState.STALE
    assert result.freshness.age_seconds == Decimal("301")


def test_cursor_pagination_deduplicates_semantic_repeats_not_operation_id() -> None:
    first = operation(
        "mutable-id-a",
        date="2026-08-10T10:00:00+00:00",
        payment_units="-3000",
    )
    duplicate_with_changed_transport_ids = dict(first)
    duplicate_with_changed_transport_ids["id"] = "mutable-id-b"
    duplicate_with_changed_transport_ids["parent_operation_id"] = "parent-operation-b"
    duplicate_with_changed_transport_ids["cursor"] = "operation-cursor-b"
    second = operation(
        "operation-two",
        date="2026-08-09T10:00:00+00:00",
        payment_units="-1500",
    )
    operations = FakeOperations(
        operation_pages={
            "": {
                "items": [first],
                "has_next": True,
                "next_cursor": "cursor-2",
            },
            "cursor-2": {
                "items": [duplicate_with_changed_transport_ids, second],
                "has_next": False,
                "next_cursor": "",
            },
        }
    )
    result = adapter(FakeClient(operations=operations)).read_operations()

    assert result.pages_loaded == 2
    assert result.duplicates_removed == 1
    assert result.truncated is False
    assert len(result.operations) == 2
    assert result.operations[0].occurred_at == datetime(
        2026,
        8,
        10,
        10,
        0,
        tzinfo=timezone.utc,
    )
    assert "mutable-id" not in result.model_dump_json()
    assert ACCOUNT_ID not in result.model_dump_json()


def test_semantically_distinct_trade_payloads_are_not_deduplicated() -> None:
    first = operation(
        "mutable-id-a",
        date="2026-08-10T10:00:00+00:00",
        payment_units="-3000",
        trades_info={"trades": [{"trade_id": "trade-a"}]},
    )
    second = operation(
        "mutable-id-b",
        date="2026-08-10T10:00:00+00:00",
        payment_units="-3000",
        trades_info={"trades": [{"trade_id": "trade-b"}]},
    )
    operations = FakeOperations(
        operation_pages={
            "": {
                "items": [first, second],
                "has_next": False,
                "next_cursor": "",
            }
        }
    )

    result = adapter(FakeClient(operations=operations)).read_operations()

    assert result.duplicates_removed == 0
    assert len(result.operations) == 2
    assert result.operations[0].fingerprint_sha256 != result.operations[1].fingerprint_sha256


def test_non_advancing_cursor_fails_closed() -> None:
    operations = FakeOperations(
        operation_pages={
            "": {
                "items": [],
                "has_next": True,
                "next_cursor": "",
            }
        }
    )

    with pytest.raises(CursorProgressError, match="OPERATIONS_CURSOR_DID_NOT_ADVANCE"):
        adapter(FakeClient(operations=operations)).read_operations()


def test_operation_history_is_explicitly_truncated_at_page_bound() -> None:
    operations = FakeOperations(
        operation_pages={
            "": {
                "items": [],
                "has_next": True,
                "next_cursor": "cursor-2",
            }
        }
    )
    policy = TInvestReadPolicyV1(max_operation_pages=1)

    result = adapter(FakeClient(operations=operations), policy=policy).read_operations()

    assert result.pages_loaded == 1
    assert result.truncated is True


def test_transient_broker_error_retries_with_bounded_backoff() -> None:
    operations = FakeOperations()
    operations.portfolio_failures = [
        FakeRpcError(grpc.StatusCode.UNAVAILABLE),
        FakeRpcError(grpc.StatusCode.UNAVAILABLE),
    ]
    sleeps: list[float] = []
    result = adapter(
        FakeClient(operations=operations),
        sleeper=sleeps.append,
    ).read_snapshot()

    assert result.normalized_position_count == 1
    assert operations.portfolio_calls == 3
    assert len(sleeps) >= 2
    assert max(sleeps) <= 1.5


def test_permission_error_is_permanent_and_not_retried() -> None:
    operations = FakeOperations()
    operations.portfolio_failures = [
        FakeRpcError(grpc.StatusCode.PERMISSION_DENIED),
    ]

    with pytest.raises(
        TInvestReadAdapterError,
        match="GET_PORTFOLIO_PERMANENT_BROKER_ERROR:PERMISSION_DENIED",
    ):
        adapter(FakeClient(operations=operations)).read_snapshot()

    assert operations.portfolio_calls == 1


def test_adapter_source_contains_no_broker_write_surface() -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "omni_cio"
        / "adapters"
        / "tinvest_read_v1.py"
    )
    source = source_path.read_text(encoding="utf-8").lower()

    forbidden = (
        "tinvest_trading_token",
        ".orders",
        ".stop_orders",
        "post_order",
        "cancel_order",
        "replace_order",
        "sandbox_client",
    )
    for marker in forbidden:
        assert marker not in source
