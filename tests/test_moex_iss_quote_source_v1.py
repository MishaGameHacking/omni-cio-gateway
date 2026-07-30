from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal
import json

import httpx
import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.market import MarketQuoteV1, MarketSourceV1, SourceAuthority
from omni_cio.contracts.v1.moex import (
    MoexIssQuoteErrorCode,
    MoexIssQuoteStatus,
    MoexIssTqbrQuoteSnapshotV1,
)
from omni_cio.market.moex_iss_quote_v1 import (
    MOEX_ISS_TQBR_QUOTE_ENDPOINT_TEMPLATE,
    MoexIssQuoteSourceError,
    build_moex_iss_tqbr_quote_url,
    fetch_moex_iss_tqbr_quote,
    parse_moex_iss_tqbr_quote_json,
)


NOW = datetime(2026, 7, 30, 12, 5, tzinfo=timezone.utc)
SECID = "SBER"
SECURITIES_COLUMNS = [
    "SECID",
    "BOARDID",
    "SHORTNAME",
    "LOTSIZE",
    "DECIMALS",
    "CURRENCYID",
]
MARKETDATA_COLUMNS = [
    "SECID",
    "BOARDID",
    "LAST",
    "BID",
    "OFFER",
    "SYSTIME",
]


def _payload(
    *,
    secid: str = SECID,
    board_id: str = "TQBR",
    short_name: object = "Сбербанк",
    lot_size: object = 10,
    decimals: object = 2,
    currency: object = "SUR",
    last: object = 310.25,
    bid: object = 310.20,
    offer: object = 310.30,
    system_time: object = "2026-07-30 15:00:00",
    securities_columns: list[str] | None = None,
    marketdata_columns: list[str] | None = None,
    securities_rows: list[list[object]] | None = None,
    marketdata_rows: list[list[object]] | None = None,
) -> bytes:
    sec_columns = securities_columns or SECURITIES_COLUMNS
    market_columns = marketdata_columns or MARKETDATA_COLUMNS
    sec_data = (
        securities_rows
        if securities_rows is not None
        else [[secid, board_id, short_name, lot_size, decimals, currency]]
    )
    market_data = (
        marketdata_rows
        if marketdata_rows is not None
        else [[secid, board_id, last, bid, offer, system_time]]
    )
    return json.dumps(
        {
            "securities": {
                "columns": sec_columns,
                "data": sec_data,
            },
            "marketdata": {
                "columns": market_columns,
                "data": market_data,
            },
        },
        ensure_ascii=False,
    ).encode()


def _official_source() -> MarketSourceV1:
    return MarketSourceV1(
        provider="Moscow Exchange ISS",
        authority=SourceAuthority.OFFICIAL,
        retrieved_at=NOW,
        source_id="ISS.stock.shares.TQBR.marketdata",
    )


def _quote() -> MarketQuoteV1:
    source = _official_source()
    return MarketQuoteV1(
        instrument_key="MOEX:TQBR:SBER",
        currency="RUB",
        as_of=datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc),
        source=source,
        last_price=Decimal("310.25"),
        best_bid=Decimal("310.20"),
        best_ask=Decimal("310.30"),
    )


def test_available_snapshot_contract_requires_consistent_official_quote() -> None:
    source = _official_source()
    quote = _quote()
    snapshot = MoexIssTqbrQuoteSnapshotV1(
        secid="sber",
        retrieved_at=NOW,
        status=MoexIssQuoteStatus.AVAILABLE,
        source=source,
        quote=quote,
        short_name="Сбербанк",
        lot_size=10,
        decimals=2,
    )

    assert snapshot.secid == "SBER"
    assert snapshot.public_unauthenticated_feed is True
    assert snapshot.delayed_data_possible is True
    assert snapshot.realtime_guaranteed is False
    assert snapshot.informational_use_only is True
    assert snapshot.raw_json_stored is False
    assert snapshot.trading_methods is False

    with pytest.raises(ValidationError):
        MoexIssTqbrQuoteSnapshotV1(
            secid="SBER",
            retrieved_at=NOW,
            status=MoexIssQuoteStatus.AVAILABLE,
            source=source,
            quote=quote.model_copy(
                update={"instrument_key": "MOEX:TQBR:GAZP"}
            ),
            short_name="Сбербанк",
            lot_size=10,
            decimals=2,
        )


