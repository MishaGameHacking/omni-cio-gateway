from __future__ import annotations

import io
import json
import ssl
import urllib.error
from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import patch
from uuid import UUID

import pytest
from cryptography.fernet import Fernet

from omnicio.broker import BrokerAccountNotAccessible, BrokerNotConnected, BrokerService
from omnicio.db import TBankConnectionRecord
from omnicio.tbank import (
    TBankAccount,
    TBankAssetTotal,
    TBankFxQuote,
    TBankInstrument,
    TBankInstrumentMetadata,
    TBankInvestClient,
    TBankMoney,
    TBankPortfolio,
    TBankPortfolioPosition,
    TBankPositions,
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
                    "openedDate": "2024-01-02T03:04:05Z",
                    "accessLevel": "ACCOUNT_ACCESS_LEVEL_READ_ONLY",
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
            opened_at=datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC),
            access_level="ACCOUNT_ACCESS_LEVEL_READ_ONLY",
        )
    ]
    request = urlopen.call_args.args[0]
    assert request.full_url.endswith("UsersService/GetAccounts")
    assert request.get_header("Authorization") == f"Bearer {credential}"
    assert json.loads(request.data.decode()) == {"status": "ACCOUNT_STATUS_OPEN"}


def test_tbank_operation_history_uses_cursor_without_write_methods() -> None:
    credential = "t.fake-owner-credential-1234567890"
    client = TBankInvestClient()
    response = FakeResponse(
        {
            "hasNext": True,
            "nextCursor": "cursor-2",
            "items": [
                {
                    "cursor": "cursor-1",
                    "brokerAccountId": "account-1",
                    "id": "operation-1",
                    "parentOperationId": "",
                    "name": "Покупка",
                    "date": "2026-10-01T12:00:00Z",
                    "type": "OPERATION_TYPE_BUY",
                    "description": "Исполненная покупка",
                    "state": "OPERATION_STATE_EXECUTED",
                    "instrumentUid": "uid-1",
                    "figi": "figi-1",
                    "instrumentType": "share",
                    "positionUid": "position-1",
                    "ticker": "TEST",
                    "classCode": "TQBR",
                    "payment": {"currency": "rub", "units": "-100", "nano": 0},
                    "price": {"currency": "rub", "units": "10", "nano": 0},
                    "commission": {"currency": "rub", "units": "-1", "nano": 0},
                    "accruedInt": {"currency": "rub", "units": "0", "nano": 0},
                    "quantity": "10",
                    "quantityRest": "0",
                    "quantityDone": "10",
                    "assetUid": "asset-1",
                    "tradesInfo": {
                        "trades": [
                            {
                                "num": "trade-1",
                                "date": "2026-10-01T12:00:01Z",
                                "quantity": "10",
                                "price": {"currency": "rub", "units": "10", "nano": 0},
                            }
                        ]
                    },
                }
            ],
        }
    )

    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        page = client.get_operations_by_cursor(
            credential,
            "prod",
            "account-1",
            from_at=datetime(2026, 9, 1, tzinfo=UTC),
            to_at=datetime(2026, 10, 2, tzinfo=UTC),
            cursor="cursor-1",
            limit=1000,
        )

    assert page.has_next is True
    assert page.next_cursor == "cursor-2"
    assert page.items[0].id == "operation-1"
    assert page.items[0].quantity_done == "10"
    assert page.items[0].trades[0].num == "trade-1"
    request = urlopen.call_args.args[0]
    assert request.full_url.endswith("OperationsService/GetOperationsByCursor")
    assert "OrdersService" not in request.full_url
    assert json.loads(request.data.decode()) == {
        "accountId": "account-1",
        "from": "2026-09-01T00:00:00Z",
        "to": "2026-10-02T00:00:00Z",
        "limit": 1000,
        "state": "OPERATION_STATE_UNSPECIFIED",
        "withoutCommissions": False,
        "withoutTrades": False,
        "withoutOvernights": False,
        "cursor": "cursor-1",
    }


