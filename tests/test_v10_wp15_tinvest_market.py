from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
from typing import Any

import grpc
import pytest

from omni_cio.adapters.tinvest_market_v1 import (
    MarketFreshnessState,
    TInvestMarketReadAdapter,
)
from omni_cio.adapters.tinvest_read_v1 import (
    BrokerDataError,
    TInvestReadPolicyV1,
)
from omni_cio.contracts.v1.portfolio import (
    InstrumentIdentity,
    InstrumentType,
)


NOW = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
ACCOUNT_ID = "account-owner-0001"
ACCOUNT_FINGERPRINT = hashlib.sha256(ACCOUNT_ID.encode("utf-8")).hexdigest()


def _instrument(uid: str, ticker: str) -> InstrumentIdentity:
    return InstrumentIdentity(
        name=f"Synthetic {ticker}",
        instrument_type=InstrumentType.SHARE,
        currency="RUB",
        lot=10,
        ticker=ticker,
        figi=f"BBG-{uid}",
        uid=uid,
    )


class _RpcError(grpc.RpcError):
    def __init__(self, code: grpc.StatusCode) -> None:
        super().__init__()
        self._code = code

    def code(self) -> grpc.StatusCode:
        return self._code


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


class _Market:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.failures: list[BaseException] = []
        self.calls = 0

    def get_last_prices(self, *, instrument_id: list[str]) -> dict[str, Any]:
        self.calls += 1
        if self.failures:
            raise self.failures.pop(0)
        requested = set(instrument_id)
        return {
            "last_prices": [
                row
                for row in self.rows
                if str(row.get("instrument_uid")) in requested
            ]
        }


class _Client:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.users = _Users()
        self.market_data = _Market(rows)

    def __enter__(self) -> _Client:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        del exc_type, exc, tb


def _row(
    uid: str,
    *,
    price_time: datetime,
    units: str = "300",
    nano: int = 500_000_000,
) -> dict[str, Any]:
    return {
        "instrument_uid": uid,
        "figi": f"BBG-{uid}",
        "price": {"units": units, "nano": nano},
        "time": price_time.isoformat(),
    }


def _adapter(
    client: _Client,
    *,
    policy: TInvestReadPolicyV1 | None = None,
    sleeper: Any = None,
) -> TInvestMarketReadAdapter:
    return TInvestMarketReadAdapter(
        client_factory=lambda: client,
        expected_account_fingerprint_sha256=ACCOUNT_FINGERPRINT,
        policy=policy,
        clock=lambda: NOW,
        monotonic=lambda: 0.0,
        sleeper=sleeper or (lambda _: None),
        random_unit=lambda: 0.0,
    )


def test_market_prices_are_bound_fresh_and_decimal_exact() -> None:
    identity = _instrument("uid-a", "AAA")
    client = _Client([_row("uid-a", price_time=NOW - timedelta(seconds=10))])

    result = _adapter(client).read_last_prices((identity,))

    assert result.account.masked_label == "***0001"
    assert ACCOUNT_ID not in result.model_dump_json()
    assert result.requested_instrument_count == 1
    assert result.returned_instrument_count == 1
    assert result.missing_instrument_count == 0
    assert result.stale_instrument_count == 0
    assert result.prices[0].price == Decimal("300.5")
    assert result.prices[0].freshness == MarketFreshnessState.FRESH


def test_market_stale_price_is_explicit() -> None:
    identity = _instrument("uid-a", "AAA")
    client = _Client([_row("uid-a", price_time=NOW - timedelta(seconds=301))])
    policy = TInvestReadPolicyV1(stale_after_seconds=300)

    result = _adapter(client, policy=policy).read_last_prices((identity,))

    assert result.stale_instrument_count == 1
    assert result.prices[0].freshness == MarketFreshnessState.STALE
    assert result.prices[0].age_seconds == Decimal("301")


def test_market_missing_price_is_strict_by_default_and_explicit_when_partial() -> None:
    first = _instrument("uid-a", "AAA")
    second = _instrument("uid-b", "BBB")
    client = _Client([_row("uid-a", price_time=NOW)])

    with pytest.raises(BrokerDataError, match="MARKET_PRICE_SET_INCOMPLETE"):
        _adapter(client).read_last_prices((first, second))

    partial_client = _Client([_row("uid-a", price_time=NOW)])
    result = _adapter(partial_client).read_last_prices(
        (first, second),
        allow_partial=True,
    )

    assert result.requested_instrument_count == 2
    assert result.returned_instrument_count == 1
    assert result.missing_instrument_count == 1


def test_market_transient_failure_reconnects_with_bounded_read_retry() -> None:
    identity = _instrument("uid-a", "AAA")
    client = _Client([_row("uid-a", price_time=NOW)])
    client.market_data.failures = [
        _RpcError(grpc.StatusCode.UNAVAILABLE),
        _RpcError(grpc.StatusCode.UNAVAILABLE),
    ]
    sleeps: list[float] = []

    result = _adapter(client, sleeper=sleeps.append).read_last_prices((identity,))

    assert result.returned_instrument_count == 1
    assert client.market_data.calls == 3
    assert len(sleeps) >= 2


def test_market_requires_strong_uid_identity() -> None:
    weak = InstrumentIdentity(
        name="Weak",
        instrument_type=InstrumentType.SHARE,
        currency="RUB",
        lot=10,
        figi="BBG-WEAK",
    )

    with pytest.raises(BrokerDataError, match="MARKET_INSTRUMENT_UID_REQUIRED"):
        _adapter(_Client([])).read_last_prices((weak,))
