from __future__ import annotations

import io
import json
import math
import socket
import ssl
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from email.message import Message
from functools import partial
from http.client import HTTPResponse
from threading import Barrier, Event
from unittest.mock import Mock, patch
from uuid import UUID

import pytest
from cryptography.fernet import Fernet

from omnicio.broker import (
    BrokerAccountNotAccessible,
    BrokerConnectionError,
    BrokerNotConnected,
    BrokerService,
)
from omnicio.db import TBankConnectionRecord
from omnicio.market import MarketService
from omnicio.tbank import (
    TBankAccount,
    TBankAccruedInterest,
    TBankFxQuote,
    TBankHistoricCandle,
    TBankInstrument,
    TBankInstrumentMetadata,
    TBankInvestClient,
    TBankLastPrice,
    TBankMarketYield,
    TBankMoney,
    TBankNotFound,
    TBankOrderBook,
    TBankOrderLevel,
    TBankPortfolioPosition,
    TBankPositions,
    TBankRateLimited,
    TBankRating,
    TBankTokenRejected,
    TBankTradingStatus,
    TBankUnavailable,
    TBankWithdrawLimits,
)


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, limit: int = -1) -> bytes:
        body = json.dumps(self.payload).encode()
        return body if limit < 0 else body[:limit]


@pytest.fixture
def market_clock(monkeypatch: pytest.MonkeyPatch) -> Mock:
    clock = Mock(return_value=1000.0)
    monkeypatch.setattr("omnicio.tbank.monotonic", clock)
    return clock


def _rate_limit_error(values: tuple[str, ...]) -> urllib.error.HTTPError:
    headers = Message()
    for value in values:
        headers["Retry-After"] = value
    return urllib.error.HTTPError(
        "https://invest-public-api.tbank.ru/rest/", 429, "Too Many Requests", headers,
        io.BytesIO(b"synthetic-provider-secret-must-not-leak"),
    )


def test_market_burst_is_atomic_across_clients_and_keeps_portfolio_independent(
    market_clock: Mock,
) -> None:
    clients = (TBankInvestClient(purpose="market"), TBankInvestClient(purpose="market"))
    start = Barrier(40)

    def read(index: int) -> float | None:
        start.wait(timeout=5)
        client = clients[index % 2]
        try:
            if index % 2:
                client.find_instruments("synthetic-market-source-a", "prod", "test")
            else:
                client.get_all_last_prices("synthetic-market-source-b", "prod")
        except TBankRateLimited as exc:
            return exc.retry_at_monotonic
        return None

    with patch("urllib.request.OpenerDirector.open", return_value=FakeResponse({})) as network:
        with ThreadPoolExecutor(max_workers=40) as readers:
            results = list(readers.map(read, range(40)))
        assert results.count(None) == 25
        assert [value for value in results if value is not None] == [1001.0] * 15
        assert network.call_count == 25

        TBankInvestClient().get_positions("synthetic-private-bearer", "prod", "account-1")
        assert network.call_count == 26

        # An exhausted market budget is checked before creating an authenticated
        # request, but cannot replace the existing scope/token validation result.
        with patch("urllib.request.Request") as authenticated_request:
            with pytest.raises(TBankRateLimited):
                clients[0].get_all_last_prices("synthetic-market-source", "prod")
            with pytest.raises(TBankTokenRejected):
                clients[0].get_all_last_prices("invalid bearer", "prod")
            with pytest.raises(TBankTokenRejected):
                clients[0]._post(token="synthetic-market-source", environment="prod",
                                 service="OrdersService", method="PostOrder", body={})
            with pytest.raises(TBankTokenRejected):
                clients[0].get_all_last_prices("synthetic-market-source", "sandbox")
        authenticated_request.assert_not_called()
        assert network.call_count == 26

        market_clock.return_value = 1001.0
        clients[1].get_all_last_prices("synthetic-market-source", "prod")
        assert network.call_count == 27


@pytest.mark.parametrize("service,limit", [("instruments", 100), ("market_data", 300)])
def test_market_minute_windows_are_shared_per_service_and_expire_individually(
    market_clock: Mock, service: str, limit: int,
) -> None:
    clients = (TBankInvestClient(purpose="market"), TBankInvestClient(purpose="market"))
    if service == "instruments":
        reads = [partial(client.find_instruments, "synthetic-market-source", "prod", "test")
                 for client in clients]
        other_service = partial(clients[0].get_all_last_prices, "synthetic-market-source", "prod")
    else:
        reads = [partial(client.get_all_last_prices, "synthetic-market-source", "prod")
                 for client in clients]
        other_service = partial(
            clients[0].find_instruments, "synthetic-market-source", "prod", "test",
        )
    read = reads[0]
    with patch("urllib.request.OpenerDirector.open", return_value=FakeResponse({})) as network:
        for index in range(limit):
            market_clock.return_value = 1000.0 + index / 10
            reads[index % 2]()
        market_clock.return_value = 1000.0 + limit / 10
        with pytest.raises(TBankRateLimited) as blocked:
            read()
        assert blocked.value.retry_at_monotonic == 1060.0
        other_service()
        assert network.call_count == limit + 1

        market_clock.return_value = 1059.999
        with pytest.raises(TBankRateLimited):
            read()
        market_clock.return_value = 1060.0
        read()
        with pytest.raises(TBankRateLimited) as next_slot:
            read()
        assert next_slot.value.retry_at_monotonic == pytest.approx(1060.1)
        assert network.call_count == limit + 2


def test_heavy_catalog_group_also_consumes_the_instruments_service_budget(
    market_clock: Mock,
) -> None:
    client = TBankInvestClient(purpose="market")
    kinds = ("share", "bond", "etf", "future", "share", "bond", "etf")
    response = FakeResponse({"instruments": []})
    with patch("urllib.request.OpenerDirector.open", return_value=response) as network:
        for index, kind in enumerate(kinds):
            market_clock.return_value = 1000.0 + index / 10
            client.get_instrument_metadata("synthetic-market-source", "prod", kind)
        with pytest.raises(TBankRateLimited) as heavy_blocked:
            client.get_instrument_metadata("synthetic-market-source", "prod", "future")
        assert heavy_blocked.value.retry_at_monotonic == 1060.0

        # A denied heavy call reserves neither the service window nor a burst
        # slot. Currencies remain usable until the shared service ceiling.
        for index in range(93):
            market_clock.return_value = 1000.0 + (len(kinds) + index) / 10
            client.get_instrument_metadata("synthetic-market-source", "prod", "currency")
        with pytest.raises(TBankRateLimited) as service_blocked:
            client.find_instruments("synthetic-market-source", "prod", "test")
        assert service_blocked.value.retry_at_monotonic == 1060.0
        client.get_all_last_prices("synthetic-market-source", "prod")
        assert network.call_count == 101


