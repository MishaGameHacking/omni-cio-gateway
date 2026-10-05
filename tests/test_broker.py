from __future__ import annotations

import io
import json
import ssl
import urllib.error
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch
from uuid import UUID

import pytest
from cryptography.fernet import Fernet

from omnicio.broker import (
    BrokerAccountNotAccessible,
    BrokerConnectionError,
    BrokerNotConnected,
    BrokerSandboxRequired,
    BrokerService,
)
from omnicio.db import TBankConnectionRecord
from omnicio.tbank import (
    TBankAccount,
    TBankAccruedInterest,
    TBankAssetTotal,
    TBankFxQuote,
    TBankHistoricCandle,
    TBankInstrument,
    TBankInstrumentMetadata,
    TBankInvestClient,
    TBankLastPrice,
    TBankMarketYield,
    TBankMoney,
    TBankOrderBook,
    TBankOrderLevel,
    TBankOrderPrice,
    TBankPortfolio,
    TBankPortfolioPosition,
    TBankPositions,
    TBankRating,
    TBankSandboxCancelResult,
    TBankSandboxMaxLots,
    TBankSandboxOrderState,
    TBankTokenRejected,
    TBankTradingStatus,
    TBankUnavailable,
    TBankUserInfo,
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


def test_tbank_get_user_info_parses_qualification_context() -> None:
    credential = "t.fake-owner-credential-1234567890"
    client = TBankInvestClient()
    response = FakeResponse(
        {
            "premStatus": False,
            "qualStatus": True,
            "qualifiedForWorkWith": ["bond", "russian_shares"],
            "tariff": "Investor",
            "riskLevelCode": "CONSERVATIVE",
            "userId": "provider-user-id",
        }
    )

    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        info = client.get_user_info(credential, "prod")

    assert info == TBankUserInfo(
        premium=False,
        qualified=True,
        qualified_for_work_with=("bond", "russian_shares"),
        tariff="Investor",
        risk_level_code="CONSERVATIVE",
    )
    request = urlopen.call_args.args[0]
    assert request.full_url.endswith("UsersService/GetInfo")
    assert request.get_header("Authorization") == f"Bearer {credential}"
    assert json.loads(request.data.decode()) == {}
    assert "provider-user-id" not in repr(info)


def test_tbank_bond_ratings_are_read_only_and_keep_agency_metadata() -> None:
    client = TBankInvestClient()
    response = FakeResponse(
        {
            "instrument": {
                "uid": "bond-uid",
                "ratings": [
                    {
                        "agencyName": "Эксперт РА",
                        "ratingLevel": "ruAA+",
                        "ratingDate": "2026-09-15T00:00:00Z",
                        "forecast": "Стабильный",
                        "isUnderWatch": False,
                    },
                    {
                        "agencyName": "АКРА",
                        "ratingLevel": "A+(RU)",
                        "ratingDate": "2026-09-20T00:00:00Z",
                        "forecast": "Позитивный",
                        "isUnderWatch": True,
                    },
                ],
            }
        }
    )

    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        result = client.get_bond_ratings(
            "t.fake-owner-credential-1234567890",
            "prod",
            "bond-uid",
        )

    assert result == (
        TBankRating(
            agency_name="Эксперт РА",
            rating_level="ruAA+",
            rating_date=datetime(2026, 9, 15, tzinfo=UTC),
            forecast="Стабильный",
            is_under_watch=False,
        ),
        TBankRating(
            agency_name="АКРА",
            rating_level="A+(RU)",
            rating_date=datetime(2026, 9, 20, tzinfo=UTC),
            forecast="Позитивный",
            is_under_watch=True,
        ),
    )
    request = urlopen.call_args.args[0]
    assert request.full_url.endswith("InstrumentsService/BondBy")
    assert json.loads(request.data.decode()) == {
        "idType": "INSTRUMENT_ID_TYPE_UID",
        "id": "bond-uid",
    }


def test_tbank_market_yields_are_batched_read_only_shortlist_signals() -> None:
    client = TBankInvestClient()
    response = FakeResponse(
        {
            "instruments": [
                {
                    "instrumentUid": "uid-1",
                    "values": [
                        {
                            "type": "INSTRUMENT_VALUE_YIELD",
                            "value": {"units": "12", "nano": 500000000},
                            "time": "2026-10-03T05:00:00Z",
                        }
                    ],
                },
                {
                    "instrumentUid": "uid-2",
                    "values": [
                        {
                            "type": "INSTRUMENT_VALUE_LAST_PRICE",
                            "value": {"units": "99", "nano": 0},
                            "time": "2026-10-03T05:00:00Z",
                        }
                    ],
                },
            ]
        }
    )

    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        result = client.get_market_yields(
            "t.fake-owner-credential-1234567890",
            "prod",
            ("uid-1", "uid-2", "uid-1"),
        )

    assert result == (
        TBankMarketYield(
            instrument_uid="uid-1",
            yield_percent="12.5",
            time=datetime(2026, 10, 3, 5, 0, tzinfo=UTC),
        ),
    )
    request = urlopen.call_args.args[0]
    assert request.full_url.endswith("MarketDataService/GetMarketValues")
    assert json.loads(request.data.decode()) == {
        "instrumentId": ["uid-1", "uid-2"],
        "values": ["INSTRUMENT_VALUE_YIELD"],
    }


def test_tbank_order_book_preserves_lot_depth_and_consistency() -> None:
    client = TBankInvestClient()
    response = FakeResponse(
        {
            "instrumentUid": "bond-uid",
            "isConsistent": True,
            "time": "2026-10-03T05:00:00Z",
            "bids": [
                {"price": {"units": "99", "nano": 900000000}, "quantity": "12"}
            ],
            "asks": [
                {"price": {"units": "100", "nano": 100000000}, "quantity": "8"}
            ],
        }
    )
    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        result = client.get_order_book(
            "t.fake-owner-credential-1234567890",
            "prod",
            "bond-uid",
            depth=10,
        )

    assert result == TBankOrderBook(
        instrument_uid="bond-uid",
        bids=(TBankOrderLevel("99.9", 12),),
        asks=(TBankOrderLevel("100.1", 8),),
        time=datetime(2026, 10, 3, 5, 0, tzinfo=UTC),
        is_consistent=True,
    )
    request = urlopen.call_args.args[0]
    assert request.full_url.endswith("MarketDataService/GetOrderBook")
    assert json.loads(request.data.decode()) == {
        "instrumentId": "bond-uid",
        "depth": 10,
    }


def test_post_sandbox_order_is_limit_only_margin_false_and_idempotent() -> None:
    client = TBankInvestClient()
    request_id = "00000000-0000-0000-0000-000000000701"
    response = FakeResponse(
        {
            "orderId": "exchange-order-1",
            "orderRequestId": request_id,
            "instrumentUid": "bond-uid",
            "executionReportStatus": "EXECUTION_REPORT_STATUS_NEW",
            "lotsRequested": "2",
            "lotsExecuted": "0",
            "totalOrderAmount": {"currency": "rub", "units": "0", "nano": 0},
            "executedCommission": {"currency": "rub", "units": "0", "nano": 0},
            "direction": "ORDER_DIRECTION_BUY",
            "orderType": "ORDER_TYPE_LIMIT",
        }
    )

    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        result = client.post_sandbox_order(
            "t.fake-owner-credential-1234567890",
            "sandbox",
            "account-1",
            "bond-uid",
            quantity_lots=2,
            price="101.25",
            direction="buy",
            request_id=request_id,
            price_type="point",
        )

    assert result == TBankSandboxOrderState(
        order_id="exchange-order-1",
        order_request_id=request_id,
        instrument_uid="bond-uid",
        execution_report_status="EXECUTION_REPORT_STATUS_NEW",
        lots_requested=2,
        lots_executed=0,
        total_order_amount=TBankMoney("RUB", "0"),
        executed_commission=TBankMoney("RUB", "0"),
        direction="ORDER_DIRECTION_BUY",
        order_type="ORDER_TYPE_LIMIT",
    )
    request = urlopen.call_args.args[0]
    assert request.full_url.endswith("SandboxService/PostSandboxOrder")
    assert json.loads(request.data.decode()) == {
        "quantity": "2",
        "price": {"units": "101", "nano": 250000000},
        "direction": "ORDER_DIRECTION_BUY",
        "accountId": "account-1",
        "orderType": "ORDER_TYPE_LIMIT",
        "orderId": request_id,
        "instrumentId": "bond-uid",
        "timeInForce": "TIME_IN_FORCE_DAY",
        "priceType": "PRICE_TYPE_POINT",
        "confirmMarginTrade": False,
    }


def test_sandbox_mutation_rejects_production_environment_before_network() -> None:
    client = TBankInvestClient()
    with (
        patch("urllib.request.urlopen") as urlopen,
        pytest.raises(ValueError, match="sandbox environment"),
    ):
        client.post_sandbox_order(
            "t.fake-owner-credential-1234567890",
            "prod",
            "account-1",
            "bond-uid",
            quantity_lots=1,
            price="100",
            direction="buy",
            request_id="00000000-0000-0000-0000-000000000702",
            price_type="point",
        )
    urlopen.assert_not_called()


def test_get_sandbox_order_state_reconciles_by_request_id() -> None:
    client = TBankInvestClient()
    request_id = "00000000-0000-0000-0000-000000000703"
    response = FakeResponse(
        {
            "orderId": "exchange-order-2",
            "orderRequestId": request_id,
            "instrumentUid": "bond-uid",
            "executionReportStatus": "EXECUTION_REPORT_STATUS_PARTIALLYFILL",
            "lotsRequested": "3",
            "lotsExecuted": "1",
            "totalOrderAmount": {"currency": "rub", "units": "1000", "nano": 0},
            "executedCommission": {"currency": "rub", "units": "2", "nano": 0},
            "direction": "ORDER_DIRECTION_SELL",
            "orderType": "ORDER_TYPE_LIMIT",
        }
    )
    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        state = client.get_sandbox_order_state(
            "t.fake-owner-credential-1234567890",
            "sandbox",
            "account-1",
            request_id=request_id,
            price_type="point",
        )

    assert state.lots_executed == 1
    request = urlopen.call_args.args[0]
    assert request.full_url.endswith("SandboxService/GetSandboxOrderState")
    assert json.loads(request.data.decode()) == {
        "accountId": "account-1",
        "orderId": request_id,
        "priceType": "PRICE_TYPE_POINT",
        "orderIdType": "ORDER_ID_TYPE_REQUEST",
    }


def test_cancel_sandbox_order_uses_request_id_not_exchange_guess() -> None:
    client = TBankInvestClient()
    request_id = "00000000-0000-0000-0000-000000000704"
    response = FakeResponse({"time": "2026-10-03T09:30:00Z"})
    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        result = client.cancel_sandbox_order(
            "t.fake-owner-credential-1234567890",
            "sandbox",
            "account-1",
            request_id=request_id,
        )

    assert result == TBankSandboxCancelResult(
        cancelled_at=datetime(2026, 10, 3, 9, 30, tzinfo=UTC)
    )
    request = urlopen.call_args.args[0]
    assert json.loads(request.data.decode()) == {
        "accountId": "account-1",
        "orderId": request_id,
        "orderIdType": "ORDER_ID_TYPE_REQUEST",
    }


def test_sandbox_max_lots_uses_non_margin_limits_only() -> None:
    client = TBankInvestClient()
    response = FakeResponse(
        {
            "buyLimits": {
                "buyMoneyAmount": {"currency": "rub", "units": "5000", "nano": 0},
                "buyMaxLots": "5",
                "buyMaxMarketLots": "5",
            },
            "sellLimits": {"sellMaxLots": "3"},
            "buyMarginLimits": {"buyMaxLots": "999"},
            "sellMarginLimits": {"sellMaxLots": "999"},
            "currency": "rub",
        }
    )
    with patch("urllib.request.urlopen", return_value=response):
        result = client.get_sandbox_max_lots(
            "t.fake-owner-credential-1234567890",
            "sandbox",
            "account-1",
            "bond-uid",
            price="100",
        )

    assert result == TBankSandboxMaxLots(
        buy_max_lots=5,
        sell_max_lots=3,
        buy_money_amount=TBankMoney("RUB", "5000"),
        currency="RUB",
    )


def test_tbank_order_price_is_read_only_cost_estimate() -> None:
    client = TBankInvestClient()
    response = FakeResponse(
        {
            "totalOrderAmount": {
                "currency": "rub",
                "units": "1012",
                "nano": 500000000,
            },
            "initialOrderAmount": {
                "currency": "rub",
                "units": "1000",
                "nano": 0,
            },
            "executedCommissionRub": {
                "currency": "rub",
                "units": "2",
                "nano": 500000000,
            },
            "serviceCommission": {
                "currency": "rub",
                "units": "0",
                "nano": 0,
            },
            "dealCommission": {
                "currency": "rub",
                "units": "2",
                "nano": 500000000,
            },
            "extraBond": {
                "aciValue": {
                    "currency": "rub",
                    "units": "10",
                    "nano": 0,
                }
            },
        }
    )

    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        result = client.get_order_price(
            "t.fake-owner-credential-1234567890",
            "prod",
            "account-1",
            "bond-uid",
            price="1000.25",
            direction="buy",
            quantity_lots=1,
        )

    assert result == TBankOrderPrice(
        total_order_amount=TBankMoney("RUB", "1012.5"),
        initial_order_amount=TBankMoney("RUB", "1000"),
        executed_commission_rub=TBankMoney("RUB", "2.5"),
        service_commission=TBankMoney("RUB", "0"),
        deal_commission=TBankMoney("RUB", "2.5"),
        bond_aci_value=TBankMoney("RUB", "10"),
    )
    request = urlopen.call_args.args[0]
    assert request.full_url.endswith("OrdersService/GetOrderPrice")
    assert json.loads(request.data.decode()) == {
        "accountId": "account-1",
        "instrumentId": "bond-uid",
        "price": {"units": "1000", "nano": 250000000},
        "direction": "ORDER_DIRECTION_BUY",
        "quantity": "1",
    }


def test_sandbox_order_price_uses_read_only_sandbox_method() -> None:
    client = TBankInvestClient()
    response = FakeResponse(
        {
            "totalOrderAmount": {"currency": "rub", "units": "100", "nano": 0},
            "initialOrderAmount": {"currency": "rub", "units": "99", "nano": 0},
            "executedCommissionRub": {"currency": "rub", "units": "1", "nano": 0},
            "serviceCommission": {"currency": "rub", "units": "0", "nano": 0},
            "dealCommission": {"currency": "rub", "units": "1", "nano": 0},
        }
    )
    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        client.get_order_price(
            "t.fake-owner-credential-1234567890",
            "sandbox",
            "account-1",
            "share-uid",
            price="99",
            direction="sell",
            quantity_lots=2,
        )
    request = urlopen.call_args.args[0]
    assert request.full_url.endswith("SandboxService/GetSandboxOrderPrice")
    assert json.loads(request.data.decode())["direction"] == "ORDER_DIRECTION_SELL"


@pytest.mark.parametrize(
    "payload",
    [
        {"premStatus": "false", "qualStatus": False},
        {"premStatus": False, "qualStatus": "false"},
        {"premStatus": False, "qualStatus": False, "qualifiedForWorkWith": "bond"},
    ],
)
def test_tbank_get_user_info_rejects_malformed_capabilities(
    payload: dict[str, object],
) -> None:
    client = TBankInvestClient()
    with (
        patch("urllib.request.urlopen", return_value=FakeResponse(payload)),
        pytest.raises(TBankUnavailable),
    ):
        client.get_user_info("t.fake-owner-credential-1234567890", "prod")


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
                    "averagePositionPriceFifo": {"currency": "rub", "units": "8900", "nano": 0},
                    "quantityLots": {"units": "1", "nano": 0},
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
            api_trade_available=False,
        ),
    )
    request = urlopen.call_args.args[0]
    assert request.full_url.endswith("InstrumentsService/Shares")
    assert json.loads(request.data.decode()) == {
        "instrumentStatus": "INSTRUMENT_STATUS_ALL",
    }


