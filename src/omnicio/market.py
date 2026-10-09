"""Read-only market-data orchestration for OmniCIO Personal."""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid4

from .broker import BrokerConnectionError, BrokerConnectionStatus, BrokerService
from .cbr import CBRClient, CBRRate, CBRUnavailable
from .tbank import (
    TBankHistoricCandle,
    TBankInstrumentMetadata,
    TBankLastPrice,
    TBankLastPriceBatch,
    TBankTradingStatus,
    TBankUnavailable,
)

type _QuoteCacheEntry = tuple[float, TBankLastPrice | None, datetime, str | None]


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
    history_from: str | None = None
    history_note: str | None = None
    price_unit: str = "unknown"
    price_currency: str | None = None
    cash_price: str | None = None
    cash_price_currency: str | None = None
    history_status: str = "available"
    trading_status_status: str = "available"
    metadata_status: str = "available"
    errors: dict[str, str | None] = field(default_factory=dict)
    history_observed_at: str | None = None


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
    price_unit: str = "unknown"
    price_currency: str | None = None
    cash_price: str | None = None
    cash_price_currency: str | None = None
    trading_status_status: str = "available"
    metadata_status: str = "available"
    errors: dict[str, str | None] = field(default_factory=dict)


class MarketStreamLimit(BrokerConnectionError):
    """The owner already has the bounded number of active market streams."""


_MARKET_PERIODS: dict[str, tuple[timedelta, str]] = {
    "1d": (timedelta(days=1), "CANDLE_INTERVAL_5_MIN"),
    "1w": (timedelta(days=7), "CANDLE_INTERVAL_HOUR"),
    "1m": (timedelta(days=31), "CANDLE_INTERVAL_4_HOUR"),
    "3m": (timedelta(days=93), "CANDLE_INTERVAL_DAY"),
    "1y": (timedelta(days=365), "CANDLE_INTERVAL_DAY"),
}

_CBR_SOURCE = "Bank of Russia"
_PROVIDER_CLOCK_SKEW_TOLERANCE = timedelta(seconds=5)

# All enrichment uses the existing four workers. At most two long history jobs
# may run or wait, one per owner, leaving capacity for short metadata/status reads.
_ENRICHMENT_WORKERS = 4
_ANCILLARY_ACTIVE_LIMIT = 2
_ENRICHMENT_PENDING_LIMIT = 200
_ENRICHMENT_OWNER_PENDING_LIMIT = 50
_HISTORY_PENDING_LIMIT = 2
_HISTORY_OWNER_PENDING_LIMIT = 1
_ENRICHMENT_CACHE_CAPACITY = 1024
_HISTORY_CACHE_CAPACITY = 64
_METADATA_CACHE_SECONDS = 60
_TRADING_CACHE_SECONDS = 15
_HISTORY_CACHE_SECONDS = 15
_ENRICHMENT_RETRY_SECONDS = 5


@dataclass(frozen=True, slots=True)
class _InstrumentHistory:
    candles: tuple[InstrumentMarketCandle, ...]
    interval: str
    history_from: str | None
    history_note: str | None


type _EnrichmentValue = TBankInstrumentMetadata | TBankTradingStatus | _InstrumentHistory
type _MarketReadKey = tuple[UUID, BrokerConnectionStatus, str, str, str]


@dataclass(frozen=True, slots=True)
class _EnrichmentResult:
    value: _EnrichmentValue | None
    error: str | None
    observed_at: datetime
    completed_at: float


@dataclass(slots=True)
class _EnrichmentEntry:
    cache_seconds: int
    future: Future[_EnrichmentResult] | None = None
    read: Callable[[], _EnrichmentValue] | None = None
    value: _EnrichmentValue | None = None
    observed_at: datetime | None = None
    error: str | None = None
    failure: Exception | None = None
    refresh_at: float = 0


@dataclass(frozen=True, slots=True)
class _EnrichmentState:
    value: _EnrichmentValue | None
    status: str
    observed_at: datetime | None
    error: str | None