def test_tbank_operation_history_uses_operations_service_on_sandbox_host() -> None:
    client = TBankInvestClient()
    response = FakeResponse({"hasNext": False, "nextCursor": "", "items": []})

    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        client.get_operations_by_cursor(
            "t.fake-owner-credential-1234567890",
            "sandbox",
            "account-1",
            from_at=datetime(2026, 10, 1, tzinfo=UTC),
            to_at=datetime(2026, 10, 2, tzinfo=UTC),
        )

    request = urlopen.call_args.args[0]
    assert request.full_url.startswith("https://sandbox-invest-public-api.tbank.ru/rest/")
    assert request.full_url.endswith("OperationsService/GetOperationsByCursor")
    assert "SandboxService" not in request.full_url


def test_tbank_find_instruments_filters_to_api_trade_available_results() -> None:
    credential = "t.fake-owner-credential-1234567890"
    client = TBankInvestClient()
    response = FakeResponse(
        {
            "instruments": [
                {
                    "uid": "uid-sber",
                    "figi": "BBG004730N88",
                    "ticker": "SBER",
                    "name": "Сбер Банк",
                    "instrumentType": "share",
                    "classCode": "TQBR",
                    "lot": 10,
                    "forQualInvestorFlag": False,
                    "forIisFlag": True,
                    "weekendFlag": False,
                    "apiTradeAvailableFlag": True,
                },
                {
                    "uid": "uid-hidden",
                    "figi": "BBG000000000",
                    "ticker": "HIDE",
                    "name": "Недоступный инструмент",
                    "instrumentType": "share",
                    "classCode": "TQBR",
                    "lot": 1,
                    "forQualInvestorFlag": False,
                    "forIisFlag": True,
                    "weekendFlag": False,
                    "apiTradeAvailableFlag": False,
                },
            ]
        }
    )

    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        instruments = client.find_instruments(credential, "prod", "SBER", limit=20)

    assert instruments == (
        TBankInstrument(
            uid="uid-sber",
            figi="BBG004730N88",
            ticker="SBER",
            name="Сбер Банк",
            instrument_type="share",
            class_code="TQBR",
            lot=10,
            for_qual_investor=False,
            for_iis=True,
            weekend_trading=False,
        ),
    )

    request = urlopen.call_args.args[0]
    assert request.full_url.endswith("InstrumentsService/FindInstrument")
    assert json.loads(request.data.decode()) == {
        "query": "SBER",
        "instrumentKind": "INSTRUMENT_TYPE_UNSPECIFIED",
        "apiTradeAvailableFlag": True,
    }


def test_tbank_find_instruments_rejects_blank_query_before_network_call() -> None:
    client = TBankInvestClient()

    with (
        patch("urllib.request.urlopen") as urlopen,
        pytest.raises(ValueError, match="1 to 64"),
    ):
        client.find_instruments(
            "t.fake-owner-credential-1234567890",
            "prod",
            "   ",
        )

    urlopen.assert_not_called()