def test_bond_metadata_preserves_structure_required_for_r4_screening() -> None:
    client = TBankInvestClient()
    response = FakeResponse(
        {
            "instruments": [
                {
                    "uid": "bond-uid",
                    "name": "Test bond",
                    "ticker": "BOND",
                    "sector": "finance",
                    "isin": "RU000BOND",
                    "countryOfRisk": "ru",
                    "currency": "rub",
                    "lot": 1,
                    "nominal": {"currency": "rub", "units": "1000", "nano": 0},
                    "maturityDate": "2028-10-03T00:00:00Z",
                    "floatingCouponFlag": False,
                    "perpetualFlag": False,
                    "amortizationFlag": False,
                    "subordinatedFlag": True,
                    "liquidityFlag": True,
                    "requiredTests": ["test_bonds_risk"],
                    "apiTradeAvailableFlag": True,
                    "buyAvailableFlag": True,
                    "sellAvailableFlag": True,
                }
            ]
        }
    )

    with patch("urllib.request.urlopen", return_value=response):
        result = client.get_instrument_metadata(
            "t.fake-owner-credential-1234567890",
            "prod",
            "bond",
        )

    item = result[0]
    assert item.nominal == TBankMoney("RUB", "1000")
    assert item.maturity_date == datetime(2028, 10, 3, tzinfo=UTC)
    assert item.floating_coupon is False
    assert item.perpetual is False
    assert item.amortization is False
    assert item.subordinated is True
    assert item.liquidity is True
    assert item.required_tests == ("test_bonds_risk",)


