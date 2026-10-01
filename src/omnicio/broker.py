"""Business boundary for the owner's T-Invest connection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from .db import Database, TBankConnectionRecord
from .security import encrypt_secret
from .tbank import TBankAccount, TBankEnvironment, TBankInvestClient


class BrokerConnectionError(RuntimeError):
    """Base owner broker connection error."""


class BrokerAccountNotAccessible(BrokerConnectionError):
    """The selected account is not accessible through the submitted token."""


@dataclass(frozen=True, slots=True)
class BrokerConnectionStatus:
    connected: bool
    environment: str | None = None
    account_id: str | None = None
    account_name: str | None = None
    verified_at: datetime | None = None


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
        )
        return _status(record)

    def status(self, user_id: UUID) -> BrokerConnectionStatus:
        record = self.database.tbank_connection(user_id)
        if record is None:
            return BrokerConnectionStatus(connected=False)
        return _status(record)

    def disconnect(self, user_id: UUID) -> bool:
        return self.database.delete_tbank_connection(user_id)


def _status(record: TBankConnectionRecord) -> BrokerConnectionStatus:
    return BrokerConnectionStatus(
        connected=True,
        environment=record.environment,
        account_id=record.account_id,
        account_name=record.account_name,
        verified_at=record.verified_at,
    )