@pytest.mark.parametrize("headers,delay", [
    ((), 60.0), (("",), 60.0), (("75",), 75.0), (("7200",), 7200.0),
    (("0",), 1.0), (("-1",), 60.0), (("1.5",), 60.0), (("NaN",), 60.0),
    (("Infinity",), 60.0), (("١٢",), 60.0), (("9" * 129,), 60.0),
    (("9" * 128,), float("9" * 128)), (("60", "7200"), 60.0),
    (("Fri, 09 Oct 2026 02:00:00 GMT",), 7200.0),
    (("Friday, 09-Oct-26 02:00:00 GMT",), 7200.0),
    (("Fri Oct  9 02:00:00 2026",), 7200.0),
    (("Thu, 08 Oct 2026 23:59:00 GMT",), 1.0),
    (("Fri, 09 Oct 2026 02:00:00 GMT, 120",), 60.0),
    (("Fri, 32 Oct 2026 02:00:00 GMT",), 60.0),
    (("Fri, 09 Oct 2026 02:00:00 +0000",), 60.0),
])
def test_market_http_429_defers_all_clients_without_replay_or_secret_exposure(
    market_clock: Mock, headers: tuple[str, ...], delay: float, caplog,
) -> None:
    error = _rate_limit_error(headers)
    client = TBankInvestClient(purpose="market")
    with (
        patch("urllib.request.OpenerDirector.open", side_effect=error) as network,
        patch("omnicio.tbank.datetime", wraps=datetime) as wall_clock,
    ):
        wall_clock.now.return_value = datetime(2026, 10, 9, tzinfo=UTC)
        with pytest.raises(TBankRateLimited) as limited:
            client.get_all_last_prices("synthetic-market-bearer-must-not-leak", "prod")
        deadline = limited.value.retry_at_monotonic
        assert math.isfinite(deadline)
        assert deadline == 1000.0 + delay
        assert error.fp.closed
        network.assert_called_once()

        network.side_effect = None
        network.return_value = FakeResponse({})
        market_clock.return_value = math.nextafter(deadline, -math.inf)
        other_client = TBankInvestClient(purpose="market")
        with pytest.raises(TBankRateLimited) as shared:
            other_client.find_instruments(
                "synthetic-other-market-bearer", "prod", "test",
            )
        assert shared.value.retry_at_monotonic == deadline
        network.assert_called_once()
        TBankInvestClient().get_positions("synthetic-private-bearer", "prod", "account-1")
        assert network.call_count == 2

        market_clock.return_value = deadline
        client.get_all_last_prices("synthetic-market-bearer-must-not-leak", "prod")
        assert network.call_count == 3
    assert "must-not-leak" not in str(limited.value)
    assert "must-not-leak" not in caplog.text


def test_parallel_success_and_shorter_http_429_cannot_erase_market_cooldown(
    market_clock: Mock,
) -> None:
    client = TBankInvestClient(purpose="market")
    success_started, short_started, finish = Event(), Event(), Event()

    def respond(request, **_kwargs):
        if request.full_url.endswith("/GetLastPrices"):
            success_started.set()
            assert finish.wait(timeout=5)
            return FakeResponse({})
        if request.full_url.endswith("/FindInstrument"):
            short_started.set()
            assert finish.wait(timeout=5)
            raise _rate_limit_error(("5",))
        raise _rate_limit_error(("120",))

    with patch("urllib.request.OpenerDirector.open", side_effect=respond) as network:
        with ThreadPoolExecutor(max_workers=2) as readers:
            success = readers.submit(client.get_all_last_prices, "synthetic-market-source", "prod")
            shorter = readers.submit(
                client.find_instruments, "synthetic-market-source", "prod", "test",
            )
            try:
                assert success_started.wait(timeout=5)
                assert short_started.wait(timeout=5)
                with pytest.raises(TBankRateLimited) as long_pause:
                    client.get_news("synthetic-market-source", "prod")
                assert long_pause.value.retry_at_monotonic == 1120.0
            finally:
                finish.set()
            assert success.result(timeout=5).prices == ()
            with pytest.raises(TBankRateLimited):
                shorter.result(timeout=5)
        with pytest.raises(TBankRateLimited) as retained:
            client.get_all_last_prices("synthetic-market-source", "prod")
        assert retained.value.retry_at_monotonic == 1120.0
        assert network.call_count == 3


@pytest.mark.parametrize("purpose,status", [("portfolio", 429), ("market", 503)])
def test_portfolio_429_and_market_server_error_do_not_pause_market_clients(
    market_clock: Mock, purpose, status: int,
) -> None:
    error = urllib.error.HTTPError(
        "https://invest-public-api.tbank.ru/rest/", status, "Unavailable", {}, io.BytesIO(b"{}"),
    )
    client = TBankInvestClient(purpose=purpose)
    read = (partial(client.get_positions, "synthetic-private-bearer", "prod", "account-1")
            if purpose == "portfolio"
            else partial(client.get_all_last_prices, "synthetic-market-source", "prod"))
    with patch("urllib.request.OpenerDirector.open", side_effect=error) as network:
        with pytest.raises(TBankUnavailable):
            read()
        network.assert_called_once()
        network.side_effect = None
        network.return_value = FakeResponse({})
        TBankInvestClient(purpose="market").get_all_last_prices("synthetic-market-source", "prod")
        assert network.call_count == 2


@pytest.mark.parametrize(
    "body", [b" " * 129, b'{"id":' + b'9' * 5000 + b'}'],
    ids=["oversized-response", "oversized-json-integer"],
)
def test_provider_body_is_bounded_and_malformed_json_fails_closed(body: bytes) -> None:
    limit = 128 if len(body) == 129 else 6000
    client = TBankInvestClient()
    with (
        patch("omnicio.tbank._MAX_RESPONSE_BYTES", limit),
        patch("urllib.request.OpenerDirector.open", return_value=io.BytesIO(body)) as request,
        pytest.raises(TBankUnavailable),
    ):
        client.get_accounts("synthetic-test-credential", "prod")
    request.assert_called_once()


@pytest.mark.parametrize("character", ["\x00", "\x1f", "\x7f", "я", " "])
def test_invalid_bearer_characters_fail_before_provider_io(character: str) -> None:
    client = TBankInvestClient()
    with (
        patch("urllib.request.OpenerDirector.open") as request,
        pytest.raises(TBankTokenRejected),
    ):
        client.get_accounts("synthetic" + character + "test-credential", "prod")
    request.assert_not_called()


def test_fund_profile_reads_explicit_expense_percent_and_preserves_provider_identity():
    payload = {
        "asset": {
            "uid": "fund-asset",
            "security": {
                "type": "etf",
                "etf": {"totalExpense": {"units": "0", "nano": 750000000}, "primaryIndex": "IMOEX"},
            },
        }
    }
    client = TBankInvestClient(purpose="market")
    with patch.object(TBankInvestClient, "_post", return_value=payload) as post:
        value = client.get_fund_profile("test-fixture", "prod", "fund-asset")
    assert value.total_expense_percent == "0.75"
    assert value.primary_index == "IMOEX"
    assert post.call_args.kwargs["body"] == {"id": "fund-asset"}
    payload["asset"]["uid"] = "another-asset"
    with (
        patch.object(TBankInvestClient, "_post", return_value=payload),
        pytest.raises(TBankUnavailable),
    ):
        client.get_fund_profile("test-fixture", "prod", "fund-asset")