def test_tbank_daily_candles_are_exchange_only_complete_liquidity_evidence() -> None:
    client = TBankInvestClient()
    now = datetime(2026, 10, 3, 5, 0, tzinfo=UTC)
    response = FakeResponse(
        {
            "candles": [
                {
                    "open": {"units": "99", "nano": 100000000},
                    "high": {"units": "100", "nano": 0},
                    "low": {"units": "98", "nano": 900000000},
                    "close": {"units": "99", "nano": 500000000},
                    "volume": "42",
                    "time": "2026-10-02T00:00:00Z",
                    "isComplete": True,
                    "candleSourceType": "CANDLE_SOURCE_EXCHANGE",
                }
            ]
        }
    )

    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        result = client.get_daily_exchange_candles(
            "t.fake-owner-credential-1234567890",
            "prod",
            "bond-uid",
            from_at=now - timedelta(days=30),
            to_at=now,
        )

    assert result == (
        TBankHistoricCandle(
            instrument_uid="bond-uid",
            close="99.5",
            volume_lots=42,
            time=datetime(2026, 10, 2, 0, 0, tzinfo=UTC),
            is_complete=True,
            source="CANDLE_SOURCE_EXCHANGE",
            open="99.1",
            high="100",
            low="98.9",
        ),
    )
    request = urlopen.call_args.args[0]
    assert request.full_url.endswith("MarketDataService/GetCandles")
    assert json.loads(request.data.decode()) == {
        "instrumentId": "bond-uid",
        "from": "2026-09-03T05:00:00Z",
        "to": "2026-10-03T05:00:00Z",
        "interval": "CANDLE_INTERVAL_DAY",
        "candleSourceType": "CANDLE_SOURCE_EXCHANGE",
    }


