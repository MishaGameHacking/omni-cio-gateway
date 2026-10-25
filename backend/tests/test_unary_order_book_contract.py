"""Official unary market-data shape; no streaming consistency is fabricated.

Contract: RussianInvestments/investAPI, src/docs/contracts/marketdata.proto,
reviewed blob e1afb1e98991e640d3705eaeabbe1c362e62bf6c.
GetOrderBookResponse has orderbook_ts; only streamed OrderBook has is_consistent.
All payloads below are explicitly synthetic and no external API is called.
"""
from __future__ import annotations

from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import os
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

os.environ.setdefault("TELEGRAM_CLIENT_ID", "123456")
os.environ.setdefault("TELEGRAM_CLIENT_SECRET", "test-only")
os.environ.setdefault("BACKEND_PUBLIC_URL", "https://example.invalid")
os.environ.setdefault("FERNET_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")

from backend import volume_market as market, volume_purchases as purchases


def unary_book():
    return {
        "instrumentUid": "fixture-security", "depth": 1,
        "orderbookTs": datetime.now(timezone.utc).isoformat(),
        "bids": [{"price": {"units": "99", "nano": 0}, "quantity": "2"}],
        "asks": [{"price": {"units": "100", "nano": 0}, "quantity": "2"}],
    }


def install_book(monkeypatch, book):
    monkeypatch.setattr(market.details, "BrokerReader", lambda user: nullcontext(None))
    def read(reader, method, payload):
        assert method == "order_book"
        assert payload == {"instrumentId": "fixture-security", "depth": 1}
        return deepcopy(book)
    monkeypatch.setattr(market, "broker_read", read)


def read_section():
    return market.liquidity_section(
        {}, "fixture-security", {"instrumentType": "share", "currency": "RUB"})


def test_order_book_adapter_calls_unary_rpc_without_inventing_stream_fields(monkeypatch):
    book, calls = unary_book(), []
    reader = SimpleNamespace(client=object(), token="synthetic-token")
    payload = {"instrumentId": "fixture-security", "depth": 1}
    def post(client, url, token, body):
        assert client is reader.client
        assert token == reader.token
        calls.append((url, body))
        return book
    monkeypatch.setattr(market.details.portfolio, "_post_tinvest", post)
    result = market.broker_read(reader, "order_book", payload)
    assert calls == [(market.details.BASE + "MarketDataService/GetOrderBook", payload)]
    assert result is book
    assert "isConsistent" not in result


def test_fresh_unary_top_of_book_is_available_without_claiming_stream_consistency(monkeypatch):
    book = unary_book()
    install_book(monkeypatch, book)
    result = read_section()
    assert "isConsistent" not in book
    assert result["state"] == "available"
    assert result["reason"] is None
    assert result["data"]["depth_consistent"] is None
    assert result["data"]["spread"] == "1"
    assert result["data"]["basis"] == "observed_top_of_book_not_guarantee_of_liquidation_or_execution"
    assert result["sources"][0]["method"] == "GetOrderBook"


@pytest.mark.parametrize("case, expected_reason", [
    ("stale", "order_book_stale_or_undated"),
    ("future", "order_book_stale_or_undated"),
    ("undated", "order_book_stale_or_undated"),
    ("false_consistency", "order_book_empty_or_not_consistent"),
    ("invalid_consistency", "order_book_empty_or_not_consistent"),
    ("empty_bids", "order_book_empty_or_not_consistent"),
    ("empty_asks", "order_book_empty_or_not_consistent"),
])
def test_unary_dossier_does_not_present_incomplete_or_adverse_evidence_as_available(
        monkeypatch, case, expected_reason):
    book = unary_book()
    if case in {"stale", "future"}:
        offset = -61 if case == "stale" else 60
        book["orderbookTs"] = (datetime.now(timezone.utc) + timedelta(seconds=offset)).isoformat()
    elif case == "undated":
        book.pop("orderbookTs")
    elif case == "false_consistency":
        book["isConsistent"] = False
    elif case == "invalid_consistency":
        book["isConsistent"] = "true"
    elif case == "empty_bids":
        book["bids"] = []
    elif case == "empty_asks":
        book["asks"] = []
    install_book(monkeypatch, book)
    result = read_section()
    assert result["state"] == "partial"
    assert result["reason"] == expected_reason
    assert result["data"]["depth_consistent"] is (False if case == "false_consistency" else None)


