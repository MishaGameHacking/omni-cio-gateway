"""Private current positions and a separately credentialed shared market reader."""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

from .db import Database, TBankConnectionRecord
from .portfolio import PortfolioAnalysis, analyze_portfolio, value_current_positions
from .security import decrypt_secret, encrypt_secret
from .tbank import (
    NEWS_MAX_PAGE_SIZE,
    OPERATIONS_MAX_PAGE_SIZE,
    READ_ONLY_ACCESS,
    TBankAccount,
    TBankAccruedInterest,
    TBankAssetFundamental,
    TBankAssetReport,
    TBankBondCoupon,
    TBankBondEvent,
    TBankCancelResult,
    TBankDividend,
    TBankEnvironment,
    TBankFundProfile,
    TBankFxQuote,
    TBankHistoricCandle,
    TBankInstrument,
    TBankInstrumentMetadata,
    TBankInvestClient,
    TBankLastPrice,
    TBankLastPriceBatch,
    TBankMarketYield,
    TBankOperationsPage,
    TBankOrderBook,
    TBankOrderEstimate,
    TBankOrderState,
    TBankPortfolio,
    TBankPositions,
    TBankRating,
    TBankSandboxCancelResult,
    TBankSandboxOrderState,
    TBankTradingStatus,
    TBankUnavailable,
    TBankUserInfo,
)

# T-Invest documents 200 unary requests/minute for InstrumentsService.
# 0.31s keeps evidence reads below that ceiling with a small scheduling margin.
INSTRUMENT_EVIDENCE_REQUEST_INTERVAL_SECONDS = 0.31
STRATEGY_RATING_READ_LIMIT = 8
_NOT_CONNECTED_MESSAGE = "T-Invest is not connected"


class BrokerConnectionError(RuntimeError):
    """Base owner broker connection error."""


class BrokerAssessmentBusy(BrokerConnectionError):
    """A bounded strategy read is already running or was just requested."""


class BrokerAccountNotAccessible(BrokerConnectionError):
    """The selected account is not accessible through the submitted token."""


class BrokerNotConnected(BrokerConnectionError):
    """No T-Invest connection exists for the owner."""


class BrokerSandboxRequired(BrokerConnectionError):
    """A mutable R6 operation was requested for a non-sandbox connection."""


class BrokerLiveRequired(BrokerConnectionError):
    """An R7 live mutation requires the exact production account with write access."""


@dataclass(frozen=True, slots=True)
class BrokerConnectionStatus:
    connected: bool
    environment: str | None = None
    account_id: str | None = None
    account_name: str | None = None
    verified_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class MarketSourceStatus:
    connected: bool
    source: str
    configuration_id: str


@dataclass(frozen=True, slots=True)
class BrokerPortfolioSnapshot:
    account_id: str
    account_name: str
    environment: TBankEnvironment
    portfolio: TBankPortfolio
    positions: TBankPositions
    refreshed_at: datetime


@dataclass(frozen=True, slots=True)
class AnalysisSource:
    id: str
    name: str
    url: str
    methods: tuple[str, ...]
    retrieved_at: datetime
    status: str


@dataclass(frozen=True, slots=True)
class BrokerAnalysisSnapshot:
    account_id: str
    account_name: str
    environment: TBankEnvironment
    refreshed_at: datetime
    analysis: PortfolioAnalysis
    sources: tuple[AnalysisSource, ...]