def test_tbank_reads_latest_usd_rub_quote_without_hardcoded_instrument_id() -> None:
    credential = "t.fake-owner-credential-1234567890"
    client = TBankInvestClient()
    instruments_response = FakeResponse(
        {
            "instruments": [
                {
                    "uid": "uid-usd-rub",
                    "figi": "FIGI-USDRUB",
                    "ticker": "USDTEST",
                    "name": "Доллар США / Российский рубль",
                    "instrumentType": "currency",
                    "classCode": "TEST",
                    "lot": 1,
                    "forQualInvestorFlag": False,
                    "forIisFlag": True,
                    "weekendFlag": True,
                    "apiTradeAvailableFlag": True,
                },
                {
                    "uid": "uid-eur-rub",
                    "figi": "FIGI-EURRUB",
                    "ticker": "EURTEST",
                    "name": "Евро / Российский рубль",
                    "instrumentType": "currency",
                    "classCode": "TEST",
                    "lot": 1,
                    "forQualInvestorFlag": False,
                    "forIisFlag": True,
                    "weekendFlag": True,
                    "apiTradeAvailableFlag": True,
                },
            ]
        }
    )
    market_response = FakeResponse(
        {
            "instruments": [
                {
                    "instrumentUid": "uid-usd-rub",
                    "ticker": "USDTEST",
                    "classCode": "TEST",
                    "priceCurrency": "rub",
                    "values": [
                        {
                            "type": "INSTRUMENT_VALUE_LAST_PRICE",
                            "value": {"units": "92", "nano": 100000000},
                            "time": "2026-10-01T12:00:05Z",
                        },
                        {
                            "type": "INSTRUMENT_VALUE_LAST_PRICE_DEALER",
                            "value": {"units": "92", "nano": 250000000},
                            "time": "2026-10-01T12:00:07Z",
                        },
                        {
                            "type": "INSTRUMENT_VALUE_CLOSE_PRICE",
                            "value": {"units": "91", "nano": 900000000},
                            "time": "2026-09-30T20:00:00Z",
                        },
                    ],
                }
            ]
        }
    )

    with patch(
        "urllib.request.urlopen",
        side_effect=[instruments_response, market_response],
    ) as urlopen:
        quote = client.get_usd_rub_quote(credential, "prod")

    assert quote == TBankFxQuote(
        instrument_uid="uid-usd-rub",
        ticker="USDTEST",
        name="Доллар США / Российский рубль",
        class_code="TEST",
        price="92.25",
        currency="RUB",
        quote_time="2026-10-01T12:00:07Z",
        source="dealer",
        previous_close="91.9",
    )

    find_request = urlopen.call_args_list[0].args[0]
    market_request = urlopen.call_args_list[1].args[0]
    assert find_request.full_url.endswith("InstrumentsService/FindInstrument")
    assert json.loads(find_request.data.decode()) == {
        "query": "USD",
        "instrumentKind": "INSTRUMENT_TYPE_CURRENCY",
        "apiTradeAvailableFlag": True,
    }
    assert market_request.full_url.endswith("MarketDataService/GetMarketValues")
    assert json.loads(market_request.data.decode()) == {
        "instrumentId": ["uid-usd-rub"],
        "values": [
            "INSTRUMENT_VALUE_LAST_PRICE",
            "INSTRUMENT_VALUE_LAST_PRICE_DEALER",
            "INSTRUMENT_VALUE_CLOSE_PRICE",
        ],
    }