def test_provider_news_keeps_exact_instrument_links_cursor_and_untrusted_text():
    payload = {
        "hasNext": True,
        "nextCursor": "15",
        "items": [
            {
                "id": "18",
                "title": "<b>Title</b>",
                "source": "https://example.invalid/news/18",
                "ts": "2026-10-06T10:00:00Z",
                "instrumentId": [{"instrument": {"instrumentUid": "exact-uid"}}],
                "priority": True,
            }
        ],
    }
    client = TBankInvestClient(purpose="market")
    with patch.object(TBankInvestClient, "_post", return_value=payload) as post:
        page = client.get_news("test-fixture", "prod", cursor="20", limit=3)
    assert page.next_cursor == "15"
    assert page.items[0].instrument_uids == ("exact-uid",)
    assert page.items[0].title == "<b>Title</b>"
    assert page.items[0].source_url == "https://example.invalid/news/18"
    assert post.call_args.kwargs["body"] == {"cursor": "20", "limit": 3}
    payload["items"][0]["source"] = "javascript:alert(1)"
    with patch.object(TBankInvestClient, "_post", return_value=payload):
        assert client.get_news("test-fixture", "prod").items[0].source_url is None
    payload["nextCursor"] = "20"
    with (
        patch.object(TBankInvestClient, "_post", return_value=payload),
        pytest.raises(TBankUnavailable),
    ):
        client.get_news("test-fixture", "prod", cursor="20")


def test_news_default_page_and_validation_share_the_provider_ceiling() -> None:
    from omnicio.tbank import NEWS_MAX_PAGE_SIZE

    client = TBankInvestClient(purpose="market")
    over_limit = NEWS_MAX_PAGE_SIZE + 1
    with patch.object(TBankInvestClient, "_post", return_value={"nextCursor": "0"}) as post:
        assert client.get_news("test-fixture", "prod").items == ()
        assert post.call_args.kwargs["body"] == {"limit": NEWS_MAX_PAGE_SIZE}
        with pytest.raises(ValueError, match="news_page_parameters_invalid"):
            client.get_news("test-fixture", "prod", limit=over_limit)
    assert post.call_count == 1


@pytest.mark.parametrize("has_next", [False, None])
def test_provider_news_terminal_flag_overrides_remaining_cursor(has_next: bool | None) -> None:
    payload = {
        "nextCursor": "20",
        "items": [{"id": "20", "title": "Observed news", "ts": "2026-10-06T10:00:00Z"}],
    }
    if has_next is not None:
        payload["hasNext"] = has_next
    with patch.object(TBankInvestClient, "_post", return_value=payload):
        page = TBankInvestClient(purpose="market").get_news("test-fixture", "prod", cursor="20")
    assert page.next_cursor is None
    assert len(page.items) == 1


def test_provider_news_accepts_empty_protojson_terminal_page() -> None:
    with patch.object(TBankInvestClient, "_post", return_value={}):
        page = TBankInvestClient(purpose="market").get_news("test-fixture", "prod")
    assert page.items == ()
    assert page.next_cursor is None


@pytest.mark.parametrize(
    "payload",
    [
        {"hasNext": "false", "nextCursor": "15"},
        {"hasNext": 1, "nextCursor": "15"},
        {"hasNext": True},
        {"hasNext": True, "nextCursor": "0"},
        {"hasNext": True, "nextCursor": "020"},
        {"hasNext": True, "nextCursor": "9223372036854775808"},
        {"hasNext": True, "nextCursor": "-1"},
    ],
)
def test_provider_news_rejects_invalid_flag_or_nonadvancing_continuation(payload: dict) -> None:
    client = TBankInvestClient(purpose="market")
    with (
        patch.object(TBankInvestClient, "_post", return_value={**payload, "items": []}),
        pytest.raises(TBankUnavailable),
    ):
        client.get_news("test-fixture", "prod", cursor="20")


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

    with patch("urllib.request.OpenerDirector.open", return_value=response) as urlopen:
        accounts = client.get_accounts(credential, "prod")

    assert accounts == [
        TBankAccount(
            id="account-1",
            name="Брокерский счёт",
            type="ACCOUNT_TYPE_TINKOFF",
            status="ACCOUNT_STATUS_OPEN",
            access_level="ACCOUNT_ACCESS_LEVEL_READ_ONLY",
        )
    ]
    request = urlopen.call_args.args[0]
    assert request.full_url.endswith("UsersService/GetAccounts")
    assert request.get_header("Authorization") == f"Bearer {credential}"
    assert json.loads(request.data.decode()) == {"status": "ACCOUNT_STATUS_ALL"}


def test_tbank_bond_ratings_are_read_only_and_keep_agency_metadata() -> None:
    client = TBankInvestClient(purpose="market")
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

    with patch("urllib.request.OpenerDirector.open", return_value=response) as urlopen:
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
    client = TBankInvestClient(purpose="market")
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

    with patch("urllib.request.OpenerDirector.open", return_value=response) as urlopen:
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
    client = TBankInvestClient(purpose="market")
    response = FakeResponse(
        {
            "instrumentUid": "bond-uid",
            "isConsistent": True,
            "time": "2026-10-03T05:00:00Z",
            "bids": [{"price": {"units": "99", "nano": 900000000}, "quantity": "12"}],
            "asks": [{"price": {"units": "100", "nano": 100000000}, "quantity": "8"}],
        }
    )
    with patch("urllib.request.OpenerDirector.open", return_value=response) as urlopen:
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