@dataclass(frozen=True, slots=True)
class BrokerEvidenceSnapshot:
    refreshed_at: datetime
    dividends: tuple[TBankDividend, ...]
    coupons: tuple[TBankBondCoupon, ...]
    bond_events: tuple[TBankBondEvent, ...]
    reports: tuple[TBankAssetReport, ...]
    fundamentals: tuple[TBankAssetFundamental, ...]
    sources: tuple[AnalysisSource, ...]
    ratings: dict[str, tuple[TBankRating, ...]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BrokerObservationBundle:
    account_id: str
    account_name: str
    environment: TBankEnvironment
    refreshed_at: datetime
    portfolio: TBankPortfolio
    positions: TBankPositions
    metadata: tuple[TBankInstrumentMetadata, ...]
    analysis: PortfolioAnalysis
    sources: tuple[AnalysisSource, ...]


class BrokerService:
    def __init__(
        self,
        database: Database,
        *,
        credential_key: str,
        tbank: TBankInvestClient,
        market_credential: str = "",
        market_tbank: TBankInvestClient | None = None,
    ) -> None:
        self.database = database
        self.credential_key = credential_key
        self.tbank = tbank
        self._market_credential = market_credential.strip()
        self.market_tbank = market_tbank or TBankInvestClient(purpose="market")
        self._market_configuration_id = str(uuid4())
        self._instrument_evidence_lock = threading.Lock()
        self._next_instrument_evidence_at = 0.0
        self._metadata_lock = threading.Lock()
        self._metadata_cache: OrderedDict[str, tuple[float, TBankInstrumentMetadata, datetime]] = (
            OrderedDict()
        )
        self._news_lock = threading.Lock()
        self._news_cache: OrderedDict[tuple[str | None, int], tuple[float, Any, datetime]] = (
            OrderedDict()
        )

    def preview_accounts(
        self,
        *,
        credential: str,
        environment: TBankEnvironment,
    ) -> list[TBankAccount]:
        if environment != "prod":
            raise BrokerAccountNotAccessible("only a real read-only broker account is supported")
        accounts = self.tbank.get_accounts(credential, environment)
        if not accounts or any(account.access_level != READ_ONLY_ACCESS for account in accounts):
            raise BrokerAccountNotAccessible("all returned accounts must have read-only access")
        if any(not account.id or not account.id.strip() for account in accounts) or len(
            {account.id for account in accounts}
        ) != len(accounts):
            raise BrokerAccountNotAccessible("broker account identities are ambiguous")
        return [replace(account, name="Брокерский счёт", opened_at=None) for account in accounts]

    def connect(
        self,
        *,
        user_id: UUID,
        credential: str,
        environment: TBankEnvironment,
        account_id: str,
        terms_version: str,
    ) -> BrokerConnectionStatus:
        accounts = self.preview_accounts(credential=credential, environment=environment)
        selected = next(
            (account for account in accounts if account.id == account_id),
            None,
        )
        if selected is None or selected.status != "ACCOUNT_STATUS_OPEN":
            raise BrokerAccountNotAccessible("selected T-Invest account is not accessible")
        encrypted = encrypt_secret(credential.strip(), self.credential_key)
        record = self.database.upsert_tbank_connection(
            user_id=user_id,
            environment=environment,
            account_id=selected.id,
            account_name=selected.name,
            encrypted_credential=encrypted,
            terms_version=terms_version,
        )
        return _status(record)

    def status(self, user_id: UUID) -> BrokerConnectionStatus:
        record = self.database.tbank_connection(user_id)
        if record is None:
            return BrokerConnectionStatus(connected=False)
        return _status(record)

    def portfolio(self, user_id: UUID) -> BrokerPortfolioSnapshot:
        bundle = self.observation_bundle(user_id)
        return BrokerPortfolioSnapshot(
            account_id=bundle.account_id,
            account_name=bundle.account_name,
            environment=bundle.environment,
            portfolio=bundle.portfolio,
            positions=bundle.positions,
            refreshed_at=bundle.refreshed_at,
        )

    def _read_portfolio(
        self,
        record: TBankConnectionRecord,
        credential: str,
        environment: TBankEnvironment,
    ) -> BrokerPortfolioSnapshot:
        with ThreadPoolExecutor(max_workers=2) as reads:
            withdrawals_read = reads.submit(
                self.tbank.get_withdraw_limits,
                credential,
                environment,
                record.account_id,
            )
            positions_read = reads.submit(
                self.tbank.get_positions,
                credential,
                environment,
                record.account_id,
            )
            positions = positions_read.result()
            try:
                withdrawals = withdrawals_read.result()
            except TBankUnavailable:
                # Positions remain visible, but cash cannot be called spendable
                # while the broker's collateral reservations are unavailable.
                withdrawals = None
        if withdrawals is not None:
            # Separate reads can cross a broker update. Preserve the holdings,
            # but withhold a cash budget until both balance observations agree.
            same_balances = sorted(positions.money, key=lambda value: value.currency) == sorted(
                withdrawals.money, key=lambda value: value.currency
            ) and sorted(positions.blocked_money, key=lambda value: value.currency) == sorted(
                withdrawals.blocked_money, key=lambda value: value.currency
            )
            positions = replace(
                positions,
                blocked_guarantee_money=withdrawals.blocked_guarantee_money,
                withdraw_limits_available=same_balances,
            )
        portfolio = value_current_positions(positions, (), ())

        self._require_current_connection(record)
        return BrokerPortfolioSnapshot(
            account_id=record.account_id,
            account_name="Брокерский счёт",
            environment=environment,
            portfolio=portfolio,
            positions=positions,
            refreshed_at=datetime.now(UTC),
        )

    def candidate_bond_ratings(
        self,
        _user_id: UUID,
        instrument_uid: str,
    ) -> tuple[TBankRating, ...]:
        credential, environment = self._market_credentials()
        result = cast(
            tuple[TBankRating, ...],
            self._paced_evidence_read(
                self.market_tbank.get_bond_ratings,
                credential,
                environment,
                instrument_uid,
            ),
        )
        return result

    def candidate_daily_exchange_candles(
        self,
        user_id: UUID,
        instrument_uid: str,
        *,
        from_at: datetime,
        to_at: datetime,
    ) -> tuple[TBankHistoricCandle, ...]:
        credential, environment = self._market_credentials()
        result = self._paced_evidence_read(
            self.market_tbank.get_daily_exchange_candles,
            credential,
            environment,
            instrument_uid,
            from_at=from_at,
            to_at=to_at,
        )
        return cast(tuple[TBankHistoricCandle, ...], result)

    def market_history_start(self, user_id: UUID, instrument_uid: str) -> datetime | None:
        credential, environment = self._market_credentials()
        first = self.market_tbank.first_daily_candle(credential, environment, instrument_uid)
        return first

    def instrument_facts(
        self,
        user_id: UUID,
        instrument_uid: str,
    ) -> tuple[TBankInstrumentMetadata, TBankAssetFundamental | None]:
        """One exact instrument read and at most one asset statistics read."""
        credential, environment = self._market_credentials()
        metadata = self.market_tbank.get_instrument_overview(
            credential,
            environment,
            instrument_uid,
        )
        if metadata.uid != instrument_uid.strip():
            raise TBankUnavailable("instrument metadata identity mismatch")
        fundamentals: tuple[TBankAssetFundamental, ...] = ()
        if metadata.asset_uid:
            try:
                fundamentals = self.market_tbank.get_asset_fundamentals(
                    credential,
                    environment,
                    (metadata.asset_uid,),
                )
            except TBankUnavailable:
                # Keep the verified instrument card usable without supplying
                # another asset's statistics or exposing provider error text.
                fundamentals = ()
        if len(fundamentals) > 1 or any(
            value.asset_uid != metadata.asset_uid for value in fundamentals
        ):
            raise TBankUnavailable("instrument fundamental identity mismatch")
        return metadata, next(iter(fundamentals), None)

    def market_instrument_metadata(
        self,
        user_id: UUID,
        instrument_uid: str,
    ) -> TBankInstrumentMetadata:
        """Typed quote units without coupling quote availability to fundamentals."""
        credential, environment = self._market_credentials()
        key = instrument_uid
        with self._metadata_lock:
            cached = self._metadata_cache.get(key)
            if cached is not None and time.monotonic() < cached[0]:
                self._metadata_cache.move_to_end(key)
                return cached[1]
        metadata = self._paced_evidence_read(
            self.market_tbank.get_instrument_overview,
            credential,
            environment,
            instrument_uid,
        )
        metadata = cast(TBankInstrumentMetadata, metadata)
        if metadata.uid != instrument_uid.strip():
            raise TBankUnavailable("instrument metadata identity mismatch")
        self._remember_metadata((metadata,))
        return metadata

    def _remember_metadata(
        self,
        metadata: tuple[TBankInstrumentMetadata, ...],
    ) -> None:
        with self._metadata_lock:
            for item in metadata:
                key = item.uid
                self._metadata_cache[key] = (
                    time.monotonic() + (60 if item.instrument_type == "bond" else 300),
                    item,
                    datetime.now(UTC),
                )
                self._metadata_cache.move_to_end(key)
            while len(self._metadata_cache) > 100_000:
                self._metadata_cache.popitem(last=False)

    def execution_instrument(self, user_id: UUID, instrument_uid: str) -> TBankInstrumentMetadata:
        raise BrokerConnectionError("broker_execution_disabled")

    def estimate_limit_order(
        self,
        user_id: UUID,
        *,
        instrument_uid: str,
        lots: int,
        price: Decimal,
        action: str,
    ) -> TBankOrderEstimate:
        raise BrokerConnectionError("broker_execution_disabled")

    def submit_limit_order(
        self,
        user_id: UUID,
        *,
        expected_account_id: str,
        expected_verified_at: datetime,
        instrument_uid: str,
        lots: int,
        price: Decimal,
        action: str,
        request_id: str,
    ) -> TBankOrderState:
        raise BrokerConnectionError("broker_execution_disabled")

    def market_exchange_candles(
        self,
        _user_id: UUID,
        instrument_uid: str,
        *,
        from_at: datetime,
        to_at: datetime,
        interval: str,
    ) -> tuple[TBankHistoricCandle, ...]:
        credential, environment = self._market_credentials()
        candles = self.market_tbank.get_exchange_candles(
            credential,
            environment,
            instrument_uid,
            from_at=from_at,
            to_at=to_at,
            interval=interval,
        )
        return candles

    def market_trading_status(
        self,
        _user_id: UUID,
        instrument_uid: str,
    ) -> TBankTradingStatus:
        credential, environment = self._market_credentials()
        result = self.market_tbank.get_trading_status(
            credential,
            environment,
            instrument_uid,
        )
        return result

    def candidate_bond_coupons(
        self,
        _user_id: UUID,
        instrument_uid: str,
        *,
        from_at: datetime,
        to_at: datetime,
    ) -> tuple[TBankBondCoupon, ...]:
        credential, environment = self._market_credentials()
        result = cast(
            tuple[TBankBondCoupon, ...],
            self._paced_evidence_read(
                self.market_tbank.get_bond_coupons,
                credential,
                environment,
                instrument_uid,
                from_at=from_at,
                to_at=to_at,
            ),
        )
        return result

    def candidate_accrued_interests(
        self,
        _user_id: UUID,
        instrument_uid: str,
        *,
        from_at: datetime,
        to_at: datetime,
    ) -> tuple[TBankAccruedInterest, ...]:
        credential, environment = self._market_credentials()
        result = self._paced_evidence_read(
            self.market_tbank.get_accrued_interests,
            credential,
            environment,
            instrument_uid,
            from_at=from_at,
            to_at=to_at,
        )
        return cast(tuple[TBankAccruedInterest, ...], result)

    def candidate_dividends(
        self,
        _user_id: UUID,
        instrument_uid: str,
        *,
        from_at: datetime,
        to_at: datetime,
    ) -> tuple[TBankDividend, ...]:
        credential, environment = self._market_credentials()
        result = self._paced_evidence_read(
            self.market_tbank.get_dividends,
            credential,
            environment,
            instrument_uid,
            from_at=from_at,
            to_at=to_at,
        )
        return cast(tuple[TBankDividend, ...], result)

    def candidate_fund_profile(self, _user_id: UUID, asset_uid: str) -> TBankFundProfile:
        credential, environment = self._market_credentials()
        result = self._paced_evidence_read(
            self.market_tbank.get_fund_profile, credential, environment, asset_uid
        )
        return cast(TBankFundProfile, result)

    def instrument_news(
        self,
        user_id: UUID,
        instrument_uid: str | None = None,
        *,
        cursor: str | None = None,
        limit: int = NEWS_MAX_PAGE_SIZE,
    ) -> dict[str, Any]:
        """Read one bounded page; exact provider UID links select company news."""
        if instrument_uid is not None and (not instrument_uid.strip() or len(instrument_uid) > 200):
            raise ValueError("instrument_uid_invalid")
        credential, environment = self._market_credentials()
        key = (cursor, limit)
        with self._news_lock:
            cached = self._news_cache.get(key)
            if cached is None or time.monotonic() >= cached[0]:
                page = self.market_tbank.get_news(
                    credential,
                    environment,
                    cursor=cursor,
                    limit=limit,
                )
                observed_at = datetime.now(UTC)
                self._news_cache[key] = (time.monotonic() + 30, page, observed_at)
                while len(self._news_cache) > 128:
                    self._news_cache.popitem(last=False)
            else:
                _deadline, page, observed_at = cached
                self._news_cache.move_to_end(key)
        items = [
            asdict(item)
            for item in page.items
            if instrument_uid is None or instrument_uid in item.instrument_uids
        ]
        return {
            "items": items,
            "next_cursor": page.next_cursor,
            "scanned_items": len(page.items),
            "instrument_uid": instrument_uid,
            "source": "T-Invest InstrumentsService.News",
            "source_url": "https://developer.tbank.ru/invest/services/instruments/methods",
            "observed_at": observed_at.isoformat(),
            "status": "available",
        }

    def candidate_bond_events(
        self,
        user_id: UUID,
        instrument_uid: str,
        *,
        from_at: datetime,
        to_at: datetime,
    ) -> tuple[TBankBondEvent, ...]:
        credential, environment = self._market_credentials()
        result = cast(
            tuple[TBankBondEvent, ...],
            self._paced_evidence_read(
                self.market_tbank.get_bond_events,
                credential,
                environment,
                instrument_uid,
                from_at=from_at,
                to_at=to_at,
            ),
        )
        return result

    def candidate_market_yields(
        self,
        user_id: UUID,
        instrument_uids: tuple[str, ...],
    ) -> tuple[TBankMarketYield, ...]:
        credential, environment = self._market_credentials()
        result = self.market_tbank.get_market_yields(
            credential,
            environment,
            instrument_uids,
        )
        return result

    def candidate_last_prices(
        self,
        user_id: UUID,
        instrument_uids: tuple[str, ...],
    ) -> tuple[TBankLastPrice, ...]:
        credential, environment = self._market_credentials()
        result = self.market_tbank.get_last_prices(
            credential,
            environment,
            instrument_uids,
        )
        return result

    def market_last_price(
        self,
        user_id: UUID,
        instrument_uid: str,
    ) -> TBankLastPrice | None:
        prices = self.candidate_last_prices(user_id, (instrument_uid,))
        return next(iter(prices), None)

    def market_last_prices(
        self,
        user_id: UUID,
        instrument_uids: tuple[str, ...],
    ) -> TBankLastPriceBatch:
        """Partial quote display never changes strict execution readers."""
        credential, environment = self._market_credentials()
        result = self.market_tbank.get_last_prices_batch(credential, environment, instrument_uids)
        return result

    def candidate_fundamentals(
        self,
        _user_id: UUID,
        asset_uids: tuple[str, ...],
    ) -> tuple[TBankAssetFundamental, ...]:
        credential, environment = self._market_credentials()
        unique = tuple(dict.fromkeys(value for value in asset_uids if value))
        result: list[TBankAssetFundamental] = []
        for start in range(0, len(unique), 100):
            result.extend(
                self._paced_evidence_read(
                    self.market_tbank.get_asset_fundamentals,
                    credential,
                    environment,
                    unique[start : start + 100],
                )
            )
        return tuple(result)

    def candidate_order_book(
        self,
        user_id: UUID,
        instrument_uid: str,
        *,
        depth: int = 10,
    ) -> TBankOrderBook:
        credential, environment = self._market_credentials()
        result = self.market_tbank.get_order_book(
            credential,
            environment,
            instrument_uid,
            depth=depth,
        )
        return result

    def live_order_state(
        self,
        user_id: UUID,
        *,
        request_id: str,
        price_type: str,
    ) -> TBankOrderState:
        raise BrokerConnectionError("broker_execution_disabled")

    def cancel_live_order(
        self,
        user_id: UUID,
        *,
        request_id: str,
    ) -> TBankCancelResult:
        raise BrokerConnectionError("broker_execution_disabled")

    def sandbox_order_state(
        self,
        user_id: UUID,
        *,
        request_id: str,
        price_type: str,
    ) -> TBankSandboxOrderState:
        raise BrokerConnectionError("broker_execution_disabled")

    def cancel_sandbox_order(
        self,
        user_id: UUID,
        *,
        request_id: str,
    ) -> TBankSandboxCancelResult:
        raise BrokerConnectionError("broker_execution_disabled")

    def analysis(self, user_id: UUID) -> BrokerAnalysisSnapshot:
        bundle = self.observation_bundle(user_id)
        return BrokerAnalysisSnapshot(
            account_id=bundle.account_id,
            account_name=bundle.account_name,
            environment=bundle.environment,
            refreshed_at=bundle.refreshed_at,
            analysis=bundle.analysis,
            sources=bundle.sources,
        )

    def _cached_portfolio_metadata(
        self, positions: TBankPositions, observed_at: datetime,
    ) -> tuple[tuple[TBankInstrumentMetadata, ...], datetime, str]:
        with self._metadata_lock:
            entries = tuple(
                cached for position in positions.holdings
                if (cached := self._metadata_cache.get(position.instrument_uid)) is not None
                and time.monotonic() < cached[0]
            )
        metadata = tuple(entry[1] for entry in entries)
        return (
            metadata,
            min((entry[2] for entry in entries), default=observed_at),
            "cached" if metadata else "not_requested",
        )

    def observation_bundle(
        self,
        user_id: UUID,
        *,
        full_catalog: bool = False,
        quick: bool = False,
    ) -> BrokerObservationBundle:
        record, credential, environment = self._connected_credential(user_id)
        snapshot = self._read_portfolio(record, credential, environment)
        catalog_observed_at = datetime.now(UTC)
        catalog_methods: tuple[str, ...] = ()
        catalog_status = "unavailable"
        metadata: tuple[TBankInstrumentMetadata, ...] = ()
        prices: tuple[TBankLastPrice, ...] = ()
        if self._market_credential:
            market_credential, market_environment = self._market_credentials()
            if quick:
                metadata, catalog_observed_at, catalog_status = self._cached_portfolio_metadata(
                    snapshot.positions, catalog_observed_at,
                )
            else:
                metadata, catalog_methods, catalog_status = self._read_catalog(
                    market_credential,
                    market_environment,
                    snapshot.portfolio,
                    full_catalog=full_catalog,
                )
                self._remember_metadata(metadata)
            uids = tuple(
                dict.fromkeys(
                    item.instrument_uid
                    for item in snapshot.positions.holdings
                    if item.instrument_uid
                )
            )
            if uids:
                try:
                    prices = self.market_tbank.get_last_prices_batch(
                        market_credential,
                        market_environment,
                        uids,
                    ).prices
                except TBankUnavailable:
                    prices = ()
        portfolio = value_current_positions(snapshot.positions, metadata, prices)
        source_root = "https://developer.tbank.ru/invest/api/"
        sources = (
            AnalysisSource(
                "portfolio",
                "T-Invest: текущие активы",
                source_root + "operations-service-get-positions",
                ("OperationsService/GetPositions",),
                snapshot.refreshed_at,
                "received",
            ),
            AnalysisSource(
                "positions",
                "T-Invest: деньги и блокировки",
                source_root + "operations-service-get-withdraw-limits",
                ("OperationsService/GetPositions", "OperationsService/GetWithdrawLimits"),
                snapshot.refreshed_at,
                "received" if snapshot.positions.withdraw_limits_available else "partial",
            ),
            AnalysisSource(
                "catalog",
                "Общие справочники инструментов",
                source_root + "instruments-service",
                catalog_methods,
                catalog_observed_at,
                catalog_status,
            ),
            AnalysisSource(
                "market_prices",
                "Общие рыночные цены",
                source_root + "market-data-service-get-last-prices",
                ("MarketDataService/GetLastPrices",),
                min((price.time for price in prices), default=snapshot.refreshed_at),
                "received" if prices else "unavailable",
            ),
        )
        self._require_current_connection(record)
        return BrokerObservationBundle(
            account_id=record.account_id,
            account_name="Брокерский счёт",
            environment=environment,
            refreshed_at=snapshot.refreshed_at,
            portfolio=portfolio,
            positions=snapshot.positions,
            metadata=metadata,
            analysis=analyze_portfolio(portfolio, snapshot.positions, metadata),
            sources=sources,
        )

    def strategy_observation(
        self, user_id: UUID,
    ) -> tuple[BrokerObservationBundle, dict[str, tuple[TBankRating, ...]]]:
        """One bounded read per owner; other owners cannot observe its results."""
        with self.database.strategy_assessment_slot(user_id) as admitted:
            if not admitted:
                raise BrokerAssessmentBusy("strategy_assessment_busy")
            return self._strategy_observation(user_id)

    def _strategy_observation(
        self,
        user_id: UUID,
    ) -> tuple[BrokerObservationBundle, dict[str, tuple[TBankRating, ...]]]:
        record = self.database.tbank_connection(user_id)
        if record is None:
            raise BrokerNotConnected(_NOT_CONNECTED_MESSAGE)
        bundle = self.observation_bundle(user_id)
        self._require_current_connection(record)
        ratings: dict[str, tuple[TBankRating, ...]] = {}
        if not self._market_credential:
            return bundle, ratings
        started = time.monotonic()
        ids = sorted(
            {item.uid for item in bundle.analysis.securities if item.instrument_type == "bond"}
        )
        for uid in ids[:STRATEGY_RATING_READ_LIMIT]:
            if time.monotonic() - started >= 8:
                break
            try:
                ratings[uid] = self.candidate_bond_ratings(user_id, uid)
            except TBankUnavailable:
                ratings[uid] = ()
        self._require_current_connection(record)
        return bundle, ratings

    def _read_catalog(
        self,
        credential: str,
        environment: TBankEnvironment,
        portfolio: TBankPortfolio,
        *,
        full_catalog: bool,
    ) -> tuple[tuple[TBankInstrumentMetadata, ...], tuple[str, ...], str]:
        metadata: list[TBankInstrumentMetadata] = []
        methods = {
            "share": "Shares",
            "bond": "Bonds",
            "etf": "Etfs",
            "currency": "Currencies",
            "future": "Futures",
        }
        requested: list[str] = []
        failed: list[str] = []
        kinds = (
            set(methods) if full_catalog else {item.instrument_type for item in portfolio.positions}
        )

        with ThreadPoolExecutor(max_workers=3) as catalog_reads:
            pending = {
                kind: catalog_reads.submit(
                    self._paced_evidence_read,
                    self.market_tbank.get_instrument_metadata,
                    credential,
                    environment,
                    kind,
                )
                for kind in sorted(kinds & methods.keys())
            }
            for kind, result in pending.items():
                requested.append("InstrumentsService/" + methods[kind])
                try:
                    metadata.extend(result.result())
                except TBankUnavailable:
                    failed.append(methods[kind])

        catalog_status = "not_requested"
        if requested:
            catalog_status = "received"
        if failed:
            catalog_status = "partial"
        return tuple(metadata), tuple(requested), catalog_status

    def _paced_evidence_read(
        self,
        operation: Callable[..., Any],
        /,
        *args: Any,
        _request_count: int = 1,
        **kwargs: Any,
    ) -> Any:
        with self._instrument_evidence_lock:
            now = time.monotonic()
            delay = self._next_instrument_evidence_at - now
            if delay > 0:
                time.sleep(delay)
                now = time.monotonic()
            self._next_instrument_evidence_at = (
                now + INSTRUMENT_EVIDENCE_REQUEST_INTERVAL_SECONDS * _request_count
            )
        return operation(*args, **kwargs)

    def _read_fundamentals(
        self,
        credential: str,
        environment: TBankEnvironment,
        asset_uids: tuple[str, ...],
    ) -> tuple[list[TBankAssetFundamental], bool]:
        fundamentals: list[TBankAssetFundamental] = []
        failed = False
        for start in range(0, len(asset_uids), 100):
            try:
                fundamentals.extend(
                    self._paced_evidence_read(
                        self.market_tbank.get_asset_fundamentals,
                        credential,
                        environment,
                        asset_uids[start : start + 100],
                    )
                )
            except TBankUnavailable:
                failed = True
        return fundamentals, failed

    def _submit_evidence_tasks(
        self,
        reads: ThreadPoolExecutor,
        metadata: tuple[TBankInstrumentMetadata, ...],
        credential: str,
        environment: TBankEnvironment,
        *,
        window_from: datetime,
        window_to: datetime,
    ) -> dict[Any, tuple[str, str]]:
        tasks: dict[Any, tuple[str, str]] = {}
        for item in metadata:
            if item.instrument_type == "share":
                tasks[
                    reads.submit(
                        self._paced_evidence_read,
                        self.market_tbank.get_dividends,
                        credential,
                        environment,
                        item.uid,
                        from_at=window_from,
                        to_at=window_to,
                    )
                ] = ("GetDividends", item.uid)
            if item.instrument_type == "bond":
                tasks[
                    reads.submit(
                        self._paced_evidence_read,
                        self.market_tbank.get_bond_ratings,
                        credential,
                        environment,
                        item.uid,
                    )
                ] = ("BondBy", item.uid)
                tasks[
                    reads.submit(
                        self._paced_evidence_read,
                        self.market_tbank.get_bond_coupons,
                        credential,
                        environment,
                        item.uid,
                        from_at=window_from,
                        to_at=window_to,
                    )
                ] = ("GetBondCoupons", item.uid)
                tasks[
                    reads.submit(
                        self._paced_evidence_read,
                        self.market_tbank.get_bond_events,
                        credential,
                        environment,
                        item.uid,
                        from_at=window_from,
                        to_at=window_to,
                    )
                ] = ("GetBondEvents", item.uid)
            if item.instrument_type in {"share", "bond"}:
                tasks[
                    reads.submit(
                        self._paced_evidence_read,
                        self.market_tbank.get_asset_reports,
                        credential,
                        environment,
                        item.uid,
                        from_at=window_from,
                        to_at=window_to,
                    )
                ] = ("GetAssetReports", item.uid)
        return tasks

    @staticmethod
    def _collect_evidence_tasks(
        tasks: dict[Any, tuple[str, str]],
        *, deadline: float,
    ) -> tuple[
        list[TBankDividend],
        list[TBankBondCoupon],
        list[TBankBondEvent],
        list[TBankAssetReport],
        set[str],
        dict[str, tuple[TBankRating, ...]],
    ]:
        dividends: list[TBankDividend] = []
        coupons: list[TBankBondCoupon] = []
        bond_events: list[TBankBondEvent] = []
        reports: list[TBankAssetReport] = []
        failed_methods: set[str] = set()
        ratings: dict[str, tuple[TBankRating, ...]] = {}
        for future, (method, instrument_uid) in tasks.items():
            try:
                rows = future.result(timeout=max(0, deadline - time.monotonic()))
            except (TBankUnavailable, TimeoutError):
                future.cancel()
                failed_methods.add(method)
                continue
            if method == "GetDividends":
                dividends.extend(cast(tuple[TBankDividend, ...], rows))
            elif method == "GetBondCoupons":
                coupons.extend(cast(tuple[TBankBondCoupon, ...], rows))
            elif method == "GetBondEvents":
                bond_events.extend(cast(tuple[TBankBondEvent, ...], rows))
            elif method == "GetAssetReports":
                reports.extend(cast(tuple[TBankAssetReport, ...], rows))
            elif method == "BondBy":
                ratings[instrument_uid] = cast(tuple[TBankRating, ...], rows)
        return dividends, coupons, bond_events, reports, failed_methods, ratings

    def evidence(
        self,
        user_id: UUID,
        bundle: BrokerObservationBundle,
        *,
        now: datetime | None = None,
    ) -> BrokerEvidenceSnapshot:
        record = self.database.tbank_connection(user_id)
        if record is None:
            raise BrokerNotConnected(_NOT_CONNECTED_MESSAGE)
        credential, environment = self._market_credentials()
        if bundle.account_id != record.account_id or bundle.environment != environment:
            raise BrokerConnectionError("evidence_account_changed")
        observed_at = (now or datetime.now(UTC)).astimezone(UTC)
        deadline = time.monotonic() + 180
        window_from = observed_at - timedelta(days=400)
        window_to = observed_at + timedelta(days=400)

        held_positions = tuple(
            position
            for position in bundle.portfolio.positions
            if position.instrument_type != "currency" and Decimal(position.quantity) != 0
        )
        held_uids = {
            position.instrument_uid for position in held_positions if position.instrument_uid
        }
        held_figis = {position.figi for position in held_positions if position.figi}
        metadata = tuple(
            item
            for item in bundle.metadata
            if item.uid in held_uids or (item.figi and item.figi in held_figis)
        )
        asset_uids = tuple(dict.fromkeys(item.asset_uid for item in metadata if item.asset_uid))

        fundamentals, fundamentals_failed = self._read_fundamentals(
            credential,
            environment,
            asset_uids,
        )
        with ThreadPoolExecutor(max_workers=4) as reads:
            tasks = self._submit_evidence_tasks(
                reads,
                metadata,
                credential,
                environment,
                window_from=window_from,
                window_to=window_to,
            )
            (
                dividends,
                coupons,
                bond_events,
                reports,
                failed_methods,
                ratings,
            ) = self._collect_evidence_tasks(tasks, deadline=deadline)

        self._require_current_connection(record)
        observed_at = datetime.now(UTC)

        root = "https://developer.tbank.ru/invest/services/instruments/methods"
        calendar_methods = ("InstrumentsService/GetDividends", "InstrumentsService/GetBondCoupons")
        event_methods = ("InstrumentsService/GetBondEvents", "InstrumentsService/GetAssetReports")
        fundamental_methods = ("InstrumentsService/GetAssetFundamentals",)
        calendar_failed = bool({"GetDividends", "GetBondCoupons"} & failed_methods)
        events_failed = bool({"GetBondEvents", "GetAssetReports"} & failed_methods)
        return BrokerEvidenceSnapshot(
            refreshed_at=observed_at,
            dividends=tuple(dividends),
            coupons=tuple(coupons),
            bond_events=tuple(bond_events),
            reports=tuple(reports),
            fundamentals=tuple(fundamentals),
            ratings=ratings,
            sources=(
                AnalysisSource(
                    id="payout_calendar",
                    name="T-Invest: календарь выплат",
                    url=root,
                    methods=calendar_methods,
                    retrieved_at=observed_at,
                    status="partial" if calendar_failed else "received",
                ),
                AnalysisSource(
                    id="issuer_events",
                    name="T-Invest: события и отчётность",
                    url=root,
                    methods=event_methods,
                    retrieved_at=observed_at,
                    status="partial" if events_failed else "received",
                ),
                AnalysisSource(
                    id="fundamentals",
                    name="T-Invest: фундаментальные показатели",
                    url=root,
                    methods=fundamental_methods,
                    retrieved_at=observed_at,
                    status="partial" if fundamentals_failed else "received",
                ),
                AnalysisSource(
                    id="credit_ratings",
                    name="T-Invest: опубликованные рейтинги эмитентов облигаций",
                    url="https://developer.tbank.ru/invest/api/instruments-service-bond-by",
                    methods=("InstrumentsService/BondBy",),
                    retrieved_at=observed_at,
                    status="partial" if "BondBy" in failed_methods else "received",
                ),
            ),
        )

    def user_info(self, user_id: UUID) -> TBankUserInfo:
        raise BrokerConnectionError("broker_data_scope_restricted")

    def revalidate_account(self, user_id: UUID) -> TBankAccount:
        _record, _credential, account = self._validated_connection(user_id)
        return account

    def history_page(
        self,
        user_id: UUID,
        *,
        from_at: datetime,
        to_at: datetime,
        cursor: str = "",
        limit: int = OPERATIONS_MAX_PAGE_SIZE,
    ) -> TBankOperationsPage:
        raise BrokerConnectionError("broker_data_scope_restricted")

    def usd_rub_quote(self, user_id: UUID) -> TBankFxQuote:
        credential, environment = self._market_credentials()
        result = self.market_tbank.get_usd_rub_quote(credential, environment)
        return result

    def search_instruments(
        self,
        user_id: UUID,
        *,
        query: str,
        limit: int = 20,
    ) -> tuple[TBankInstrument, ...]:
        credential, environment = self._market_credentials()
        result = self.market_tbank.find_instruments(
            credential,
            environment,
            query,
            limit=limit,
        )
        return result

    def disconnect(self, user_id: UUID) -> bool:
        return self.database.delete_tbank_connection(user_id)

    def live_account(self, user_id: UUID) -> TBankAccount:
        raise BrokerConnectionError("broker_execution_disabled")

    def _connected_credential(
        self,
        user_id: UUID,
    ) -> tuple[TBankConnectionRecord, str, TBankEnvironment]:
        record, credential, _account = self._validated_connection(user_id)
        return record, credential, "prod"

    def _validated_connection(
        self,
        user_id: UUID,
    ) -> tuple[TBankConnectionRecord, str, TBankAccount]:
        record = self.database.tbank_connection(user_id)
        if record is None:
            raise BrokerNotConnected(_NOT_CONNECTED_MESSAGE)
        if record.environment != "prod":
            raise BrokerAccountNotAccessible("only a real read-only broker account is supported")
        credential = decrypt_secret(record.encrypted_credential, self.credential_key)
        accounts = self.preview_accounts(credential=credential, environment="prod")
        account = next((item for item in accounts if item.id == record.account_id), None)
        if account is None or account.status != "ACCOUNT_STATUS_OPEN":
            raise BrokerAccountNotAccessible("selected T-Invest account is no longer open")
        self._require_current_connection(record)
        return record, credential, account

    def _market_credentials(self) -> tuple[str, TBankEnvironment]:
        if not self._market_credential:
            raise TBankUnavailable("shared_market_source_unavailable")
        return self._market_credential, "prod"

    def market_status(self) -> MarketSourceStatus:
        return MarketSourceStatus(
            bool(self._market_credential),
            "tbank",
            self._market_configuration_id,
        )

    def market_catalog(self) -> tuple[TBankInstrumentMetadata, ...]:
        credential, environment = self._market_credentials()
        empty = TBankPortfolio(None, None, None, None, (), ())
        metadata, _methods, status = self._read_catalog(
            credential,
            environment,
            empty,
            full_catalog=True,
        )
        if status != "received":
            raise TBankUnavailable("shared_market_catalog_incomplete")
        self._remember_metadata(metadata)
        return metadata

    def market_all_last_prices(self) -> TBankLastPriceBatch:
        credential, environment = self._market_credentials()
        return self.market_tbank.get_all_last_prices(credential, environment)

    def _require_current_connection(self, expected: TBankConnectionRecord) -> None:
        if self.database.tbank_connection(expected.user_id) != expected:
            raise BrokerConnectionError("T-Invest connection changed during the read")


def _status(record: TBankConnectionRecord) -> BrokerConnectionStatus:
    return BrokerConnectionStatus(
        connected=True,
        environment=record.environment,
        account_id=record.account_id,
        account_name="Брокерский счёт",
        verified_at=record.verified_at,
    )
