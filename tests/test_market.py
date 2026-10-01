from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import patch
from uuid import UUID

import pytest

from omnicio.cbr import CBRClient, CBRRate, CBRUnavailable
from omnicio.market import MarketService
from omnicio.tbank import TBankFxQuote


class FakeXmlResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> FakeXmlResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


def test_cbr_client_reads_daily_usd_rate_and_caches_it() -> None:
    xml = b"""<?xml version="1.0" encoding="windows-1251"?>
<ValCurs Date="01.10.2026" name="Foreign Currency Market">
  <Valute ID="R01235">
    <NumCode>840</NumCode>
    <CharCode>USD</CharCode>
    <Nominal>1</Nominal>
    <Name>US Dollar</Name>
    <Value>91,2345</Value>
  </Valute>
</ValCurs>
"""
    client = CBRClient(cache_seconds=3600)

    with patch(
        "urllib.request.urlopen",
        return_value=FakeXmlResponse(xml),
    ) as urlopen:
        first = client.usd_rub_rate()
        second = client.usd_rub_rate()

    assert first.currency == "RUB"
    assert first.value == "91.2345"
    assert first.nominal == 1
    assert first.effective_date == date(2026, 10, 1)
    assert second == first
    urlopen.assert_called_once()


def test_cbr_client_backs_off_after_initial_provider_failure() -> None:
    client = CBRClient(failure_retry_seconds=300)

    with patch(
        "urllib.request.urlopen",
        side_effect=TimeoutError("timeout"),
    ) as urlopen:
        with pytest.raises(CBRUnavailable):
            client.usd_rub_rate()
        with pytest.raises(CBRUnavailable):
            client.usd_rub_rate()

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
            price="92.25",
            currency="RUB",
            quote_time=self.quote_time,
            source="dealer",
            previous_close="91.9",
        )


class FakeCBR:
    def usd_rub_rate(self) -> CBRRate:
        return CBRRate(
            currency="RUB",
            value="91.2345",
            nominal=1,
            effective_date=date(2026, 10, 1),
            fetched_at=datetime(2026, 10, 1, 12, 0, tzinfo=UTC),
        )


def test_market_service_calculates_change_and_marks_fresh_quote_live() -> None:
    now = datetime.now(UTC)
    service = MarketService(
        broker=FakeBroker(now.isoformat()),  # type: ignore[arg-type]
        cbr=FakeCBR(),  # type: ignore[arg-type]
        live_after_seconds=30,
    )

    snapshot = service.usd_rub(UUID("00000000-0000-0000-0000-000000000001"))

    assert snapshot.pair == "USD/RUB"
    assert snapshot.price == "92.25"
    assert snapshot.source == "dealer"
    assert snapshot.status == "live"
    assert snapshot.change == "0.35"
    assert snapshot.change_percent is not None
    assert snapshot.change_percent.startswith("0.3808")
    assert snapshot.cbr_reference is not None
    assert snapshot.cbr_reference.value == "91.2345"


def test_market_service_marks_old_provider_timestamp_stale() -> None:
    service = MarketService(
        broker=FakeBroker("2026-01-01T00:00:00Z"),  # type: ignore[arg-type]
        cbr=FakeCBR(),  # type: ignore[arg-type]
        live_after_seconds=30,
    )

    snapshot = service.usd_rub(UUID("00000000-0000-0000-0000-000000000001"))

    assert snapshot.status == "stale"
    assert snapshot.age_seconds > 30
