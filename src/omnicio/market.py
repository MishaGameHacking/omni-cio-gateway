"""Shared market collection and analysis, independent of user sessions or portfolios."""

from __future__ import annotations

import logging
import re
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID, uuid4

from .broker import BrokerConnectionError, BrokerService, MarketSourceStatus
from .cbr import CBRClient, CBRRate, CBRUnavailable
from .freshness import EVIDENCE_RETRIEVAL_MAX_AGE, ISSUER_NEWS_MAX_AGE, describe_freshness
from .intelligence import (
    EvidenceDocument,
    InstrumentRiskAssessment,
    MarketPriceChange,
    assess_candidate_fundamental_risk,
    build_news_evidence,
    market_price_changes,
)
from .monitoring import NEWS_BUDGET_SECONDS, NEWS_MAX_PAGES_PER_RUN, NEWS_MAX_PATH_PROOFS
from .news import NewsClient, NewsNotFound, NewsUnavailable
from .tbank import (
    NEWS_MAX_PAGE_SIZE,
    TBankAssetFundamental,
    TBankHistoricCandle,
    TBankInstrumentMetadata,
    TBankLastPrice,
    TBankLastPriceBatch,
    TBankTradingStatus,
    TBankUnavailable,
)

logger = logging.getLogger(__name__)

# A source/cache namespace, never a user or an authority for private data.
PUBLIC_MARKET_SCOPE = UUID(int=0)
_QUOTE_REFRESH_SECONDS = 10
_QUOTE_CACHE_CAPACITY = 2048
_CATALOG_REFRESH_SECONDS = 6 * 3600
_REFERENCE_REFRESH_SECONDS = 300
_FUNDAMENTAL_REFRESH_SECONDS = 60
_FUNDAMENTAL_BATCH_SIZE = 50
_COLLECTOR_SHUTDOWN_SECONDS = 8
_PUBLIC_PAGE_LIMIT = 200
_PUBLIC_NEWS_CAPACITY = 5000

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

# All readers share four enrichment workers. At most two long history jobs
# may run or wait, leaving capacity for short metadata/status reads.
_ENRICHMENT_WORKERS = 4
_ANCILLARY_ACTIVE_LIMIT = 2
_ENRICHMENT_PENDING_LIMIT = 200
_HISTORY_PENDING_LIMIT = 2
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
type _MarketReadKey = tuple[UUID, MarketSourceStatus, str, str, str]


@dataclass(frozen=True, slots=True)
class _CollectorResult:
    status: str
    observed_at: datetime | None = None
    items: int = 0