def test_tbank_find_instruments_filters_to_api_trade_available_results() -> None:
    credential = "t.fake-owner-credential-1234567890"
    client = TBankInvestClient(purpose="market")
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

    with patch("urllib.request.OpenerDirector.open", return_value=response) as urlopen:
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
    client = TBankInvestClient(purpose="market")

    with (
        patch("urllib.request.OpenerDirector.open") as urlopen,
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
    client = TBankInvestClient(purpose="market")
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
        "urllib.request.OpenerDirector.open",
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


def test_metadata_adapter_preserves_unknown_qualification_and_all_status_records() -> None:
    client = TBankInvestClient(purpose="market")
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

    with patch("urllib.request.OpenerDirector.open", return_value=response) as urlopen:
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
    client = TBankInvestClient(purpose="market")
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

    with patch("urllib.request.OpenerDirector.open", return_value=response):
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
    client = TBankInvestClient(purpose="market")
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
                    "candleSource": "CANDLE_SOURCE_EXCHANGE",
                }
            ]
        }
    )

    with patch("urllib.request.OpenerDirector.open", return_value=response) as urlopen:
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
    "source_fields",
    [
        {},
        {"candleSource": None},
        {"candleSource": "CANDLE_SOURCE_DEALER_WEEKEND"},
        {"candleSource": "CANDLE_SOURCE_EXCHANGE", "candleSourceType": None},
        {
            "candleSource": "CANDLE_SOURCE_EXCHANGE",
            "candleSourceType": "CANDLE_SOURCE_DEALER_WEEKEND",
        },
        {
            "candleSource": "CANDLE_SOURCE_DEALER_WEEKEND",
            "candleSourceType": "CANDLE_SOURCE_EXCHANGE",
        },
    ],
)
def test_tbank_daily_candles_require_confirmed_exchange_source(
    source_fields: dict[str, str | None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = TBankInvestClient(purpose="market")
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
    candle.update(source_fields)
    response = FakeResponse({"candles": [candle]})
    from_at = now - timedelta(days=30)
    monkeypatch.setattr(
        "urllib.request.OpenerDirector.open",
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
    client = TBankInvestClient(purpose="market")
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

    with patch("urllib.request.OpenerDirector.open", return_value=response) as urlopen:
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


@pytest.mark.parametrize(
    "parts,expected",
    [
        ({"units": "9223372036854775807", "nano": 999999999}, "9223372036854775807.999999999"),
        ({"units": "-9223372036854775808", "nano": -999999999}, "-9223372036854775808.999999999"),
        ({"units": "10", "nano": 2147483647}, "12.147483647"),
        ({"units": "10", "nano": -2147483648}, "7.852516352"),
        ({"units": "1e2", "nano": "1.0"}, "100.000000001"),
        ({"units": 1.0, "nano": 1.0}, "1.000000001"),
        ({"units": None, "nano": 1}, "0.000000001"),
        ({"units": "1", "nano": None}, "1"),
        ({"units": None, "nano": None}, "0"),
        ({}, "0"),
    ],
)
def test_tbank_money_preserves_protojson_integer_edges_and_defaults(parts, expected) -> None:
    client = TBankInvestClient()
    response = FakeResponse({"money": [{"currency": "RUB", **parts}]})
    with patch("urllib.request.OpenerDirector.open", return_value=response):
        positions = client.get_positions("synthetic-test-credential", "prod", "synthetic-account")
    assert positions.money[0].value == expected


@pytest.mark.parametrize(
    "parts",
    [
        {"units": "9223372036854775808"},
        {"units": "-9223372036854775809"},
        {"nano": 2147483648},
        {"nano": -2147483649},
    ],
)
def test_tbank_money_rejects_parts_outside_signed_wire_types(parts) -> None:
    client = TBankInvestClient()
    response = FakeResponse({"money": [{"currency": "RUB", **parts}]})
    with (
        patch("urllib.request.OpenerDirector.open", return_value=response),
        pytest.raises(TBankUnavailable),
    ):
        client.get_positions("synthetic-test-credential", "prod", "synthetic-account")


def test_tbank_intraday_exchange_candles_validate_ohlc_and_exchange_source() -> None:
    client = TBankInvestClient(purpose="market")
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
                    "candleSource": "CANDLE_SOURCE_EXCHANGE",
                }
            ]
        }
    )

    with patch("urllib.request.OpenerDirector.open", return_value=response) as urlopen:
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


@pytest.mark.parametrize(
    "source_fields",
    [
        {"candleSource": "CANDLE_SOURCE_EXCHANGE"},
        {"candleSourceType": "CANDLE_SOURCE_EXCHANGE"},
        {"candleSource": "CANDLE_SOURCE_EXCHANGE", "candleSourceType": "CANDLE_SOURCE_EXCHANGE"},
    ],
)
def test_tbank_live_candle_defaults_preserve_unfinished_zero_volume(source_fields) -> None:
    # HistoricCandle.candle_source is a response field; the request's source
    # field differs. Proto3 omits implicit false/zero scalars from JSON.
    row = {
        "open": {"units": "100"},
        "high": {"units": "102"},
        "low": {"units": "99"},
        "close": {"units": "101"},
        "time": "2026-10-09T06:30:00Z",
        **source_fields,
    }
    with patch("urllib.request.OpenerDirector.open", return_value=FakeResponse({"candles": [row]})):
        result = TBankInvestClient(purpose="market").get_exchange_candles(
            "synthetic-test-credential",
            "prod",
            "uid-1",
            from_at=datetime(2026, 10, 8, 7, tzinfo=UTC),
            to_at=datetime(2026, 10, 9, 7, tzinfo=UTC),
            interval="CANDLE_INTERVAL_5_MIN",
        )
    assert len(result) == 1
    assert result[0].source == "CANDLE_SOURCE_EXCHANGE"
    assert result[0].close == "101"
    assert result[0].is_complete is False
    assert result[0].volume_lots == 0


@pytest.mark.parametrize("field", ["isComplete", "volume", "candleSource"])
def test_tbank_candle_explicit_null_never_becomes_a_proto_default(field: str) -> None:
    row = {
        "open": {"units": "100"},
        "high": {"units": "102"},
        "low": {"units": "99"},
        "close": {"units": "101"},
        "time": "2026-10-09T06:30:00Z",
        "candleSource": "CANDLE_SOURCE_EXCHANGE",
        field: None,
    }
    read = partial(
        TBankInvestClient(purpose="market").get_exchange_candles,
        "synthetic-test-credential",
        "prod",
        "uid-1",
        from_at=datetime(2026, 10, 8, 7, tzinfo=UTC),
        to_at=datetime(2026, 10, 9, 7, tzinfo=UTC),
        interval="CANDLE_INTERVAL_5_MIN",
    )
    with (
        patch("urllib.request.OpenerDirector.open", return_value=FakeResponse({"candles": [row]})),
        pytest.raises(TBankUnavailable),
    ):
        read()


@pytest.mark.parametrize(
    "method, field", [("GetCandles", "candles"), ("GetLastPrices", "lastPrices")]
)
@pytest.mark.parametrize("explicit_null", [False, True])
def test_tbank_market_empty_repeated_fields_are_distinct_from_malformed_null(
    method: str,
    field: str,
    explicit_null: bool,
) -> None:
    client = TBankInvestClient(purpose="market")
    read = (
        partial(
            client.get_exchange_candles,
            "synthetic-test-credential",
            "prod",
            "uid-1",
            from_at=datetime(2026, 10, 8, tzinfo=UTC),
            to_at=datetime(2026, 10, 9, tzinfo=UTC),
            interval="CANDLE_INTERVAL_5_MIN",
        )
        if method == "GetCandles"
        else partial(client.get_last_prices, "synthetic-test-credential", "prod", ("uid-1",))
    )
    with patch(
        "urllib.request.OpenerDirector.open",
        return_value=FakeResponse(
            {field: None} if explicit_null else {},
        ),
    ):
        if explicit_null or method == "GetLastPrices":
            with pytest.raises(TBankUnavailable):
                read()
        else:
            assert read() == ()


