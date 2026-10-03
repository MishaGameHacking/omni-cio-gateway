"""Business boundary for the owner's T-Invest connection and read-only data."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from .db import Database, TBankConnectionRecord
from .portfolio import PortfolioAnalysis, analyze_portfolio
from .security import decrypt_secret, encrypt_secret
from .tbank import (
    TBankAccount,
    TBankAssetFundamental,
    TBankAssetReport,
    TBankBondCoupon,
    TBankBondEvent,
    TBankDividend,
    TBankEnvironment,
    TBankFxQuote,
    TBankHistoricCandle,
    TBankInstrument,
    TBankInstrumentMetadata,
    TBankInvestClient,
    TBankLastPrice,
    TBankMarketYield,
    TBankOperationsPage,
    TBankOrderBook,
    TBankCancelResult,
    TBankMaxLots,
    TBankOrderPrice,
    TBankOrderState,
    TBankPortfolio,
    TBankPositions,
    TBankRating,
    TBankSandboxCancelResult,
    TBankSandboxMaxLots,
    TBankSandboxOrderState,
    TBankUnavailable,
    TBankUserInfo,
)

# T-Invest documents 200 unary requests/minute for InstrumentsService.
# 0.31s keeps evidence reads below that ceiling with a small scheduling margin.
INSTRUMENT_EVIDENCE_REQUEST_INTERVAL_SECONDS = 0.31


class BrokerConnectionError(RuntimeError):
    """Base owner broker connection error."""


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
class BrokerPortfolioSnapshot:
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
    ) -> None:
        self.database = database
        self.credential_key = credential_key
        self.tbank = tbank
        self._instrument_evidence_lock = threading.Lock()
        self._next_instrument_evidence_at = 0.0

    def preview_accounts(
        self,
        *,
        credential: str,
        environment: TBankEnvironment,
    ) -> list[TBankAccount]:
        return self.tbank.get_accounts(credential, environment)

    def connect(
        self,
        *,
        user_id: UUID,
        credential: str,
        environment: TBankEnvironment,
        account_id: str,
        terms_version: str,
    ) -> BrokerConnectionStatus:
        accounts = self.tbank.get_accounts(credential, environment)
        selected = next(
            (account for account in accounts if account.id == account_id),
            None,
        )
        if selected is None or selected.status != "ACCOUNT_STATUS_OPEN":
            raise BrokerAccountNotAccessible(
                "selected T-Invest account is not accessible"
            )
        if selected.access_level not in {
            "ACCOUNT_ACCESS_LEVEL_FULL_ACCESS",
            "ACCOUNT_ACCESS_LEVEL_READ_ONLY",
        }:
            raise BrokerAccountNotAccessible(
                "selected T-Invest account has no verified read access"
            )

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
        record, credential, environment = self._connected_credential(user_id)
        return self._read_portfolio(record, credential, environment)

    def _read_portfolio(
        self,
        record: TBankConnectionRecord,
        credential: str,
        environment: TBankEnvironment,
    ) -> BrokerPortfolioSnapshot:
        with ThreadPoolExecutor(max_workers=2) as reads:
            portfolio_read = reads.submit(
                self.tbank.get_portfolio,
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
            portfolio = portfolio_read.result()
            positions = positions_read.result()

        return BrokerPortfolioSnapshot(
            account_name=record.account_name,
            environment=environment,
            portfolio=portfolio,
            positions=positions,
            refreshed_at=datetime.now(UTC),
        )

    def candidate_bond_ratings(
        self,
        user_id: UUID,
        instrument_uid: str,
    ) -> tuple[TBankRating, ...]:
        _record, credential, environment = self._connected_credential(user_id)
        return cast(
            tuple[TBankRating, ...],
            self._paced_evidence_read(
                self.tbank.get_bond_ratings,
                credential,
                environment,
                instrument_uid,
            ),
        )

    def candidate_daily_exchange_candles(
        self,
        user_id: UUID,
        instrument_uid: str,
        *,
        from_at: datetime,
        to_at: datetime,
    ) -> tuple[TBankHistoricCandle, ...]:
        _record, credential, environment = self._connected_credential(user_id)
        return self.tbank.get_daily_exchange_candles(
            credential,
            environment,
            instrument_uid,
            from_at=from_at,
            to_at=to_at,
        )

    def candidate_bond_coupons(
        self,
        user_id: UUID,
        instrument_uid: str,
        *,
        from_at: datetime,
        to_at: datetime,
    ) -> tuple[TBankBondCoupon, ...]:
        _record, credential, environment = self._connected_credential(user_id)
        return cast(
            tuple[TBankBondCoupon, ...],
            self._paced_evidence_read(
                self.tbank.get_bond_coupons,
                credential,
                environment,
                instrument_uid,
                from_at=from_at,
                to_at=to_at,
            ),
        )

    def candidate_bond_events(
        self,
        user_id: UUID,
        instrument_uid: str,
        *,
        from_at: datetime,
        to_at: datetime,
    ) -> tuple[TBankBondEvent, ...]:
        _record, credential, environment = self._connected_credential(user_id)
        return cast(
            tuple[TBankBondEvent, ...],
            self._paced_evidence_read(
                self.tbank.get_bond_events,
                credential,
                environment,
                instrument_uid,
                from_at=from_at,
                to_at=to_at,
            ),
        )

    def candidate_market_yields(
        self,
        user_id: UUID,
        instrument_uids: tuple[str, ...],
    ) -> tuple[TBankMarketYield, ...]:
        _record, credential, environment = self._connected_credential(user_id)
        return self.tbank.get_market_yields(
            credential,
            environment,
            instrument_uids,
        )

    def candidate_last_prices(
        self,
        user_id: UUID,
        instrument_uids: tuple[str, ...],
    ) -> tuple[TBankLastPrice, ...]:
        _record, credential, environment = self._connected_credential(user_id)
        return self.tbank.get_last_prices(
            credential,
            environment,
            instrument_uids,
        )

    def candidate_fundamentals(
        self,
        user_id: UUID,
        asset_uids: tuple[str, ...],
    ) -> tuple[TBankAssetFundamental, ...]:
        _record, credential, environment = self._connected_credential(user_id)
        unique = tuple(dict.fromkeys(value for value in asset_uids if value))
        result: list[TBankAssetFundamental] = []
        for start in range(0, len(unique), 100):
            result.extend(
                self._paced_evidence_read(
                    self.tbank.get_asset_fundamentals,
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
        _record, credential, environment = self._connected_credential(user_id)
        return self.tbank.get_order_book(
            credential,
            environment,
            instrument_uid,
            depth=depth,
        )

    def candidate_order_price(
        self,
        user_id: UUID,
        instrument_uid: str,
        *,
        price: str,
        direction: str,
        quantity_lots: int,
    ) -> TBankOrderPrice:
        record, credential, environment = self._connected_credential(user_id)
        if direction not in {"buy", "sell"}:
            raise ValueError("candidate order price direction is invalid")
        return self.tbank.get_order_price(
            credential,
            environment,
            record.account_id,
            instrument_uid,
            price=price,
            direction=cast(Any, direction),
            quantity_lots=quantity_lots,
        )

    def live_order_price(
        self,
        user_id: UUID,
        instrument_uid: str,
        *,
        price: str,
        direction: str,
        quantity_lots: int,
    ) -> TBankOrderPrice:
        record, credential, environment = self._live_credential(user_id)
        if direction not in {"buy", "sell"}:
            raise ValueError("live order price direction is invalid")
        return self.tbank.get_order_price(
            credential,
            environment,
            record.account_id,
            instrument_uid,
            price=price,
            direction=cast(Any, direction),
            quantity_lots=quantity_lots,
        )

    def live_max_lots(
        self,
        user_id: UUID,
        instrument_uid: str,
        *,
        price: str,
    ) -> TBankMaxLots:
        record, credential, environment = self._live_credential(user_id)
        return self.tbank.get_max_lots(
            credential,
            environment,
            record.account_id,
            instrument_uid,
            price=price,
        )

    def post_live_order(
        self,
        user_id: UUID,
        instrument_uid: str,
        *,
        quantity_lots: int,
        price: str,
        direction: str,
        request_id: str,
        price_type: str,
    ) -> TBankOrderState:
        record, credential, environment = self._live_credential(user_id)
        if direction not in {"buy", "sell"}:
            raise ValueError("live order direction is invalid")
        if price_type not in {"point", "currency"}:
            raise ValueError("live order price type is invalid")
        return self.tbank.post_order(
            credential,
            environment,
            record.account_id,
            instrument_uid,
            quantity_lots=quantity_lots,
            price=price,
            direction=cast(Any, direction),
            request_id=request_id,
            price_type=cast(Any, price_type),
        )

    def live_order_state(
        self,
        user_id: UUID,
        *,
        request_id: str,
        price_type: str,
    ) -> TBankOrderState:
        record, credential, environment = self._prod_credential(
            user_id,
            require_full_access=False,
        )
        if price_type not in {"point", "currency"}:
            raise ValueError("live order price type is invalid")
        return self.tbank.get_order_state(
            credential,
            environment,
            record.account_id,
            request_id=request_id,
            price_type=cast(Any, price_type),
        )

    def cancel_live_order(
        self,
        user_id: UUID,
        *,
        request_id: str,
    ) -> TBankCancelResult:
        record, credential, environment = self._live_credential(user_id)
        return self.tbank.cancel_order(
            credential,
            environment,
            record.account_id,
            request_id=request_id,
        )

    def sandbox_order_price(
        self,
        user_id: UUID,
        instrument_uid: str,
        *,
        price: str,
        direction: str,
        quantity_lots: int,
    ) -> TBankOrderPrice:
        record, credential, environment = self._sandbox_credential(user_id)
        if direction not in {"buy", "sell"}:
            raise ValueError("sandbox order price direction is invalid")
        return self.tbank.get_order_price(
            credential,
            environment,
            record.account_id,
            instrument_uid,
            price=price,
            direction=cast(Any, direction),
            quantity_lots=quantity_lots,
        )

    def sandbox_max_lots(
        self,
        user_id: UUID,
        instrument_uid: str,
        *,
        price: str,
    ) -> TBankSandboxMaxLots:
        record, credential, environment = self._sandbox_credential(user_id)
        return self.tbank.get_sandbox_max_lots(
            credential,
            environment,
            record.account_id,
            instrument_uid,
            price=price,
        )

    def post_sandbox_order(
        self,
        user_id: UUID,
        instrument_uid: str,
        *,
        quantity_lots: int,
        price: str,
        direction: str,
        request_id: str,
        price_type: str,
    ) -> TBankSandboxOrderState:
        record, credential, environment = self._sandbox_credential(user_id)
        if direction not in {"buy", "sell"}:
            raise ValueError("sandbox order direction is invalid")
        if price_type not in {"point", "currency"}:
            raise ValueError("sandbox order price type is invalid")
        return self.tbank.post_sandbox_order(
            credential,
            environment,
            record.account_id,
            instrument_uid,
            quantity_lots=quantity_lots,
            price=price,
            direction=cast(Any, direction),
            request_id=request_id,
            price_type=cast(Any, price_type),
        )

    def sandbox_order_state(
        self,
        user_id: UUID,
        *,
        request_id: str,
        price_type: str,
    ) -> TBankSandboxOrderState:
        record, credential, environment = self._sandbox_credential(user_id)
        if price_type not in {"point", "currency"}:
            raise ValueError("sandbox order price type is invalid")
        return self.tbank.get_sandbox_order_state(
            credential,
            environment,
            record.account_id,
            request_id=request_id,
            price_type=cast(Any, price_type),
        )

    def cancel_sandbox_order(
        self,
        user_id: UUID,
        *,
        request_id: str,
    ) -> TBankSandboxCancelResult:
        record, credential, environment = self._sandbox_credential(user_id)
        return self.tbank.cancel_sandbox_order(
            credential,
            environment,
            record.account_id,
            request_id=request_id,
        )

    def analysis(self, user_id: UUID) -> BrokerAnalysisSnapshot:
        bundle = self.observation_bundle(user_id)
        return BrokerAnalysisSnapshot(
            account_name=bundle.account_name,
            environment=bundle.environment,
            refreshed_at=bundle.refreshed_at,
            analysis=bundle.analysis,
            sources=bundle.sources,
        )

    def observation_bundle(
        self,
        user_id: UUID,
        *,
        full_catalog: bool = False,
    ) -> BrokerObservationBundle:
        record, credential, environment = self._connected_credential(user_id)
        snapshot = self._read_portfolio(record, credential, environment)
        metadata, catalog_methods, catalog_status = self._read_catalog(
            credential,
            environment,
            snapshot.portfolio,
            full_catalog=full_catalog,
        )
        source_root = "https://developer.tbank.ru/invest/api/"
        sources = (
            AnalysisSource(
                id="portfolio",
                name="T-Invest: портфель",
                url=source_root + "operations-service-get-portfolio",
                methods=("OperationsService/GetPortfolio",),
                retrieved_at=snapshot.refreshed_at,
                status="received",
            ),
            AnalysisSource(
                id="positions",
                name="T-Invest: деньги и блокировки",
                url=source_root + "operations-service-get-positions",
                methods=("OperationsService/GetPositions",),
                retrieved_at=snapshot.refreshed_at,
                status="received",
            ),
            AnalysisSource(
                id="catalog",
                name="T-Invest: справочники инструментов",
                url=source_root + "instruments-service",
                methods=catalog_methods,
                retrieved_at=datetime.now(UTC),
                status=catalog_status,
            ),
        )
        return BrokerObservationBundle(
            account_id=record.account_id,
            account_name=record.account_name,
            environment=environment,
            refreshed_at=snapshot.refreshed_at,
            portfolio=snapshot.portfolio,
            positions=snapshot.positions,
            metadata=metadata,
            analysis=analyze_portfolio(
                snapshot.portfolio,
                snapshot.positions,
                metadata,
            ),
            sources=sources,
        )

    def _read_catalog(
        self,
        credential: str,
        environment: TBankEnvironment,
        portfolio: TBankPortfolio,
        *,
        full_catalog: bool,
    ) -> tuple[tuple[TBankInstrumentMetadata, ...], tuple[str, ...], str]:
        metadata: list[TBankInstrumentMetadata] = []
        methods = {"share": "Shares", "bond": "Bonds", "etf": "Etfs"}
        requested: list[str] = []
        failed: list[str] = []
        kinds = (
            set(methods)
            if full_catalog
            else {item.instrument_type for item in portfolio.positions}
        )

        with ThreadPoolExecutor(max_workers=3) as catalog_reads:
            pending = {
                kind: catalog_reads.submit(
                    self.tbank.get_instrument_metadata,
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
        **kwargs: Any,
    ) -> Any:
        with self._instrument_evidence_lock:
            now = time.monotonic()
            delay = self._next_instrument_evidence_at - now
            if delay > 0:
                time.sleep(delay)
                now = time.monotonic()
            self._next_instrument_evidence_at = (
                now + INSTRUMENT_EVIDENCE_REQUEST_INTERVAL_SECONDS
            )
        return operation(*args, **kwargs)

    def evidence(
        self,
        user_id: UUID,
        bundle: BrokerObservationBundle,
        *,
        now: datetime | None = None,
    ) -> BrokerEvidenceSnapshot:
        _record, credential, environment = self._connected_credential(user_id)
        observed_at = (now or datetime.now(UTC)).astimezone(UTC)
        window_from = observed_at - timedelta(days=400)
        window_to = observed_at + timedelta(days=400)

        held_positions = tuple(
            position
            for position in bundle.portfolio.positions
            if position.instrument_type != "currency"
            and Decimal(position.quantity) != 0
        )
        held_uids = {
            position.instrument_uid
            for position in held_positions
            if position.instrument_uid
        }
        held_figis = {position.figi for position in held_positions if position.figi}
        metadata = tuple(
            item
            for item in bundle.metadata
            if item.uid in held_uids or (item.figi and item.figi in held_figis)
        )
        asset_uids = tuple(dict.fromkeys(item.asset_uid for item in metadata if item.asset_uid))

        fundamentals: list[TBankAssetFundamental] = []
        fundamentals_failed = False
        for start in range(0, len(asset_uids), 100):
            try:
                fundamentals.extend(
                    self._paced_evidence_read(
                        self.tbank.get_asset_fundamentals,
                        credential,
                        environment,
                        asset_uids[start : start + 100],
                    )
                )
            except TBankUnavailable:
                fundamentals_failed = True

        dividends: list[TBankDividend] = []
        coupons: list[TBankBondCoupon] = []
        bond_events: list[TBankBondEvent] = []
        reports: list[TBankAssetReport] = []
        failed_methods: set[str] = set()

        tasks: dict[Any, tuple[str, str]] = {}
        with ThreadPoolExecutor(max_workers=4) as reads:
            for item in metadata:
                if item.instrument_type == "share":
                    tasks[
                        reads.submit(
                            self._paced_evidence_read,
                            self.tbank.get_dividends,
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
                            self.tbank.get_bond_coupons,
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
                            self.tbank.get_bond_events,
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
                            self.tbank.get_asset_reports,
                            credential,
                            environment,
                            item.uid,
                            from_at=window_from,
                            to_at=window_to,
                        )
                    ] = ("GetAssetReports", item.uid)

            for future, (method, _instrument_uid) in tasks.items():
                try:
                    rows = future.result()
                except TBankUnavailable:
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
                    name="Банк России: рейтинговый репозитарий — reference only",
                    url="https://ratings.cbr.ru/",
                    methods=(),
                    retrieved_at=observed_at,
                    status="not_requested",
                ),
            ),
        )

    def user_info(self, user_id: UUID) -> TBankUserInfo:
        _record, credential, environment = self._connected_credential(user_id)
        return self.tbank.get_user_info(credential, environment)

    def revalidate_account(self, user_id: UUID) -> TBankAccount:
        record, credential, environment = self._connected_credential(user_id)
        accounts = self.tbank.get_accounts(credential, environment)
        account = next((item for item in accounts if item.id == record.account_id), None)
        if account is None or account.status != "ACCOUNT_STATUS_OPEN":
            raise BrokerAccountNotAccessible("selected T-Invest account is no longer open")
        if account.access_level not in {
            "ACCOUNT_ACCESS_LEVEL_FULL_ACCESS",
            "ACCOUNT_ACCESS_LEVEL_READ_ONLY",
        }:
            raise BrokerAccountNotAccessible("T-Invest read access could not be verified")
        return account

    def history_page(
        self,
        user_id: UUID,
        *,
        from_at: datetime,
        to_at: datetime,
        cursor: str = "",
        limit: int = 1000,
    ) -> TBankOperationsPage:
        record, credential, environment = self._connected_credential(user_id)
        return self.tbank.get_operations_by_cursor(
            credential,
            environment,
            record.account_id,
            from_at=from_at,
            to_at=to_at,
            cursor=cursor,
            limit=limit,
        )

    def usd_rub_quote(self, user_id: UUID) -> TBankFxQuote:
        _record, credential, environment = self._connected_credential(user_id)
        return self.tbank.get_usd_rub_quote(credential, environment)

    def search_instruments(
        self,
        user_id: UUID,
        *,
        query: str,
        limit: int = 20,
    ) -> tuple[TBankInstrument, ...]:
        record, credential, environment = self._connected_credential(user_id)
        return self.tbank.find_instruments(
            credential,
            environment,
            query,
            limit=limit,
        )

    def disconnect(self, user_id: UUID) -> bool:
        return self.database.delete_tbank_connection(user_id)

    def live_account(self, user_id: UUID) -> TBankAccount:
        record, _credential, _environment = self._prod_credential(
            user_id,
            require_full_access=True,
        )
        account = self.revalidate_account(user_id)
        if (
            account.id != record.account_id
            or account.access_level != "ACCOUNT_ACCESS_LEVEL_FULL_ACCESS"
        ):
            raise BrokerLiveRequired(
                "R7 live execution requires an open account with full access"
            )
        return account

    def _live_credential(
        self,
        user_id: UUID,
    ) -> tuple[TBankConnectionRecord, str, TBankEnvironment]:
        return self._prod_credential(user_id, require_full_access=True)

    def _prod_credential(
        self,
        user_id: UUID,
        *,
        require_full_access: bool,
    ) -> tuple[TBankConnectionRecord, str, TBankEnvironment]:
        record, credential, environment = self._connected_credential(user_id)
        if environment != "prod":
            raise BrokerLiveRequired(
                "R7 live execution requires the exact production broker connection"
            )
        accounts = self.tbank.get_accounts(credential, environment)
        selected = next(
            (account for account in accounts if account.id == record.account_id),
            None,
        )
        if selected is None or selected.status != "ACCOUNT_STATUS_OPEN":
            raise BrokerLiveRequired("R7 production account is no longer open")
        allowed = {"ACCOUNT_ACCESS_LEVEL_FULL_ACCESS"}
        if not require_full_access:
            allowed.add("ACCOUNT_ACCESS_LEVEL_READ_ONLY")
        if selected.access_level not in allowed:
            raise BrokerLiveRequired("R7 production account access is not sufficient")
        return record, credential, environment

    def _sandbox_credential(
        self,
        user_id: UUID,
    ) -> tuple[TBankConnectionRecord, str, TBankEnvironment]:
        record, credential, environment = self._connected_credential(user_id)
        if environment != "sandbox":
            raise BrokerSandboxRequired(
                "R6 sandbox execution requires a sandbox broker connection"
            )
        return record, credential, environment

    def _connected_credential(
        self,
        user_id: UUID,
    ) -> tuple[TBankConnectionRecord, str, TBankEnvironment]:
        record = self.database.tbank_connection(user_id)
        if record is None:
            raise BrokerNotConnected("T-Invest is not connected")
        if record.environment not in {"prod", "sandbox"}:
            raise BrokerConnectionError("stored T-Invest environment is invalid")
        environment = cast(TBankEnvironment, record.environment)
        credential = decrypt_secret(record.encrypted_credential, self.credential_key)
        return record, credential, environment


def _status(record: TBankConnectionRecord) -> BrokerConnectionStatus:
    return BrokerConnectionStatus(
        connected=True,
        environment=record.environment,
        account_id=record.account_id,
        account_name=record.account_name,
        verified_at=record.verified_at,
    )
