"""Read-only market-data orchestration for OmniCIO Personal."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from uuid import UUID

from .broker import BrokerService
from .cbr import CBRClient, CBRRate, CBRUnavailable
from .tbank import TBankLastPrice, TBankTradingStatus, TBankUnavailable


@dataclass(frozen=True, slots=True)
class MarketReferenceRate:
    source: str
    value: str
    currency: str
    effective_date: str
    fetched_at: str


@dataclass(frozen=True, slots=True)
class CBRIndicator:
    code: str
    value: str
    unit: str
    effective_date: str


@dataclass(frozen=True, slots=True)
class CBRIndicatorSnapshot:
    source: str
    fetched_at: str
    freshness: str
    key_rate: CBRIndicator
    usd_rub: CBRIndicator
    eur_rub: CBRIndicator


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
    cbr_next_reference: MarketReferenceRate | None


@dataclass(frozen=True, slots=True)
class InstrumentMarketCandle:
    time: str
    open: str
    high: str
    low: str
    close: str
    volume_lots: int
    is_complete: bool


@dataclass(frozen=True, slots=True)
class InstrumentMarketSnapshot:
    instrument_uid: str
    period: str
    interval: str
    source: str
    observed_at: str
    last_price: str | None
    quote_time: str | None
    quote_age_seconds: int | None
    quote_status: str
    trading_status: str
    api_trade_available: bool
    limit_order_available: bool
    market_order_available: bool
    candles: tuple[InstrumentMarketCandle, ...]


@dataclass(frozen=True, slots=True)
class InstrumentLiveState:
    instrument_uid: str
    observed_at: str
    last_price: str | None
    quote_time: str | None
    quote_age_seconds: int | None
    quote_status: str
    trading_status: str
    api_trade_available: bool
    limit_order_available: bool
    market_order_available: bool


_MARKET_PERIODS: dict[str, tuple[timedelta, str]] = {
    "1d": (timedelta(days=1), "CANDLE_INTERVAL_5_MIN"),
    "1w": (timedelta(days=7), "CANDLE_INTERVAL_HOUR"),
    "1m": (timedelta(days=31), "CANDLE_INTERVAL_4_HOUR"),
    "3m": (timedelta(days=93), "CANDLE_INTERVAL_DAY"),
    "1y": (timedelta(days=365), "CANDLE_INTERVAL_DAY"),
}

_PROVIDER_CLOCK_SKEW_TOLERANCE = timedelta(seconds=5)


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

    def cbr_indicators(self) -> CBRIndicatorSnapshot:
        indicators = self.cbr.latest_indicators()
        return CBRIndicatorSnapshot(
            source="Bank of Russia",
            fetched_at=indicators.fetched_at.isoformat(),
            freshness=indicators.freshness,
            key_rate=CBRIndicator(
                code="KEY_RATE",
                value=indicators.key_rate.value,
                unit="percent",
                effective_date=indicators.key_rate.effective_date.isoformat(),
            ),
            usd_rub=CBRIndicator(
                code="USD_RUB",
                value=indicators.usd_rub.value,
                unit="RUB",
                effective_date=indicators.usd_rub.effective_date.isoformat(),
            ),
            eur_rub=CBRIndicator(
                code="EUR_RUB",
                value=indicators.eur_rub.value,
                unit="RUB",
                effective_date=indicators.eur_rub.effective_date.isoformat(),
            ),
        )

    def usd_rub(self, user_id: UUID) -> UsdRubSnapshot:
        quote = self.broker.usd_rub_quote(user_id)
        observed = datetime.now(UTC)
        quote_time = _parse_provider_time(quote.quote_time)
        age_seconds = max(0, int((observed - quote_time).total_seconds()))
        change, change_percent = _change(quote.price, quote.previous_close)

        reference: MarketReferenceRate | None = None
        next_reference: MarketReferenceRate | None = None
        try:
            rate = self.cbr.usd_rub_rate()
        except CBRUnavailable:
            pass
        else:
            reference = _reference_rate(rate)

        try:
            latest_rate = self.cbr.latest_usd_rub_rate()
        except CBRUnavailable:
            pass
        else:
            if reference is not None and latest_rate.effective_date > rate.effective_date:
                next_reference = _reference_rate(latest_rate)

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
            cbr_next_reference=next_reference,
        )

    def instrument_snapshot(
        self,
        user_id: UUID,
        instrument_uid: str,
        *,
        period: str,
    ) -> InstrumentMarketSnapshot:
        config = _MARKET_PERIODS.get(period)
        if config is None:
            raise ValueError("unsupported market period")
        window, interval = config
        requested_at = datetime.now(UTC)
        candles = self.broker.market_exchange_candles(
            user_id,
            instrument_uid,
            from_at=requested_at - window,
            to_at=requested_at,
            interval=interval,
        )
        price = self.broker.market_last_price(user_id, instrument_uid)
        trading = self.broker.market_trading_status(user_id, instrument_uid)
        observed = datetime.now(UTC)

        live = _instrument_live_state(
            instrument_uid,
            observed=observed,
            last_price=price,
            trading=trading,
            live_after_seconds=self.live_after_seconds,
        )
        market_candles = tuple(
            InstrumentMarketCandle(
                time=item.time.astimezone(UTC).isoformat(),
                open=_required_market_price(item.open),
                high=_required_market_price(item.high),
                low=_required_market_price(item.low),
                close=item.close,
                volume_lots=item.volume_lots,
                is_complete=item.is_complete,
            )
            for item in candles
        )
        return InstrumentMarketSnapshot(
            instrument_uid=instrument_uid,
            period=period,
            interval=interval,
            source="T-Invest exchange candles",
            observed_at=observed.isoformat(),
            last_price=live.last_price,
            quote_time=live.quote_time,
            quote_age_seconds=live.quote_age_seconds,
            quote_status=live.quote_status,
            trading_status=live.trading_status,
            api_trade_available=live.api_trade_available,
            limit_order_available=live.limit_order_available,
            market_order_available=live.market_order_available,
            candles=market_candles,
        )

    def instrument_live_state(
        self,
        user_id: UUID,
        instrument_uid: str,
    ) -> InstrumentLiveState:
        price = self.broker.market_last_price(user_id, instrument_uid)
        trading = self.broker.market_trading_status(user_id, instrument_uid)
        observed = datetime.now(UTC)
        return _instrument_live_state(
            instrument_uid,
            observed=observed,
            last_price=price,
            trading=trading,
            live_after_seconds=self.live_after_seconds,
        )


def _required_market_price(value: str | None) -> str:
    if value is None:
        raise TBankUnavailable("T-Invest market candle is missing OHLC price")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise TBankUnavailable("T-Invest market candle contains invalid OHLC price") from exc
    if not number.is_finite() or number <= 0:
        raise TBankUnavailable("T-Invest market candle contains non-positive OHLC price")
    return value


def _instrument_live_state(
    instrument_uid: str,
    *,
    observed: datetime,
    last_price: TBankLastPrice | None,
    trading: TBankTradingStatus,
    live_after_seconds: int,
) -> InstrumentLiveState:
    price = last_price
    status = trading

    quote_time: datetime | None = None
    age_seconds: int | None = None
    quote_status = "missing"
    price_value: str | None = None
    if price is not None:
        quote_time = price.time.astimezone(UTC)
        provider_age = observed - quote_time
        if provider_age < -_PROVIDER_CLOCK_SKEW_TOLERANCE:
            quote_status = "future"
        else:
            age_seconds = max(0, int(provider_age.total_seconds()))
            quote_status = "live" if age_seconds <= live_after_seconds else "stale"
            price_value = price.price

    return InstrumentLiveState(
        instrument_uid=instrument_uid,
        observed_at=observed.isoformat(),
        last_price=price_value,
        quote_time=quote_time.isoformat() if quote_time is not None else None,
        quote_age_seconds=age_seconds,
        quote_status=quote_status,
        trading_status=status.trading_status,
        api_trade_available=status.api_trade_available,
        limit_order_available=status.limit_order_available,
        market_order_available=status.market_order_available,
    )


def _reference_rate(rate: CBRRate) -> MarketReferenceRate:
    return MarketReferenceRate(
        source="Bank of Russia",
        value=rate.value,
        currency=rate.currency,
        effective_date=rate.effective_date.isoformat(),
        fetched_at=rate.fetched_at.isoformat(),
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