def test_unavailable_snapshot_contract_requires_safe_error() -> None:
    snapshot = MoexIssTqbrQuoteSnapshotV1(
        secid=SECID,
        retrieved_at=NOW,
        status=MoexIssQuoteStatus.UNAVAILABLE,
        error_code=MoexIssQuoteErrorCode.NETWORK_ERROR,
    )

    assert snapshot.source is None
    assert snapshot.quote is None

    with pytest.raises(ValidationError):
        MoexIssTqbrQuoteSnapshotV1(
            secid=SECID,
            retrieved_at=NOW,
            status=MoexIssQuoteStatus.UNAVAILABLE,
        )


def test_build_url_is_fixed_https_and_rejects_path_injection() -> None:
    assert build_moex_iss_tqbr_quote_url(" sber ") == (
        MOEX_ISS_TQBR_QUOTE_ENDPOINT_TEMPLATE.format(secid="SBER")
    )
    for invalid in ("SBER/../../x", "SBER?x=1", "", "СБЕР", "A" * 37):
        with pytest.raises(MoexIssQuoteSourceError, match="SECID_INVALID"):
            build_moex_iss_tqbr_quote_url(invalid)


def test_parse_official_json_normalizes_decimal_currency_and_moscow_time() -> None:
    snapshot = parse_moex_iss_tqbr_quote_json(
        _payload(),
        secid="sber",
        retrieved_at=NOW,
    )

    assert snapshot.status is MoexIssQuoteStatus.AVAILABLE
    assert snapshot.source is not None
    assert snapshot.source.authority is SourceAuthority.OFFICIAL
    assert snapshot.quote is not None
    assert snapshot.quote.currency == "RUB"
    assert snapshot.quote.last_price == Decimal("310.25")
    assert snapshot.quote.best_bid == Decimal("310.2")
    assert snapshot.quote.best_ask == Decimal("310.3")
    assert snapshot.quote.as_of == datetime(
        2026,
        7,
        30,
        12,
        0,
        tzinfo=timezone.utc,
    )
    assert snapshot.lot_size == 10
    assert snapshot.decimals == 2


def test_parse_accepts_partial_quote_but_requires_at_least_one_price() -> None:
    last_only = parse_moex_iss_tqbr_quote_json(
        _payload(bid=None, offer=None),
        secid=SECID,
        retrieved_at=NOW,
    )
    assert last_only.quote is not None
    assert last_only.quote.last_price == Decimal("310.25")

    with pytest.raises(
        MoexIssQuoteSourceError,
        match=MoexIssQuoteErrorCode.EMPTY.value,
    ):
        parse_moex_iss_tqbr_quote_json(
            _payload(last=None, bid=None, offer=None),
            secid=SECID,
            retrieved_at=NOW,
        )


@pytest.mark.parametrize(
    ("payload", "error_code"),
    [
        (
            b'{"securities":{},"securities":{},"marketdata":{}}',
            MoexIssQuoteErrorCode.DUPLICATE_CONFLICT,
        ),
        (
            _payload(securities_columns=["SECID"]),
            MoexIssQuoteErrorCode.SCHEMA_INVALID,
        ),
        (
            _payload(securities_rows=[]),
            MoexIssQuoteErrorCode.EMPTY,
        ),
        (
            _payload(
                securities_rows=[
                    ["SBER", "TQBR", "Сбербанк", 10, 2, "SUR"],
                    ["SBER", "TQBR", "Сбербанк", 10, 2, "SUR"],
                ]
            ),
            MoexIssQuoteErrorCode.DUPLICATE_CONFLICT,
        ),
        (
            _payload(secid="GAZP"),
            MoexIssQuoteErrorCode.IDENTITY_MISMATCH,
        ),
        (
            _payload(currency="USD"),
            MoexIssQuoteErrorCode.CURRENCY_INVALID,
        ),
        (
            _payload(bid=311, offer=310),
            MoexIssQuoteErrorCode.PRICE_INVALID,
        ),
        (
            _payload(last="NaN"),
            MoexIssQuoteErrorCode.PRICE_INVALID,
        ),
        (
            _payload(system_time="not-a-timestamp"),
            MoexIssQuoteErrorCode.TIMESTAMP_INVALID,
        ),
        (
            _payload(system_time="2026-07-30 15:11:00"),
            MoexIssQuoteErrorCode.TIMESTAMP_INVALID,
        ),
        (
            b'{"securities":NaN,"marketdata":{}}',
            MoexIssQuoteErrorCode.JSON_INVALID,
        ),
    ],
)
def test_parse_fails_closed_for_invalid_payloads(
    payload: bytes,
    error_code: MoexIssQuoteErrorCode,
) -> None:
    with pytest.raises(MoexIssQuoteSourceError, match=error_code.value):
        parse_moex_iss_tqbr_quote_json(
            payload,
            secid=SECID,
            retrieved_at=NOW,
        )