def _read_enrichment(read: Callable[[], _EnrichmentValue]) -> _EnrichmentResult:
    value, error = _market_component(read)
    return _EnrichmentResult(value, error, datetime.now(UTC), time.monotonic())


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
        self._public_admission = threading.BoundedSemaphore(2)
        self._cache_lock = threading.Lock()
        self._enrichment_pool = ThreadPoolExecutor(
            max_workers=_ENRICHMENT_WORKERS, thread_name_prefix="market-enrichment",
        )
        self._enrichment: OrderedDict[_MarketReadKey, _EnrichmentEntry] = OrderedDict()
        self._last_dispatched_owner: dict[str, UUID] = {}
        self._active_enrichment: dict[Future[_EnrichmentResult], _MarketReadKey] = {}
        self._connection_reads: OrderedDict[
            UUID, tuple[int, BrokerConnectionStatus],
        ] = OrderedDict()
        self._read_sequence = 0
        self._quotes: OrderedDict[
            tuple[UUID, BrokerConnectionStatus, str], _QuoteCacheEntry,
        ] = OrderedDict()
        self._streams: dict[UUID, set[str]] = {}
        self._closed = False

    def acquire_stream(self, user_id: UUID) -> str:
        with self._cache_lock:
            if self._closed:
                raise MarketStreamLimit("market_stream_closed")
            leases = self._streams.setdefault(user_id, set())
            if len(leases) >= 2:
                raise MarketStreamLimit("market_stream_limit")
            lease = uuid4().hex
            leases.add(lease)
            return lease

    def release_stream(self, user_id: UUID, lease: str) -> None:
        with self._cache_lock:
            leases = self._streams.get(user_id)
            if leases is not None:
                leases.discard(lease)
                if not leases:
                    self._streams.pop(user_id, None)

    def close(self) -> None:
        with self._cache_lock:
            self._closed = True
            self._streams.clear()
            futures = list(self._active_enrichment)
            self._enrichment.clear()
            self._last_dispatched_owner.clear()
            self._active_enrichment.clear()
            self._connection_reads.clear()
            self._quotes.clear()
        for future in futures:
            future.cancel()
        self._enrichment_pool.shutdown(wait=False, cancel_futures=True)

    @staticmethod
    def _harvest_enrichment(entry: _EnrichmentEntry) -> None:
        if entry.future is None or not entry.future.done():
            return
        try:
            result = entry.future.result()
        except Exception as error:
            # Keep authentication/connection failures fail-closed for readers,
            # while allowing a bounded later retry instead of a poisoned Future.
            entry.future = None
            entry.failure = error
            entry.refresh_at = time.monotonic() + _ENRICHMENT_RETRY_SECONDS
            return
        entry.future = None
        entry.failure = None
        entry.error = result.error
        entry.refresh_at = result.completed_at + (
            entry.cache_seconds if result.error is None else _ENRICHMENT_RETRY_SECONDS
        )
        if result.error is None:
            entry.value = result.value
            entry.observed_at = result.observed_at

    def _discard_previous_connections(
        self, user_id: UUID, connection: BrokerConnectionStatus,
    ) -> list[Future[_EnrichmentResult]]:
        discarded: list[Future[_EnrichmentResult]] = []
        # Snapshot keys because revoked entries are removed during this pass.
        for previous in tuple(self._enrichment):
            if previous[0] == user_id and previous[1] != connection:
                entry = self._enrichment.pop(previous)
                if entry.future is not None:
                    discarded.append(entry.future)
        return discarded

    def _connection(self, user_id: UUID) -> BrokerConnectionStatus:
        # Reserve order before database I/O. An old request may finish its
        # status read after a newer connection was already observed and cached.
        with self._cache_lock:
            if self._closed:
                raise BrokerConnectionError("market_service_closed")
            self._read_sequence += 1
            sequence = self._read_sequence
        connection = self.broker.status(user_id)
        discarded: list[Future[_EnrichmentResult]] = []
        with self._cache_lock:
            if self._closed:
                raise BrokerConnectionError("market_service_closed")
            previous = self._connection_reads.get(user_id)
            if previous is not None and previous[0] > sequence:
                if previous[1] != connection:
                    raise BrokerConnectionError("market_account_changed")
            else:
                self._connection_reads[user_id] = (sequence, connection)
                self._connection_reads.move_to_end(user_id)
                if previous is not None and previous[1] != connection:
                    discarded = self._discard_previous_connections(user_id, connection)
                while len(self._connection_reads) > _ENRICHMENT_CACHE_CAPACITY:
                    self._connection_reads.popitem(last=False)
        for future in discarded:
            future.cancel()
        return connection

    def _enrichment_admitted(self, key: _MarketReadKey) -> bool:
        pending = [candidate for candidate, entry in self._enrichment.items()
                   if entry.read is not None]
        pending.extend(candidate for future, candidate in self._active_enrichment.items()
                       if not future.done())
        if (len(pending) >= _ENRICHMENT_PENDING_LIMIT
                or sum(candidate[0] == key[0] for candidate in pending)
                >= _ENRICHMENT_OWNER_PENDING_LIMIT):
            return False
        if key[2] != "history":
            ancillary = [candidate for candidate in pending if candidate[2] != "history"]
            return (len(ancillary) < _ENRICHMENT_PENDING_LIMIT - _HISTORY_PENDING_LIMIT
                    and sum(candidate[0] == key[0] for candidate in ancillary)
                    < _ENRICHMENT_OWNER_PENDING_LIMIT - _HISTORY_OWNER_PENDING_LIMIT)
        history = [candidate for candidate in pending if candidate[2] == "history"]
        return (len(history) < _HISTORY_PENDING_LIMIT
                and sum(candidate[0] == key[0] for candidate in history)
                < _HISTORY_OWNER_PENDING_LIMIT)

    def _trim_enrichment(self) -> None:
        history_count = sum(key[2] == "history" for key in self._enrichment)
        for key in tuple(self._enrichment):
            entry = self._enrichment[key]
            if (entry.read is not None
                    or entry.future is not None and not entry.future.done()):
                continue
            if (len(self._enrichment) > _ENRICHMENT_CACHE_CAPACITY
                    or key[2] == "history" and history_count > _HISTORY_CACHE_CAPACITY):
                self._enrichment.pop(key)
                history_count -= key[2] == "history"

    def _dispatch_enrichment(self) -> list[Future[_EnrichmentResult]]:
        """Called under the cache lock; never fill the executor with waiting metadata.

        Two slots serve short reads, two serve history. Bounded pending intents
        drain automatically, alternating owners when both have waiting work, so
        refreshing the first table rows cannot starve later instrument metadata.
        """
        dispatched: list[Future[_EnrichmentResult]] = []
        if self._closed:
            return dispatched
        for lane, limit in (("history", _HISTORY_PENDING_LIMIT),
                            ("ancillary", _ANCILLARY_ACTIVE_LIMIT)):
            entries = [(key, entry) for key, entry in self._enrichment.items()
                       if (key[2] == "history") == (lane == "history")]
            running = sum(not future.done() for future, key in self._active_enrichment.items()
                          if (key[2] == "history") == (lane == "history"))
            waiting = [(key, entry) for key, entry in entries if entry.read is not None]
            while running < limit and waiting:
                previous_owner = self._last_dispatched_owner.get(lane)
                index = next((index for index, (key, _) in enumerate(waiting)
                              if key[0] != previous_owner), 0)
                key, entry = waiting.pop(index)
                assert entry.read is not None
                entry.future = self._enrichment_pool.submit(_read_enrichment, entry.read)
                self._active_enrichment[entry.future] = key
                entry.read = None
                dispatched.append(entry.future)
                self._last_dispatched_owner[lane] = key[0]
                running += 1
        return dispatched

    def _continue_enrichment(self, _finished: Future[_EnrichmentResult]) -> None:
        with self._cache_lock:
            self._active_enrichment.pop(_finished, None)
            dispatched = self._dispatch_enrichment()
        # A Future may already be done when its callback is attached. Register
        # outside the lock: immediate callbacks must not deadlock the scheduler.
        for future in dispatched:
            future.add_done_callback(self._continue_enrichment)

    def _schedule_enrichment(
        self, key: _MarketReadKey, read: Callable[[], _EnrichmentValue], *, cache_seconds: int,
    ) -> None:
        with self._cache_lock:
            if self._closed:
                raise BrokerConnectionError("market_service_closed")
            observed = self._connection_reads.get(key[0])
            if observed is not None and observed[1] != key[1]:
                # A request can pause after observing its connection. Once a
                # newer one is accepted, old intents must not consume capacity.
                raise BrokerConnectionError("market_account_changed")
            dispatched = self._queue_enrichment(key, read, cache_seconds)
        for future in dispatched:
            future.add_done_callback(self._continue_enrichment)

    def _queue_enrichment(
        self, key: _MarketReadKey, read: Callable[[], _EnrichmentValue], cache_seconds: int,
    ) -> list[Future[_EnrichmentResult]]:
        entry = self._enrichment.get(key)
        if entry is not None:
            self._enrichment.move_to_end(key)
            self._harvest_enrichment(entry)
            if (entry.read is not None or entry.future is not None
                    or time.monotonic() < entry.refresh_at):
                return []
        if not self._enrichment_admitted(key):
            return []
        if entry is None:
            self._enrichment[key] = _EnrichmentEntry(cache_seconds, read=read)
        else:
            entry.read = read
            entry.error = None
        self._trim_enrichment()
        return self._dispatch_enrichment()

    def _enrichment_state(self, key: _MarketReadKey) -> _EnrichmentState:
        with self._cache_lock:
            if self._closed:
                raise BrokerConnectionError("market_service_closed")
            entry = self._enrichment.get(key)
            if entry is None:
                # Queue pressure is pending work, not an empty provider result.
                return _EnrichmentState(None, "loading", None, None)
            self._harvest_enrichment(entry)
            if entry.failure is not None:
                raise entry.failure
            status = "available"
            if entry.error is not None:
                status = "unavailable"
            elif (entry.read is not None or entry.future is not None
                  or time.monotonic() >= entry.refresh_at):
                status = "loading"
            return _EnrichmentState(entry.value, status, entry.observed_at, entry.error)

    def _instrument_metadata(
        self, user_id: UUID, connection: BrokerConnectionStatus, uid: str,
    ) -> tuple[TBankInstrumentMetadata | None, str]:
        key = (user_id, connection, "metadata", uid, "")
        self._schedule_enrichment(
            key, lambda: self.broker.market_instrument_metadata(user_id, uid),
            cache_seconds=_METADATA_CACHE_SECONDS,
        )
        return self._metadata_state(key)

    def _metadata_state(self, key: _MarketReadKey) -> tuple[TBankInstrumentMetadata | None, str]:
        result = self._enrichment_state(key)
        metadata = result.value
        if metadata is None:
            return None, result.status
        if not isinstance(metadata, TBankInstrumentMetadata) or metadata.uid != key[3]:
            return None, "unavailable"
        return metadata, result.status

    def batch_quotes(self, user_id: UUID, instrument_uids: tuple[str, ...]) -> dict[str, object]:
        if (not 1 <= len(instrument_uids) <= 50 or len(set(instrument_uids)) != len(instrument_uids)
                or any(not uid or len(uid) > 128 or not all(char.isascii() and (
                    char.isalnum() or char in "_-"
                ) for char in uid) for uid in instrument_uids)):
            raise ValueError("market_instrument_limit")
        connection = self._connection(user_id)
        entries = self._batch_quote_entries(user_id, connection, instrument_uids)
        now = datetime.now(UTC)
        items = [self._batch_quote_item(user_id, connection, uid, entries[uid], now)
                 for uid in instrument_uids]
        if self.broker.status(user_id) != connection:
            raise BrokerConnectionError("market_account_changed")
        return {"items": items, "source": "T-Invest", "observed_at": now.isoformat(),
                "refresh_after_seconds": 10}

    def _batch_quote_entries(
        self, user_id: UUID, connection: BrokerConnectionStatus, instrument_uids: tuple[str, ...],
    ) -> dict[str, _QuoteCacheEntry]:
        with self._cache_lock:
            cached = {uid: self._quotes.get((user_id, connection, uid)) for uid in instrument_uids}
        missing = tuple(uid for uid, entry in cached.items()
                        if entry is None or entry[0] <= time.monotonic())
        if missing:
            quote_batch, error = _market_component(
                lambda: _checked_quote_batch(
                    self.broker.market_last_prices(user_id, missing), missing,
                ),
            )
            by_uid, unavailable = quote_batch if quote_batch is not None else ({}, set())
            fetched_at = datetime.now(UTC)
            with self._cache_lock:
                for uid in missing:
                    quote_error = "source_unavailable" if uid in unavailable else error
                    entry = (time.monotonic() + 10, by_uid.get(uid), fetched_at, quote_error)
                    self._quotes[(user_id, connection, uid)] = entry
                    self._quotes.move_to_end((user_id, connection, uid))
                    cached[uid] = entry
                while len(self._quotes) > 2048:
                    self._quotes.popitem(last=False)
        return {uid: entry for uid, entry in cached.items() if entry is not None}

    def _batch_quote_item(
        self, user_id: UUID, connection: BrokerConnectionStatus, uid: str,
        quote_entry: _QuoteCacheEntry, now: datetime,
    ) -> dict[str, object]:
        metadata, metadata_status = self._instrument_metadata(user_id, connection, uid)
        live = _instrument_live_state(
            uid, observed=now, last_price=quote_entry[1], trading=None,
            live_after_seconds=self.live_after_seconds, metadata=metadata,
        )
        payload = asdict(live)
        for key in ("trading_status", "api_trade_available", "limit_order_available",
                    "market_order_available", "trading_status_status"):
            payload.pop(key)
        payload["observed_at"] = quote_entry[2].isoformat()
        payload["metadata_status"] = (
            "unavailable" if live.errors.get("metadata") else metadata_status
        )
        payload["errors"] = {
            "quote": quote_entry[3] or live.errors.get("quote"),
            "metadata": "source_unavailable" if metadata_status == "unavailable"
            else live.errors.get("metadata"),
        }
        if quote_entry[3] is not None:
            payload["quote_status"] = "unavailable"
        return payload

    def cbr_indicators(self) -> CBRIndicatorSnapshot:
        indicators = self.cbr.latest_indicators()
        return CBRIndicatorSnapshot(
            source=_CBR_SOURCE,
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

    def public_reference(self, currency: str, period: str) -> dict[str, object]:
        """Anonymous reference data only: never access BrokerService or tenant storage."""
        if currency not in {"USD", "EUR", "CNY"} or period not in {"1m", "3m", "1y"}:
            raise ValueError("unsupported public reference request")
        if not self._public_admission.acquire(blocking=False):
            raise CBRUnavailable("Public reference refresh is busy")
        try:
            result: dict[str, object] = {
                "source": _CBR_SOURCE, "source_url": "https://www.cbr.ru/development/SXML/",
                "currency": currency, "period": period, "unit": "RUB per currency unit",
                "indicators": None, "history": None, "status": "unavailable",
                "exchange_quotes": "broker_connection_required",
                "public_exchange_distribution": "agreement_not_configured",
                "personal_data": False,
                "history_error": None, "indicators_error": None,
            }
            try:
                result["history"] = asdict(self.cbr.reference_history(currency, period))
            except CBRUnavailable:
                result["history_error"] = "source_unavailable"
            try:
                result["indicators"] = asdict(self.cbr_indicators())
            except CBRUnavailable:
                result["indicators_error"] = "source_unavailable"
            if result["history"] is not None and result["indicators"] is not None:
                result["status"] = "available"
            elif result["history"] is not None or result["indicators"] is not None:
                result["status"] = "partial"
            return result
        finally:
            self._public_admission.release()

    def usd_rub(self, user_id: UUID) -> UsdRubSnapshot:
        quote = self.broker.usd_rub_quote(user_id)
        observed = datetime.now(UTC)
        quote_time = _parse_provider_time(quote.quote_time)
        provider_age = observed - quote_time
        if provider_age < -_PROVIDER_CLOCK_SKEW_TOLERANCE:
            raise TBankUnavailable("fx_quote_timestamp_invalid")
        if quote.currency.upper() != "RUB":
            raise TBankUnavailable("fx_quote_currency_invalid")
        price = _required_market_price(quote.price)
        age_seconds = max(0, int(provider_age.total_seconds()))
        try:
            previous_close = _required_market_price(quote.previous_close)
        except TBankUnavailable:
            # A missing or corrupt reference must not invent a daily change,
            # nor hide an independently valid current quote.
            previous_close = None
        change, change_percent = _change(price, previous_close)

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
            price=price,
            currency=quote.currency,
            ticker=quote.ticker,
            instrument_name=quote.name,
            class_code=quote.class_code,
            source=quote.source,
            quote_time=quote_time.isoformat(),
            observed_at=observed.isoformat(),
            age_seconds=age_seconds,
            status="live" if age_seconds <= self.live_after_seconds else "stale",
            previous_close=previous_close,
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
        if config is None and period != "all":
            raise ValueError("unsupported market period")
        connection = self._connection(user_id)
        requested_at = datetime.now(UTC)
        key = (user_id, connection, "history", instrument_uid, period)
        self._schedule_enrichment(
            key, lambda: self._instrument_history(user_id, instrument_uid, period, requested_at),
            cache_seconds=_HISTORY_CACHE_SECONDS,
        )
        live = self._live_state(user_id, connection, instrument_uid)
        history_state = self._enrichment_state(key)
        history = history_state.value
        if not isinstance(history, _InstrumentHistory):
            history = _InstrumentHistory(
                (), config[1] if config is not None else "CANDLE_INTERVAL_MONTH", None, None,
            )
        if self.broker.status(user_id) != connection:
            raise BrokerConnectionError("market_account_changed")
        observed = datetime.now(UTC)
        history_status = history_state.status
        if history_status == "available" and not history.candles:
            history_status = "empty"

        return InstrumentMarketSnapshot(
            instrument_uid=instrument_uid,
            period=period,
            interval=history.interval,
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
            candles=history.candles,
            history_from=history.history_from,
            history_note=history.history_note,
            price_unit=live.price_unit,
            price_currency=live.price_currency,
            cash_price=live.cash_price,
            cash_price_currency=live.cash_price_currency,
            history_status=history_status,
            trading_status_status=live.trading_status_status,
            metadata_status=live.metadata_status,
            errors={**live.errors, "history": history_state.error},
            history_observed_at=(
                history_state.observed_at.isoformat() if history_state.observed_at else None
            ),
        )

    def _instrument_history(
        self, user_id: UUID, instrument_uid: str, period: str, requested_at: datetime,
    ) -> _InstrumentHistory:
        history_from = None
        history_note = None
        if period == "all":
            candles, interval, history_from = self._available_history(
                user_id, instrument_uid, requested_at,
            )
            resolution = "месячные" if interval == "CANDLE_INTERVAL_MONTH" else "дневные"
            history_note = f"Доступная история источника; {resolution} свечи без учёта выплат."
        else:
            window, interval = _MARKET_PERIODS[period]
            candles = self.broker.market_exchange_candles(
                user_id, instrument_uid, from_at=requested_at - window,
                to_at=requested_at, interval=interval,
            )
        market_candles = tuple(
            InstrumentMarketCandle(
                time=item.time.astimezone(UTC).isoformat(),
                open=_required_market_price(item.open), high=_required_market_price(item.high),
                low=_required_market_price(item.low), close=_required_market_price(item.close),
                volume_lots=item.volume_lots, is_complete=item.is_complete,
            ) for item in candles
        )
        return _InstrumentHistory(market_candles, interval, history_from, history_note)

    def _available_history(
        self, user_id: UUID, instrument_uid: str, requested_at: datetime,
    ) -> tuple[tuple[TBankHistoricCandle, ...], str, str]:
        connection = self.broker.status(user_id)
        first = self.broker.market_history_start(user_id, instrument_uid)
        cursor, interval, history_from = _available_history_window(first, requested_at)
        history_floor = cursor
        candles: dict[datetime, TBankHistoricCandle] = {}
        reads = 0
        while cursor < requested_at:
            self._validate_history_connection(user_id, connection)
            end = min(cursor.replace(year=cursor.year + 10), requested_at)
            begin = cursor
            if interval == "CANDLE_INTERVAL_MONTH" and end - begin < timedelta(days=28):
                begin -= timedelta(days=31)
            for candle in self.broker.market_exchange_candles(
                user_id, instrument_uid, from_at=begin, to_at=end, interval=interval,
            ):
                if history_floor <= candle.time <= requested_at:
                    candles[candle.time] = candle
            reads += 1
            cursor = end
            if reads >= 8 and cursor < requested_at:
                raise TBankUnavailable("instrument_history_exceeds_request_budget")
        self._validate_history_connection(user_id, connection)
        return tuple(candles[key] for key in sorted(candles)), interval, history_from

    def _validate_history_connection(
        self, user_id: UUID, connection: BrokerConnectionStatus,
    ) -> None:
        """Revalidate long history between provider reads and before acceptance."""
        with self._cache_lock:
            if self._closed:
                raise BrokerConnectionError("market_service_closed")
        if self.broker.status(user_id) != connection:
            raise BrokerConnectionError("market_account_changed")

    def instrument_live_state(
        self,
        user_id: UUID,
        instrument_uid: str,
    ) -> InstrumentLiveState:
        connection = self._connection(user_id)
        live = self._live_state(user_id, connection, instrument_uid)
        if self.broker.status(user_id) != connection:
            raise BrokerConnectionError("market_account_changed")
        return live

    def _live_state(
        self, user_id: UUID, connection: BrokerConnectionStatus, instrument_uid: str,
    ) -> InstrumentLiveState:
        metadata_key = (user_id, connection, "metadata", instrument_uid, "")
        trading_key = (user_id, connection, "trading", instrument_uid, "")
        self._schedule_enrichment(
            metadata_key, lambda: self.broker.market_instrument_metadata(user_id, instrument_uid),
            cache_seconds=_METADATA_CACHE_SECONDS,
        )
        self._schedule_enrichment(
            trading_key, lambda: self.broker.market_trading_status(user_id, instrument_uid),
            cache_seconds=_TRADING_CACHE_SECONDS,
        )
        price, quote_error = _market_component(
            lambda: self.broker.market_last_price(user_id, instrument_uid),
        )
        trading_state = self._enrichment_state(trading_key)
        trading = (
            trading_state.value if isinstance(trading_state.value, TBankTradingStatus) else None
        )
        metadata, metadata_status = self._metadata_state(metadata_key)
        live = _instrument_live_state(
            instrument_uid,
            observed=datetime.now(UTC),
            last_price=price,
            trading=trading,
            live_after_seconds=self.live_after_seconds,
            metadata=metadata,
        )
        return InstrumentLiveState(
            instrument_uid=live.instrument_uid, observed_at=live.observed_at,
            last_price=live.last_price, quote_time=live.quote_time,
            quote_age_seconds=live.quote_age_seconds,
            quote_status="unavailable" if quote_error else live.quote_status,
            trading_status=live.trading_status, api_trade_available=live.api_trade_available,
            limit_order_available=live.limit_order_available,
            market_order_available=live.market_order_available,
            price_unit=live.price_unit, price_currency=live.price_currency,
            cash_price=live.cash_price, cash_price_currency=live.cash_price_currency,
            trading_status_status=(
                "unavailable" if trading_state.error or live.errors.get("trading_status")
                else trading_state.status
            ),
            metadata_status="unavailable" if live.errors.get("metadata") else metadata_status,
            errors={"quote": quote_error or live.errors.get("quote"),
                    "trading_status": trading_state.error or live.errors.get("trading_status"),
                    "metadata": "source_unavailable" if metadata_status == "unavailable"
                    else live.errors.get("metadata")},
        )


def _checked_quote_batch(
    batch: TBankLastPriceBatch, requested: tuple[str, ...],
) -> tuple[dict[str, TBankLastPrice], set[str]]:
    prices = {item.instrument_uid: item for item in batch.prices}
    unavailable = set(batch.unavailable_uids)
    if (set(prices) - set(requested) or unavailable - set(requested)
            or set(prices) & unavailable or len(prices) != len(batch.prices)):
        raise TBankUnavailable("market_quote_batch_identity_mismatch")
    return prices, unavailable


def _market_component[T](read: Callable[[], T]) -> tuple[T | None, str | None]:
    try:
        return read(), None
    except TBankUnavailable:
        return None, "source_unavailable"


def _available_history_window(
    first: datetime | None, requested_at: datetime,
) -> tuple[datetime, str, str]:
    if first is None or first.tzinfo is None or first > requested_at:
        raise TBankUnavailable("instrument_history_start_unavailable")
    if requested_at - first > timedelta(days=366 * 80):
        raise TBankUnavailable("instrument_history_exceeds_request_budget")
    cursor = first.astimezone(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    interval = "CANDLE_INTERVAL_MONTH"
    if requested_at - cursor < timedelta(days=28):
        interval = "CANDLE_INTERVAL_DAY"
        cursor = min(cursor, requested_at - timedelta(days=1))
    return cursor, interval, first.isoformat()


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


def _quote_values(
    instrument_uid: str,
    *,
    observed: datetime,
    last_price: TBankLastPrice | None,
    live_after_seconds: int,
) -> tuple[str | None, datetime | None, int | None, str, str | None]:
    price = last_price
    quote_time: datetime | None = None
    age_seconds: int | None = None
    quote_status = "missing"
    price_value: str | None = None
    error = None
    if price is not None:
        try:
            if price.instrument_uid != instrument_uid or price.time.tzinfo is None:
                raise TBankUnavailable("quote_identity_or_timestamp_invalid")
            quote_time = price.time.astimezone(UTC)
            provider_age = observed - quote_time
            if provider_age < -_PROVIDER_CLOCK_SKEW_TOLERANCE:
                quote_status = "future"
            else:
                age_seconds = max(0, int(provider_age.total_seconds()))
                quote_status = "live" if age_seconds <= live_after_seconds else "stale"
                price_value = _required_market_price(price.price)
        except TBankUnavailable:
            quote_status, price_value = "unavailable", None
            error = "source_unavailable"
    return price_value, quote_time, age_seconds, quote_status, error


def _instrument_live_state(
    instrument_uid: str,
    *,
    observed: datetime,
    last_price: TBankLastPrice | None,
    trading: TBankTradingStatus | None,
    live_after_seconds: int,
    metadata: TBankInstrumentMetadata | None,
) -> InstrumentLiveState:
    price_value, quote_time, age_seconds, quote_status, quote_error = _quote_values(
        instrument_uid, observed=observed, last_price=last_price,
        live_after_seconds=live_after_seconds,
    )
    errors: dict[str, str | None] = {
        "quote": quote_error, "metadata": None, "trading_status": None,
    }

    price_unit, currency, cash_price, cash_currency = "unknown", None, None, None
    if metadata is not None:
        try:
            if metadata.uid != instrument_uid:
                raise TBankUnavailable("instrument_market_metadata_identity_mismatch")
            price_unit, currency, cash_price, cash_currency = _market_price_units(
                metadata, price_value,
            )
        except TBankUnavailable:
            metadata = None
            errors["metadata"] = "source_unavailable"
    if trading is not None and trading.instrument_uid != instrument_uid:
        trading = None
        errors["trading_status"] = "source_unavailable"
    trading_status_status = "available" if trading is not None else "unavailable"
    if trading is None:
        trading = TBankTradingStatus(instrument_uid, "UNKNOWN", False, False, False, False, False)

    return InstrumentLiveState(
        instrument_uid=instrument_uid,
        observed_at=observed.isoformat(),
        last_price=price_value,
        quote_time=quote_time.isoformat() if quote_time is not None else None,
        quote_age_seconds=age_seconds,
        quote_status=quote_status,
        trading_status=trading.trading_status,
        api_trade_available=trading.api_trade_available,
        limit_order_available=trading.limit_order_available,
        market_order_available=trading.market_order_available,
        price_unit=price_unit,
        price_currency=currency,
        cash_price=cash_price,
        cash_price_currency=cash_currency,
        metadata_status="available" if metadata is not None else "unavailable",
        trading_status_status=trading_status_status,
        errors=errors,
    )


def _market_price_units(
    metadata: TBankInstrumentMetadata, price: str | None,
) -> tuple[str, str | None, str | None, str | None]:
    """Keep history in exchange units; never apply today's nominal/FX to old candles.

    https://developer.tbank.ru/invest/intro/developer/table_order_currency
    Bond money equivalents are clean prices (without accrued coupon). Futures
    remain points: their monetary price-step value can change over time.
    """
    currency = metadata.currency.upper() or None
    kind = metadata.instrument_type.lower()
    if kind in {"share", "etf"}:
        return "currency" if currency else "unknown", currency, price, currency
    if kind == "bond":
        cash_price = _bond_cash_price(metadata, price)
        return "percent_nominal", None, cash_price, currency if cash_price is not None else None
    if kind in {"futures", "option"}:
        return "points", None, None, None
    if kind == "currency":
        # Exchange quotation can be per nominal; a bare currency symbol would
        # incorrectly imply that it is already a per-unit cash valuation.
        return "per_nominal", currency, None, None
    return "unknown", None, None, None


def _bond_cash_price(metadata: TBankInstrumentMetadata, price: str | None) -> str | None:
    nominal = metadata.nominal
    currency = metadata.currency.upper() or None
    if (nominal is None or price is None
            or nominal.currency.upper() != currency):
        return None
    try:
        value = Decimal(nominal.value)
    except InvalidOperation as exc:
        raise TBankUnavailable("instrument_nominal_invalid") from exc
    if not value.is_finite() or value <= 0:
        raise TBankUnavailable("instrument_nominal_invalid")
    return format(Decimal(price) * value / 100, "f")


def _reference_rate(rate: CBRRate) -> MarketReferenceRate:
    return MarketReferenceRate(
        source=_CBR_SOURCE,
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