def test_tbank_reads_portfolio_and_positions() -> None:
    credential = "t.fake-owner-credential-1234567890"
    client = TBankInvestClient()

    portfolio_response = FakeResponse(
        {
            "totalAmountPortfolio": {"currency": "rub", "units": "125000", "nano": 500000000},
            "totalAmountShares": {"currency": "rub", "units": "100000", "nano": 0},
            "totalAmountCurrencies": {"currency": "rub", "units": "25000", "nano": 500000000},
            "expectedYield": {"units": "12", "nano": 340000000},
            "dailyYield": {"currency": "rub", "units": "540", "nano": 120000000},
            "dailyYieldRelative": {"units": "0", "nano": 430000000},
            "positions": [
                {
                    "ticker": "TEST",
                    "figi": "BBG000TEST",
                    "instrumentUid": "uid-1",
                    "instrumentType": "share",
                    "quantity": {"units": "10", "nano": 0},
                    "currentPrice": {"currency": "rub", "units": "10000", "nano": 0},
                    "averagePositionPrice": {"currency": "rub", "units": "9000", "nano": 0},
                    "expectedYield": {"units": "11", "nano": 110000000},
                    "dailyYield": {"currency": "rub", "units": "100", "nano": 0},
                    "currentNkd": {"currency": "rub", "units": "12", "nano": 500000000},
                    "blocked": False,
                    "blockedLots": {"units": "2", "nano": 0},
                }
            ],
        }
    )
    positions_response = FakeResponse(
        {
            "money": [{"currency": "rub", "units": "25000", "nano": 500000000}],
            "blocked": [{"currency": "rub", "units": "100", "nano": 0}],
            "limitsLoadingInProgress": False,
        }
    )
    with patch(
        "urllib.request.urlopen",
        side_effect=[portfolio_response, positions_response],
    ) as urlopen:
        portfolio = client.get_portfolio(credential, "prod", "account-1")
        positions = client.get_positions(credential, "prod", "account-1")

    assert portfolio.total == TBankMoney(currency="RUB", value="125000.5")
    assert portfolio.expected_yield_percent == "12.34"
    assert portfolio.asset_totals[0] == TBankAssetTotal(
        kind="shares",
        money=TBankMoney(currency="RUB", value="100000"),
    )
    assert portfolio.positions[0].ticker == "TEST"
    assert portfolio.positions[0].quantity == "10"
    assert portfolio.positions[0].current_nkd == TBankMoney(currency="RUB", value="12.5")
    assert portfolio.positions[0].blocked_lots == "2"
    assert positions.money == (TBankMoney(currency="RUB", value="25000.5"),)
    assert positions.blocked_money == (TBankMoney(currency="RUB", value="100"),)
    portfolio_request = urlopen.call_args_list[0].args[0]
    positions_request = urlopen.call_args_list[1].args[0]
    assert portfolio_request.full_url.endswith("OperationsService/GetPortfolio")
    assert json.loads(portfolio_request.data.decode()) == {
        "accountId": "account-1",
        "currency": "RUB",
    }
    assert positions_request.full_url.endswith("OperationsService/GetPositions")


def test_metadata_adapter_preserves_unknown_qualification_and_all_status_records() -> None:
    client = TBankInvestClient()
    response = FakeResponse(
        {
            "instruments": [
                {
                    "uid": "uid-1",
                    "name": "Issuer",
                    "ticker": "TEST",
                    "sector": "energy",
                    "isin": "RU000TEST",
                    "countryOfRisk": "ru",
                    "apiTradeAvailableFlag": False,
                }
            ]
        }
    )

    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        result = client.get_instrument_metadata(
            "t.fake-owner-credential-1234567890",
            "prod",
            "share",
        )

    assert result == (
        TBankInstrumentMetadata(
            uid="uid-1",
            name="Issuer",
            ticker="TEST",
            isin="RU000TEST",
            instrument_type="share",
            sector="energy",
            country_of_risk="RU",
            for_qual_investor=None,
        ),
    )
    request = urlopen.call_args.args[0]
    assert request.full_url.endswith("InstrumentsService/Shares")
    assert json.loads(request.data.decode()) == {
        "instrumentStatus": "INSTRUMENT_STATUS_ALL",
    }


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"instruments": [{"uid": "one"}, {"uid": "one"}]},
        {"instruments": [{"uid": "one", "forQualInvestorFlag": "false"}]},
    ],
)
def test_malformed_metadata_cannot_look_like_a_valid_catalog(
    payload: dict[str, object],
) -> None:
    client = TBankInvestClient()
    response = FakeResponse(payload)

    with (
        patch("urllib.request.urlopen", return_value=response),
        pytest.raises(TBankUnavailable),
    ):
        client.get_instrument_metadata(
            "t.fake-owner-credential-1234567890",
            "prod",
            "bond",
        )


