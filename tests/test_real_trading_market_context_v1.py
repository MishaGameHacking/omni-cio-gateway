from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from omni_cio.real_trading.client_v1 import RealTradingApiFailure
from omni_cio.real_trading.market_context_v1 import market_context_from_snapshot


UID = "e6123145-9665-43e0-8413-cd61b8aa9b13"


def snapshot() -> dict:
    return {
        "status": "ok",
        "retrieved_at": datetime(2026, 8, 3, 7, 0, tzinfo=timezone.utc).isoformat(),
        "instrument_uid": UID,
        "components": {
            "instrument_reference": "ok",
            "last_price": "ok",
            "trading_status": "ok",
            "order_book": "ok",
        },
        "instrument_reference": {
            "status": "resolved",
            "identity_check": {"overall": "PASS"},
            "instrument": {
                "uid": UID,
                "ticker": "SBER",
                "isin": "RU0009029540",
                "instrument_kind": "INSTRUMENT_TYPE_SHARE",
                "instrument_type": "share",
                "lot": 1,
                "currency": "RUB",
                "min_price_increment": "0.01",
                "api_trade_available_flag": True,
            },
        },
        "trading_status": {
            "status": "ok",
            "trading_status": "SECURITY_TRADING_STATUS_NORMAL_TRADING",
            "limit_order_available_flag": True,
            "api_trade_available_flag": True,
        },
        "order_book": {
            "status": "ok",
            "time": "2026-08-03T06:59:59+00:00",
            "best_bid": {"price": "276.50", "quantity": 1},
            "best_ask": {"price": "276.60", "quantity": 1},
        },
    }


def test_market_adapter_builds_strict_context_from_read_only_snapshot() -> None:
    result = market_context_from_snapshot(snapshot(), instrument_uid=UID)
    assert result.instrument_uid == UID
    assert result.ticker == "SBER"
    assert result.instrument_type == "share"
    assert result.currency == "RUB"
    assert result.lot == 1
    assert result.min_price_increment == Decimal("0.01")
    assert result.api_trade_available is True
    assert result.limit_orders_available is True
    assert result.retrieved_at == datetime(
        2026, 8, 3, 6, 59, 59, tzinfo=timezone.utc
    )


def test_partial_trusted_snapshot_is_rejected() -> None:
    payload = snapshot()
    payload["components"]["order_book"] = "error"
    with pytest.raises(RealTradingApiFailure) as exc_info:
        market_context_from_snapshot(payload, instrument_uid=UID)
    assert exc_info.value.code == "REAL_MARKET_DATA_INCOMPLETE"


def test_identity_conflict_is_rejected() -> None:
    payload = snapshot()
    payload["instrument_reference"]["identity_check"] = {"overall": "FAIL"}
    with pytest.raises(RealTradingApiFailure) as exc_info:
        market_context_from_snapshot(payload, instrument_uid=UID)
    assert exc_info.value.code == "REAL_INSTRUMENT_IDENTITY_MISMATCH"


def test_uid_substitution_is_rejected() -> None:
    payload = snapshot()
    payload["instrument_reference"]["instrument"]["uid"] = "different"
    with pytest.raises(RealTradingApiFailure) as exc_info:
        market_context_from_snapshot(payload, instrument_uid=UID)
    assert exc_info.value.code == "REAL_INSTRUMENT_IDENTITY_MISMATCH"


def test_non_cash_v1_instrument_type_is_rejected() -> None:
    payload = snapshot()
    payload["instrument_reference"]["instrument"]["instrument_kind"] = (
        "INSTRUMENT_TYPE_FUTURES"
    )
    payload["instrument_reference"]["instrument"]["instrument_type"] = "futures"
    with pytest.raises(RealTradingApiFailure) as exc_info:
        market_context_from_snapshot(payload, instrument_uid=UID)
    assert exc_info.value.code == "REAL_INSTRUMENT_TYPE_NOT_ALLOWED"


def test_missing_order_book_timestamp_is_rejected() -> None:
    payload = snapshot()
    del payload["order_book"]["time"]
    with pytest.raises(RealTradingApiFailure) as exc_info:
        market_context_from_snapshot(payload, instrument_uid=UID)
    assert exc_info.value.code == "REAL_MARKET_DATA_INCOMPLETE"


def test_trade_availability_requires_both_reference_and_live_status() -> None:
    payload = snapshot()
    payload["trading_status"]["api_trade_available_flag"] = False
    result = market_context_from_snapshot(payload, instrument_uid=UID)
    assert result.api_trade_available is False


def test_input_payload_is_not_mutated() -> None:
    payload = snapshot()
    before = deepcopy(payload)
    market_context_from_snapshot(payload, instrument_uid=UID)
    assert payload == before
