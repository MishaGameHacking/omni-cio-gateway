"""Business boundary for the owner's T-Invest connection and read-only data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from .db import Database, TBankConnectionRecord
from .security import decrypt_secret, encrypt_secret
from .tbank import (
    TBankAccount,
    TBankEnvironment,
    TBankInvestClient,
    TBankOperationsPage,
    TBankPortfolio,
    TBankPositions,
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
class BrokerOperationsSnapshot:
    account_name: str
    environment: TBankEnvironment
    operations: TBankOperationsPage
    refreshed_at: datetime


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
        portfolio = self.tbank.get_portfolio(
            credential,
            environment,
            record.account_id,
        )
        positions = self.tbank.get_positions(
            credential,
            environment,
            record.account_id,
        )
        return BrokerPortfolioSnapshot(
            account_name=record.account_name,
            environment=environment,
            portfolio=portfolio,
            positions=positions,
            refreshed_at=datetime.now(UTC),
        )

    def operations(
        self,
        user_id: UUID,
        *,
        limit: int = 30,
        cursor: str | None = None,
    ) -> BrokerOperationsSnapshot:
        record, credential, environment = self._connected_credential(user_id)
        operations = self.tbank.get_operations(
            credential,
            environment,
            record.account_id,
            limit=limit,
            cursor=cursor,
        )
        return BrokerOperationsSnapshot(
            account_name=record.account_name,
            environment=environment,
            operations=operations,
            refreshed_at=datetime.now(UTC),
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
