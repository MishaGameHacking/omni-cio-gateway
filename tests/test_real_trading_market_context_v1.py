from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from omni_cio.real_trading.client_v1 import RealTradingApiFailure
from omni_cio.real_trading.market_context_v1 import market_context_from_snapshot


UID = "instrument-uid"


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
                "isin": "TEST-ISIN",
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


def test_builds_context_from_read_only_snapshot() -> None:
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


def test_partial_snapshot_and_identity_conflict_are_rejected() -> None:
    partial = snapshot()
    partial["components"]["order_book"] = "error"
    with pytest.raises(RealTradingApiFailure) as partial_error:
        market_context_from_snapshot(partial, instrument_uid=UID)
    assert partial_error.value.code == "REAL_MARKET_DATA_INCOMPLETE"

    conflict = snapshot()
    conflict["instrument_reference"]["identity_check"] = {"overall": "FAIL"}
    with pytest.raises(RealTradingApiFailure) as identity_error:
        market_context_from_snapshot(conflict, instrument_uid=UID)
    assert identity_error.value.code == "REAL_INSTRUMENT_IDENTITY_MISMATCH"


def test_uid_substitution_and_unsupported_type_are_rejected() -> None:
    changed = snapshot()
    changed["instrument_reference"]["instrument"]["uid"] = "other"
    with pytest.raises(RealTradingApiFailure) as uid_error:
        market_context_from_snapshot(changed, instrument_uid=UID)
    assert uid_error.value.code == "REAL_INSTRUMENT_IDENTITY_MISMATCH"

    future = snapshot()
    future["instrument_reference"]["instrument"]["instrument_kind"] = (
        "INSTRUMENT_TYPE_FUTURES"
    )
    future["instrument_reference"]["instrument"]["instrument_type"] = "futures"
    with pytest.raises(RealTradingApiFailure) as kind_error:
        market_context_from_snapshot(future, instrument_uid=UID)
    assert kind_error.value.code == "REAL_INSTRUMENT_TYPE_NOT_ALLOWED"


def test_order_book_time_and_live_trade_flags_fail_closed() -> None:
    missing_time = snapshot()
    del missing_time["order_book"]["time"]
    with pytest.raises(RealTradingApiFailure) as time_error:
        market_context_from_snapshot(missing_time, instrument_uid=UID)
    assert time_error.value.code == "REAL_MARKET_DATA_INCOMPLETE"

    unavailable = snapshot()
    unavailable["trading_status"]["api_trade_available_flag"] = False
    result = market_context_from_snapshot(unavailable, instrument_uid=UID)
    assert result.api_trade_available is False


def test_input_payload_is_not_mutated() -> None:
    payload = snapshot()
    before = deepcopy(payload)
    market_context_from_snapshot(payload, instrument_uid=UID)
    assert payload == before
