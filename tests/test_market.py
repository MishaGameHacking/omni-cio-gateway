from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from unittest.mock import patch
from uuid import UUID

import pytest

from omnicio.cbr import CBRClient, CBRRate, CBRUnavailable
from omnicio.market import MarketService
from omnicio.tbank import (
    TBankFxQuote,
    TBankHistoricCandle,
    TBankLastPrice,
    TBankTradingStatus,
    TBankUnavailable,
)


class FakeXmlResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> FakeXmlResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


def _cbr_xml(*, effective_date: str, value: str) -> bytes:
    return f"""<?xml version="1.0" encoding="windows-1251"?>
<ValCurs Date="{effective_date}" name="Foreign Currency Market">
  <Valute ID="R01235">
    <NumCode>840</NumCode>
    <CharCode>USD</CharCode>
    <Nominal>1</Nominal>
    <Name>US Dollar</Name>
    <Value>{value}</Value>
  </Valute>
</ValCurs>
""".encode()


def test_cbr_client_fetches_requested_effective_day_not_next_published_rate() -> None:
    today_xml = _cbr_xml(effective_date="01.10.2026", value="83,5588")
    next_xml = _cbr_xml(effective_date="02.10.2026", value="83,2454")
    client = CBRClient(cache_seconds=3600)

    with patch(
        "urllib.request.urlopen",
        side_effect=[
            FakeXmlResponse(today_xml),
            FakeXmlResponse(next_xml),
        ],
    ) as urlopen:
        today = client.usd_rub_rate(date(2026, 10, 1))
        latest = client.latest_usd_rub_rate()
        cached_today = client.usd_rub_rate(date(2026, 10, 1))

    assert today.value == "83.5588"
    assert today.effective_date == date(2026, 10, 1)
    assert latest.value == "83.2454"
    assert latest.effective_date == date(2026, 10, 2)
    assert cached_today == today
    assert "date_req=01/10/2026" in urlopen.call_args_list[0].args[0].full_url
    assert "date_req=" not in urlopen.call_args_list[1].args[0].full_url
    assert urlopen.call_count == 2


def test_cbr_client_backs_off_after_initial_provider_failure() -> None:
    client = CBRClient(failure_retry_seconds=300)

    with patch(
        "urllib.request.urlopen",
        side_effect=TimeoutError("timeout"),
    ) as urlopen:
        with pytest.raises(CBRUnavailable):
            client.usd_rub_rate(date(2026, 10, 1))
        with pytest.raises(CBRUnavailable):
            client.usd_rub_rate(date(2026, 10, 1))

    urlopen.assert_called_once()


class FakeBroker:
    def __init__(self, quote_time: str) -> None:
        self.quote_time = quote_time

    def usd_rub_quote(self, user_id: UUID) -> TBankFxQuote:
        assert user_id == UUID("00000000-0000-0000-0000-000000000001")
        return TBankFxQuote(
            instrument_uid="uid-usd-rub",
            ticker="USDTEST",
            name="Доллар США / Российский рубль",
            class_code="TEST",
            price="83.37",
            currency="RUB",
            quote_time=self.quote_time,
            source="dealer",
            previous_close="83.10",
        )

    def market_exchange_candles(
        self,
        user_id: UUID,
        instrument_uid: str,
        *,
        from_at: datetime,
        to_at: datetime,
        interval: str,
    ) -> tuple[TBankHistoricCandle, ...]:
        assert user_id == UUID("00000000-0000-0000-0000-000000000001")
        assert instrument_uid == "uid-1"
        assert interval == "CANDLE_INTERVAL_4_HOUR"
        assert to_at - from_at == timedelta(days=31)
        return (
            TBankHistoricCandle(
                instrument_uid="uid-1",
                open="100",
                high="103",
                low="99",
                close="102",
                volume_lots=42,
                time=to_at - timedelta(hours=4),
                is_complete=True,
                source="CANDLE_SOURCE_EXCHANGE",
            ),
        )

    def market_last_price(
        self,
        user_id: UUID,
        instrument_uid: str,
    ) -> TBankLastPrice:
        assert user_id == UUID("00000000-0000-0000-0000-000000000001")
        assert instrument_uid == "uid-1"
        return TBankLastPrice(
            instrument_uid="uid-1",
            price="102.5",
            time=datetime.now(UTC),
        )

    def market_trading_status(
        self,
        user_id: UUID,
        instrument_uid: str,
    ) -> TBankTradingStatus:
        assert user_id == UUID("00000000-0000-0000-0000-000000000001")
        assert instrument_uid == "uid-1"
        return TBankTradingStatus(
            instrument_uid="uid-1",
            trading_status="SECURITY_TRADING_STATUS_NORMAL_TRADING",
            limit_order_available=True,
            market_order_available=False,
            api_trade_available=True,
            best_price_order_available=True,
            only_best_price=False,
        )