@pytest.mark.parametrize("units", ["NaN", "Infinity"])
def test_non_finite_broker_money_fails_at_provider_boundary(units: str) -> None:
    payload = {"totalAmountPortfolio": {"currency": "rub", "units": units}}
    client = TBankInvestClient()
    response = FakeResponse(payload)

    with (
        patch("urllib.request.urlopen", return_value=response),
        pytest.raises(TBankUnavailable),
    ):
        client.get_portfolio(
            "t.fake-owner-credential-1234567890",
            "prod",
            "account-1",
        )


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
                opened_at=datetime(2024, 1, 2, tzinfo=UTC),
                access_level="ACCOUNT_ACCESS_LEVEL_READ_ONLY",
            )
        ]

    def get_accounts(self, credential: str, environment: str):
        assert credential == "t.fake-owner-credential-1234567890"
        assert environment == "prod"
        return self.accounts


    def get_usd_rub_quote(self, credential: str, environment: str):
        assert credential == "t.fake-owner-credential-1234567890"
        assert environment == "prod"
        return TBankFxQuote(
            instrument_uid="uid-usd-rub",
            ticker="USDTEST",
            name="Доллар США / Российский рубль",
            class_code="TEST",
            price="92.25",
            currency="RUB",
            quote_time="2026-10-01T12:00:07Z",
            source="dealer",
            previous_close="91.9",
        )

    def find_instruments(
        self,
        credential: str,
        environment: str,
        query: str,
        *,
        limit: int = 20,
    ):
        assert credential == "t.fake-owner-credential-1234567890"
        assert environment == "prod"
        assert query == "SBER"
        assert limit == 20
        return (
            TBankInstrument(
                uid="uid-sber",
                figi="BBG004730N88",
                ticker="SBER",
                name="Сбер Банк",
                instrument_type="share",
                class_code="TQBR",
                lot=10,
                for_qual_investor=False,
                for_iis=True,
                weekend_trading=False,
            ),
        )

    def get_portfolio(self, credential: str, environment: str, account_id: str):
        assert credential == "t.fake-owner-credential-1234567890"
        assert environment == "prod"
        assert account_id == "account-1"
        return TBankPortfolio(
            total=TBankMoney(currency="RUB", value="1000"),
            expected_yield_percent="5",
            daily_yield=TBankMoney(currency="RUB", value="10"),
            daily_yield_percent="1",
            asset_totals=(),
            positions=(),
        )

    def get_positions(self, credential: str, environment: str, account_id: str):
        assert credential == "t.fake-owner-credential-1234567890"
        assert environment == "prod"
        assert account_id == "account-1"
        return TBankPositions(
            money=(TBankMoney(currency="RUB", value="100"),),
            blocked_money=(),
            limits_loading_in_progress=False,
        )



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


def test_broker_service_decrypts_saved_credential_only_for_read_calls() -> None:
    database = FakeDatabase()
    owner_id = UUID("00000000-0000-0000-0000-000000000001")
    credential = "t.fake-owner-credential-1234567890"
    key = Fernet.generate_key().decode("ascii")
    service = BrokerService(database, credential_key=key, tbank=FakeTBank())

    service.connect(
        user_id=owner_id,
        credential=credential,
        environment="prod",
        account_id="account-1",
        terms_version="2026-10-01-v2",
    )

    portfolio = service.portfolio(owner_id)
    instruments = service.search_instruments(owner_id, query="SBER")
    quote = service.usd_rub_quote(owner_id)

    assert portfolio.portfolio.total.value == "1000"
    assert portfolio.positions.money[0].value == "100"
    assert instruments[0].ticker == "SBER"
    assert quote.price == "92.25"
    assert quote.source == "dealer"
    assert not hasattr(portfolio, "credential")
    assert credential.encode() not in database.saved_ciphertext


def test_broker_service_keeps_two_users_strictly_isolated() -> None:
    database = FakeDatabase()
    first_user = UUID("00000000-0000-0000-0000-000000000001")
    second_user = UUID("00000000-0000-0000-0000-000000000002")
    service = BrokerService(
        database,
        credential_key=Fernet.generate_key().decode("ascii"),
        tbank=FakeTBank(),
    )

    service.connect(
        user_id=first_user,
        credential="t.fake-owner-credential-1234567890",
        environment="prod",
        account_id="account-1",
        terms_version="2026-10-01-v2",
    )

    assert service.status(first_user).connected is True
    assert service.status(second_user).connected is False
    with pytest.raises(BrokerNotConnected):
        service.portfolio(second_user)
    with pytest.raises(BrokerNotConnected):
        service.analysis(second_user)
    assert service.disconnect(second_user) is False
    assert service.status(first_user).connected is True