@pytest.mark.parametrize(
    "source_name",
    [None, "CANDLE_SOURCE_DEALER_WEEKEND"],
)
def test_tbank_daily_candles_require_confirmed_exchange_source(
    source_name: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = TBankInvestClient()
    now = datetime(2026, 10, 3, 5, 0, tzinfo=UTC)
    candle: dict[str, object] = {
        "open": {"units": "100", "nano": 0},
        "high": {"units": "101", "nano": 0},
        "low": {"units": "99", "nano": 0},
        "close": {"units": "100", "nano": 0},
        "volume": "1",
        "time": "2026-10-02T00:00:00Z",
        "isComplete": True,
    }
    if source_name is not None:
        candle["candleSourceType"] = source_name
    response = FakeResponse({"candles": [candle]})
    from_at = now - timedelta(days=30)
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *_args, **_kwargs: response,
    )

    with pytest.raises(TBankUnavailable, match="exchange-sourced"):
        client.get_daily_exchange_candles(
            "t.fake-owner-credential-1234567890",
            "prod",
            "bond-uid",
            from_at=from_at,
            to_at=now,
        )


def test_tbank_last_prices_are_read_only_batched_quote_evidence() -> None:
    client = TBankInvestClient()
    response = FakeResponse(
        {
            "lastPrices": [
                {
                    "instrumentUid": "uid-1",
                    "price": {"units": "123", "nano": 450000000},
                    "time": "2026-10-03T04:00:00Z",
                },
                {
                    "instrumentUid": "uid-2",
                    "price": {"units": "98", "nano": 500000000},
                    "time": "2026-10-03T04:00:01Z",
                },
            ]
        }
    )

    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        prices = client.get_last_prices(
            "t.fake-owner-credential-1234567890",
            "prod",
            ("uid-1", "uid-2", "uid-1"),
        )

    assert prices == (
        TBankLastPrice(
            instrument_uid="uid-1",
            price="123.45",
            time=datetime(2026, 10, 3, 4, 0, tzinfo=UTC),
        ),
        TBankLastPrice(
            instrument_uid="uid-2",
            price="98.5",
            time=datetime(2026, 10, 3, 4, 0, 1, tzinfo=UTC),
        ),
    )
    request = urlopen.call_args.args[0]
    assert request.full_url.endswith("MarketDataService/GetLastPrices")
    assert json.loads(request.data.decode()) == {
        "instrumentId": ["uid-1", "uid-2"],
        "lastPriceType": "LAST_PRICE_EXCHANGE",
        "instrumentStatus": "INSTRUMENT_STATUS_BASE",
    }