@patch("urllib.request.OpenerDirector.open")
def test_tbank_exchange_candles_reject_too_short_window_before_network(
    urlopen: Mock,
) -> None:
    client = TBankInvestClient(purpose="market")
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
    client = TBankInvestClient(purpose="market")
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

    with patch("urllib.request.OpenerDirector.open", return_value=response) as urlopen:
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


@pytest.mark.parametrize("explicit_null", [False, True])
def test_tbank_trading_status_implicit_false_cannot_enable_missing_permissions(
    explicit_null: bool,
) -> None:
    payload = {
        "instrumentUid": "uid-1",
        "tradingStatus": "SECURITY_TRADING_STATUS_NORMAL_TRADING",
        "apiTradeAvailableFlag": True,
    }
    if explicit_null:
        payload["onlyBestPrice"] = None
    read = partial(
        TBankInvestClient(purpose="market").get_trading_status,
        "synthetic-test-credential",
        "prod",
        "uid-1",
    )
    with patch("urllib.request.OpenerDirector.open", return_value=FakeResponse(payload)):
        if explicit_null:
            with pytest.raises(TBankUnavailable):
                read()
        else:
            result = read()
            assert result.trading_status == "SECURITY_TRADING_STATUS_NORMAL_TRADING"
            assert result.api_trade_available is True
            assert not any(
                (
                    result.limit_order_available,
                    result.market_order_available,
                    result.best_price_order_available,
                    result.only_best_price,
                )
            )


def test_tbank_accrued_interest_preserves_value_and_timestamp() -> None:
    client = TBankInvestClient(purpose="market")
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

    with patch("urllib.request.OpenerDirector.open", return_value=response) as urlopen:
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


@pytest.mark.parametrize("invalid", ["negative_nkd", "zero_nominal", "duplicate_date"])
def test_accrued_interest_never_accepts_invalid_money_or_ambiguous_observations(invalid):
    row = {
        "date": "2026-10-03T00:00:00Z",
        "value": {"units": "17", "nano": 250000000},
        "valuePercent": {"units": "1", "nano": 725000000},
        "nominal": {"units": "1000", "nano": 0},
    }
    if invalid == "negative_nkd":
        row["value"] = {"units": "-1", "nano": 0}
    if invalid == "zero_nominal":
        row["nominal"] = {"units": "0", "nano": 0}
    payload = {"accruedInterests": [row, row] if invalid == "duplicate_date" else [row]}
    client = TBankInvestClient(purpose="market")
    begin, end = datetime(2026, 10, 2, tzinfo=UTC), datetime(2026, 10, 3, tzinfo=UTC)
    with (
        patch.object(TBankInvestClient, "_post", return_value=payload),
        pytest.raises(TBankUnavailable),
    ):
        client.get_accrued_interests("fixture", "prod", "bond-uid", from_at=begin, to_at=end)


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
    client = TBankInvestClient(purpose="market")
    response = FakeResponse(payload)

    with (
        patch("urllib.request.OpenerDirector.open", return_value=response),
        pytest.raises(TBankUnavailable),
    ):
        client.get_instrument_metadata(
            "t.fake-owner-credential-1234567890",
            "prod",
            "bond",
        )


@pytest.mark.parametrize("units", ["NaN", "Infinity"])
def test_non_finite_broker_money_fails_at_provider_boundary(units: str) -> None:
    payload = {"money": [{"currency": "rub", "units": units}]}
    client = TBankInvestClient()
    response = FakeResponse(payload)

    with (
        patch("urllib.request.OpenerDirector.open", return_value=response),
        pytest.raises(TBankUnavailable),
    ):
        client.get_positions(
            "t.fake-owner-credential-1234567890",
            "prod",
            "account-1",
        )


def test_tbank_tls_verification_failure_is_reported_as_unavailable() -> None:
    client = TBankInvestClient()
    error = urllib.error.URLError(ssl.SSLCertVerificationError(1, "certificate verify failed"))

    with (
        patch("urllib.request.OpenerDirector.open", side_effect=error),
        pytest.raises(TBankUnavailable, match="TLS certificate verification failed"),
    ):
        client.get_accounts("t.fake-owner-credential-1234567890", "prod")


@pytest.mark.parametrize("status,expected,message", [
    (401, TBankTokenRejected, "rejected"), (403, TBankTokenRejected, "rejected"),
    (404, TBankNotFound, "object was not found"),
])
def test_tbank_preserves_http_error_authority_without_response_body(
    status, expected, message,
) -> None:
    error = urllib.error.HTTPError(
        "https://invest-public-api.tbank.ru/",
        status,
        "Unauthorized",
        {},
        io.BytesIO(b'{"message":"credential must never be surfaced"}'),
    )
    client = TBankInvestClient()

    with (
        patch("urllib.request.OpenerDirector.open", side_effect=error),
        pytest.raises(expected, match=message) as failure,
    ):
        client.get_accounts("t.fake-owner-credential-1234567890", "prod")
    assert "credential must never be surfaced" not in str(failure.value)


