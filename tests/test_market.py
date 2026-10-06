from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from unittest.mock import Mock, patch
from uuid import UUID

import pytest

from omnicio.cbr import (
    CBRClient,
    CBRHistory,
    CBRHistoryPoint,
    CBRIndicators,
    CBRKeyRate,
    CBRRate,
    CBRUnavailable,
)
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
        pytest.raises(CBRUnavailable, match="no current key rate"),
    ):
        client.latest_indicators()


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
        assert user_id == UUID("00000000-0000-0000-0000-000000000001")
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

    state = service.instrument_live_state(
        UUID("00000000-0000-0000-0000-000000000001"),
        "uid-1",
    )

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

    snapshot = service.instrument_snapshot(
        UUID("00000000-0000-0000-0000-000000000001"),
        "uid-1",
        period="1y",
    )

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
    (_history_row("05.10.2026", "80") + _history_row("05.10.2026", "81"), "R01235"),
    (_history_row("05.10.2026", "80"), "R01239"),
    ("<!DOCTYPE x><Record/>", "R01235"),
])
def test_public_history_rejects_unknown_conflicting_or_future_facts(rows: str, code: str) -> None:
    response = FakeXmlResponse(_history_xml(rows=rows, code=code))
    with patch("urllib.request.urlopen", return_value=response), pytest.raises(CBRUnavailable):
        CBRClient()._fetch_reference_history("USD", "1m", date(2026, 10, 6))


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
