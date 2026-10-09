"""All available history stays source-bound, time-bounded, and account-consistent."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta, tzinfo
from functools import partial
from threading import Event
from typing import Any
from unittest.mock import Mock, patch
from uuid import UUID

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from test_market import _finish_market_reads
from test_workspace_api import OWNER
from test_workspace_api import workspace_http as workspace_http

from omnicio.broker import BrokerConnectionError, BrokerConnectionStatus, BrokerService
from omnicio.cbr import CBRClient
from omnicio.db import Database, TBankConnectionRecord
from omnicio.main import app
from omnicio.market import CBRIndicator, CBRIndicatorSnapshot, MarketService, UsdRubSnapshot
from omnicio.security import encrypt_secret
from omnicio.tbank import (
    TBankHistoricCandle,
    TBankInstrumentMetadata,
    TBankInvestClient,
    TBankLastPrice,
    TBankMoney,
    TBankTradingStatus,
    TBankUnavailable,
)

NOW = datetime(2026, 10, 6, 12, tzinfo=UTC)
UID = "instrument-history"


class FixedDatetime(datetime):
    @classmethod
    def now(cls, tz: tzinfo | None = None) -> datetime:
        return NOW.astimezone(tz) if tz is not None else NOW.replace(tzinfo=None)


def candle(at: datetime) -> TBankHistoricCandle:
    return TBankHistoricCandle(
        instrument_uid=UID,
        open="100",
        high="102",
        low="99",
        close="101",
        volume_lots=100,
        time=at,
        is_complete=True,
        source="CANDLE_SOURCE_EXCHANGE",
    )


def history_broker(first: datetime | None = None) -> Mock:
    broker = Mock(spec=BrokerService)
    broker.status.return_value = BrokerConnectionStatus(True, "prod", "account-a", verified_at=NOW)
    broker.market_history_start.return_value = first
    broker.market_exchange_candles.return_value = ()
    broker.market_last_price.return_value = TBankLastPrice(UID, "101", NOW)
    broker.market_instrument_metadata.return_value = TBankInstrumentMetadata(
        UID, "History instrument", "HIST", "", "share", "", "RU", False, currency="rub",
    )
    broker.market_trading_status.return_value = TBankTradingStatus(
        UID,
        "SECURITY_TRADING_STATUS_NORMAL_TRADING",
        True,
        False,
        True,
        False,
        False,
    )
    return broker


def market(broker: Mock) -> MarketService:
    return MarketService(broker=broker, cbr=Mock(spec=CBRClient))


@pytest.mark.parametrize("surface", ["1m", "live"])
@pytest.mark.parametrize(
    "kind, nominal, unit, cash_price", [
        ("share", None, "currency", "101"),
        ("bond", TBankMoney("rub", "1000"), "percent_nominal", "1010"),
        ("bond", TBankMoney("usd", "1000"), "percent_nominal", None),
        ("bond", None, "percent_nominal", None),
        ("futures", None, "points", None),
        ("currency", None, "per_nominal", None),
        ("unrecognized", None, "unknown", None),
    ],
)
def test_native_market_units_are_explicit_and_history_never_uses_current_nominal(
    surface: str, kind: str, nominal: TBankMoney | None, unit: str, cash_price: str | None,
) -> None:
    broker = history_broker()
    broker.market_instrument_metadata.return_value = replace(
        broker.market_instrument_metadata.return_value, instrument_type=kind, nominal=nominal,
    )
    broker.market_exchange_candles.return_value = (candle(NOW - timedelta(days=1)),)
    service = market(broker)
    operation = (
        partial(service.instrument_live_state, OWNER.id, UID) if surface == "live"
        else partial(service.instrument_snapshot, OWNER.id, UID, period=surface)
    )
    try:
        with patch("omnicio.market.datetime", FixedDatetime):
            operation()
            _finish_market_reads(service)
            result = operation()
    finally:
        service.close()
    assert result.price_unit == unit
    assert result.last_price == "101"
    assert result.cash_price == cash_price
    assert result.price_currency == ("RUB" if kind in {"share", "currency"} else None)
    if surface != "live":
        assert result.candles[0].close == "101"


def test_all_history_uses_real_first_date_ten_year_chunks_and_unique_sorted_months() -> None:
    first = datetime(2001, 3, 15, tzinfo=UTC)
    broker = history_broker(first)

    def read(owner: UUID, instrument: str, **window: Any) -> tuple[TBankHistoricCandle, ...]:
        assert owner == OWNER.id
        assert instrument == UID
        # Exercise the real adapter window guard without any provider access.
        with patch.object(TBankInvestClient, "_post", return_value={"candles": []}):
            TBankInvestClient().get_exchange_candles("test-token", "prod", UID, **window)
        begin, end = window["from_at"], window["to_at"]
        last_month = end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return (candle(last_month), candle(begin), candle(NOW + timedelta(days=1)))

    broker.market_exchange_candles.side_effect = read
    service = market(broker)
    try:
        with patch("omnicio.market.datetime", FixedDatetime):
            service.instrument_snapshot(OWNER.id, UID, period="all")
            _finish_market_reads(service)
            result = service.instrument_snapshot(OWNER.id, UID, period="all")
    finally:
        service.close()
    assert result.period == "all"
    assert result.interval == "CANDLE_INTERVAL_MONTH"
    assert result.history_from == first.isoformat()
    assert result.history_note
    assert "без учёта выплат" in result.history_note
    calls = broker.market_exchange_candles.call_args_list
    assert len(calls) == 3
    assert [call.kwargs["from_at"] for call in calls] == [
        datetime(2001, 3, 1, tzinfo=UTC),
        datetime(2011, 3, 1, tzinfo=UTC),
        datetime(2021, 3, 1, tzinfo=UTC),
    ]
    assert calls[-1].kwargs["to_at"] == NOW
    dates = [item.time for item in result.candles]
    assert dates == sorted(set(dates))
    assert len(dates) == 4
    assert max(dates) <= NOW.isoformat()


def test_all_history_month_boundary_short_tail_stays_inside_provider_window() -> None:
    broker = history_broker(datetime(2016, 10, 6, tzinfo=UTC))

    def read(owner: UUID, instrument: str, **window: Any) -> tuple[TBankHistoricCandle, ...]:
        assert window["interval"] == "CANDLE_INTERVAL_MONTH"
        assert timedelta(days=28) <= window["to_at"] - window["from_at"] <= timedelta(days=3660)
        return ()

    broker.market_exchange_candles.side_effect = read
    service = market(broker)
    try:
        with patch("omnicio.market.datetime", FixedDatetime):
            service.instrument_snapshot(OWNER.id, UID, period="all")
            _finish_market_reads(service)
            result = service.instrument_snapshot(OWNER.id, UID, period="all")
    finally:
        service.close()
    assert result.history_status == "empty"
    assert broker.market_exchange_candles.call_count == 2
    tail = broker.market_exchange_candles.call_args.kwargs
    assert tail["to_at"] == NOW
    assert tail["from_at"] < datetime(2026, 10, 1, tzinfo=UTC)


def test_all_history_recent_listing_uses_daily_resolution_without_invented_origin() -> None:
    first = NOW - timedelta(days=1)
    broker = history_broker(first)
    broker.market_exchange_candles.return_value = (candle(first),)
    service = market(broker)
    try:
        with patch("omnicio.market.datetime", FixedDatetime):
            service.instrument_snapshot(OWNER.id, UID, period="all")
            _finish_market_reads(service)
            result = service.instrument_snapshot(OWNER.id, UID, period="all")
    finally:
        service.close()
    assert result.interval == "CANDLE_INTERVAL_DAY"
    assert result.history_from == first.isoformat()
    assert result.candles[0].time == first.isoformat()
    assert broker.market_exchange_candles.call_count == 1


def test_history_refresh_keeps_old_candles_and_source_time_until_real_recovery() -> None:
    broker = history_broker()
    old = replace(candle(NOW - timedelta(hours=4)), is_complete=False)
    corrected = replace(old, close="102", is_complete=True)
    entered, release = Event(), Event()

    def read(user, uid, **kwargs):
        if broker.market_exchange_candles.call_count == 2:
            entered.set()
            assert release.wait(timeout=5)
            raise TBankUnavailable("transient history failure")
        return (old if broker.market_exchange_candles.call_count == 1 else corrected,)

    broker.market_exchange_candles.side_effect = read
    service = market(broker)
    try:
        with (
            patch("omnicio.market.time.monotonic") as clock,
            patch("omnicio.market.datetime") as wall,
        ):
            clock.return_value = 0
            wall.now.side_effect = lambda _tz: NOW + timedelta(seconds=clock.return_value)
            service.instrument_snapshot(OWNER.id, UID, period="1m")
            _finish_market_reads(service)
            initial = service.instrument_snapshot(OWNER.id, UID, period="1m")
            assert initial.history_status == "available"
            assert initial.history_observed_at == NOW.isoformat()
            clock.return_value = 16
            pending = service.instrument_snapshot(OWNER.id, UID, period="1m")
            assert entered.wait(timeout=5)
            assert pending.history_status == "loading"
            assert pending.candles == initial.candles
            assert pending.history_observed_at == initial.history_observed_at
            clock.return_value = 17
            release.set()
            _finish_market_reads(service)
            failed = service.instrument_snapshot(OWNER.id, UID, period="1m")
            assert failed.history_status == "unavailable"
            assert failed.errors["history"] == "source_unavailable"
            assert failed.candles == initial.candles
            assert failed.history_observed_at == initial.history_observed_at
            assert failed.last_price == "101"
            clock.return_value = 21
            service.instrument_snapshot(OWNER.id, UID, period="1m")
            assert broker.market_exchange_candles.call_count == 2
            clock.return_value = 22
            service.instrument_snapshot(OWNER.id, UID, period="1m")
            _finish_market_reads(service)
            recovered = service.instrument_snapshot(OWNER.id, UID, period="1m")
            assert recovered.history_status == "available"
            assert recovered.errors["history"] is None
            assert recovered.candles[0].close == "102"
            assert recovered.candles[0].is_complete is True
            assert recovered.history_observed_at == (NOW + timedelta(seconds=22)).isoformat()
            assert broker.market_exchange_candles.call_count == 3
    finally:
        release.set()
        service.close()


def test_busy_history_period_never_returns_another_periods_candles() -> None:
    broker = history_broker(NOW - timedelta(days=400))
    entered, release = Event(), Event()

    def read(user, uid, **kwargs):
        if kwargs["interval"] == "CANDLE_INTERVAL_MONTH":
            entered.set()
            assert release.wait(timeout=5)
            return (replace(candle(NOW - timedelta(days=30)), close="100"),)
        return (replace(candle(NOW - timedelta(minutes=5)), close="102"),)

    broker.market_exchange_candles.side_effect = read
    service = market(broker)
    try:
        with patch("omnicio.market.datetime", FixedDatetime):
            first = service.instrument_snapshot(OWNER.id, UID, period="all")
            assert entered.wait(timeout=5)
            assert first.history_status == "loading"
            another_period = service.instrument_snapshot(OWNER.id, UID, period="1d")
            assert another_period.history_status == "loading"
            assert another_period.candles == ()
            assert another_period.history_observed_at is None
            assert another_period.interval == "CANDLE_INTERVAL_5_MIN"
            assert another_period.last_price == "101"
            assert broker.market_exchange_candles.call_count == 1
            release.set()
            _finish_market_reads(service)
            service.instrument_snapshot(OWNER.id, UID, period="1d")
            _finish_market_reads(service)
            ready = service.instrument_snapshot(OWNER.id, UID, period="1d")
            assert ready.period == "1d"
            assert ready.history_status == "available"
            assert ready.candles[0].close == "102"
            assert ready.candles[0].time == (NOW - timedelta(minutes=5)).isoformat()
            assert broker.market_exchange_candles.call_count == 2
    finally:
        release.set()
        service.close()


@pytest.mark.parametrize(
    "first", [None, datetime(2020, 1, 1), NOW + timedelta(days=1), datetime(1800, 1, 1, tzinfo=UTC)]
)
def test_unknown_future_naive_or_over_budget_first_date_fails_before_candle_reads(
    first: datetime | None,
) -> None:
    broker = history_broker(first)
    service = market(broker)
    try:
        with patch("omnicio.market.datetime", FixedDatetime):
            service.instrument_snapshot(OWNER.id, UID, period="all")
            _finish_market_reads(service)
            result = service.instrument_snapshot(OWNER.id, UID, period="all")
    finally:
        service.close()
    assert result.history_status == "unavailable"
    assert result.errors["history"] == "source_unavailable"
    assert result.last_price is not None
    broker.market_exchange_candles.assert_not_called()
    assert broker.market_last_price.call_count == 2


@pytest.mark.parametrize("surface", ["all", "1m", "live"])
def test_market_discards_every_result_if_account_changes_during_last_read(surface: str) -> None:
    broker = history_broker(datetime(2025, 1, 1, tzinfo=UTC))
    original = broker.market_trading_status.return_value
    original_price = broker.market_last_price.return_value
    connection_changed = Event()

    def changed(*args: Any) -> TBankTradingStatus:
        broker.status.return_value = BrokerConnectionStatus(True, "sandbox", "new-account")
        connection_changed.set()
        return original

    def last_price_after_change(*args: Any) -> TBankLastPrice:
        assert connection_changed.wait(timeout=5)
        return original_price

    broker.market_trading_status.side_effect = changed
    broker.market_last_price.side_effect = last_price_after_change
    service = market(broker)
    if surface == "live":
        operation = partial(service.instrument_live_state, OWNER.id, UID)
    else:
        operation = partial(service.instrument_snapshot, OWNER.id, UID, period=surface)
    try:
        with patch("omnicio.market.datetime", FixedDatetime), pytest.raises(BrokerConnectionError):
            operation()
    finally:
        service.close()


@pytest.mark.parametrize("fallback", [False, True])
def test_first_daily_candle_uses_verified_uid_and_typed_lookup_only_when_needed(
    fallback: bool,
) -> None:
    first = "2004-02-01T00:00:00Z"
    initial = {"instrument": {"uid": UID, "instrumentType": "share"}}
    dated = {"instrument": {"uid": UID, "first1dayCandleDate": first}}
    with patch.object(
        TBankInvestClient, "_post", side_effect=[initial, dated] if fallback else [dated]
    ) as read:
        result = TBankInvestClient().first_daily_candle("test-token", "prod", UID)
    assert result == datetime(2004, 2, 1, tzinfo=UTC)
    assert [call.kwargs["method"] for call in read.call_args_list] == (
        ["GetInstrumentBy", "ShareBy"] if fallback else ["GetInstrumentBy"]
    )
    assert all(
        call.kwargs["body"] == {"idType": "INSTRUMENT_ID_TYPE_UID", "id": UID}
        for call in read.call_args_list
    )


@pytest.mark.parametrize("fallback", [False, True])
def test_first_daily_candle_rejects_wrong_instrument_in_both_lookup_responses(
    fallback: bool,
) -> None:
    wrong = {
        "instrument": {"uid": "another-instrument", "first1dayCandleDate": "2000-01-01T00:00:00Z"}
    }
    values = (
        [{"instrument": {"uid": UID, "instrumentType": "bond"}}, wrong] if fallback else [wrong]
    )
    tbank = TBankInvestClient()
    with (
        patch.object(TBankInvestClient, "_post", side_effect=values),
        pytest.raises(TBankUnavailable, match="identity"),
    ):
        tbank.first_daily_candle("test-token", "prod", UID)


def test_first_candle_unknown_metadata_stays_unknown_and_month_window_limits_are_enforced() -> None:
    with patch.object(
        TBankInvestClient,
        "_post",
        return_value={"instrument": {"uid": UID, "instrumentType": "future-new-kind"}},
    ) as read:
        assert TBankInvestClient().first_daily_candle("test-token", "prod", UID) is None
    read.assert_called_once()
    tbank = TBankInvestClient()
    for window in (timedelta(days=27), timedelta(days=3661)):
        with patch.object(TBankInvestClient, "_post") as read, pytest.raises(ValueError):
            tbank.get_exchange_candles(
                "test-token",
                "prod",
                UID,
                from_at=NOW - window,
                to_at=NOW,
                interval="CANDLE_INTERVAL_MONTH",
            )
        read.assert_not_called()


@pytest.mark.parametrize("surface", ["first", "candles"])
@pytest.mark.parametrize("change", ["account", "credential", "disconnect"])
def test_broker_history_reads_revalidate_saved_connection_after_provider_io(
    surface: str, change: str
) -> None:
    key = Fernet.generate_key().decode()
    record = TBankConnectionRecord(
        OWNER.id,
        "prod",
        "account-a",
        "Account",
        encrypt_secret("test-credential", key),
        NOW,
        NOW,
    )
    database, tbank = Mock(spec=Database), Mock(spec=TBankInvestClient)
    database.tbank_connection.return_value = record

    def changed(*args: Any, **kwargs: Any) -> Any:
        database.tbank_connection.return_value = (
            None
            if change == "disconnect"
            else replace(
                record,
                **(
                    {"account_id": "new-account"}
                    if change == "account"
                    else {"encrypted_credential": b"new-ciphertext"}
                ),
            )
        )
        return NOW - timedelta(days=100) if surface == "first" else ()

    tbank.first_daily_candle.side_effect = tbank.get_exchange_candles.side_effect = changed
    broker = BrokerService(database, credential_key=key, tbank=tbank)
    if surface == "first":
        operation = partial(broker.market_history_start, OWNER.id, UID)
    else:
        operation = partial(
            broker.market_exchange_candles, OWNER.id, UID,
            from_at=NOW - timedelta(days=100), to_at=NOW, interval="CANDLE_INTERVAL_MONTH",
        )
    with pytest.raises(BrokerConnectionError, match="connection changed"):
        operation()


def test_all_history_http_is_valid_owner_bound_and_discards_revoked_session(
    workspace_http: tuple[TestClient, Mock, Mock, Mock],
) -> None:
    client, auth, _, _ = workspace_http
    broker = history_broker(datetime(2025, 1, 1, tzinfo=UTC))
    service = market(broker)
    try:
        with (
            patch.object(app.state, "market_service", service, create=True),
            patch("omnicio.market.datetime", FixedDatetime),
        ):
            assert client.get(f"/api/market/instruments/{UID}?period=all").status_code == 200
            _finish_market_reads(service)
            result = client.get(f"/api/market/instruments/{UID}?period=all&user_id=other")
            assert result.status_code == 200
            assert result.json()["period"] == "all"
            assert result.json()["history_status"] == "empty"
            assert result.headers["cache-control"] == "private, no-store"
            broker.market_history_start.assert_called_once_with(OWNER.id, UID)
            auth.refresh_session.side_effect = [OWNER, None]
            revoked = client.get(f"/api/market/instruments/{UID}?period=all")
            assert revoked.status_code == 401
            assert "candles" not in revoked.json()
    finally:
        service.close()


def test_instrument_facts_http_keeps_owner_precondition_and_discards_revoked_response(
    workspace_http: tuple[TestClient, Mock, Mock, Mock],
) -> None:
    client, auth, _, _ = workspace_http
    broker = history_broker()
    payload = {"instrument_uid": UID, "status": "partial", "metrics": []}
    with (
        patch.object(app.state, "broker_service", broker, create=True),
        patch("omnicio.main.instrument_facts", return_value=payload) as read,
    ):
        response = client.get(f"/api/market/instruments/{UID}/facts?user_id=another-owner")
        assert response.status_code == 200
        assert response.json() == payload
        assert response.headers["cache-control"] == "private, no-store"
        read.assert_called_once_with(user_id=OWNER.id, instrument_uid=UID, broker=broker)
        stale = client.get(
            f"/api/market/instruments/{UID}/facts", headers={"X-Omnicio-Profile": "000000502"},
        )
        assert stale.status_code == 409
        assert read.call_count == 1
        auth.refresh_session.side_effect = [OWNER, None]
        revoked = client.get(f"/api/market/instruments/{UID}/facts")
        assert revoked.status_code == 401
        assert "metrics" not in revoked.json()


@pytest.mark.parametrize("endpoint", ["usd-rub", "cbr-indicators"])
@pytest.mark.parametrize("change", ["revoked", "replaced"])
def test_legacy_market_http_discards_results_after_session_changes(
    workspace_http: tuple[TestClient, Mock, Mock, Mock], endpoint: str, change: str,
) -> None:
    client, auth, _, _ = workspace_http
    source = Mock(spec=MarketService)
    indicator = CBRIndicator("USD", "90", "RUB", NOW.date().isoformat())
    source.cbr_indicators.return_value = CBRIndicatorSnapshot(
        "synthetic", NOW.isoformat(), "live", indicator, indicator, indicator,
    )
    source.usd_rub.return_value = UsdRubSnapshot(
        "USD/RUB", "90", "RUB", "USD", "Synthetic USD", "TEST", "synthetic",
        NOW.isoformat(), NOW.isoformat(), 0, "live", None, None, None, None, None,
    )
    with patch.object(app.state, "market_service", source, create=True):
        available = client.get(f"/api/market/{endpoint}")
        assert available.status_code == 200
        assert available.headers["cache-control"] == "private, no-store"
        auth.refresh_session.side_effect = [
            OWNER, None if change == "revoked" else replace(OWNER, id=UUID(int=999)),
        ]
        response = client.get(f"/api/market/{endpoint}")
    assert response.status_code == (401 if change == "revoked" else 409)
    body = response.json()
    assert "price" not in body
    assert "key_rate" not in body


@pytest.mark.parametrize(
    ("error", "status"),
    [(ValueError("invalid input"), 422), (TBankUnavailable("private provider detail"), 503)],
)
def test_instrument_facts_http_reports_bounded_errors_without_provider_details(
    workspace_http: tuple[TestClient, Mock, Mock, Mock], error: Exception, status: int,
) -> None:
    client, _, _, _ = workspace_http
    with (
        patch.object(app.state, "broker_service", history_broker(), create=True),
        patch("omnicio.main.instrument_facts", side_effect=error),
    ):
        response = client.get(f"/api/market/instruments/{UID}/facts")
    assert response.status_code == status
    assert "private provider detail" not in response.text
