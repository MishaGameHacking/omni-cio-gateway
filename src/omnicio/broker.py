"""Business boundary for the owner's T-Invest connection and read-only data."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from .db import Database, TBankConnectionRecord
from .portfolio import PortfolioAnalysis, analyze_portfolio
from .security import decrypt_secret, encrypt_secret
from .tbank import (
    TBankAccount,
    TBankEnvironment,
    TBankFxQuote,
    TBankInstrument,
    TBankInstrumentMetadata,
    TBankInvestClient,
    TBankOperationsPage,
    TBankPortfolio,
    TBankPositions,
    TBankUnavailable,
)


class BrokerConnectionError(RuntimeError):
    """Base owner broker connection error."""


class BrokerAccountNotAccessible(BrokerConnectionError):
    """The selected account is not accessible through the submitted token."""


class BrokerNotConnected(BrokerConnectionError):
    """No T-Invest connection exists for the owner."""


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
        if selected is None:
            raise BrokerAccountNotAccessible(
                "selected T-Invest account is not accessible"
            )
        if selected.access_level == "ACCOUNT_ACCESS_LEVEL_NO_ACCESS":
            raise BrokerAccountNotAccessible(
                "selected T-Invest account has no token access"
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