def test_tbank_intraday_exchange_candles_validate_ohlc_and_exchange_source() -> None:
    client = TBankInvestClient()
    now = datetime(2026, 10, 3, 5, 0, tzinfo=UTC)
    response = FakeResponse(
        {
            "candles": [
                {
                    "open": {"units": "100", "nano": 0},
                    "high": {"units": "102", "nano": 0},
                    "low": {"units": "99", "nano": 500000000},
                    "close": {"units": "101", "nano": 250000000},
                    "volume": "15",
                    "time": "2026-10-03T04:00:00Z",
                    "isComplete": False,
                    "candleSourceType": "CANDLE_SOURCE_EXCHANGE",
                }
            ]
        }
    )

    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        candles = client.get_exchange_candles(
            "t.fake-owner-credential-1234567890",
            "prod",
            "uid-1",
            from_at=now - timedelta(hours=8),
            to_at=now,
            interval="CANDLE_INTERVAL_5_MIN",
        )

    assert candles == (
        TBankHistoricCandle(
            instrument_uid="uid-1",
            open="100",
            high="102",
            low="99.5",
            close="101.25",
            volume_lots=15,
            time=datetime(2026, 10, 3, 4, 0, tzinfo=UTC),
            is_complete=False,
            source="CANDLE_SOURCE_EXCHANGE",
        ),
    )
    call = urlopen.call_args
    assert call is not None
    request = next(iter(call.args), None)
    assert request is not None
    assert request.full_url.endswith("MarketDataService/GetCandles")
    assert json.loads(request.data.decode()) == {
        "instrumentId": "uid-1",
        "from": "2026-10-02T21:00:00Z",
        "to": "2026-10-03T05:00:00Z",
        "interval": "CANDLE_INTERVAL_5_MIN",
        "candleSourceType": "CANDLE_SOURCE_EXCHANGE",
    }


