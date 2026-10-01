from __future__ import annotations

import io
import json
import ssl
import urllib.error
from datetime import UTC, datetime
from unittest.mock import patch
from uuid import UUID

import pytest
from cryptography.fernet import Fernet

from omnicio.broker import BrokerAccountNotAccessible, BrokerService
from omnicio.db import TBankConnectionRecord
from omnicio.tbank import (
    TBankAccount,
    TBankInvestClient,
    TBankTokenRejected,
    TBankUnavailable,
)


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


def test_tbank_get_accounts_uses_bearer_without_exposing_token() -> None:
    credential = "t.fake-owner-credential-1234567890"
    client = TBankInvestClient()
    response = FakeResponse(
        {
            "accounts": [
                {
                    "id": "account-1",
                    "name": "Основной",
                    "type": "ACCOUNT_TYPE_TINKOFF",
                    "status": "ACCOUNT_STATUS_OPEN",
                }
            ]
        }
    )

    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        accounts = client.get_accounts(credential, "prod")

    assert accounts == [
        TBankAccount(
            id="account-1",
            name="Основной",
            type="ACCOUNT_TYPE_TINKOFF",
            status="ACCOUNT_STATUS_OPEN",
        )
    ]
    request = urlopen.call_args.args[0]
    assert request.full_url.endswith("UsersService/GetAccounts")
    assert request.get_header("Authorization") == f"Bearer {credential}"
    assert json.loads(request.data.decode()) == {"status": "ACCOUNT_STATUS_OPEN"}


def test_tbank_tls_verification_failure_is_reported_as_unavailable() -> None:
    client = TBankInvestClient()
    error = urllib.error.URLError(
        ssl.SSLCertVerificationError(1, "certificate verify failed")
    )

    with (
        patch("urllib.request.urlopen", side_effect=error),
        pytest.raises(TBankUnavailable, match="TLS certificate verification failed"),
    ):
        client.get_accounts("t.fake-owner-credential-1234567890", "prod")


def test_tbank_rejects_unauthorized_credential_without_response_body() -> None:
    error = urllib.error.HTTPError(
        "https://invest-public-api.tbank.ru/",
        401,
        "Unauthorized",
        {},
        io.BytesIO(b'{"message":"credential must never be surfaced"}'),
    )
    client = TBankInvestClient()

    with (
        patch("urllib.request.urlopen", side_effect=error),
        pytest.raises(TBankTokenRejected, match="rejected"),
    ):
        client.get_accounts("t.fake-owner-credential-1234567890", "prod")


class FakeTBank:
    def __init__(self) -> None:
        self.accounts = [
            TBankAccount(
                id="account-1",
                name="Основной",
                type="ACCOUNT_TYPE_TINKOFF",
                status="ACCOUNT_STATUS_OPEN",
            )
        ]

    def get_accounts(self, credential: str, environment: str):
        assert credential == "t.fake-owner-credential-1234567890"
        assert environment == "prod"
        return self.accounts


class FakeDatabase:
    def __init__(self) -> None:
        self.record: TBankConnectionRecord | None = None
        self.saved_ciphertext = b""

    def upsert_tbank_connection(self, **kwargs):
        self.saved_ciphertext = kwargs["encrypted_credential"]
        assert kwargs["terms_version"] == "2026-10-01-v2"
        now = datetime.now(UTC)
        self.record = TBankConnectionRecord(
            user_id=kwargs["user_id"],
            environment=kwargs["environment"],
            account_id=kwargs["account_id"],
            account_name=kwargs["account_name"],
            encrypted_credential=kwargs["encrypted_credential"],
            verified_at=now,
            updated_at=now,
        )
        return self.record

    def tbank_connection(self, user_id: UUID):
        if self.record and self.record.user_id == user_id:
            return self.record
        return None

    def delete_tbank_connection(self, user_id: UUID) -> bool:
        if self.record and self.record.user_id == user_id:
            self.record = None
            return True
        return False


def test_broker_service_encrypts_credential_and_returns_safe_status() -> None:
    database = FakeDatabase()
    owner_id = UUID("00000000-0000-0000-0000-000000000001")
    credential = "t.fake-owner-credential-1234567890"
    service = BrokerService(
        database,
        credential_key=Fernet.generate_key().decode("ascii"),
        tbank=FakeTBank(),
    )

    status = service.connect(
        user_id=owner_id,
        credential=credential,
        environment="prod",
        account_id="account-1",
        terms_version="2026-10-01-v2",
    )

    assert status.connected is True
    assert status.account_id == "account-1"
    assert database.saved_ciphertext != credential.encode()
    assert credential.encode() not in database.saved_ciphertext
    assert not hasattr(status, "credential")


def test_broker_service_refuses_account_outside_credential_scope() -> None:
    database = FakeDatabase()
    service = BrokerService(
        database,
        credential_key=Fernet.generate_key().decode("ascii"),
        tbank=FakeTBank(),
    )

    with pytest.raises(BrokerAccountNotAccessible):
        service.connect(
            user_id=UUID("00000000-0000-0000-0000-000000000001"),
            credential="t.fake-owner-credential-1234567890",
            environment="prod",
            account_id="account-other",
            terms_version="2026-10-01-v2",
        )

    assert database.record is None