def test_broker_revalidates_selected_account_read_permission() -> None:
    database = FakeDatabase()
    user_id = UUID("00000000-0000-0000-0000-000000000001")
    fake = FakeTBank()
    service = BrokerService(
        database,
        credential_key=Fernet.generate_key().decode("ascii"),
        tbank=fake,
    )
    service.connect(
        user_id=user_id,
        credential="t.fake-owner-credential-1234567890",
        environment="prod",
        account_id="account-1",
        terms_version="2026-10-01-v2",
    )

    account = service.revalidate_account(user_id)
    assert account.access_level == "ACCOUNT_ACCESS_LEVEL_READ_ONLY"

    fake.accounts = [replace(account, access_level="ACCOUNT_ACCESS_LEVEL_NO_ACCESS")]
    with pytest.raises(BrokerAccountNotAccessible):
        service.revalidate_account(user_id)


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


def test_daily_observation_can_refresh_all_supported_catalog_kinds() -> None:
    database = FakeDatabase()
    user_id = UUID("00000000-0000-0000-0000-000000000001")
    fake = FakeTBank()
    service = BrokerService(
        database,
        credential_key=Fernet.generate_key().decode("ascii"),
        tbank=fake,
    )
    service.connect(
        user_id=user_id,
        credential="t.fake-owner-credential-1234567890",
        environment="prod",
        account_id="account-1",
        terms_version="2026-10-01-v2",
    )

    with patch.object(
        fake,
        "get_instrument_metadata",
        create=True,
        return_value=(),
    ) as catalog:
        snapshot = service.observation_bundle(user_id, full_catalog=True)

    assert catalog.call_count == 3
    assert {call.args[2] for call in catalog.call_args_list} == {"share", "bond", "etf"}
    assert snapshot.sources[-1].status == "received"


def test_analysis_metadata_outage_is_partial_and_calls_are_bounded_by_kind() -> None:
    database = FakeDatabase()
    user_id = UUID("00000000-0000-0000-0000-000000000001")
    fake = FakeTBank()
    baseline = fake.get_portfolio(
        "t.fake-owner-credential-1234567890",
        "prod",
        "account-1",
    )
    holdings = tuple(
        TBankPortfolioPosition(
            ticker=str(index),
            figi=str(index),
            instrument_uid=str(index),
            instrument_type="share",
            quantity="1",
            current_price=TBankMoney("RUB", "1"),
            average_price=None,
            expected_yield_percent="0",
            daily_yield=None,
            blocked=False,
        )
        for index in range(200)
    )
    service = BrokerService(
        database,
        credential_key=Fernet.generate_key().decode("ascii"),
        tbank=fake,
    )
    service.connect(
        user_id=user_id,
        credential="t.fake-owner-credential-1234567890",
        environment="prod",
        account_id="account-1",
        terms_version="2026-10-01-v2",
    )

    with (
        patch.object(
            fake,
            "get_portfolio",
            return_value=replace(baseline, positions=holdings),
        ),
        patch.object(
            fake,
            "get_instrument_metadata",
            create=True,
            side_effect=TBankUnavailable("unavailable"),
        ) as catalog,
    ):
        snapshot = service.analysis(user_id)

    assert catalog.call_count == 1
    assert snapshot.analysis.security_count == 200
    assert snapshot.analysis.status == "partial"
    assert snapshot.sources[-1].status == "partial"
    assert snapshot.analysis.rub_cash_unblocked == "100"
    assert "t.fake" not in repr(snapshot)