@patch("urllib.request.urlopen")
def test_tbank_exchange_candles_reject_too_short_window_before_network(
    urlopen: Mock,
) -> None:
    client = TBankInvestClient()
    now = datetime(2026, 10, 3, 5, 0, tzinfo=UTC)
    from_at = now - timedelta(minutes=4, seconds=59)

    with pytest.raises(ValueError, match="at least one candle interval"):
        client.get_exchange_candles(
            "t.fake-owner-credential-1234567890",
            "prod",
            "uid-1",
            from_at=from_at,
            to_at=now,
            interval="CANDLE_INTERVAL_5_MIN",
        )

    urlopen.assert_not_called()


def test_tbank_trading_status_is_bound_to_requested_instrument() -> None:
    client = TBankInvestClient()
    response = FakeResponse(
        {
            "instrumentUid": "uid-1",
            "tradingStatus": "SECURITY_TRADING_STATUS_NORMAL_TRADING",
            "limitOrderAvailableFlag": True,
            "marketOrderAvailableFlag": False,
            "apiTradeAvailableFlag": True,
            "bestpriceOrderAvailableFlag": True,
            "onlyBestPrice": False,
        }
    )

    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        result = client.get_trading_status(
            "t.fake-owner-credential-1234567890",
            "prod",
            "uid-1",
        )

    assert result == TBankTradingStatus(
        instrument_uid="uid-1",
        trading_status="SECURITY_TRADING_STATUS_NORMAL_TRADING",
        limit_order_available=True,
        market_order_available=False,
        api_trade_available=True,
        best_price_order_available=True,
        only_best_price=False,
    )
    call = urlopen.call_args
    assert call is not None
    request = next(iter(call.args), None)
    assert request is not None
    assert request.full_url.endswith("MarketDataService/GetTradingStatus")
    assert json.loads(request.data.decode()) == {"instrumentId": "uid-1"}


