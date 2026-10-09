from __future__ import annotations

import io
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from functools import partial
from threading import Event, Lock, current_thread
from unittest.mock import Mock, patch
from uuid import UUID

import pytest

from omnicio.broker import BrokerConnectionError, BrokerService, MarketSourceStatus
from omnicio.cbr import (
    CBRClient,
    CBRHistory,
    CBRHistoryPoint,
    CBRIndicators,
    CBRKeyRate,
    CBRRate,
    CBRUnavailable,
)
from omnicio.market import PUBLIC_MARKET_SCOPE, MarketService, MarketStreamLimit, _CollectorState
from omnicio.news import NewsClient, NewsNotFound, NewsUnavailable
from omnicio.tbank import (
    TBankFxQuote,
    TBankHistoricCandle,
    TBankInstrumentMetadata,
    TBankInvestClient,
    TBankLastPrice,
    TBankLastPriceBatch,
    TBankTradingStatus,
    TBankUnavailable,
)


def _finish_market_reads(service: MarketService) -> None:
    """Wait for deterministic test transport, outside the scheduler's lock."""
    with service._cache_lock:
        futures = [entry.future for entry in service._enrichment.values()
                   if entry.future is not None]
    for future in futures:
        future.result(timeout=5)


class FakeXmlResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> FakeXmlResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, amount: int = -1) -> bytes:
        if amount < 0:
            return self.payload
        return self.payload[:amount]


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


def _cbr_indicators_xml(*, effective_date: str, usd: str, eur: str) -> bytes:
    return f"""<?xml version="1.0" encoding="windows-1251"?>
<ValCurs Date="{effective_date}" name="Foreign Currency Market">
  <Valute ID="R01235">
    <CharCode>USD</CharCode>
    <Nominal>1</Nominal>
    <Value>{usd}</Value>
  </Valute>
  <Valute ID="R01239">
    <CharCode>EUR</CharCode>
    <Nominal>1</Nominal>
    <Value>{eur}</Value>
  </Valute>
</ValCurs>
""".encode()


def _cbr_key_rate_soap(*, effective_date: str, rate: str) -> bytes:
    embedded = (
        f"&lt;Root&gt;&lt;KR&gt;&lt;DT&gt;{effective_date}T00:00:00&lt;/DT&gt;"
        f"&lt;Rate&gt;{rate}&lt;/Rate&gt;&lt;/KR&gt;&lt;/Root&gt;"
    )
    return f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <KeyRateXMLResponse xmlns="http://web.cbr.ru/">
      <KeyRateXMLResult>{embedded}</KeyRateXMLResult>
    </KeyRateXMLResponse>
  </soap:Body>