@pytest.mark.parametrize("case, expected_reason", [
    ("wrong_identity", "order_book_identity_mismatch"),
    ("missing_identity", "order_book_identity_mismatch"),
    ("malformed_side", "order_book_value_invalid"),
    ("malformed_level", "order_book_value_invalid"),
    ("zero_price", "order_book_value_invalid"),
    ("zero_quantity", "order_book_value_invalid"),
    ("fractional_quantity", "order_book_value_invalid"),
    ("crossed", "order_book_crossed_observation"),
])
def test_unary_dossier_identity_numbers_and_crossed_quotes_fail_closed(monkeypatch, case, expected_reason):
    book = unary_book()
    if case == "wrong_identity":
        book["instrumentUid"] = "another-synthetic-security"
    elif case == "missing_identity":
        book.pop("instrumentUid")
    elif case == "malformed_side":
        book["asks"] = {}
    elif case == "malformed_level":
        book["asks"] = [None]
    elif case == "zero_price":
        book["asks"][0]["price"]["units"] = "0"
    elif case == "zero_quantity":
        book["asks"][0]["quantity"] = "0"
    elif case == "fractional_quantity":
        book["asks"][0]["quantity"] = "0.5"
    elif case == "crossed":
        book["bids"][0]["price"]["units"] = "101"
    install_book(monkeypatch, book)
    with pytest.raises(HTTPException) as error:
        read_section()
    assert error.value.status_code == 502
    assert error.value.detail == expected_reason


def test_purchase_liquidity_uses_unary_data_and_still_preserves_real_blockers():
    now = datetime.now(timezone.utc)
    book = unary_book()
    book["orderbookTs"] = now.isoformat()
    trading = {"limitOrderAvailableFlag": True, "apiTradeAvailableFlag": True}
    assert purchases.liquidity_reasons(book, trading, "100", 1, now) == []
    stale = {**book, "orderbookTs": (now - timedelta(seconds=61)).isoformat(), "asks": []}
    reasons = purchases.liquidity_reasons(stale, trading, "100", 1, now)
    assert "order_book_stale_or_undated" in reasons
    assert "insufficient_visible_liquidity_at_limit" in reasons
    assert "order_book_not_consistent" not in reasons


@pytest.mark.parametrize("flag", [False, None, 0, "true"])
def test_explicit_adverse_or_malformed_consistency_still_blocks_purchase(flag):
    now = datetime.now(timezone.utc)
    book = {**unary_book(), "orderbookTs": now.isoformat(), "isConsistent": flag}
    trading = {"limitOrderAvailableFlag": True, "apiTradeAvailableFlag": True}
    assert "order_book_not_consistent" in purchases.liquidity_reasons(book, trading, "100", 1, now)


@pytest.mark.parametrize("include_empty_sides", [False, True])
def test_actual_empty_undated_unary_shape_stays_unavailable(monkeypatch, include_empty_sides):
    # Observed live response shape, with synthetic identity and no quote values.
    book = {"instrumentUid": "fixture-security", "depth": 1}
    if include_empty_sides:
        book.update(bids=[], asks=[])
    install_book(monkeypatch, book)
    result = read_section()
    assert result["state"] == "partial"
    assert result["reason"] == "order_book_stale_or_undated"
    assert result["data"]["best_bid"] is None
    assert result["data"]["best_ask"] is None
    assert result["data"]["spread"] is None
    assert result["data"]["depth_consistent"] is None