def test_tbank_accrued_interest_preserves_value_and_timestamp() -> None:
    client = TBankInvestClient()
    response = FakeResponse(
        {
            "accruedInterests": [
                {
                    "date": "2026-10-03T00:00:00Z",
                    "value": {"units": "17", "nano": 250000000},
                    "valuePercent": {"units": "1", "nano": 725000000},
                    "nominal": {"units": "1000", "nano": 0},
                }
            ]
        }
    )

    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        result = client.get_accrued_interests(
            "t.fake-owner-credential-1234567890",
            "prod",
            "bond-uid",
            from_at=datetime(2026, 10, 2, tzinfo=UTC),
            to_at=datetime(2026, 10, 3, tzinfo=UTC),
        )

    assert result == (
        TBankAccruedInterest(
            instrument_uid="bond-uid",
            date=datetime(2026, 10, 3, tzinfo=UTC),
            value="17.25",
            value_percent="1.725",
            nominal="1000",
        ),
    )
    request = urlopen.call_args.args[0]
    assert request.full_url.endswith("InstrumentsService/GetAccruedInterests")
    assert json.loads(request.data.decode()) == {
        "instrumentId": "bond-uid",
        "from": "2026-10-02T00:00:00Z",
        "to": "2026-10-03T00:00:00Z",
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


def test_broker_sandbox_mutation_guard_rejects_prod_connection() -> None:
    database = FakeDatabase()
    owner_id = UUID("00000000-0000-0000-0000-000000000001")
    key = Fernet.generate_key().decode("ascii")
    service = BrokerService(
        database,
        credential_key=key,
        tbank=FakeTBank(),
    )
    service.connect(
        user_id=owner_id,
        credential="t.fake-owner-credential-1234567890",
        environment="prod",
        account_id="account-1",
        terms_version="2026-10-01-v2",
    )

    with pytest.raises(BrokerSandboxRequired):
        service.post_sandbox_order(
            owner_id,
            "bond-uid",
            quantity_lots=1,
            price="100",
            direction="buy",
            request_id="00000000-0000-0000-0000-000000000705",
            price_type="point",
        )


def test_evidence_reads_are_paced_across_concurrent_users() -> None:
    service = BrokerService(
        FakeDatabase(),
        credential_key=Fernet.generate_key().decode("ascii"),
        tbank=FakeTBank(),
    )

    with (
        patch("omnicio.broker.time.monotonic", side_effect=[0.0, 0.1, 0.31]),
        patch("omnicio.broker.time.sleep") as sleep_mock,
    ):
        first = service._paced_evidence_read(lambda: "first")
        second = service._paced_evidence_read(lambda: "second")

    assert first == "first"
    assert second == "second"
    sleep_mock.assert_called_once()
    assert sleep_mock.call_args.args[0] == pytest.approx(0.21)


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


@pytest.mark.parametrize("operation", ["portfolio", "analysis"])
def test_broker_read_discards_result_after_connection_changes(operation: str) -> None:
    database = FakeDatabase()
    user_id = UUID(int=1)
    broker = FakeTBank()
    service = BrokerService(
        database, credential_key=Fernet.generate_key().decode("ascii"), tbank=broker,
    )
    service.connect(
        user_id=user_id, credential="t.fake-owner-credential-1234567890",
        environment="prod", account_id="account-1", terms_version="2026-10-01-v2",
    )
    original = broker.get_positions

    def disconnected(*args):
        value = original(*args)
        database.delete_tbank_connection(user_id)
        return value

    with (
        patch.object(broker, "get_positions", side_effect=disconnected),
        pytest.raises(BrokerConnectionError, match="connection changed"),
    ):
        getattr(service, operation)(user_id)


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


@pytest.mark.parametrize(
    ("status", "access_level"),
    [
        ("ACCOUNT_STATUS_CLOSED", "ACCOUNT_ACCESS_LEVEL_READ_ONLY"),
        ("ACCOUNT_STATUS_OPEN", "ACCOUNT_ACCESS_LEVEL_NO_ACCESS"),
        ("ACCOUNT_STATUS_OPEN", ""),
        ("ACCOUNT_STATUS_OPEN", "ACCOUNT_ACCESS_LEVEL_UNSPECIFIED"),
    ],
)
def test_broker_connect_fails_closed_without_verified_read_access(
    status: str,
    access_level: str,
) -> None:
    database = FakeDatabase()
    fake = FakeTBank()
    fake.accounts = [replace(fake.accounts[0], status=status, access_level=access_level)]
    service = BrokerService(
        database,
        credential_key=Fernet.generate_key().decode("ascii"),
        tbank=fake,
    )

    with pytest.raises(BrokerAccountNotAccessible):
        service.connect(
            user_id=UUID("00000000-0000-0000-0000-000000000001"),
            credential="t.fake-owner-credential-1234567890",
            environment="prod",
            account_id="account-1",
            terms_version="2026-10-02-v6",
        )

    assert database.record is None


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


def test_tbank_asset_fundamentals_are_batched_and_finite() -> None:
    client = TBankInvestClient()
    response = FakeResponse(
        {
            "fundamentals": [
                {
                    "assetUid": "asset-1",
                    "currency": "rub",
                    "revenueTtm": 1250.5,
                    "ebitdaTtm": 200.0,
                    "netIncomeTtm": 100.0,
                    "freeCashFlowTtm": 80.0,
                    "totalDebtMrq": 300.0,
                    "totalDebtToEquityMrq": 0.4,
                    "totalDebtToEbitdaMrq": 1.5,
                    "netDebtToEbitda": 1.2,
                    "currentRatioMrq": 1.3,
                    "fixedChargeCoverageRatioFy": 4.1,
                    "netInterestMarginMrq": 0.0,
                    "roe": 0.15,
                    "roa": 0.08,
                    "fiscalPeriodStartDate": "2025-01-01T00:00:00Z",
                    "fiscalPeriodEndDate": "2025-12-31T00:00:00Z",
                }
            ]
        }
    )

    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        result = client.get_asset_fundamentals(
            "t.fake-owner-credential-1234567890",
            "prod",
            ("asset-1", "asset-1"),
        )

    assert len(result) == 1
    assert result[0].asset_uid == "asset-1"
    assert result[0].revenue_ttm == "1250.5"
    assert result[0].net_interest_margin_mrq is None
    assert result[0].fiscal_period_end_date == datetime(2025, 12, 31, tzinfo=UTC)
    request = urlopen.call_args.args[0]
    assert request.full_url.endswith("InstrumentsService/GetAssetFundamentals")
    assert json.loads(request.data.decode()) == {"assets": ["asset-1"]}


def test_tbank_bond_events_preserve_documented_default_date() -> None:
    client = TBankInvestClient()
    response = FakeResponse(
        {
            "events": [
                {
                    "instrumentId": "bond-uid",
                    "eventNumber": 8,
                    "eventDate": "2026-09-20T00:00:00Z",
                    "eventType": "EVENT_TYPE_COUPON",
                    "defaultDate": "2026-09-30T00:00:00Z",
                    "payDate": "2026-09-25T00:00:00Z",
                    "payOneBond": {"currency": "rub", "units": "50", "nano": 0},
                    "execution": "not_executed",
                    "operationType": "OPERATION_TYPE_COUPON",
                    "note": "",
                }
            ]
        }
    )

    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        events = client.get_bond_events(
            "t.fake-owner-credential-1234567890",
            "prod",
            "bond-uid",
            from_at=datetime(2026, 9, 1, tzinfo=UTC),
            to_at=datetime(2026, 10, 2, tzinfo=UTC),
        )

    assert events[0].default_date == datetime(2026, 9, 30, tzinfo=UTC)
    assert events[0].pay_one_bond == TBankMoney("RUB", "50")
    request = urlopen.call_args.args[0]
    assert request.full_url.endswith("InstrumentsService/GetBondEvents")
    assert json.loads(request.data.decode()) == {
        "instrumentId": "bond-uid",
        "from": "2026-09-01T00:00:00Z",
        "to": "2026-10-02T00:00:00Z",
        "type": "EVENT_TYPE_UNSPECIFIED",
    }


def test_tbank_asset_reports_reject_mismatched_instrument_subject() -> None:
    client = TBankInvestClient()
    response = FakeResponse(
        {
            "events": [
                {
                    "instrumentId": "other-uid",
                    "reportDate": "2026-09-30T00:00:00Z",
                    "periodYear": 2026,
                    "periodNum": 3,
                    "periodType": "PERIOD_TYPE_QUARTER",
                    "createdAt": "2026-09-29T18:00:00Z",
                }
            ]
        }
    )

    from_at = datetime(2026, 9, 1, tzinfo=UTC)
    to_at = datetime(2026, 10, 2, tzinfo=UTC)
    with (
        patch("urllib.request.urlopen", return_value=response),
        pytest.raises(TBankUnavailable, match="instrument does not match"),
    ):
        client.get_asset_reports(
            "t.fake-owner-credential-1234567890",
            "prod",
            "asset-report-uid",
            from_at=from_at,
            to_at=to_at,
        )


def test_tbank_fundamentals_reject_non_finite_provider_values() -> None:
    client = TBankInvestClient()
    response = FakeResponse(
        {
            "fundamentals": [
                {
                    "assetUid": "asset-1",
                    "currency": "rub",
                    "revenueTtm": float("inf"),
                }
            ]
        }
    )

    with (
        patch("urllib.request.urlopen", return_value=response),
        pytest.raises(TBankUnavailable, match="non-finite"),
    ):
        client.get_asset_fundamentals(
            "t.fake-owner-credential-1234567890",
            "prod",
            ("asset-1",),
        )