</soap:Envelope>
""".encode()


def test_key_rate_history_preserves_each_effective_day_and_exact_requested_window() -> None:
    payload = b"""<Root>
    <KR><DT>2026-09-30T00:00:00</DT><Rate>18</Rate></KR>
    <KR><DT>2026-10-01T00:00:00</DT><Rate>17,5</Rate></KR>
    <KR><DT>2026-10-02T00:00:00</DT><Rate>17</Rate></KR>
    </Root>"""
    with patch("urllib.request.urlopen", return_value=FakeXmlResponse(payload)) as request:
        rates = CBRClient().key_rate_history(date(2026, 10, 1), date(2026, 10, 2))
    assert [(row.effective_date, row.value) for row in rates] == [
        (date(2026, 10, 1), "17.5"), (date(2026, 10, 2), "17"),
    ]
    body = request.call_args.args[0].data
    assert b"<fromDate>2026-10-01T00:00:00</fromDate>" in body
    assert b"<ToDate>2026-10-02T23:59:59</ToDate>" in body
    service, oldest, newest = CBRClient(), date(2020, 1, 1), date(2026, 10, 2)
    with patch("urllib.request.urlopen") as request, pytest.raises(ValueError):
        service.key_rate_history(oldest, newest)
    request.assert_not_called()


def test_key_rate_history_refuses_duplicate_source_dates() -> None:
    payload = b"""<Root>
    <KR><DT>2026-10-01T00:00:00</DT><Rate>18</Rate></KR>
    <KR><DT>2026-10-01T00:00:00</DT><Rate>17</Rate></KR></Root>"""
    service, oldest, newest = CBRClient(), date(2026, 10, 1), date(2026, 10, 2)
    with (
        patch("urllib.request.urlopen", return_value=FakeXmlResponse(payload)),
        pytest.raises(CBRUnavailable, match="duplicate"),
    ):
        service.key_rate_history(oldest, newest)


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
    requested_date = date(2026, 10, 1)

    with patch(
        "urllib.request.urlopen",
        side_effect=TimeoutError("timeout"),
    ) as urlopen:
        with pytest.raises(CBRUnavailable):
            client.usd_rub_rate(requested_date)
        with pytest.raises(CBRUnavailable):
            client.usd_rub_rate(requested_date)

    urlopen.assert_called_once()


def test_cbr_client_fetches_and_caches_compact_public_indicators() -> None:
    client = CBRClient(indicator_cache_seconds=300)
    daily = _cbr_indicators_xml(
        effective_date="03.10.2026",
        usd="83,4839",
        eur="94,3201",
    )
    key_rate = _cbr_key_rate_soap(effective_date="2026-10-02", rate="14.00")

    with patch(
        "urllib.request.urlopen",
        side_effect=[
            FakeXmlResponse(daily),
            FakeXmlResponse(key_rate),
        ],
    ) as urlopen:
        indicators = client.latest_indicators()
        cached = client.latest_indicators()

    assert indicators == cached
    assert indicators.usd_rub.value == "83.4839"
    assert indicators.usd_rub.effective_date == date(2026, 10, 3)
    assert indicators.eur_rub.value == "94.3201"
    assert indicators.eur_rub.effective_date == date(2026, 10, 3)
    assert indicators.key_rate.value == "14"
    assert indicators.key_rate.effective_date == date(2026, 10, 2)
    assert urlopen.call_count == 2

    daily_request = urlopen.call_args_list[0].args[0]
    key_rate_request = urlopen.call_args_list[1].args[0]
    assert daily_request.full_url == "https://www.cbr.ru/scripts/XML_daily.asp"
    assert key_rate_request.full_url == "https://www.cbr.ru/DailyInfoWebServ/DailyInfo.asmx"
    assert key_rate_request.data is not None
    assert b"<KeyRateXML" in key_rate_request.data
    assert b"<fromDate>" in key_rate_request.data
    assert b"<ToDate>" in key_rate_request.data


def test_cbr_client_rejects_key_rate_without_current_effective_value() -> None:
    client = CBRClient()
    daily = _cbr_indicators_xml(
        effective_date="03.10.2026",
        usd="83,4839",
        eur="94,3201",
    )
    future_key_rate = _cbr_key_rate_soap(
        effective_date="2999-01-01",
        rate="99.00",
    )

    with (
        patch(
            "urllib.request.urlopen",
            side_effect=[
                FakeXmlResponse(daily),
                FakeXmlResponse(future_key_rate),
            ],
        ),
        pytest.raises(CBRUnavailable, match="no requested key rate"),
    ):
        client.latest_indicators()


class FakeBroker:
    def __init__(self, quote_time: str) -> None:
        self.quote_time = quote_time

    def market_status(self) -> MarketSourceStatus:
        return MarketSourceStatus(True, "tbank", "fixture-source")

    def status(self, user_id: UUID) -> None:
        raise AssertionError("Public market data must never inspect a user connection")

    def market_instrument_metadata(
        self, user_id: UUID, instrument_uid: str,
    ) -> TBankInstrumentMetadata:
        assert instrument_uid == "uid-1"
        return TBankInstrumentMetadata(
            uid=instrument_uid, name="Fixture share", ticker="FIX", isin="",
            instrument_type="share", sector="", country_of_risk="RU",
            for_qual_investor=False, currency="RUB",
        )

    def usd_rub_quote(self, user_id: UUID) -> TBankFxQuote:
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

    def latest_indicators(self) -> CBRIndicators:
        fetched_at = datetime(2026, 10, 3, 7, 0, tzinfo=UTC)
        return CBRIndicators(
            usd_rub=CBRRate(
                currency="RUB",
                value="83.4839",
                nominal=1,
                effective_date=date(2026, 10, 3),
                fetched_at=fetched_at,
            ),
            eur_rub=CBRRate(
                currency="RUB",
                value="94.3201",
                nominal=1,
                effective_date=date(2026, 10, 3),
                fetched_at=fetched_at,
            ),
            key_rate=CBRKeyRate(
                value="14",
                effective_date=date(2026, 10, 2),
                fetched_at=fetched_at,
            ),
            fetched_at=fetched_at,
            freshness="fresh",
        )


def test_market_service_maps_broker_independent_cbr_indicators() -> None:
    service = MarketService(
        broker=FakeBroker(datetime.now(UTC).isoformat()),  # type: ignore[arg-type]
        cbr=FakeCBR(),  # type: ignore[arg-type]
    )

    snapshot = service.cbr_indicators()

    assert snapshot.source == "Bank of Russia"
    assert snapshot.freshness == "fresh"
    assert snapshot.key_rate.code == "KEY_RATE"
    assert snapshot.key_rate.value == "14"
    assert snapshot.key_rate.unit == "percent"
    assert snapshot.key_rate.effective_date == "2026-10-02"
    assert snapshot.usd_rub.value == "83.4839"
    assert snapshot.eur_rub.value == "94.3201"


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


@pytest.mark.parametrize("ahead_seconds", [5, 6])
def test_fx_quote_uses_the_same_provider_clock_tolerance_as_instrument_quotes(
    ahead_seconds: int,
) -> None:
    now = datetime(2026, 10, 8, tzinfo=UTC)
    broker = FakeBroker((now + timedelta(seconds=ahead_seconds)).isoformat())
    service = MarketService(broker=broker, cbr=FakeCBR())  # type: ignore[arg-type]
    owner = UUID("00000000-0000-0000-0000-000000000001")
    with patch("omnicio.market.datetime") as clock:
        clock.now.return_value = now
        clock.fromisoformat.side_effect = datetime.fromisoformat
        if ahead_seconds == 5:
            snapshot = service.usd_rub(owner)
            assert snapshot.status == "live"
            assert snapshot.age_seconds == 0
        else:
            with pytest.raises(TBankUnavailable, match="quote_timestamp"):
                service.usd_rub(owner)


@pytest.mark.parametrize("changes", [
    {"price": "0"}, {"price": "-83.37"}, {"price": "NaN"}, {"currency": "EUR"},
])
def test_invalid_fx_price_or_currency_cannot_be_presented_as_live(
    changes: dict[str, str],
) -> None:
    owner = UUID("00000000-0000-0000-0000-000000000001")
    broker = FakeBroker(datetime.now(UTC).isoformat())
    quote = replace(broker.usd_rub_quote(owner), **changes)
    with patch.object(broker, "usd_rub_quote", return_value=quote):
        service = MarketService(broker=broker, cbr=FakeCBR())  # type: ignore[arg-type]
        with pytest.raises(TBankUnavailable):
            service.usd_rub(owner)


@pytest.mark.parametrize("previous", ["0", "-83.10", "NaN"])
def test_invalid_fx_previous_close_does_not_hide_valid_current_quote(previous: str) -> None:
    owner = UUID("00000000-0000-0000-0000-000000000001")
    broker = FakeBroker(datetime.now(UTC).isoformat())
    quote = replace(broker.usd_rub_quote(owner), previous_close=previous)
    with patch.object(broker, "usd_rub_quote", return_value=quote):
        service = MarketService(broker=broker, cbr=FakeCBR())  # type: ignore[arg-type]
        snapshot = service.usd_rub(owner)
    assert snapshot.status == "live"
    assert snapshot.price == "83.37"
    assert snapshot.previous_close is None
    assert snapshot.change is None
    assert snapshot.change_percent is None


def test_market_service_instrument_snapshot_preserves_quote_time_ohlc_and_status() -> None:
    service = MarketService(
        broker=FakeBroker(datetime.now(UTC).isoformat()),  # type: ignore[arg-type]
        cbr=FakeCBR(),  # type: ignore[arg-type]
        live_after_seconds=30,
    )

    operation = partial(
        service.instrument_snapshot,
        UUID("00000000-0000-0000-0000-000000000001"),
        "uid-1",
        period="1m",
    )
    try:
        operation()
        _finish_market_reads(service)
        snapshot = operation()
    finally:
        service.close()

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
    candle = next(iter(snapshot.candles), None)
    assert candle is not None
    assert candle.open == "100"
    assert candle.high == "103"
    assert candle.low == "99"
    assert candle.close == "102"
    assert candle.is_complete is True


def test_market_service_future_quote_timestamp_fails_closed() -> None:
    broker = FakeBroker(datetime.now(UTC).isoformat())

    def future_price(
        user_id: UUID,
        instrument_uid: str,
    ) -> TBankLastPrice:
        assert instrument_uid == "uid-1"
        return TBankLastPrice(
            instrument_uid="uid-1",
            price="102.5",
            time=datetime.now(UTC) + timedelta(hours=1),
        )

    broker.market_last_price = future_price  # type: ignore[method-assign]
    service = MarketService(
        broker=broker,  # type: ignore[arg-type]
        cbr=FakeCBR(),  # type: ignore[arg-type]
        live_after_seconds=30,
    )

    try:
        state = service.instrument_live_state(
            UUID("00000000-0000-0000-0000-000000000001"),
            "uid-1",
        )
    finally:
        service.close()

    assert state.quote_status == "future"
    assert state.last_price is None
    assert state.quote_age_seconds is None
    assert state.quote_time is not None


def test_market_service_one_year_period_stays_within_provider_request_window() -> None:
    class OneYearBroker(FakeBroker):
        def market_exchange_candles(
            self,
            user_id: UUID,
            instrument_uid: str,
            *,
            from_at: datetime,
            to_at: datetime,
            interval: str,
        ) -> tuple[TBankHistoricCandle, ...]:
            assert to_at - from_at == timedelta(days=365)
            assert interval == "CANDLE_INTERVAL_DAY"
            return super().market_exchange_candles(
                user_id,
                instrument_uid,
                from_at=to_at - timedelta(days=31),
                to_at=to_at,
                interval="CANDLE_INTERVAL_4_HOUR",
            )

    service = MarketService(
        broker=OneYearBroker(datetime.now(UTC).isoformat()),  # type: ignore[arg-type]
        cbr=FakeCBR(),  # type: ignore[arg-type]
        live_after_seconds=30,
    )

    operation = partial(
        service.instrument_snapshot,
        UUID("00000000-0000-0000-0000-000000000001"),
        "uid-1",
        period="1y",
    )
    try:
        operation()
        _finish_market_reads(service)
        snapshot = operation()
    finally:
        service.close()

    assert snapshot.period == "1y"
    assert snapshot.interval == "CANDLE_INTERVAL_DAY"


def test_market_service_rejects_malformed_provider_ohlc_as_unavailable() -> None:
    broker = FakeBroker(datetime.now(UTC).isoformat())
    original = broker.market_exchange_candles

    def malformed(*args: object, **kwargs: object) -> tuple[TBankHistoricCandle, ...]:
        candles = original(*args, **kwargs)  # type: ignore[arg-type]
        candle = next(iter(candles), None)
        assert candle is not None
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

    operation = partial(
        service.instrument_snapshot,
        UUID("00000000-0000-0000-0000-000000000001"), "uid-1", period="1m",
    )
    try:
        operation()
        _finish_market_reads(service)
        snapshot = operation()
    finally:
        service.close()
    assert snapshot.history_status == "unavailable"
    assert snapshot.errors["history"] == "source_unavailable"
    assert snapshot.candles == ()
    assert snapshot.last_price == "102.5"


def test_market_service_rejects_unknown_instrument_period_before_provider_read() -> None:
    service = MarketService(
        broker=FakeBroker(datetime.now(UTC).isoformat()),  # type: ignore[arg-type]
        cbr=FakeCBR(),  # type: ignore[arg-type]
    )

    try:
        with pytest.raises(ValueError, match="unsupported market period"):
            service.instrument_snapshot(
                UUID("00000000-0000-0000-0000-000000000001"),
                "uid-1",
                period="decade",
            )
    finally:
        service.close()


@pytest.mark.parametrize("failed", ["history", "quote", "trading_status", "metadata"])
def test_provider_component_failure_keeps_independent_market_data(failed: str) -> None:
    broker = FakeBroker(datetime.now(UTC).isoformat())
    methods = {"history": "market_exchange_candles", "quote": "market_last_price",
               "trading_status": "market_trading_status", "metadata": "market_instrument_metadata"}
    setattr(broker, methods[failed], Mock(side_effect=TBankUnavailable("private upstream text")))
    service = MarketService(broker=broker, cbr=FakeCBR())  # type: ignore[arg-type]
    try:
        operation = partial(
            service.instrument_snapshot,
            UUID("00000000-0000-0000-0000-000000000001"), "uid-1", period="1m",
        )
        operation()
        _finish_market_reads(service)
        result = operation()
        assert result.errors[failed] == "source_unavailable"
        assert bool(result.candles) is (failed != "history")
        assert result.last_price == (None if failed == "quote" else "102.5")
        if failed == "trading_status":
            assert result.trading_status == "UNKNOWN"
            assert result.api_trade_available is False
        if failed == "metadata":
            assert result.price_unit == "unknown"
            assert result.price_currency is None
        assert "private" not in str(result)
    finally:
        service.close()


def test_metadata_retry_deadline_survives_continuous_stream_readers() -> None:
    owner, uid = UUID(int=1), "uid-1"
    fixture = FakeBroker(datetime.now(UTC).isoformat())
    broker = Mock(wraps=fixture)
    metadata = fixture.market_instrument_metadata(owner, uid)
    broker.market_instrument_metadata.side_effect = [TBankUnavailable("transient"), metadata]
    service = MarketService(broker=broker, cbr=Mock(spec=CBRClient))
    leases = [service.acquire_stream(owner), service.acquire_stream(owner)]
    try:
        with patch("omnicio.market.time.monotonic") as clock:
            # Two permitted streams read the same instrument at staggered intervals.
            for at in (0, 2.5, 4.9):
                clock.return_value = at
                service.instrument_live_state(owner, uid)
                _finish_market_reads(service)
                result = service.instrument_live_state(owner, uid)
                assert result.metadata_status == "unavailable"
                assert result.last_price == "102.5"
            assert broker.market_instrument_metadata.call_count == 1
            clock.return_value = 5
            service.instrument_live_state(owner, uid)
            _finish_market_reads(service)
            recovered = service.instrument_live_state(owner, uid)
            assert broker.market_instrument_metadata.call_count == 2
            assert recovered.metadata_status == "available"
            assert recovered.price_currency == "RUB"
    finally:
        for lease in leases:
            service.release_stream(owner, lease)
        service.close()


def test_blocked_metadata_does_not_delay_live_quote_and_completion_is_adopted() -> None:
    owner, uid = UUID(int=1), "uid-1"
    fixture = FakeBroker(datetime.now(UTC).isoformat())
    broker = Mock(wraps=fixture)
    service = MarketService(broker=broker, cbr=Mock(spec=CBRClient))
    entered, release = Event(), Event()

    def delayed_metadata(user_id: UUID, instrument_uid: str) -> TBankInstrumentMetadata:
        entered.set()
        assert release.wait(timeout=5)
        return fixture.market_instrument_metadata(user_id, instrument_uid)

    broker.market_instrument_metadata.side_effect = delayed_metadata
    try:
        with ThreadPoolExecutor(max_workers=1) as readers:
            quote = readers.submit(service.instrument_live_state, owner, uid)
            try:
                assert entered.wait(timeout=5)
                result = quote.result(timeout=1)
                assert result.last_price == "102.5"
                assert result.quote_status == "live"
                assert result.metadata_status == "loading"
            finally:
                release.set()
            _finish_market_reads(service)
            assert service.instrument_live_state(owner, uid).metadata_status == "available"
            broker.market_instrument_metadata.assert_called_once_with(PUBLIC_MARKET_SCOPE, uid)
    finally:
        release.set()
        service.close()


def test_real_wire_history_is_single_flight_and_never_blocks_an_independent_quote() -> None:
    owner, uid, now = UUID(int=1), "uid-1", datetime.now(UTC)
    fixture = FakeBroker(now.isoformat())
    broker, client = Mock(wraps=fixture), TBankInvestClient(purpose="market")
    entered = {name: Event() for name in ("history", "metadata", "trading")}
    release = {name: Event() for name in entered}
    row = {"open": {"units": "100"}, "high": {"units": "102"},
           "low": {"units": "99"}, "close": {"units": "101"},
           "time": now.isoformat(), "candleSource": "CANDLE_SOURCE_EXCHANGE"}

    def transport(request, **kwargs):
        if request.full_url.endswith("/GetCandles"):
            body = json.loads(request.data)
            assert body["candleSourceType"] == "CANDLE_SOURCE_EXCHANGE"
            assert "candleSource" not in body
            entered["history"].set()
            assert release["history"].wait(timeout=5)
            payload = {"candles": [row]}
        else:
            assert request.full_url.endswith("/GetLastPrices")
            payload = {"lastPrices": [{"instrumentUid": uid, "time": now.isoformat(),
                                       "price": {"units": "101", "nano": 1}}]}
        return io.BytesIO(json.dumps(payload).encode())

    def metadata(user_id, instrument_uid):
        entered["metadata"].set()
        assert release["metadata"].wait(timeout=5)
        return fixture.market_instrument_metadata(user_id, instrument_uid)

    def trading(user_id, instrument_uid):
        entered["trading"].set()
        assert release["trading"].wait(timeout=5)
        return fixture.market_trading_status(user_id, instrument_uid)

    broker.market_exchange_candles.side_effect = lambda _user, instrument_uid, **kwargs: (
        client.get_exchange_candles("synthetic-test-credential", "prod", instrument_uid, **kwargs)
    )
    broker.market_last_price.side_effect = lambda _user, instrument_uid: client.get_last_prices(
        "synthetic-test-credential", "prod", (instrument_uid,),
    )[0]
    broker.market_instrument_metadata.side_effect = metadata
    broker.market_trading_status.side_effect = trading
    service = MarketService(broker=broker, cbr=Mock(spec=CBRClient))
    try:
        with (
            patch("urllib.request.OpenerDirector.open", side_effect=transport),
            ThreadPoolExecutor(max_workers=2) as requests,
        ):
            first = requests.submit(service.instrument_snapshot, owner, uid, period="1d")
            try:
                assert all(event.wait(timeout=5) for event in entered.values())
                pending = first.result(timeout=1)
                assert pending.last_price == "101.000000001"
                assert pending.quote_status == "live"
                assert pending.history_status == "loading"
                assert pending.history_observed_at is None
                assert pending.metadata_status == pending.trading_status_status == "loading"
                second = requests.submit(service.instrument_snapshot, owner, uid, period="1d")
                assert second.result(timeout=1).last_price == pending.last_price
                assert broker.market_exchange_candles.call_count == 1
                release["history"].set()
                with service._cache_lock:
                    history = next(entry.future for key, entry in service._enrichment.items()
                                   if key[2] == "history")
                assert history is not None
                history.result(timeout=5)
                ready = service.instrument_snapshot(owner, uid, period="1d")
                assert ready.history_status == "available"
                assert ready.metadata_status == "loading"
                assert ready.candles[0].close == "101"
                assert ready.candles[0].is_complete is False
                assert ready.candles[0].volume_lots == 0
                assert ready.history_observed_at is not None
                again = service.instrument_snapshot(owner, uid, period="1d")
                assert again.history_observed_at == ready.history_observed_at
                assert broker.market_exchange_candles.call_count == 1
            finally:
                for event in release.values():
                    event.set()
                _finish_market_reads(service)
    finally:
        for event in release.values():
            event.set()
        service.close()


def test_metadata_backlog_reserves_history_workers_and_all_quote_rows_progress() -> None:
    owner, another, now = UUID(int=1), UUID(int=2), datetime.now(UTC)
    uids = tuple(f"uid-{index}" for index in range(50))
    broker = Mock()
    broker.market_status.side_effect = lambda: MarketSourceStatus(True, "tbank", "shared")
    broker.market_last_prices.side_effect = lambda user, ids: TBankLastPriceBatch(tuple(
        TBankLastPrice(uid, "101", now) for uid in ids
    ))
    broker.market_last_price.side_effect = lambda user, uid: TBankLastPrice(uid, "101", now)
    broker.market_trading_status.side_effect = lambda user, uid: TBankTradingStatus(
        uid, "SECURITY_TRADING_STATUS_NORMAL_TRADING", False, False, True, False, False,
    )
    metadata_release, two_started, backlog_finished, last_finished = (Event() for _ in range(4))
    history_release = Event()
    history_entered = {"selected-1": Event(), "selected-2": Event()}
    metadata_seen: list[str] = []
    seen_lock = Lock()

    def metadata(user, uid):
        with seen_lock:
            metadata_seen.append(uid)
            if len(metadata_seen) == 2:
                two_started.set()
        assert metadata_release.wait(timeout=5)
        with seen_lock:
            if len(metadata_seen) >= 49:
                backlog_finished.set()
            if uid == uids[-1]:
                last_finished.set()
        return TBankInstrumentMetadata(
            uid, uid, uid, "", "share", "", "RU", False, currency="RUB",
        )

    def history(user, uid, **kwargs):
        history_entered[uid].set()
        assert history_release.wait(timeout=5)
        return ()

    broker.market_instrument_metadata.side_effect = metadata
    broker.market_exchange_candles.side_effect = history
    service = MarketService(broker=broker, cbr=Mock(spec=CBRClient))
    try:
        with ThreadPoolExecutor(max_workers=2) as requests:
            try:
                batch = service.batch_quotes(owner, uids)
                assert two_started.wait(timeout=5)
                assert all(item["last_price"] == "101" for item in batch["items"])
                assert len(metadata_seen) == 2
                for user in (owner, another):
                    result = requests.submit(
                        service.instrument_snapshot, user, f"selected-{user.int}", period="1d",
                    )
                    assert history_entered[f"selected-{user.int}"].wait(timeout=1)
                    snapshot = result.result(timeout=1)
                    assert snapshot.last_price == "101"
                    assert snapshot.history_status == "loading"
                # History is still blocked. Its separate slots must not stop
                # either the current quotes or FIFO completion of metadata.
                metadata_release.set()
                assert backlog_finished.wait(timeout=5)
                service.batch_quotes(owner, uids)
                assert last_finished.wait(timeout=5)
                with service._cache_lock:
                    finishing = [entry.future for key, entry in service._enrichment.items()
                                 if key[2] == "metadata" and entry.future is not None]
                for future in finishing:
                    future.result(timeout=5)
                ready = service.batch_quotes(owner, uids)
                assert all(item["last_price"] == "101" for item in ready["items"])
                assert all(item["price_currency"] == "RUB" for item in ready["items"])
                assert set(uids) <= set(metadata_seen)
                assert all(metadata_seen.count(uid) == 1 for uid in uids)
                requests.submit(service.close).result(timeout=1)
                assert not service._enrichment
                with pytest.raises(BrokerConnectionError, match="closed"):
                    service.instrument_snapshot(owner, "selected", period="1d")
            finally:
                metadata_release.set()
                history_release.set()
    finally:
        metadata_release.set()
        history_release.set()
        service.close()


def test_late_source_observation_cannot_evict_current_market_cache() -> None:
    owner, uid, now = UUID(int=1), "uid-1", datetime.now(UTC)
    old = MarketSourceStatus(True, "prod", "old")
    current_connection = MarketSourceStatus(
        True, "prod", "current",
    )
    current, first_old = old, True
    entered, release = Event(), Event()

    def status():
        nonlocal first_old
        if current_thread().name.startswith("late-old") and first_old:
            first_old = False
            captured = current
            entered.set()
            assert release.wait(timeout=5)
            return captured
        return current

    broker = Mock(wraps=FakeBroker(now.isoformat()))
    broker.market_status.side_effect = status
    service = MarketService(broker=broker, cbr=Mock(spec=CBRClient))
    try:
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="late-old") as readers:
            obsolete = readers.submit(service.instrument_live_state, owner, uid)
            try:
                assert entered.wait(timeout=5)
                current = current_connection
                service.instrument_live_state(owner, uid)
                _finish_market_reads(service)
                assert service.instrument_live_state(owner, uid).metadata_status == "available"
            finally:
                release.set()
            with pytest.raises(BrokerConnectionError):
                obsolete.result(timeout=5)
            with service._cache_lock:
                assert {key[1] for key in service._enrichment} == {current_connection}
            broker.market_instrument_metadata.assert_called_once()
    finally:
        release.set()
        service.close()


def test_late_intent_cannot_schedule_reads_after_a_new_source_is_accepted() -> None:
    owner, uid, now = UUID(int=1), "uid-1", datetime.now(UTC)
    old = MarketSourceStatus(True, "prod", "old")
    new = MarketSourceStatus(True, "prod", "new")
    current = old
    broker = Mock(wraps=FakeBroker(now.isoformat()))
    broker.market_status.side_effect = lambda: current
    service = MarketService(broker=broker, cbr=Mock(spec=CBRClient))
    accepted, release = Event(), Event()
    connection = service._connection

    def pause_after_accepted() -> MarketSourceStatus:
        captured = connection()
        if current_thread().name.startswith("old-intent"):
            assert captured == old
            accepted.set()
            assert release.wait(timeout=5)
        return captured

    try:
        with (
            patch.object(service, "_connection", side_effect=pause_after_accepted),
            ThreadPoolExecutor(max_workers=1, thread_name_prefix="old-intent") as requests,
        ):
            obsolete = requests.submit(service.instrument_live_state, owner, uid)
            try:
                assert accepted.wait(timeout=5)
                current = new
                service.instrument_live_state(owner, uid)
                _finish_market_reads(service)
                assert service.instrument_live_state(owner, uid).metadata_status == "available"
            finally:
                release.set()
            with pytest.raises(BrokerConnectionError):
                obsolete.result(timeout=5)
            with service._cache_lock:
                assert {key[1] for key in service._enrichment} == {new}
            broker.market_instrument_metadata.assert_called_once()
            broker.market_trading_status.assert_called_once()
            # The accepted source quote is shared by subsequent readers.
            assert broker.market_last_price.call_count == 1
    finally:
        release.set()
        service.close()


def test_batch_quotes_share_cache_across_users_and_invalidate_on_source_rotation() -> None:
    owner = UUID("00000000-0000-0000-0000-000000000001")
    broker = Mock()
    first = MarketSourceStatus(True, "prod", "first")
    broker.market_status.return_value = first
    broker.market_last_prices.return_value = TBankLastPriceBatch((
        TBankLastPrice("uid-1", "10", datetime.now(UTC)),
        TBankLastPrice("uid-2", "NaN", datetime.now(UTC)),
    ))
    release = Event()

    def metadata_read(user_id: UUID, uid: str) -> TBankInstrumentMetadata:
        assert release.wait(timeout=5)
        return TBankInstrumentMetadata(uid, uid, uid, "", "share", "", "RU", False,
                                       currency="RUB")

    broker.market_instrument_metadata.side_effect = metadata_read
    service = MarketService(broker=broker, cbr=FakeCBR())  # type: ignore[arg-type]
    try:
        result = service.batch_quotes(owner, ("uid-1", "uid-2"))
        rows = result["items"]
        assert rows[0]["last_price"] == "10"
        assert rows[0]["metadata_status"] == "loading"
        assert rows[0]["price_currency"] is None
        assert rows[1]["quote_status"] == "unavailable"
        assert rows[1]["last_price"] is None
        service.batch_quotes(UUID(int=2), ("uid-1", "uid-2"))
        assert broker.market_last_prices.call_count == 1
        broker.status.assert_not_called()
        broker.market_status.return_value = MarketSourceStatus(True, "prod", "second")
        service.batch_quotes(owner, ("uid-1", "uid-2"))
        assert broker.market_last_prices.call_count == 2
    finally:
        release.set()
        service.close()


@pytest.mark.parametrize(
    "failure", ["non_finite", "price_missing", "timestamp", "uid", "duplicate"],
)
def test_quote_batch_uses_real_parser_and_keeps_strict_consumers_fail_closed(failure: str) -> None:
    owner, now = UUID(int=1), datetime.now(UTC)
    good = {"instrumentUid": "good", "price": {"units": "100", "nano": 0},
            "time": now.isoformat()}
    bad = {**good, "instrumentUid": "bad"}
    changes = {
        "non_finite": {"price": {"units": "NaN"}}, "price_missing": {"price": None},
        "timestamp": {"time": "not-a-timestamp"}, "uid": {"instrumentUid": "unexpected"},
        "duplicate": {"instrumentUid": "good"},
    }
    bad.update(changes[failure])
    client, broker = TBankInvestClient(purpose="market"), Mock()
    broker.market_status.return_value = MarketSourceStatus(True, "prod", "synthetic")
    broker.market_last_prices.side_effect = lambda _user, uids: client.get_last_prices_batch(
        "synthetic-token", "prod", uids,
    )
    broker.market_instrument_metadata.side_effect = lambda _user, uid: TBankInstrumentMetadata(
        uid, uid, uid, "", "share", "", "RU", False, currency="RUB",
    )
    service = MarketService(broker=broker, cbr=FakeCBR())  # type: ignore[arg-type]
    try:
        with patch.object(TBankInvestClient, "_post", return_value={"lastPrices": [good, bad]}):
            result = service.batch_quotes(owner, ("good", "bad", "absent"))
            with pytest.raises(TBankUnavailable):
                client.get_last_prices("synthetic-token", "prod", ("good", "bad", "absent"))
        items = {item["instrument_uid"]: item for item in result["items"]}
        if failure in {"uid", "duplicate"}:
            assert all(item["quote_status"] == "unavailable" for item in items.values())
            assert all(item["last_price"] is None for item in items.values())
        else:
            assert items["good"]["quote_status"] == "live"
            assert items["good"]["last_price"] == "100"
            assert items["bad"]["quote_status"] == "unavailable"
            assert items["bad"]["last_price"] is None
            assert items["bad"]["quote_time"] is None
            # A missing requested UID is incomplete provider evidence. Strict
            # consumers must not interpret that partial response as a full set.
            assert items["absent"]["quote_status"] == "unavailable"
        assert items["bad"]["errors"]["quote"] == "source_unavailable"
    finally:
        service.close()


@pytest.mark.parametrize("bad_price", [
    {"units": "1.5"}, {"nano": 0.1}, {"nano": "0.1"},
    {"units": "9223372036854775808"}, {"units": "-9223372036854775809"},
    {"nano": 2147483648}, {"nano": -2147483649},
    {"units": "1e999999"}, {"units": "1e1000000"},
    {"units": "NaN"}, {"nano": "sNaN"}, {"units": "Infinity"},
    {"units": True}, {"nano": []},
])
def test_invalid_protojson_price_cannot_escape_or_contaminate_valid_quotes(bad_price) -> None:
    owner, now = UUID(int=1), datetime.now(UTC)
    payload = json.dumps({"lastPrices": [
        {"instrumentUid": "good", "price": {"units": "1e2", "nano": 1.0},
         "time": now.isoformat()},
        {"instrumentUid": "bad", "price": bad_price, "time": now.isoformat()},
    ]}).encode()
    client, broker = TBankInvestClient(purpose="market"), Mock()
    broker.market_status.return_value = MarketSourceStatus(True, "prod", "synthetic")
    broker.market_last_prices.side_effect = lambda _user, uids: client.get_last_prices_batch(
        "synthetic-test-credential", "prod", uids,
    )
    broker.market_instrument_metadata.side_effect = lambda _user, uid: TBankInstrumentMetadata(
        uid, uid, uid, "", "share", "", "RU", False, currency="RUB",
    )
    service = MarketService(broker=broker, cbr=Mock(spec=CBRClient))
    try:
        with patch(
            "urllib.request.OpenerDirector.open",
            side_effect=lambda *args, **kwargs: io.BytesIO(payload),
        ):
            batch = client.get_last_prices_batch(
                "synthetic-test-credential", "prod", ("good", "bad"),
            )
            assert [(row.instrument_uid, row.price) for row in batch.prices] == [
                ("good", "100.000000001"),
            ]
            assert batch.unavailable_uids == ("bad",)
            with pytest.raises(TBankUnavailable):
                client.get_last_prices("synthetic-test-credential", "prod", ("good", "bad"))
            result = service.batch_quotes(owner, ("good", "bad"))
        items = {item["instrument_uid"]: item for item in result["items"]}
        assert items["good"]["quote_status"] == "live"
        assert items["good"]["last_price"] == "100.000000001"
        assert items["bad"]["quote_status"] == "unavailable"
        assert items["bad"]["last_price"] is None
        assert items["bad"]["errors"]["quote"] == "source_unavailable"
    finally:
        service.close()


def test_stream_admission_is_per_owner_bounded_and_idempotently_released() -> None:
    service = MarketService(broker=Mock(), cbr=FakeCBR())  # type: ignore[arg-type]
    owner, another = UUID(int=1), UUID(int=2)
    first, second = service.acquire_stream(owner), service.acquire_stream(owner)
    with pytest.raises(MarketStreamLimit):
        service.acquire_stream(owner)
    other = service.acquire_stream(another)
    service.release_stream(another, first)
    with pytest.raises(MarketStreamLimit):
        service.acquire_stream(owner)
    service.release_stream(owner, first)
    service.release_stream(owner, first)
    replacement = service.acquire_stream(owner)
    for user_id, lease in ((owner, second), (owner, replacement), (another, other)):
        service.release_stream(user_id, lease)
    assert service._streams == {}
    service.close()
    with pytest.raises(MarketStreamLimit, match="market_stream_closed"):
        service.acquire_stream(owner)
    service.release_stream(owner, replacement)


def _history_xml(*, rows: str, code: str = "R01235") -> bytes:
    return f'<ValCurs ID="{code}">{rows}</ValCurs>'.encode()


def _history_row(day: str, value: str, nominal: str = "1") -> str:
    return (f'<Record Date="{day}" Id="R01235"><Nominal>{nominal}</Nominal>'
            f'<Value>{value}</Value></Record>')


def test_public_history_preserves_exact_units_and_does_not_fill_missing_days() -> None:
    client = CBRClient()
    payload = _history_xml(rows=_history_row("02.10.2026", "123,4567", "10")
                           + _history_row("05.10.2026", "12,3401"))
    with patch("urllib.request.urlopen", return_value=FakeXmlResponse(payload)) as request:
        result = client._fetch_reference_history("USD", "1m", date(2026, 10, 6))
    assert result.points == (CBRHistoryPoint("2026-10-02", "12.34567"),
                             CBRHistoryPoint("2026-10-05", "12.3401"))
    assert result.currency == "USD"
    assert result.freshness == "received"
    assert result.to_date == "2026-10-06"
    assert "VAL_NM_RQ=R01235" in request.call_args.args[0].full_url
    assert not request.call_args.args[0].has_header("Authorization")


@pytest.mark.parametrize("rows,code", [
    (_history_row("07.10.2026", "80"), "R01235"),
    (_history_row("05.10.2026", "80", "0"), "R01235"),
    (_history_row("05.10.2026", "NaN"), "R01235"),
    (_history_row("05.10.2026", "1e-99999999"), "R01235"),
    (_history_row("05.10.2026", "８０"), "R01235"),
    (_history_row("05.10.2026", "80", "١"), "R01235"),
    (_history_row("05.10.2026", "80") + _history_row("05.10.2026", "81"), "R01235"),
    (_history_row("05.10.2026", "80"), "R01239"),
    ("<!DOCTYPE x><Record/>", "R01235"),
])
def test_public_history_rejects_unknown_conflicting_or_future_facts(rows: str, code: str) -> None:
    response = FakeXmlResponse(_history_xml(rows=rows, code=code))
    client = CBRClient()
    target = date(2026, 10, 6)
    with patch("urllib.request.urlopen", return_value=response), pytest.raises(CBRUnavailable):
        client._fetch_reference_history("USD", "1m", target)


def test_public_history_empty_is_empty_and_old_cache_keeps_original_timestamp() -> None:
    client = CBRClient(cache_seconds=0)
    with patch("urllib.request.urlopen", return_value=FakeXmlResponse(_history_xml(rows=""))):
        empty = client._fetch_reference_history("USD", "1m", date(2026, 10, 6))
    assert empty.points == ()
    with patch.object(
        client, "_fetch_reference_history", side_effect=[empty, CBRUnavailable("offline")],
    ) as fetch:
        first = client.reference_history("USD", "1m")
        old = client.reference_history("USD", "1m")
        again = client.reference_history("USD", "1m")
    assert old.fetched_at == first.fetched_at == again.fetched_at
    assert old.freshness == again.freshness == "cached"
    assert fetch.call_count == 2
    with patch.object(client, "_fetch_reference_history") as fetch:
        with pytest.raises(ValueError):
            client.reference_history("https://127.0.0.1/", "1m")
        fetch.assert_not_called()


def test_public_reference_never_reads_broker_and_releases_admission_after_failure() -> None:
    broker = Mock()
    cbr = Mock(spec=CBRClient)
    cbr.reference_history.side_effect = CBRUnavailable("offline")
    cbr.latest_indicators.side_effect = CBRUnavailable("offline")
    service = MarketService(broker=broker, cbr=cbr)
    for _ in range(3):
        result = service.public_reference("USD", "1m")
        assert result["status"] == "unavailable"
        assert result["history"] is None
        assert result["indicators"] is None
        assert result["personal_data"] is False
    assert not broker.mock_calls
    cbr.reference_history.side_effect = None
    cbr.reference_history.return_value = CBRHistory(
        "USD", "1m", "2026-09-05", "2026-10-06", "2026-10-06T10:00:00+00:00",
        "https://www.cbr.ru/scripts/XML_dynamic.asp", "received", (),
    )
    partial = service.public_reference("USD", "1m")
    assert partial["status"] == "partial"
    assert partial["history"] is not None
    assert partial["indicators"] is None
    assert not broker.mock_calls


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "0", "1e999999999", "1000000001"])
@pytest.mark.parametrize("feed", ["usd", "indicators"])
def test_cbr_currency_feeds_reject_invalid_values_before_caching(value, feed):
    client = CBRClient()
    payload = _cbr_indicators_xml(effective_date="01.10.2026", usd=value, eur="95")
    response = FakeXmlResponse(payload)
    read = client.usd_rub_rate if feed == "usd" else client.latest_indicators
    arguments = (date(2026, 10, 1),) if feed == "usd" else ()
    with (
        patch("urllib.request.urlopen", return_value=response),
        pytest.raises(CBRUnavailable),
    ):
        read(*arguments)
    assert not client._cached
    assert client._indicator_cached is None


@pytest.mark.parametrize("fault", ["duplicate", "truncated", "doctype", "oversized"])
def test_cbr_daily_reference_rejects_ambiguous_or_unbounded_responses(fault):
    payload = _cbr_xml(effective_date="01.10.2026", value="90")
    if fault == "duplicate":
        row = payload[payload.index(b"  <Valute"):payload.index(b"</ValCurs>")]
        payload = payload.replace(b"</ValCurs>", row + b"</ValCurs>")
    elif fault == "truncated":
        payload = payload.replace(b"</ValCurs>", b"")
    elif fault == "doctype":
        payload = payload.replace(b"<ValCurs", b'<!DOCTYPE ValCurs [<!ENTITY x "90">]><ValCurs', 1)
    else:
        payload += b" " * 512_001
    client, requested = CBRClient(), date(2026, 10, 1)
    response = FakeXmlResponse(payload)
    with (
        patch("urllib.request.urlopen", return_value=response),
        pytest.raises(CBRUnavailable),
    ):
        client.usd_rub_rate(requested)


def test_cbr_requested_date_rejects_future_rate_and_preserves_weekend_effective_date():
    client = CBRClient(cache_seconds=0)
    requested = date(2026, 10, 3)
    with patch("urllib.request.urlopen", side_effect=[
        FakeXmlResponse(_cbr_xml(effective_date="05.10.2026", value="90")),
        FakeXmlResponse(_cbr_xml(effective_date="02.10.2026", value="90")),
    ]):
        with pytest.raises(CBRUnavailable, match="future rate"):
            client.usd_rub_rate(requested)
        # A prior effective date on a non-publication day remains valid.
        rate = client.usd_rub_rate(date(2026, 10, 4))
    assert rate.effective_date == date(2026, 10, 2)
    assert rate.value == "90"


def test_public_collectors_run_without_users_survive_source_failure_and_share_results() -> None:
    now = datetime.now(UTC)
    broker = Mock(spec=BrokerService)
    broker.market_status.return_value = MarketSourceStatus(True, "tbank", "fixture-source")
    broker.market_catalog.return_value = (TBankInstrumentMetadata(
        "uid-1", "Fixture share", "FIX", "", "share", "", "RU", False,
        currency="RUB", asset_uid="asset-1",
    ),)
    broker.market_all_last_prices.return_value = TBankLastPriceBatch((
        TBankLastPrice("uid-1", "101", now - timedelta(seconds=2)),
    ))
    broker.candidate_fundamentals.return_value = ()
    broker.instrument_news.return_value = {
        "items": [], "next_cursor": None, "observed_at": now.isoformat(),
    }
    cbr, news = Mock(spec=CBRClient), Mock(spec=NewsClient)
    cbr.latest_indicators.side_effect = CBRUnavailable("fixture source outage")
    news.headlines.return_value = {
        "items": [], "freshness": "fresh", "fetched_at": now.isoformat(),
    }
    service = MarketService(broker=broker, cbr=cbr, news=news)
    quotes_done, risk_done = Event(), Event()
    quote_read, risk_read = service._collect_quotes, service._collect_fundamentals

    def collect_quotes():
        result = quote_read()
        quotes_done.set()
        return result

    def collect_risk():
        assert quotes_done.wait(timeout=5)
        result = risk_read()
        risk_done.set()
        return result

    try:
        with (patch.object(service, "_collect_quotes", side_effect=collect_quotes),
              patch.object(service, "_collect_fundamentals", side_effect=collect_risk)):
            service.start()
            first_workers = tuple(service._collectors)
            service.start()
            assert tuple(service._collectors) == first_workers
            assert risk_done.wait(timeout=5)
            snapshot = service.public_snapshot()
            assert snapshot["items"][0]["last_price"] == "101"
            assert snapshot["items"][0]["risk"]["state"] == "data_missing"
            assert snapshot["status"]["running"] is True
            assert snapshot["status"]["coverage"]["instruments"] == 1
            assert snapshot["status"]["user_tokens_used"] is False
            assert snapshot["status"]["sources"]["reference"]["status"] == "unavailable"
            for user_id in (UUID(int=1), UUID(int=2)):
                result = service.batch_quotes(user_id, ("uid-1",))
                assert result["items"][0]["last_price"] == "101"
            broker.market_last_prices.assert_not_called()
            broker.market_instrument_metadata.assert_not_called()
            broker.status.assert_not_called()
            broker.portfolio.assert_not_called()
            broker.candidate_fundamentals.assert_called_once_with(
                PUBLIC_MARKET_SCOPE, ("asset-1",),
            )
    finally:
        service.close()
    assert all(not worker.is_alive() for worker in first_workers)


def test_shared_market_reports_catalog_outage_and_clears_data_on_source_revocation() -> None:
    broker = Mock(spec=BrokerService)
    broker.market_status.return_value = MarketSourceStatus(True, "tbank", "source-one")
    broker.market_catalog.side_effect = TBankUnavailable("catalog unavailable")
    broker.market_all_last_prices.return_value = TBankLastPriceBatch((
        TBankLastPrice("uid-1", "101", datetime.now(UTC) - timedelta(minutes=15)),
    ))
    service = MarketService(broker=broker, cbr=Mock(spec=CBRClient))
    try:
        service._collect_quotes()
        status = service.status()
        assert status["coverage"]["catalog_status"] == "unavailable"
        assert status["coverage"]["instruments"] == 0
        assert status["coverage"]["quote_instruments"] == 1
        assert status["market_source"]["real_time_guaranteed"] is False
        broker.market_status.return_value = MarketSourceStatus(False, "tbank", "source-two")
        snapshot = service.public_snapshot()
        assert snapshot["items"] == []
        assert snapshot["price_changes"] == []
        assert snapshot["status"]["coverage"]["quote_instruments"] == 0
        broker.market_all_last_prices.assert_called_once()
        broker.status.assert_not_called()
    finally:
        service.close()


def test_public_news_reuses_collected_pages_exact_uids_and_preserves_source_freshness() -> None:
    now = datetime.now(UTC)
    broker = Mock(spec=BrokerService)
    broker.market_status.return_value = MarketSourceStatus(True, "tbank", "fixture-news")

    def item(ident: str, uids: tuple[str, ...], age: int) -> dict[str, object]:
        return {
            "id": ident, "title": "Fixture issuer update", "summary": "Public source summary",
            "instrument_uids": uids, "occurred_at": now - timedelta(minutes=age),
            "source": "Fixture provider", "source_url": "https://example.com/issuer",
            "priority": False,
        }

    broker.instrument_news.side_effect = [
        {"items": [item("1", ("uid-a",), 1), item("2", ("uid-b",), 2)],
         "next_cursor": "page-two", "observed_at": now.isoformat()},
        {"items": [item("3", (), 3)], "next_cursor": None,
         "observed_at": (now - timedelta(seconds=2)).isoformat()},
    ]
    service = MarketService(broker=broker, cbr=Mock(spec=CBRClient))
    try:
        result = service._collect_instrument_news()
        service._collector_states["instrument_news"] = _CollectorState(
            result.status, now, result.observed_at, result.items,
        )
        first = service.public_news(limit=2)
        assert [row["id"] for row in first["items"]] == ["1", "2"]
        assert first["status"] == "available"
        assert first["observed_at"] == now.isoformat()
        assert first["coverage"]["all_market_news"] is False
        last = service.public_news(limit=2, cursor=first["next_cursor"])
        assert [row["id"] for row in last["items"]] == ["3"]
        assert last["next_cursor"] is None
        assert last["items"][0]["observed_at"] == (now - timedelta(seconds=2)).isoformat()
        bookmark = service.public_news_item("3")
        assert bookmark["observed_at"] == last["items"][0]["observed_at"]
        assert bookmark["summary"] == "Public source summary"
        assert bookmark["full_content_available"] is False
        assert bookmark["content_scope"] == "source_summary"
        assert bookmark["content"] is None
        with pytest.raises(NewsNotFound):
            service.public_news_item("4")
        matched = service.public_news("uid-b", query="issuer")
        assert [row["id"] for row in matched["items"]] == ["2"]
        assert service.public_news("uid-c")["items"] == []
        assert broker.instrument_news.call_count == 2
        assert all(call.args[0] == PUBLIC_MARKET_SCOPE
                   for call in broker.instrument_news.call_args_list)
        broker.status.assert_not_called()
        with pytest.raises(ValueError, match="cursor_expired"):
            service.public_news(cursor="unknown")
        with patch("omnicio.market.datetime") as clock:
            clock.fromisoformat.side_effect = datetime.fromisoformat
            clock.now.return_value = now + timedelta(minutes=2)
            stale = service.public_news("uid-b")
            assert stale["status"] == "stale"
            assert stale["observed_at"] == now.isoformat()
            assert stale["items"][0]["observed_at"] == now.isoformat()
            assert service.public_news_item("1")["freshness"] == "stale"
            assert service.public_news_item("3")["observed_at"] == bookmark["observed_at"]
            clock.now.return_value = now + timedelta(days=3)
            assert service.public_news("uid-b")["items"] == []
            with pytest.raises(NewsNotFound):
                service.public_news_item("1")
        broker.market_status.return_value = MarketSourceStatus(False, "tbank", "revoked")
        assert service.public_news("uid-b")["status"] == "unavailable"
        assert service.public_news("uid-b")["items"] == []
        assert service.status()["sources"]["instrument_news"]["status"] == "not_configured"
        with pytest.raises(NewsUnavailable):
            service.public_news_item("1")
    finally:
        service.close()


@pytest.mark.parametrize("source_id", [
    "", "0", "-1", "01", "9" * 19, "a" * 63, "A" * 64, "١", "1١", "../../private",
    "https://www.cbr.ru/press/event/1",
])
def test_public_news_bookmark_rejects_invalid_identity_before_any_source_access(source_id) -> None:
    broker, news = Mock(spec=BrokerService), Mock(spec=NewsClient)
    service = MarketService(broker=broker, cbr=Mock(spec=CBRClient), news=news)
    try:
        with pytest.raises(ValueError, match="news_source_id_invalid"):
            service.public_news_item(source_id)
        assert not broker.mock_calls
        assert not news.mock_calls
    finally:
        service.close()


def test_public_cbr_bookmark_preserves_stale_headline_without_broker_or_full_article() -> None:
    now = datetime.now(UTC)
    broker, news = Mock(spec=BrokerService), Mock(spec=NewsClient)
    news.cached_headline.return_value = {
        "id": "a" * 64, "title": "Source headline", "source": "Банк России",
        "url": "https://www.cbr.ru/press/event/1", "published_at": now.isoformat(),
        "fetched_at": (now - timedelta(minutes=6)).isoformat(), "freshness": "cached",
        "content": "Do not expose full article from another cache", "private_field": "canary",
    }
    news.cached_headline.return_value["published_at"] = (now - timedelta(hours=1)).isoformat()
    service = MarketService(broker=broker, cbr=Mock(spec=CBRClient), news=news)
    try:
        result = service.public_news_item("a" * 64)
        assert result["id"] == "a" * 64
        assert result["observed_at"] == news.cached_headline.return_value["fetched_at"]
        assert result["freshness"] == "stale"
        assert result["full_content_available"] is False
        assert result["content_scope"] == "headline"
        assert result["content"] is None
        assert "private_field" not in result
        assert not broker.mock_calls
        news.headlines.assert_not_called()
        news.read_source.assert_not_called()
        news.cached_headline.return_value["fetched_at"] = (now + timedelta(hours=1)).isoformat()
        with pytest.raises(NewsUnavailable):
            service.public_news_item("a" * 64)
    finally:
        service.close()