@pytest.mark.parametrize("failure", ["truncated", "invalid_utf8"])
@pytest.mark.parametrize("consumer", ["quote_client", "market"])
def test_tbank_real_response_failure_is_safe_and_never_replays(failure, consumer, caplog) -> None:
    credential = "synthetic-credential-must-not-leak"
    body = b'{"lastPrices":[' if failure == "truncated" else b'{"secret":"\xff"}'
    length = len(body) + (200 if failure == "truncated" else 0)
    client, broker = TBankInvestClient(purpose="market"), Mock()
    broker.status.return_value = "synthetic-account"
    broker.market_last_prices.side_effect = lambda owner, uids: client.get_last_prices_batch(
        credential,
        "prod",
        uids,
    )
    broker.market_instrument_metadata.return_value = TBankInstrumentMetadata(
        "uid-1",
        "Synthetic share",
        "SYN",
        "",
        "share",
        "",
        "RU",
        False,
        currency="RUB",
    )
    service = MarketService(broker=broker, cbr=Mock())
    receiver, sender = socket.socketpair()
    try:
        sender.sendall(f"HTTP/1.1 200 OK\r\nContent-Length: {length}\r\n\r\n".encode() + body)
        sender.shutdown(socket.SHUT_WR)
        with HTTPResponse(receiver) as response:
            response.begin()
            with patch("urllib.request.OpenerDirector.open", return_value=response) as request:
                if consumer == "market":
                    payload = service.batch_quotes(UUID(int=1), ("uid-1",))
                    item = payload["items"][0]
                    assert item["quote_status"] == "unavailable"
                    assert item["last_price"] is None
                    assert item["errors"]["quote"] == "source_unavailable"
                else:
                    operation = (
                        partial(
                            client.get_last_prices_batch,
                            credential,
                            "prod",
                            ("uid-1",),
                        )
                        if consumer == "quote_client"
                        else partial(
                            client.submit_limit_order,
                            credential,
                            "sandbox",
                            "synthetic-account",
                            instrument_uid="uid-1",
                            lots=1,
                            price=Decimal("10"),
                            action="buy",
                            request_id=str(UUID(int=2)),
                        )
                    )
                    with pytest.raises(TBankUnavailable) as failure_result:
                        operation()
                    assert credential not in str(failure_result.value)
                    assert "secret" not in str(failure_result.value)
                request.assert_called_once()
                if consumer == "order_client":
                    assert request.call_args.args[0].full_url.endswith(
                        "SandboxService/PostSandboxOrder",
                    )
            assert response.isclosed()
        assert credential not in caplog.text
        assert "secret" not in caplog.text
    finally:
        service.close()
        receiver.close()
        sender.close()


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
        assert credential == "synthetic-shared-market-token"
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
        assert credential == "synthetic-shared-market-token"
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
        raise AssertionError("private portfolio statistics are forbidden")

    def get_positions(self, credential: str, environment: str, account_id: str):
        assert credential == "t.fake-owner-credential-1234567890"
        assert environment == "prod"
        assert account_id == "account-1"
        return TBankPositions(
            money=(TBankMoney(currency="RUB", value="100"),),
            blocked_money=(),
            limits_loading_in_progress=False,
        )

    def get_withdraw_limits(self, credential: str, environment: str, account_id: str):
        assert credential == "t.fake-owner-credential-1234567890"
        assert environment == "prod"
        assert account_id == "account-1"
        return TBankWithdrawLimits((TBankMoney("RUB", "100"),), (), ())


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

    with pytest.raises(BrokerConnectionError, match="broker_execution_disabled"):
        service.cancel_sandbox_order(
            owner_id,
            request_id="00000000-0000-0000-0000-000000000705",
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
    provider = FakeTBank()
    service = BrokerService(
        database,
        credential_key=key,
        tbank=provider,
        market_credential="synthetic-shared-market-token",
        market_tbank=provider,
    )

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

    assert portfolio.portfolio.total.value == "100"
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
        database,
        credential_key=Fernet.generate_key().decode("ascii"),
        tbank=broker,
    )
    service.connect(
        user_id=user_id,
        credential="t.fake-owner-credential-1234567890",
        environment="prod",
        account_id="account-1",
        terms_version="2026-10-01-v2",
    )
    original = broker.get_positions

    def disconnected(*args):
        value = original(*args)
        database.delete_tbank_connection(user_id)
        return value

    read = getattr(service, operation)
    with (
        patch.object(broker, "get_positions", side_effect=disconnected),
        pytest.raises(BrokerConnectionError, match="connection changed"),
    ):
        read(user_id)


@pytest.mark.parametrize(
    "operation,provider_method",
    [
        ("revalidate_account", "get_accounts"),
    ],
)
def test_account_evidence_is_discarded_after_credentials_change(operation, provider_method):
    database, provider, user_id = FakeDatabase(), FakeTBank(), UUID(int=1)
    service = BrokerService(database, credential_key=Fernet.generate_key().decode(), tbank=provider)
    service.connect(
        user_id=user_id,
        credential="t.fake-owner-credential-1234567890",
        environment="prod",
        account_id="account-1",
        terms_version="2026-10-01-v2",
    )
    replacement_credential = Fernet(service.credential_key.encode()).encrypt(
        b"synthetic-replacement-credential"
    )

    def replace_credential(*args, **kwargs):
        # Equal clock ticks must not hide an actual credential replacement.
        database.record = replace(database.record, encrypted_credential=replacement_credential)
        return provider.accounts if operation == "revalidate_account" else Mock()

    arguments = (
        {"from_at": datetime(2026, 1, 1, tzinfo=UTC), "to_at": datetime.now(UTC)}
        if operation == "history_page"
        else {}
    )
    read_source = getattr(service, operation)
    with (
        patch.object(provider, provider_method, side_effect=replace_credential, create=True),
        pytest.raises(BrokerConnectionError, match="connection changed"),
    ):
        read_source(user_id, **arguments)


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
        ("ACCOUNT_STATUS_OPEN", "ACCOUNT_ACCESS_LEVEL_FULL_ACCESS"),
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


@pytest.mark.parametrize("identity", ["", "   "])
def test_broker_rejects_missing_account_identity_before_connect(identity: str) -> None:
    database = FakeDatabase()
    fake = FakeTBank()
    fake.accounts = [replace(fake.accounts[0], id=identity)]
    service = BrokerService(
        database,
        credential_key=Fernet.generate_key().decode("ascii"),
        tbank=fake,
    )
    with pytest.raises(BrokerAccountNotAccessible):
        service.preview_accounts(
            credential="t.fake-owner-credential-1234567890", environment="prod"
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


def test_tbank_asset_fundamentals_are_batched_and_finite() -> None:
    client = TBankInvestClient(purpose="market")
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

    with patch("urllib.request.OpenerDirector.open", return_value=response) as urlopen:
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
    client = TBankInvestClient(purpose="market")
    response = FakeResponse(
        {
            "events": [
                {
                    "instrumentId": "bond-uid",
                    "eventNumber": 8,
                    "eventDate": "2026-09-20T00:00:00Z",
                    "eventType": "EVENT_TYPE_CPN",
                    "defaultDate": "2026-09-30T00:00:00Z",
                    "payDate": "2026-09-25T00:00:00Z",
                    "payOneBond": {"currency": "rub", "units": "50", "nano": 0},
                    "execution": "D",
                    "operationType": "Фиксированный",
                    "fixDate": "2026-09-19T00:00:00Z",
                    "rateDate": "2026-06-25T00:00:00Z",
                    "value": {"units": "20", "nano": 500000000},
                    "note": "",
                }
            ]
        }
    )

    with patch("urllib.request.OpenerDirector.open", return_value=response) as urlopen:
        events = client.get_bond_events(
            "t.fake-owner-credential-1234567890",
            "prod",
            "bond-uid",
            from_at=datetime(2026, 9, 1, tzinfo=UTC),
            to_at=datetime(2026, 10, 2, tzinfo=UTC),
        )

    assert events[0].default_date == datetime(2026, 9, 30, tzinfo=UTC)
    assert events[0].pay_one_bond == TBankMoney("RUB", "50")
    assert events[0].fix_date == datetime(2026, 9, 19, tzinfo=UTC)
    assert events[0].rate_date == datetime(2026, 6, 25, tzinfo=UTC)
    assert events[0].value == "20.5"
    request = urlopen.call_args.args[0]
    assert request.full_url.endswith("InstrumentsService/GetBondEvents")
    assert json.loads(request.data.decode()) == {
        "instrumentId": "bond-uid",
        "from": "2026-09-01T00:00:00Z",
        "to": "2026-10-02T00:00:00Z",
        "type": "EVENT_TYPE_UNSPECIFIED",
    }


def test_tbank_asset_reports_reject_mismatched_instrument_subject() -> None:
    client = TBankInvestClient(purpose="market")
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
        patch("urllib.request.OpenerDirector.open", return_value=response),
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
    client = TBankInvestClient(purpose="market")
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
        patch("urllib.request.OpenerDirector.open", return_value=response),
        pytest.raises(TBankUnavailable, match="non-finite"),
    ):
        client.get_asset_fundamentals(
            "t.fake-owner-credential-1234567890",
            "prod",
            ("asset-1",),
        )


