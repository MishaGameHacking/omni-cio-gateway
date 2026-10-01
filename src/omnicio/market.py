"""Read-only market-data orchestration for OmniCIO Personal."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID

from .broker import BrokerService
from .cbr import CBRClient, CBRUnavailable

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MarketReferenceRate:
    source: str
    value: str
    currency: str
    effective_date: str
    fetched_at: str


@dataclass(frozen=True, slots=True)
class UsdRubSnapshot:
    pair: str
    price: str
    currency: str
    ticker: str
    instrument_name: str
    class_code: str
    source: str
    quote_time: str
    observed_at: str
    age_seconds: int
    status: str
    previous_close: str | None
    change: str | None
    change_percent: str | None
    cbr_reference: MarketReferenceRate | None


class MarketService:
    def __init__(
        self,
        *,
        broker: BrokerService,
        cbr: CBRClient,
        live_after_seconds: int = 30,
    ) -> None:
        self.broker = broker
        self.cbr = cbr
        self.live_after_seconds = live_after_seconds

    def usd_rub(self, user_id: UUID) -> UsdRubSnapshot:
        quote = self.broker.usd_rub_quote(user_id)
        observed = datetime.now(UTC)
        quote_time = _parse_provider_time(quote.quote_time)
        age_seconds = max(0, int((observed - quote_time).total_seconds()))
        change, change_percent = _change(quote.price, quote.previous_close)

        reference: MarketReferenceRate | None = None
        try:
            rate = self.cbr.usd_rub_rate()
        except CBRUnavailable:
            logger.warning("Bank of Russia reference rate unavailable")
        else:
            reference = MarketReferenceRate(
                source="Bank of Russia",
                value=rate.value,
                currency=rate.currency,
                effective_date=rate.effective_date.isoformat(),
                fetched_at=rate.fetched_at.isoformat(),
            )

        return UsdRubSnapshot(
            pair="USD/RUB",
            price=quote.price,
            currency=quote.currency,
            ticker=quote.ticker,
            instrument_name=quote.name,
            class_code=quote.class_code,
            source=quote.source,
            quote_time=quote_time.isoformat(),
            observed_at=observed.isoformat(),
            age_seconds=age_seconds,
            status="live" if age_seconds <= self.live_after_seconds else "stale",
            previous_close=quote.previous_close,
            change=change,
            change_percent=change_percent,
            cbr_reference=reference,
        )


def _parse_provider_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid provider quote timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("provider quote timestamp must include timezone")
    return parsed.astimezone(UTC)


def _change(
    price_value: str,
    previous_close_value: str | None,
) -> tuple[str | None, str | None]:
    if previous_close_value is None:
        return None, None
    try:
        price = Decimal(price_value)
        previous_close = Decimal(previous_close_value)
    except InvalidOperation as exc:
        raise ValueError("invalid market price") from exc
    if previous_close == 0:
        return None, None

    change = price - previous_close
    change_percent = (change / previous_close) * Decimal(100)
    return (
        _decimal_text(change),
        _decimal_text(change_percent),
    )


def _decimal_text(value: Decimal) -> str:
    if value == 0:
        return "0"
    return format(value.normalize(), "f")