@dataclass(frozen=True, slots=True)
class _CollectorState:
    status: str = "not_started"
    last_attempt_at: datetime | None = None
    observed_at: datetime | None = None
    items: int = 0
    error: str | None = None


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
        news: NewsClient | None = None,
    ) -> None:
        self.broker = broker
        self.cbr = cbr
        self.live_after_seconds = live_after_seconds
        self.news = news
        self._public_admission = threading.BoundedSemaphore(2)
        self._cache_lock = threading.Lock()
        self._enrichment_pool = ThreadPoolExecutor(
            max_workers=_ENRICHMENT_WORKERS, thread_name_prefix="market-enrichment",
        )
        self._enrichment: OrderedDict[_MarketReadKey, _EnrichmentEntry] = OrderedDict()
        self._active_enrichment: dict[Future[_EnrichmentResult], _MarketReadKey] = {}
        self._connection_reads: OrderedDict[
            UUID, tuple[int, MarketSourceStatus],
        ] = OrderedDict()
        self._read_sequence = 0
        self._quotes: OrderedDict[
            tuple[UUID, MarketSourceStatus, str], _QuoteCacheEntry,
        ] = OrderedDict()
        self._streams: dict[UUID, set[str]] = {}
        self._closed = False
        self._stop = threading.Event()
        self._collectors: list[threading.Thread] = []
        self._collector_states: dict[str, _CollectorState] = {
            name: _CollectorState()
            for name in ("reference", "news", "quotes", "fundamentals", "instrument_news")
        }
        self._catalog: tuple[TBankInstrumentMetadata, ...] = ()
        self._catalog_by_uid: dict[str, TBankInstrumentMetadata] = {}
        self._catalog_observed_at: datetime | None = None
        self._catalog_refresh_at = 0.0
        self._catalog_status = "not_started"
        self._shared_prices: dict[str, TBankLastPrice] = {}
        self._quote_observed_at: datetime | None = None
        self._shared_quote_refresh_at = 0.0
        self._fundamentals: dict[str, TBankAssetFundamental] = {}
        self._risk_assessments: dict[str, InstrumentRiskAssessment] = {}
        self._price_changes: tuple[MarketPriceChange, ...] = ()
        self._fundamental_cursor = 0
        self._source_generation: MarketSourceStatus | None = None
        self._market_news: OrderedDict[str, EvidenceDocument] = OrderedDict()
        self._news_cursor: str | None = None
        self._news_seen_cursors: set[str] = set()
        self._news_scan_complete = False
        self._news_truncated = False

    def start(self) -> None:
        """Start independent source collectors once, even with no registered or active users."""
        tasks = [
            ("reference", self._collect_reference, _REFERENCE_REFRESH_SECONDS),
            ("quotes", self._collect_quotes, _QUOTE_REFRESH_SECONDS),
            ("fundamentals", self._collect_fundamentals, _FUNDAMENTAL_REFRESH_SECONDS),
            ("instrument_news", self._collect_instrument_news, _QUOTE_REFRESH_SECONDS),
        ]
        if self.news is not None:
            tasks.append(("news", self._collect_news, _REFERENCE_REFRESH_SECONDS))
        with self._cache_lock:
            if self._closed:
                raise BrokerConnectionError("market_service_closed")
            if self._collectors:
                return
            self._collectors = [threading.Thread(
                target=self._collector_loop, args=(name, collect, interval),
                name=f"public-market-{name}", daemon=True,
            ) for name, collect, interval in tasks]
            for worker in self._collectors:
                worker.start()

    def _collector_loop(
        self, name: str, collect: Callable[[], _CollectorResult], interval: int,
    ) -> None:
        while not self._stop.is_set():
            attempted = datetime.now(UTC)
            try:
                result = collect()
            except (BrokerConnectionError, TBankUnavailable, CBRUnavailable, NewsUnavailable):
                with self._cache_lock:
                    previous = self._collector_states[name]
                    self._collector_states[name] = _CollectorState(
                        "unavailable", attempted, previous.observed_at, previous.items,
                        "source_unavailable",
                    )
                logger.warning("Public market collector unavailable: %s", name)
            except Exception:
                # Keep the source independent and retry boundedly. Never log
                # provider exceptions: they may contain authentication headers.
                with self._cache_lock:
                    previous = self._collector_states[name]
                    self._collector_states[name] = _CollectorState(
                        "unavailable", attempted, previous.observed_at, previous.items,
                        "collector_failed",
                    )
                logger.error("Public market collector failed: %s", name)
            else:
                with self._cache_lock:
                    self._collector_states[name] = _CollectorState(
                        result.status, attempted, result.observed_at, result.items,
                    )
            self._stop.wait(interval)

    def _collect_reference(self) -> _CollectorResult:
        snapshot = self.cbr_indicators()
        return _CollectorResult(snapshot.freshness, _parse_provider_time(snapshot.fetched_at), 3)

    def _collect_news(self) -> _CollectorResult:
        if self.news is None:
            return _CollectorResult("not_configured")
        payload = self.news.headlines()
        return _CollectorResult(
            str(payload["freshness"]), _parse_provider_time(str(payload["fetched_at"])),
            len(payload["items"]),
        )

    def _shared_source(self) -> MarketSourceStatus:
        return self._connection()

    def _refresh_catalog(self, source: MarketSourceStatus) -> None:
        with self._cache_lock:
            if time.monotonic() < self._catalog_refresh_at:
                return
        try:
            catalog = self.broker.market_catalog()
        except (BrokerConnectionError, TBankUnavailable):
            with self._cache_lock:
                self._catalog_status = "unavailable"
                self._catalog_refresh_at = time.monotonic() + _FUNDAMENTAL_REFRESH_SECONDS
            return
        if self.broker.market_status() != source:
            raise BrokerConnectionError("market_source_changed")
        with self._cache_lock:
            if self._closed or self._source_generation != source:
                raise BrokerConnectionError("market_source_changed")
            self._catalog = catalog
            self._catalog_by_uid = {item.uid: item for item in catalog}
            self._catalog_observed_at = datetime.now(UTC)
            self._catalog_status = "available" if catalog else "empty"
            self._catalog_refresh_at = time.monotonic() + _CATALOG_REFRESH_SECONDS

    def _collect_quotes(self) -> _CollectorResult:
        source = self._shared_source()
        if not source.connected:
            return _CollectorResult("not_configured")
        self._refresh_catalog(source)
        batch = self.broker.market_all_last_prices()
        observed = datetime.now(UTC)
        prices = {price.instrument_uid: price for price in batch.prices}
        if len(prices) != len(batch.prices) or self.broker.market_status() != source:
            raise BrokerConnectionError("market_source_changed")
        with self._cache_lock:
            if self._closed or self._source_generation != source:
                raise BrokerConnectionError("market_source_changed")
            previous = self._shared_prices
            self._price_changes = market_price_changes(
                batch.prices, previous, observed_at=observed,
            )
            self._shared_prices = prices
            self._quote_observed_at = observed
            self._shared_quote_refresh_at = time.monotonic() + _QUOTE_REFRESH_SECONDS
            # Global snapshots have no tenant component. Discard delisted/missing
            # quotes instead of presenting an old price as a newly fetched one.
            self._quotes.clear()
        status = "partial" if batch.unavailable_uids else "fresh"
        return _CollectorResult(status if prices else "empty", observed, len(prices))

    def _collect_fundamentals(self) -> _CollectorResult:
        source = self._shared_source()
        if not source.connected:
            return _CollectorResult("not_configured")
        with self._cache_lock:
            catalog = self._catalog
            asset_uids = sorted({item.asset_uid for item in catalog if item.asset_uid})
            if not asset_uids:
                return _CollectorResult("waiting_for_catalog")
            start = self._fundamental_cursor % len(asset_uids)
            selected = tuple(asset_uids[start:start + _FUNDAMENTAL_BATCH_SIZE])
            self._fundamental_cursor = (start + len(selected)) % len(asset_uids)
        fundamentals = self.broker.candidate_fundamentals(PUBLIC_MARKET_SCOPE, selected)
        if self.broker.market_status() != source:
            raise BrokerConnectionError("market_source_changed")
        now = datetime.now(UTC)
        by_asset = {item.asset_uid: item for item in fundamentals}
        if len(by_asset) != len(fundamentals) or not by_asset.keys() <= set(selected):
            raise TBankUnavailable("market_fundamental_identity_mismatch")
        assessments = {item.uid: assess_candidate_fundamental_risk(
            item, by_asset.get(item.asset_uid), assessed_at=now,
        ) for item in catalog if item.asset_uid in selected}
        with self._cache_lock:
            if self._closed or self._source_generation != source:
                raise BrokerConnectionError("market_source_changed")
            for uid in selected:
                self._fundamentals.pop(uid, None)
            self._fundamentals.update(by_asset)
            self._risk_assessments.update(assessments)
            count = len(self._risk_assessments)
        return _CollectorResult("partial" if len(by_asset) < len(selected) else "fresh", now, count)

    def _collect_instrument_news(self) -> _CollectorResult:
        source = self._shared_source()
        if not source.connected:
            return _CollectorResult("not_configured")
        started = time.monotonic()
        # Refresh the head on every cycle, then advance a bounded continuation.
        # The API's limited history is not coverage of all news on the internet.
        cursor: str | None = None
        latest_observed: datetime | None = None
        for page_index in range(NEWS_MAX_PAGES_PER_RUN):
            if self._stop.is_set() or time.monotonic() - started >= NEWS_BUDGET_SECONDS:
                break
            page = self.broker.instrument_news(
                PUBLIC_MARKET_SCOPE, cursor=cursor, limit=NEWS_MAX_PAGE_SIZE,
            )
            cursor, observed = self._accept_news_page(source, page, cursor, page_index == 0)
            latest_observed = max(latest_observed or observed, observed)
            if cursor is None:
                break
        with self._cache_lock:
            count = len(self._market_news)
            complete = self._news_scan_complete and not self._news_truncated
        return _CollectorResult("fresh" if complete else "partial", latest_observed, count)

    def _accept_news_page(
        self, source: MarketSourceStatus, page: dict[str, Any], cursor: str | None,
        first_page: bool,
    ) -> tuple[str | None, datetime]:
        observed = _parse_provider_time(str(page["observed_at"]))
        documents = build_news_evidence(None, page["items"], observed_at=observed)
        if self.broker.market_status() != source:
            raise BrokerConnectionError("market_source_changed")
        with self._cache_lock:
            if self._closed or self._source_generation != source:
                raise BrokerConnectionError("market_source_changed")
            self._merge_news_documents(documents, observed)
            next_cursor = self._next_news_cursor(cursor, page["next_cursor"], first_page)
        return next_cursor, observed

    def _merge_news_documents(
        self, documents: tuple[EvidenceDocument, ...], observed: datetime,
    ) -> None:
        """Keep bounded, source-timestamped evidence under the caller's cache lock."""
        for document in documents:
            self._market_news[document.provider_key] = replace(document, payload={
                **document.payload, "observed_at": observed.isoformat(),
            })
        self._market_news = OrderedDict(
            (key, document) for key, document in self._market_news.items()
            if document.published_at is not None
            and observed - ISSUER_NEWS_MAX_AGE <= document.published_at <= observed
        )
        while len(self._market_news) > _PUBLIC_NEWS_CAPACITY:
            self._market_news.popitem(last=False)
            self._news_truncated = True

    def _next_news_cursor(
        self, cursor: str | None, next_cursor: str | None, first_page: bool,
    ) -> str | None:
        """Advance the bounded source scan under the caller's cache lock."""
        if first_page and self._news_cursor is not None:
            return self._news_cursor
        if next_cursor is None:
            self._news_cursor = None
            self._news_seen_cursors.clear()
            self._news_scan_complete = True
            return None
        if next_cursor in self._news_seen_cursors:
            self._news_cursor = None
            self._news_seen_cursors.clear()
            self._news_scan_complete = False
            raise TBankUnavailable("market_news_cursor_cycle")
        if cursor is not None:
            self._news_seen_cursors.add(cursor)
        if len(self._news_seen_cursors) >= NEWS_MAX_PATH_PROOFS:
            self._news_seen_cursors.clear()
            self._news_cursor = None
            self._news_scan_complete = False
            self._news_truncated = True
            return None
        self._news_cursor = str(next_cursor)
        self._news_scan_complete = False
        return self._news_cursor

    def status(self) -> dict[str, object]:
        """Public source health; no tenant identity, credential, or portfolio state."""
        source = self._shared_source()
        now = datetime.now(UTC)
        with self._cache_lock:
            states = dict(self._collector_states)
            running = bool(self._collectors) and all(
                worker.is_alive() for worker in self._collectors
            )
            catalog_size = len(self._catalog)
            quote_size = len(self._shared_prices)
            risk_size = len(self._risk_assessments)
            news_size = len(self._market_news)
            news_complete = self._news_scan_complete
            news_truncated = self._news_truncated
            catalog_at = self._catalog_observed_at
            catalog_status = self._catalog_status
            quote_times = tuple(self._shared_prices.values())
        quote_freshness: dict[str, int] = {}
        for price in quote_times:
            quote_status = _quote_values(
                price.instrument_uid, observed=now, last_price=price,
                live_after_seconds=self.live_after_seconds,
            )[3]
            quote_freshness[quote_status] = quote_freshness.get(quote_status, 0) + 1
        return {
            "mode": "continuous", "running": running and not self._stop.is_set(),
            "scope": "public", "user_tokens_used": False,
            "requires_account": False, "observed_at": now.isoformat(),
            "market_source": {"source": source.source, "configured": source.connected,
                              "real_time_guaranteed": False},
            "sources": {
                name: _collector_status(name, state, now) for name, state in states.items()
            },
            "coverage": {
                "scope": "configured_provider_catalog", "all_internet": False,
                "catalog_status": catalog_status, "instruments": catalog_size,
                "quote_instruments": quote_size, "risk_assessments": risk_size,
                "instrument_news_items": news_size, "news_scan_complete": news_complete,
                "news_truncated": news_truncated, "quote_freshness": quote_freshness,
                "catalog_observed_at": catalog_at.isoformat() if catalog_at else None,
                "instrument_types": ["share", "bond", "etf", "currency", "future"],
            },
        }

    def public_snapshot(
        self, *, query: str = "", instrument_type: str | None = None,
        limit: int = 100, offset: int = 0,
    ) -> dict[str, object]:
        """Serve already collected observations; reading a page never starts analysis."""
        if (len(query) > 200 or not 1 <= limit <= _PUBLIC_PAGE_LIMIT or offset < 0
                or instrument_type not in {None, "share", "bond", "etf", "currency", "future"}):
            raise ValueError("market_query_invalid")
        source = self._shared_source()
        now = datetime.now(UTC)
        with self._cache_lock:
            catalog = self._catalog
            prices = dict(self._shared_prices)
            risks = dict(self._risk_assessments)
            fundamentals = dict(self._fundamentals)
            news = sorted((item for item in self._market_news.values()
                           if item.published_at is not None
                           and now - ISSUER_NEWS_MAX_AGE <= item.published_at <= now),
                          key=lambda item: (
                item.published_at or datetime.min.replace(tzinfo=UTC)
            ), reverse=True)
            changes = tuple(self._price_changes)
            observed_at = self._quote_observed_at
        needle = query.strip().casefold()
        selected = [item for item in catalog
                    if (instrument_type is None or item.instrument_type == instrument_type)
                    and (not needle or needle in
                         f"{item.ticker} {item.name} {item.isin}".casefold())]
        items = []
        for item in selected[offset:offset + limit]:
            live = _instrument_live_state(
                item.uid, observed=now, last_price=prices.get(item.uid), trading=None,
                live_after_seconds=self.live_after_seconds, metadata=item,
            )
            items.append({
                **asdict(live), "ticker": item.ticker, "name": item.name,
                "instrument_type": item.instrument_type, "sector": item.sector,
                "risk": _public_risk(risks.get(item.uid), now),
                "fundamental": asdict(fundamentals[item.asset_uid])
                if item.asset_uid in fundamentals else None,
            })
        if self.broker.market_status() != source:
            raise BrokerConnectionError("market_source_changed")
        return {
            "items": items, "total": len(selected), "offset": offset, "limit": limit,
            "has_more": offset + limit < len(selected), "scope": "public",
            "source": "T-Invest", "observed_at": observed_at.isoformat() if observed_at else None,
            "price_changes": [asdict(change) for change in changes[:20]],
            "news": [item.payload for item in news[:20]],
            "change_period": "between_source_observations", "real_time_guaranteed": False,
            "status": self.status(),
        }

    def public_news(
        self, instrument_uid: str | None = None, *, query: str = "",
        limit: int = 20, cursor: str | None = None,
    ) -> dict[str, Any]:
        """Filter shared evidence by exact provider UID, never by a user's portfolio."""
        if (not 1 <= limit <= NEWS_MAX_PAGE_SIZE or len(query) > 200
                or instrument_uid is not None and not 1 <= len(instrument_uid) <= 128
                or cursor is not None and not 1 <= len(cursor) <= 64):
            raise ValueError("news_query_invalid")
        source = self._shared_source()
        now = datetime.now(UTC)
        with self._cache_lock:
            documents = tuple(self._market_news.values())
            state = self._collector_states["instrument_news"]
            truncated = self._news_truncated
        rows = _public_news_rows(documents, instrument_uid, now)
        sources = ["T-Invest InstrumentsService.News"] if source.connected else []
        source_times = [state.observed_at] if state.observed_at is not None else []
        cbr_fresh = None
        public = self._public_cbr_news(instrument_uid, has_instrument_news=bool(rows))
        if public is not None:
            cbr_fresh = public["freshness"] in {"fresh", "cached"}
            sources.append("Банк России")
            source_times.append(_parse_provider_time(str(public["fetched_at"])))
            rows.extend({**item, "source_url": item["url"], "summary": "",
                         "occurred_at": item["published_at"], "instrument_uids": (),
                         "observed_at": public["fetched_at"],
                         "priority": False, "content_scope": "headline"}
                        for item in public["items"])
        items, total, next_cursor = _public_news_page(rows, query, limit, cursor)
        status = _public_news_status(
            source.connected, str(_collector_status("instrument_news", state, now)["status"]),
            has_items=bool(items), cbr_fresh=cbr_fresh,
        )
        if self.broker.market_status() != source:
            raise BrokerConnectionError("market_source_changed")
        return {
            "items": items, "total": total, "scanned_items": len(rows),
            "next_cursor": next_cursor,
            "instrument_uid": instrument_uid, "query": query, "status": status,
            "scope": "public_sources", "search_scope": "shared_server_sources",
            "sources": sources, "web_search": False,
            "observed_at": max(source_times).isoformat() if source_times else None,
            "coverage": {
                "all_market_news": False, "truncated": truncated or next_cursor is not None,
            },
        }

    def _public_cbr_news(
        self, instrument_uid: str | None, *, has_instrument_news: bool,
    ) -> dict[str, Any] | None:
        if self.news is None or instrument_uid is not None:
            return None
        try:
            return self.news.headlines()
        except NewsUnavailable:
            if not has_instrument_news:
                raise
            return None

    def public_news_item(self, source_id: str) -> dict[str, Any]:
        """Resolve a bookmark from shared summaries; never fetch a full article."""
        if not isinstance(source_id, str) or re.fullmatch(
            r"(?:[1-9]\d{0,18}|[0-9a-f]{64})", source_id, flags=re.ASCII,
        ) is None or len(source_id) <= 19 and int(source_id) > 2**63 - 1:
            raise ValueError("news_source_id_invalid")
        now = datetime.now(UTC)
        source: MarketSourceStatus | None = None
        if len(source_id) == 64:
            if self.news is None:
                raise NewsUnavailable("news_source_unavailable")
            cached = self.news.cached_headline(source_id)
            payload: dict[str, Any] = {
                **cached, "source_url": cached["url"], "summary": "",
                "instrument_uids": (), "priority": False,
                "occurred_at": cached["published_at"], "observed_at": cached["fetched_at"],
            }
            content_scope, interval = "headline", _REFERENCE_REFRESH_SECONDS
            source_status = str(cached["freshness"])
        else:
            payload, source_status, source = self._cached_instrument_news_item(source_id, now)
            content_scope, interval = "source_summary", _QUOTE_REFRESH_SECONDS * 3
        try:
            observed = _parse_provider_time(str(payload["observed_at"]))
            published = _parse_provider_time(str(payload["occurred_at"]))
        except (KeyError, ValueError) as exc:
            raise NewsUnavailable("news_source_unavailable") from exc
        freshness = describe_freshness(
            observed, max_age=timedelta(seconds=interval), coverage="complete",
            effective_at=published, now=now,
        )
        if freshness.status == "unavailable" or published > now:
            raise NewsUnavailable("news_source_unavailable")
        if source is not None and self.broker.market_status() != source:
            raise BrokerConnectionError("market_source_changed")
        return {
            **{key: payload.get(key) for key in (
                "id", "title", "summary", "source", "source_url", "instrument_uids", "priority",
            )},
            "occurred_at": published.isoformat(), "observed_at": observed.isoformat(),
            "scope": "public_sources", "content_scope": content_scope,
            "content": None, "full_content_available": False,
            "content_status": "unavailable", "content_reason": "full_content_not_collected",
            "freshness": freshness.status, "source_status": source_status,
            "cached": True, "web_search": False,
        }

    def _cached_instrument_news_item(
        self, source_id: str, now: datetime,
    ) -> tuple[dict[str, Any], str, MarketSourceStatus]:
        source = self._shared_source()
        with self._cache_lock:
            document = self._market_news.get(source_id)
            state = self._collector_states["instrument_news"]
        if document is None:
            if not source.connected or state.status in {"not_started", "unavailable"}:
                raise NewsUnavailable("news_source_unavailable")
            raise NewsNotFound("news_source_not_found")
        if (document.published_at is None
                or not now - ISSUER_NEWS_MAX_AGE <= document.published_at <= now):
            raise NewsNotFound("news_source_not_found")
        payload = {**document.payload, "occurred_at": document.published_at.isoformat()}
        source_status = str(_collector_status("instrument_news", state, now)["status"])
        return payload, source_status, source

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
        self._stop.set()
        with self._cache_lock:
            self._closed = True
            self._streams.clear()
            futures = list(self._active_enrichment)
            self._enrichment.clear()
            self._active_enrichment.clear()
            self._connection_reads.clear()
            self._quotes.clear()
            self._shared_prices.clear()
            self._market_news.clear()
            self._risk_assessments.clear()
            self._price_changes = ()
        for future in futures:
            future.cancel()
        self._enrichment_pool.shutdown(wait=False, cancel_futures=True)
        deadline = time.monotonic() + _COLLECTOR_SHUTDOWN_SECONDS
        for worker in self._collectors:
            worker.join(timeout=max(0, deadline - time.monotonic()))

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
        self, user_id: UUID, connection: MarketSourceStatus,
    ) -> list[Future[_EnrichmentResult]]:
        discarded: list[Future[_EnrichmentResult]] = []
        # Snapshot keys because revoked entries are removed during this pass.
        for previous in tuple(self._enrichment):
            if previous[0] == user_id and previous[1] != connection:
                entry = self._enrichment.pop(previous)
                if entry.future is not None:
                    discarded.append(entry.future)
        return discarded

    def _reset_shared_source(self, connection: MarketSourceStatus) -> None:
        """Invalidate a source generation atomically under the caller's cache lock."""
        self._catalog = ()
        self._catalog_by_uid.clear()
        self._catalog_observed_at = None
        self._catalog_refresh_at = 0
        self._catalog_status = "not_started" if connection.connected else "not_configured"
        self._shared_prices.clear()
        self._quote_observed_at = None
        self._shared_quote_refresh_at = 0
        self._fundamentals.clear()
        self._risk_assessments.clear()
        self._price_changes = ()
        self._fundamental_cursor = 0
        self._market_news.clear()
        self._news_cursor = None
        self._news_seen_cursors.clear()
        self._news_scan_complete = False
        self._news_truncated = False
        for name in ("quotes", "fundamentals", "instrument_news"):
            self._collector_states[name] = _CollectorState(self._catalog_status)
        self._source_generation = connection

    def _connection(self) -> MarketSourceStatus:
        # The shared source generation replaces all per-user broker connections.
        # A credential rotation invalidates source caches for every consumer.
        with self._cache_lock:
            if self._closed:
                raise BrokerConnectionError("market_service_closed")
            self._read_sequence += 1
            sequence = self._read_sequence
        connection = self.broker.market_status()
        discarded: list[Future[_EnrichmentResult]] = []
        with self._cache_lock:
            if self._closed:
                raise BrokerConnectionError("market_service_closed")
            previous = self._connection_reads.get(PUBLIC_MARKET_SCOPE)
            if previous is not None and previous[0] > sequence:
                if previous[1] != connection:
                    raise BrokerConnectionError("market_source_changed")
            else:
                self._connection_reads[PUBLIC_MARKET_SCOPE] = (sequence, connection)
                self._connection_reads.move_to_end(PUBLIC_MARKET_SCOPE)
                if self._source_generation != connection:
                    self._reset_shared_source(connection)
                if previous is not None and previous[1] != connection:
                    discarded = self._discard_previous_connections(PUBLIC_MARKET_SCOPE, connection)
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
        if len(pending) >= _ENRICHMENT_PENDING_LIMIT:
            return False
        if key[2] != "history":
            ancillary = [candidate for candidate in pending if candidate[2] != "history"]
            return len(ancillary) < _ENRICHMENT_PENDING_LIMIT - _HISTORY_PENDING_LIMIT
        history = [candidate for candidate in pending if candidate[2] == "history"]
        return len(history) < _HISTORY_PENDING_LIMIT

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
        drain in source order, so refreshing the first table rows cannot starve
        later instrument metadata. No source request depends on a user's plan.
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
                key, entry = waiting.pop(0)
                assert entry.read is not None
                entry.future = self._enrichment_pool.submit(_read_enrichment, entry.read)
                self._active_enrichment[entry.future] = key
                entry.read = None
                dispatched.append(entry.future)
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
                raise BrokerConnectionError("market_source_changed")
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
        self, user_id: UUID, connection: MarketSourceStatus, uid: str,
    ) -> tuple[TBankInstrumentMetadata | None, str]:
        with self._cache_lock:
            shared = self._catalog_by_uid.get(uid)
        if shared is not None:
            return shared, "available"
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

    def batch_quotes(self, _user_id: UUID, instrument_uids: tuple[str, ...]) -> dict[str, object]:
        if (not 1 <= len(instrument_uids) <= 50 or len(set(instrument_uids)) != len(instrument_uids)
                or any(not uid or len(uid) > 128 or not all(char.isascii() and (
                    char.isalnum() or char in "_-"
                ) for char in uid) for uid in instrument_uids)):
            raise ValueError("market_instrument_limit")
        connection = self._connection()
        entries = self._batch_quote_entries(PUBLIC_MARKET_SCOPE, connection, instrument_uids)
        now = datetime.now(UTC)
        items = [self._batch_quote_item(PUBLIC_MARKET_SCOPE, connection, uid, entries[uid], now)
                 for uid in instrument_uids]
        if self.broker.market_status() != connection:
            raise BrokerConnectionError("market_source_changed")
        return {"items": items, "source": "T-Invest", "observed_at": now.isoformat(),
                "scope": "public", "real_time_guaranteed": False,
                "refresh_after_seconds": _QUOTE_REFRESH_SECONDS}

    def _batch_quote_entries(
        self, user_id: UUID, connection: MarketSourceStatus, instrument_uids: tuple[str, ...],
    ) -> dict[str, _QuoteCacheEntry]:
        with self._cache_lock:
            cached = {uid: self._cached_quote(connection, uid) for uid in instrument_uids}
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
                    entry = (time.monotonic() + _QUOTE_REFRESH_SECONDS,
                             by_uid.get(uid), fetched_at, quote_error)
                    self._quotes[(user_id, connection, uid)] = entry
                    self._quotes.move_to_end((user_id, connection, uid))
                    cached[uid] = entry
                while len(self._quotes) > _QUOTE_CACHE_CAPACITY:
                    self._quotes.popitem(last=False)
        return {uid: entry for uid, entry in cached.items() if entry is not None}

    def _cached_quote(self, source: MarketSourceStatus, uid: str) -> _QuoteCacheEntry | None:
        """Read under the cache lock; the autonomous snapshot serves every visitor."""
        if (source == self._source_generation and self._quote_observed_at is not None
                and time.monotonic() < self._shared_quote_refresh_at
                and uid in self._shared_prices):
            return (self._shared_quote_refresh_at, self._shared_prices[uid],
                    self._quote_observed_at, None)
        return self._quotes.get((PUBLIC_MARKET_SCOPE, source, uid))

    def _batch_quote_item(
        self, user_id: UUID, connection: MarketSourceStatus, uid: str,
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
                "exchange_quotes": "server_source",
                "public_exchange_distribution": "separate_server_source",
                "market_source_status_url": "/api/public/market-status",
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

    def usd_rub(self, _user_id: UUID) -> UsdRubSnapshot:
        quote = self.broker.usd_rub_quote(PUBLIC_MARKET_SCOPE)
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
        _user_id: UUID,
        instrument_uid: str,
        *,
        period: str,
    ) -> InstrumentMarketSnapshot:
        config = _MARKET_PERIODS.get(period)
        if config is None and period != "all":
            raise ValueError("unsupported market period")
        connection = self._connection()
        requested_at = datetime.now(UTC)
        key = (PUBLIC_MARKET_SCOPE, connection, "history", instrument_uid, period)
        self._schedule_enrichment(
            key, lambda: self._instrument_history(
                PUBLIC_MARKET_SCOPE, instrument_uid, period, requested_at,
            ),
            cache_seconds=_HISTORY_CACHE_SECONDS,
        )
        live = self._live_state(PUBLIC_MARKET_SCOPE, connection, instrument_uid)
        history_state = self._enrichment_state(key)
        history = history_state.value
        if not isinstance(history, _InstrumentHistory):
            history = _InstrumentHistory(
                (), config[1] if config is not None else "CANDLE_INTERVAL_MONTH", None, None,
            )
        if self.broker.market_status() != connection:
            raise BrokerConnectionError("market_source_changed")
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
        connection = self.broker.market_status()
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
        self, _user_id: UUID, connection: MarketSourceStatus,
    ) -> None:
        """Revalidate long history between provider reads and before acceptance."""
        with self._cache_lock:
            if self._closed:
                raise BrokerConnectionError("market_service_closed")
        if self.broker.market_status() != connection:
            raise BrokerConnectionError("market_source_changed")

    def instrument_live_state(
        self,
        _user_id: UUID,
        instrument_uid: str,
    ) -> InstrumentLiveState:
        connection = self._connection()
        live = self._live_state(PUBLIC_MARKET_SCOPE, connection, instrument_uid)
        if self.broker.market_status() != connection:
            raise BrokerConnectionError("market_source_changed")
        return live

    def _live_state(
        self, user_id: UUID, connection: MarketSourceStatus, instrument_uid: str,
    ) -> InstrumentLiveState:
        trading_key = (user_id, connection, "trading", instrument_uid, "")
        metadata, metadata_status = self._instrument_metadata(user_id, connection, instrument_uid)
        self._schedule_enrichment(
            trading_key, lambda: self.broker.market_trading_status(user_id, instrument_uid),
            cache_seconds=_TRADING_CACHE_SECONDS,
        )
        quote_entry = self._live_quote(connection, instrument_uid)
        price, quote_error = quote_entry[1], quote_entry[3]
        trading_state = self._enrichment_state(trading_key)
        trading = (
            trading_state.value if isinstance(trading_state.value, TBankTradingStatus) else None
        )
        live = _instrument_live_state(
            instrument_uid,
            observed=datetime.now(UTC),
            last_price=price,
            trading=trading,
            live_after_seconds=self.live_after_seconds,
            metadata=metadata,
        )
        return InstrumentLiveState(
            instrument_uid=live.instrument_uid, observed_at=quote_entry[2].isoformat(),
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

    def _live_quote(
        self, source: MarketSourceStatus, instrument_uid: str,
    ) -> _QuoteCacheEntry:
        key = (PUBLIC_MARKET_SCOPE, source, instrument_uid)
        with self._cache_lock:
            cached = self._cached_quote(source, instrument_uid)
        if cached is not None and time.monotonic() < cached[0]:
            return cached
        price, error = _market_component(
            lambda: self.broker.market_last_price(PUBLIC_MARKET_SCOPE, instrument_uid),
        )
        result = (time.monotonic() + _QUOTE_REFRESH_SECONDS, price, datetime.now(UTC), error)
        with self._cache_lock:
            if self._closed or self._source_generation != source:
                raise BrokerConnectionError("market_source_changed")
            self._quotes[key] = result
            self._quotes.move_to_end(key)
            while len(self._quotes) > _QUOTE_CACHE_CAPACITY:
                self._quotes.popitem(last=False)
        return result


def _public_news_rows(
    documents: tuple[EvidenceDocument, ...], instrument_uid: str | None, now: datetime,
) -> list[dict[str, Any]]:
    rows = []
    for document in documents:
        payload = document.payload
        uids = payload.get("instrument_uids")
        if (document.published_at is None
                or not now - ISSUER_NEWS_MAX_AGE <= document.published_at <= now
                or not isinstance(uids, (list, tuple))
                or instrument_uid is not None and instrument_uid not in uids):
            continue
        row = dict(payload)
        row["occurred_at"] = document.published_at.isoformat()
        row["content_scope"] = "source_summary"
        rows.append(row)
    return rows


def _public_news_page(
    rows: list[dict[str, Any]], query: str, limit: int, cursor: str | None,
) -> tuple[list[dict[str, Any]], int, str | None]:
    rows.sort(key=lambda item: (str(item["occurred_at"]), str(item["id"])), reverse=True)
    terms = query.casefold().split()
    matches = [row for row in rows if all(
        term in f"{row.get('title', '')} {row.get('summary', '')}".casefold()
        for term in terms
    )]
    start = 0
    if cursor is not None:
        index = next((index for index, row in enumerate(matches) if row["id"] == cursor), None)
        if index is None:
            raise ValueError("news_cursor_expired")
        start = index + 1
    items = matches[start:start + limit]
    more = start + limit < len(matches)
    return items, len(matches), str(items[-1]["id"]) if more and items else None


def _public_news_status(
    connected: bool, source_status: str, *, has_items: bool, cbr_fresh: bool | None,
) -> str:
    if not connected and cbr_fresh is None:
        return "unavailable"
    if not has_items and cbr_fresh is None and source_status == "not_started":
        return "loading"
    if connected and source_status == "stale":
        return "partial" if cbr_fresh else "stale"
    if connected and source_status in {"unavailable", "partial", "not_started"}:
        return "partial" if has_items or cbr_fresh is not None else "unavailable"
    if not connected and cbr_fresh is False:
        return "stale"
    return "available" if has_items else "empty"


def _collector_status(name: str, state: _CollectorState, now: datetime) -> dict[str, object]:
    intervals = {
        "quotes": _QUOTE_REFRESH_SECONDS, "reference": _REFERENCE_REFRESH_SECONDS,
        "news": _REFERENCE_REFRESH_SECONDS, "fundamentals": _FUNDAMENTAL_REFRESH_SECONDS,
        "instrument_news": _QUOTE_REFRESH_SECONDS,
    }
    interval = intervals[name]
    freshness = describe_freshness(
        state.observed_at, max_age=timedelta(seconds=interval * 3),
        coverage="complete" if state.status == "fresh" else "partial", now=now,
    )
    status = state.status
    if status in {"fresh", "cached", "partial"}:
        status = freshness.status
    return {
        "status": status,
        "last_attempt_at": state.last_attempt_at.isoformat() if state.last_attempt_at else None,
        "observed_at": state.observed_at.isoformat() if state.observed_at else None,
        "age_seconds": freshness.age_seconds, "refresh_interval_seconds": interval,
        "items": state.items, "error": state.error,
    }


def _public_risk(
    assessment: InstrumentRiskAssessment | None, now: datetime,
) -> dict[str, object] | None:
    if assessment is None:
        return None
    payload = asdict(assessment)
    assessed_at = _parse_provider_time(str(assessment.evidence["assessed_at"]))
    if now - assessed_at > EVIDENCE_RETRIEVAL_MAX_AGE:
        payload["state"] = "data_missing"
        payload["source_status"] = "partial"
        payload["reasons"] = [*assessment.reasons, "provider_evidence_stale"]
    return payload


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
    if kind in {"future", "futures", "option"}:
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