def _strategy_broker():
    database = FakeDatabase()
    user_id = UUID(int=1)
    broker = FakeTBank()
    service = BrokerService(
        database,
        credential_key=Fernet.generate_key().decode("ascii"),
        tbank=broker,
        market_credential="synthetic-shared-market-token",
        market_tbank=broker,
    )
    service.connect(
        user_id=user_id,
        credential="t.fake-owner-credential-1234567890",
        environment="prod",
        account_id="account-1",
        terms_version="2026-10-01-v2",
    )

    @contextmanager
    def slot(owner):
        assert owner == user_id
        yield True

    database.strategy_assessment_slot = slot
    return service, database, broker, user_id


def test_strategy_rating_reads_are_bounded_and_connection_checked(monkeypatch):
    from test_strategy_assessment import position, snapshot

    from omnicio.broker import BrokerObservationBundle

    service, _, tbank, owner = _strategy_broker()
    analysis = snapshot(
        *(position(uid=f"bond-{i:02d}", value="1000") for i in range(20)),
        nav="110000",
        cash="90000",
    )
    bundle = Mock(spec=BrokerObservationBundle)
    bundle.analysis = analysis
    monkeypatch.setattr(service, "observation_bundle", lambda user: bundle)
    calls = []

    def read(credential, environment, uid):
        calls.append(uid)
        assert credential == "synthetic-shared-market-token"
        assert environment == "prod"
        return ()

    monkeypatch.setattr(tbank, "get_bond_ratings", read, raising=False)
    monkeypatch.setattr(service, "_paced_evidence_read", lambda fn, *args: fn(*args))
    observed, ratings = service.strategy_observation(owner)
    assert observed is bundle
    assert len(calls) == 8
    assert list(ratings) == calls == sorted(calls)
    assert all(values == () for values in ratings.values())


@pytest.mark.parametrize("mutation", ["credential", "account", "delete"])
def test_strategy_rating_read_discards_changed_connection(monkeypatch, mutation):
    from test_strategy_assessment import position, snapshot

    from omnicio.broker import BrokerObservationBundle

    service, database, tbank, owner = _strategy_broker()
    bundle = Mock(spec=BrokerObservationBundle)
    bundle.analysis = snapshot(position())
    monkeypatch.setattr(service, "observation_bundle", lambda user: bundle)

    def read(*args):
        if mutation == "delete":
            database.delete_tbank_connection(owner)
        elif mutation == "account":
            database.record = replace(database.record, account_id="new-account")
        else:
            database.record = replace(database.record, encrypted_credential=b"new-encrypted")
        return ()

    monkeypatch.setattr(tbank, "get_bond_ratings", read, raising=False)
    monkeypatch.setattr(service, "_paced_evidence_read", lambda fn, *args: fn(*args))
    with pytest.raises(BrokerConnectionError):
        service.strategy_observation(owner)


def test_strategy_read_uses_shared_admission_and_releases_on_error(monkeypatch):
    from omnicio.broker import BrokerAssessmentBusy

    service, database, _, owner = _strategy_broker()
    state = {"admitted": False, "released": False}

    @contextmanager
    def slot(user):
        assert user == owner
        try:
            yield state["admitted"]
        finally:
            state["released"] = True

    database.strategy_assessment_slot = slot
    read = Mock(side_effect=TBankUnavailable("synthetic failure"))
    monkeypatch.setattr(service, "_strategy_observation", read)
    with pytest.raises(BrokerAssessmentBusy):
        service.strategy_observation(owner)
    read.assert_not_called()
    assert state["released"] is True
    state.update(admitted=True, released=False)
    with pytest.raises(TBankUnavailable):
        service.strategy_observation(owner)
    assert state["released"] is True
    read.assert_called_once_with(owner)


@pytest.mark.parametrize(
    "purpose,service,method",
    [
        ("portfolio", "UsersService", "GetInfo"),
        ("portfolio", "OperationsService", "GetPortfolio"),
        ("portfolio", "OperationsService", "GetOperationsByCursor"),
        ("portfolio", "InstrumentsService", "News"),
        ("portfolio", "MarketDataService", "GetLastPrices"),
        ("market", "UsersService", "GetAccounts"),
        ("market", "OperationsService", "GetPositions"),
        ("market", "OrdersService", "PostOrder"),
        ("market", "UsersService", "PayIn"),
        ("portfolio", "UsersService", "FutureUnknownMethod"),
    ],
)
def test_credential_scopes_deny_disallowed_methods_before_any_network(purpose, service, method):
    client = TBankInvestClient(purpose=purpose)
    with (
        patch("urllib.request.OpenerDirector.open") as network,
        pytest.raises(TBankTokenRejected, match="permitted data scope"),
    ):
        client._post(
            token="synthetic-private-bearer", environment="prod",
            service=service, method=method, body={},
        )
    network.assert_not_called()


@pytest.mark.parametrize("environment", ["prod", "sandbox"])
def test_trade_and_history_adapters_have_no_executable_provider_requests(environment):
    client = TBankInvestClient()
    now = datetime.now(UTC)
    operations = (
        lambda: client.submit_limit_order(
            "synthetic-bearer",
            environment,
            "account-1",
            instrument_uid="uid",
            lots=1,
            price=Decimal(10),
            action="buy",
            request_id=str(UUID(int=1)),
        ),
        lambda: client.get_portfolio("synthetic-bearer", environment, "account-1"),
        lambda: client.get_user_info("synthetic-bearer", environment),
        lambda: client.get_operations_by_cursor(
            "synthetic-bearer", environment, "account-1", from_at=now, to_at=now
        ),
    )
    with patch.object(TBankInvestClient, "_post") as network:
        for operation in operations:
            with pytest.raises(TBankTokenRejected):
                operation()
    network.assert_not_called()


@pytest.mark.parametrize(
    "access",
    [
        "ACCOUNT_ACCESS_LEVEL_FULL_ACCESS",
        "ACCOUNT_ACCESS_LEVEL_NO_ACCESS",
        "ACCOUNT_ACCESS_LEVEL_UNSPECIFIED",
        "",
        None,
        1,
        99,
        True,
    ],
)
def test_account_verification_rejects_every_non_readonly_scope(access):
    payload = {
        "accounts": [{"id": "account-1", "status": "ACCOUNT_STATUS_OPEN", "accessLevel": access}]
    }
    client = TBankInvestClient()
    with (
        patch("urllib.request.OpenerDirector.open", return_value=FakeResponse(payload)),
        pytest.raises(TBankTokenRejected),
    ):
        client.get_accounts("synthetic-private-credential", "prod")