def test_fetch_uses_fixed_get_query_and_no_credentials() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.scheme == "https"
        assert request.url.host == "iss.moex.com"
        assert request.url.path.endswith("/boards/TQBR/securities/SBER.json")
        assert request.url.params["iss.meta"] == "off"
        assert request.url.params["iss.only"] == "securities,marketdata"
        assert request.url.params["securities.columns"] == ",".join(
            SECURITIES_COLUMNS
        )
        assert request.url.params["marketdata.columns"] == ",".join(
            MARKETDATA_COLUMNS
        )
        assert "authorization" not in request.headers
        assert "cookie" not in request.headers
        return httpx.Response(
            200,
            request=request,
            headers={"content-type": "application/json; charset=utf-8"},
            content=_payload(),
        )

    snapshot = fetch_moex_iss_tqbr_quote(
        secid="sber",
        retrieved_at=NOW,
        transport=httpx.MockTransport(handler),
    )

    assert snapshot.status is MoexIssQuoteStatus.AVAILABLE
    assert snapshot.quote is not None


def test_fetch_network_http_content_type_size_and_redirect_fail_closed() -> None:
    def network_failure(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("private failure", request=request)

    cases: tuple[
        tuple[
            Callable[[httpx.Request], httpx.Response],
            MoexIssQuoteErrorCode,
            int,
        ],
        ...,
    ] = (
        (network_failure, MoexIssQuoteErrorCode.NETWORK_ERROR, 1_000_000),
        (
            lambda request: httpx.Response(503, request=request),
            MoexIssQuoteErrorCode.HTTP_ERROR,
            1_000_000,
        ),
        (
            lambda request: httpx.Response(
                200,
                request=request,
                headers={"content-type": "text/html"},
                content=b"<html>not json</html>",
            ),
            MoexIssQuoteErrorCode.CONTENT_TYPE_INVALID,
            1_000_000,
        ),
        (
            lambda request: httpx.Response(
                200,
                request=request,
                headers={"content-type": "application/json"},
                content=b"x" * 2_000,
            ),
            MoexIssQuoteErrorCode.RESPONSE_TOO_LARGE,
            1_024,
        ),
        (
            lambda request: httpx.Response(
                302,
                request=request,
                headers={"location": "https://example.invalid"},
            ),
            MoexIssQuoteErrorCode.HTTP_ERROR,
            1_000_000,
        ),
    )

    for handler, expected, limit in cases:
        snapshot = fetch_moex_iss_tqbr_quote(
            secid=SECID,
            retrieved_at=NOW,
            transport=httpx.MockTransport(handler),
            max_response_bytes=limit,
        )
        assert snapshot.status is MoexIssQuoteStatus.UNAVAILABLE
        assert snapshot.error_code is expected
        assert snapshot.quote is None
        assert snapshot.raw_json_stored is False


def test_fetch_invalid_json_is_redacted_and_guards_precede_network() -> None:
    def invalid_json(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            headers={"content-type": "application/json"},
            content=b'{"upstream_secret":"do not copy"',
        )

    snapshot = fetch_moex_iss_tqbr_quote(
        secid=SECID,
        retrieved_at=NOW,
        transport=httpx.MockTransport(invalid_json),
    )
    assert snapshot.error_code is MoexIssQuoteErrorCode.JSON_INVALID
    assert "upstream_secret" not in " ".join(snapshot.warnings)

    called = False

    def must_not_call(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, request=request)

    with pytest.raises(MoexIssQuoteSourceError):
        fetch_moex_iss_tqbr_quote(
            secid="../SBER",
            retrieved_at=NOW,
            transport=httpx.MockTransport(must_not_call),
        )
    assert called is False


def test_serialized_snapshot_excludes_raw_and_sensitive_payload() -> None:
    snapshot = parse_moex_iss_tqbr_quote_json(
        _payload(),
        secid=SECID,
        retrieved_at=NOW,
    )
    serialized = json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False)

    assert "raw_payload" not in serialized
    assert "upstream_body" not in serialized
    assert "authorization" not in serialized.lower()
    assert "cookie" not in serialized.lower()
    assert "account_number" not in serialized.lower()
    assert snapshot.raw_json_stored is False
    assert snapshot.credentials_present is False
    assert snapshot.broker_write_called is False
    assert snapshot.order_created is False


def test_source_module_has_no_route_or_broker_write_surface() -> None:
    import omni_cio.market.moex_iss_quote_v1 as module

    assert not hasattr(module, "app")
    assert not hasattr(module, "router")
    assert not hasattr(module, "create_order")
    assert not hasattr(module, "post_order")
    assert not hasattr(module, "cancel_order")