class FakeCBR:
    def usd_rub_rate(self, effective_on: date | None = None) -> CBRRate:
        assert effective_on is None
        return CBRRate(
            currency="RUB",
            value="83.5588",
            nominal=1,
            effective_date=date(2026, 10, 1),
            fetched_at=datetime(2026, 10, 1, 12, 0, tzinfo=UTC),
        )

    def latest_usd_rub_rate(self) -> CBRRate:
        return CBRRate(
            currency="RUB",
            value="83.2454",
            nominal=1,
            effective_date=date(2026, 10, 2),
            fetched_at=datetime(2026, 10, 1, 15, 30, tzinfo=UTC),
        )


def test_market_service_separates_market_today_cbr_and_next_cbr_rate() -> None:
    now = datetime.now(UTC)
    service = MarketService(
        broker=FakeBroker(now.isoformat()),  # type: ignore[arg-type]
        cbr=FakeCBR(),  # type: ignore[arg-type]
        live_after_seconds=30,
    )

    snapshot = service.usd_rub(UUID("00000000-0000-0000-0000-000000000001"))

    assert snapshot.pair == "USD/RUB"
    assert snapshot.price == "83.37"
    assert snapshot.source == "dealer"
    assert snapshot.status == "live"
    assert snapshot.change == "0.27"
    assert snapshot.change_percent is not None
    assert snapshot.cbr_reference is not None
    assert snapshot.cbr_reference.value == "83.5588"
    assert snapshot.cbr_reference.effective_date == "2026-10-01"
    assert snapshot.cbr_next_reference is not None
    assert snapshot.cbr_next_reference.value == "83.2454"
    assert snapshot.cbr_next_reference.effective_date == "2026-10-02"


def test_market_service_marks_old_provider_timestamp_stale() -> None:
    service = MarketService(
        broker=FakeBroker("2026-01-01T00:00:00Z"),  # type: ignore[arg-type]
        cbr=FakeCBR(),  # type: ignore[arg-type]
        live_after_seconds=30,
    )

    snapshot = service.usd_rub(UUID("00000000-0000-0000-0000-000000000001"))

    assert snapshot.status == "stale"
    assert snapshot.age_seconds > 30


def test_market_service_instrument_snapshot_preserves_quote_time_ohlc_and_status() -> None:
    service = MarketService(
        broker=FakeBroker(datetime.now(UTC).isoformat()),  # type: ignore[arg-type]
        cbr=FakeCBR(),  # type: ignore[arg-type]
        live_after_seconds=30,
    )

    snapshot = service.instrument_snapshot(
        UUID("00000000-0000-0000-0000-000000000001"),
        "uid-1",
        period="1m",
    )

    assert snapshot.instrument_uid == "uid-1"
    assert snapshot.period == "1m"
    assert snapshot.interval == "CANDLE_INTERVAL_4_HOUR"
    assert snapshot.source == "T-Invest exchange candles"
    assert snapshot.last_price == "102.5"
    assert snapshot.quote_status == "live"
    assert snapshot.trading_status == "SECURITY_TRADING_STATUS_NORMAL_TRADING"
    assert snapshot.api_trade_available is True
    assert snapshot.limit_order_available is True
    assert snapshot.market_order_available is False
    assert len(snapshot.candles) == 1
    assert snapshot.candles[0].open == "100"
    assert snapshot.candles[0].high == "103"
    assert snapshot.candles[0].low == "99"
    assert snapshot.candles[0].close == "102"
    assert snapshot.candles[0].is_complete is True


def test_market_service_rejects_malformed_provider_ohlc_as_unavailable() -> None:
    broker = FakeBroker(datetime.now(UTC).isoformat())
    original = broker.market_exchange_candles

    def malformed(*args: object, **kwargs: object) -> tuple[TBankHistoricCandle, ...]:
        candles = original(*args, **kwargs)  # type: ignore[arg-type]
        candle = candles[0]
        return (
            TBankHistoricCandle(
                instrument_uid=candle.instrument_uid,
                open=None,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume_lots=candle.volume_lots,
                time=candle.time,
                is_complete=candle.is_complete,
                source=candle.source,
            ),
        )

    broker.market_exchange_candles = malformed  # type: ignore[method-assign]
    service = MarketService(
        broker=broker,  # type: ignore[arg-type]
        cbr=FakeCBR(),  # type: ignore[arg-type]
        live_after_seconds=30,
    )

    with pytest.raises(TBankUnavailable, match="missing OHLC"):
        service.instrument_snapshot(
            UUID("00000000-0000-0000-0000-000000000001"),
            "uid-1",
            period="1m",
        )


def test_market_service_rejects_unknown_instrument_period_before_provider_read() -> None:
    service = MarketService(
        broker=FakeBroker(datetime.now(UTC).isoformat()),  # type: ignore[arg-type]
        cbr=FakeCBR(),  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError, match="unsupported market period"):
        service.instrument_snapshot(
            UUID("00000000-0000-0000-0000-000000000001"),
            "uid-1",
            period="all",
        )