def test_account_validation_checks_nonselected_accounts_again_on_every_refresh():
    database, provider, owner = FakeDatabase(), FakeTBank(), UUID(int=1)
    broker = BrokerService(database, credential_key=Fernet.generate_key().decode(), tbank=provider)
    broker.connect(
        user_id=owner,
        credential="t.fake-owner-credential-1234567890",
        environment="prod",
        account_id="account-1",
        terms_version="2026-10-01-v2",
    )
    provider.accounts.append(
        replace(
            provider.accounts[0],
            id="another-account",
            access_level="ACCOUNT_ACCESS_LEVEL_FULL_ACCESS",
        )
    )
    with (
        patch.object(provider, "get_positions") as positions,
        pytest.raises(BrokerAccountNotAccessible),
    ):
        broker.portfolio(owner)
    positions.assert_not_called()
    provider.accounts = []
    with pytest.raises(BrokerAccountNotAccessible):
        broker.revalidate_account(owner)


def test_current_positions_have_quantities_cash_and_no_purchase_statistics():
    payload = {
        "accountId": "account-1",
        "money": [{"currency": "RUB", "units": "100"}],
        "securities": [
            {
                "instrumentUid": "share-1",
                "figi": "FIGI1",
                "ticker": "SHARE",
                "instrumentType": "share",
                "balance": "5",
                "blocked": "2",
                "averagePositionPrice": {"currency": "RUB", "units": "1000"},
            }
        ],
        "futures": [{"instrumentUid": "future-1", "balance": "3"}],
        "options": [{"instrumentUid": "option-1", "balance": "1"}],
    }
    with patch("urllib.request.OpenerDirector.open", return_value=FakeResponse(payload)) as network:
        positions = TBankInvestClient().get_positions(
            "synthetic-private-token", "prod", "account-1"
        )
    assert [item.quantity for item in positions.holdings] == ["7", "3", "1"]
    assert positions.holdings[0].blocked_lots == "2"
    assert all(
        item.current_price is None
        and item.average_price is None
        and item.expected_yield_amount is None
        for item in positions.holdings
    )
    assert positions.money == (TBankMoney("RUB", "100"),)
    assert network.call_args.args[0].full_url.endswith("OperationsService/GetPositions")


@pytest.mark.parametrize(
    "payload",
    [
        {"accountId": "other-account"},
        {"securities": [{"instrumentUid": "uid"}, {"instrumentUid": "uid"}]},
        {"securities": [{"instrumentUid": "uid", "blocked": "-1"}]},
        {"securities": [{"instrumentUid": "uid", "balance": "9223372036854775808"}]},
        {"securities": [{"balance": "1"}]},
        {"limitsLoadingInProgress": "false"},
    ],
)
def test_current_positions_reject_ambiguous_identity_or_malformed_values(payload):
    client = TBankInvestClient()
    with (
        patch("urllib.request.OpenerDirector.open", return_value=FakeResponse(payload)),
        pytest.raises(TBankUnavailable),
    ):
        client.get_positions("synthetic-private-token", "prod", "account-1")


def test_public_market_reads_never_look_up_user_connections_or_fall_back_to_their_token():
    database = Mock()
    database.tbank_connection.side_effect = AssertionError("market read used private connection")
    private, market = Mock(), Mock()
    market.get_last_prices.return_value = (TBankLastPrice("uid", "10", datetime.now(UTC)),)
    broker = BrokerService(
        database,
        credential_key=Fernet.generate_key().decode(),
        tbank=private,
        market_tbank=market,
        market_credential="synthetic-shared-market-token",
    )
    assert broker.market_last_price(UUID(int=1), "uid").price == "10"
    assert broker.market_last_price(UUID(int=2), "uid").price == "10"
    assert all(
        call.args[0] == "synthetic-shared-market-token"
        for call in market.get_last_prices.call_args_list
    )
    private.assert_not_called()
    no_source = BrokerService(
        database, credential_key=Fernet.generate_key().decode(), tbank=private
    )
    with pytest.raises(TBankUnavailable, match="shared_market_source_unavailable"):
        no_source.market_last_price(UUID(int=1), "uid")
    database.tbank_connection.assert_not_called()


def test_unknown_market_price_preserves_real_holding_without_zero_nav_or_return():
    from omnicio.portfolio import analyze_portfolio, value_current_positions

    holding = TBankPortfolioPosition(
        "SHARE", "figi", "uid", "share", "7", None, None, None, None, False
    )
    positions = TBankPositions((TBankMoney("RUB", "100"),), (), False, holdings=(holding,))
    portfolio = value_current_positions(positions, (), ())
    analysis = analyze_portfolio(portfolio, positions, ())
    assert portfolio.positions[0].quantity == "7"
    assert portfolio.total is None
    assert analysis.nav_rub is None
    assert analysis.rub_cash_unblocked is None
    assert analysis.rub_cash_blocked is None
    assert analysis.rub_cash_total == "100"
    assert portfolio.expected_yield_percent is None
    assert portfolio.daily_yield is None
    assert portfolio.positions[0].quantity_lots is None


def test_shared_market_value_converts_bond_quote_percent_and_never_recovers_purchase_prices():
    from omnicio.portfolio import value_current_positions

    holding = TBankPortfolioPosition(
        "BOND", "figi", "bond", "bond", "2", None, TBankMoney("RUB", "10"), "55", None, False
    )
    positions = TBankPositions((TBankMoney("RUB", "100"),), (), False, holdings=(holding,))
    metadata = TBankInstrumentMetadata(
        "bond",
        "Bond",
        "BOND",
        "",
        "bond",
        "finance",
        "RU",
        False,
        currency="RUB",
        nominal=TBankMoney("RUB", "1000"),
        accrued_interest=TBankMoney("RUB", "20"),
        lot=1,
    )
    portfolio = value_current_positions(
        positions, (metadata,), (TBankLastPrice("bond", "95", datetime.now(UTC)),)
    )
    assert portfolio.total == TBankMoney("RUB", "2040")
    assert portfolio.positions[0].current_price == TBankMoney("RUB", "950")
    assert portfolio.positions[0].average_price is None
    assert portfolio.positions[0].expected_yield_amount is None


def test_all_quotes_is_explicit_and_an_empty_requested_batch_performs_no_io():
    client = TBankInvestClient(purpose="market")
    payload = {
        "lastPrices": [
            {
                "instrumentUid": "not-individually-requested",
                "price": {"units": "5"},
                "time": datetime.now(UTC).isoformat(),
            }
        ]
    }
    with patch("urllib.request.OpenerDirector.open", return_value=FakeResponse(payload)) as network:
        assert client.get_last_prices_batch("synthetic-shared-token", "prod", ()).prices == ()
        network.assert_not_called()
        result = client.get_all_last_prices("synthetic-shared-token", "prod")
    assert result.prices[0].instrument_uid == "not-individually-requested"
    assert json.loads(network.call_args.args[0].data)["instrumentId"] == []
