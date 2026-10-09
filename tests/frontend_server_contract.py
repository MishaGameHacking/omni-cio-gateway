"""Emit actual server results for the isolated browser regression server.

Prices, portfolio values and candles pass through T-Invest JSON decoding and parsing,
portfolio calculations, recorded SQL bindings, MarketService and actual HTTP/SSE
serializers. Provider transport and database cursors are isolated fixtures;
PostgreSQL integration tests execute the SQL. Account lookup, instrument metadata
and trading status remain controlled fixtures. The browser consumes the server response.
Strategy results use the actual research engine with explicitly synthetic test prices.
"""

from __future__ import annotations

import io
import json
from contextlib import nullcontext
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import Mock, patch
from urllib.request import Request
from uuid import UUID

from fastapi.testclient import TestClient
from test_backtest import END, START, ZERO_COSTS, prices, research_document

from omnicio import main
from omnicio.backtest import run_strategy_backtest
from omnicio.billing import BillingConfig, BillingService
from omnicio.broker import BrokerObservationBundle, BrokerService, MarketSourceStatus
from omnicio.cbr import CBRClient
from omnicio.db import UserRecord
from omnicio.goal_planning import goal_forecast
from omnicio.market import MarketService
from omnicio.portfolio import analyze_portfolio, value_current_positions
from omnicio.portfolio_store import PortfolioStore
from omnicio.service import AuthService
from omnicio.tbank import (
    TBankInstrumentMetadata,
    TBankInvestClient,
    TBankLastPrice,
    TBankMoney,
    TBankTradingStatus,
    _quotation,
)
from omnicio.workspace import default_preferences
from omnicio.workspace_store import WorkspaceStore, _Basis, _History


def _wire_quotation(value: str) -> dict[str, str | int]:
    """Encode synthetic positive test prices without bypassing the provider parser."""
    units, _, fraction = value.partition(".")
    parts: dict[str, str | int] = {"units": units, "nano": int(fraction.ljust(9, "0"))}
    return {key: part for key, part in parts.items() if part not in ("0", 0)}


def _market_http_contract(
    *, price: str, metadata: TBankInstrumentMetadata,
    candles: tuple[dict[str, object], ...] = (), snapshot_price: str | None = None,
) -> dict[str, Any]:
    uid = "synthetic-a"
    credential = "synthetic-browser-contract-credential"
    provider = TBankInvestClient(purpose="market")
    current_price = snapshot_price or price

    def provider_response(request: Request, **_kwargs: object) -> io.BytesIO:
        """Only controlled wire JSON crosses the real provider's HTTP boundary."""
        assert request.get_method() == "POST"
        assert isinstance(request.data, bytes)
        body = json.loads(request.data)
        payload: dict[str, object]
        if request.full_url.endswith("MarketDataService/GetCandles"):
            assert body["instrumentId"] == uid
            assert body["candleSourceType"] == "CANDLE_SOURCE_EXCHANGE"
            payload = {"candles": candles}
        else:
            assert request.full_url.endswith("MarketDataService/GetLastPrices")
            assert body["instrumentId"] in ([], [uid])
            assert body["lastPriceType"] == "LAST_PRICE_EXCHANGE"
            payload = {"lastPrices": [{"instrumentUid": uid,
                                      "price": _wire_quotation(current_price),
                                      "time": datetime.now(UTC).isoformat()}]}
        return io.BytesIO(json.dumps(payload).encode())

    def last_price(_user: UUID, instrument_uid: str) -> TBankLastPrice:
        return provider.get_last_prices(
            credential, "prod", (instrument_uid,),
        )[0]

    broker = Mock(spec=BrokerService)
    broker.market_status.return_value = MarketSourceStatus(True, "tbank", "synthetic-source")
    broker.status.side_effect = AssertionError("Public market must not use personal credentials")
    broker.market_catalog.return_value = (metadata,)
    broker.market_all_last_prices.side_effect = (
        lambda: provider.get_all_last_prices(credential, "prod")
    )
    broker.market_last_price.side_effect = last_price
    broker.market_last_prices.side_effect = (
        lambda _user, instrument_uids: provider.get_last_prices_batch(
            credential, "prod", instrument_uids,
        )
    )
    broker.market_exchange_candles.side_effect = (
        lambda _user, instrument_uid, **window: provider.get_exchange_candles(
            credential, "prod", instrument_uid, **window,
        )
    )
    broker.market_trading_status.return_value = TBankTradingStatus(
        uid, "SECURITY_TRADING_STATUS_NORMAL_TRADING", True, True, True, True, False,
    )
    broker.market_instrument_metadata.return_value = metadata
    market = MarketService(broker=broker, cbr=Mock(spec=CBRClient))
    auth = Mock(spec=AuthService)
    auth.refresh_session.side_effect = AssertionError("Public market must not require an account")
    original_next = main._next_instrument_market_event

    async def without_provider_poll_delay(*args: object, **kwargs: object) -> tuple:
        event, payload, _, retry, failures, stop = await original_next(*args, **kwargs)
        if event == "market":
            # End the next stream observation through the shared source state.
            broker.market_status.side_effect = ValueError("test-end")
        return event, payload, 0, retry, failures, stop

    snapshot = None
    with (
        patch.object(main.app.state, "auth_service", auth, create=True),
        patch.object(main.app.state, "market_service", market, create=True),
        patch.object(main, "_next_instrument_market_event", without_provider_poll_delay),
        patch("urllib.request.OpenerDirector.open", side_effect=provider_response),
    ):
        # No lifespan: no database, broker credentials, live network or workers.
        client = TestClient(main.app, base_url=main.CANONICAL_ORIGIN)
        try:
            if snapshot_price is not None:
                rest = client.get(f"/api/market/instruments/{uid}", params={"period": "1m"},
                                  headers={"X-Omnicio-Profile": "000000123"})
                assert rest.status_code == 200, rest.text
                # The first response may correctly contain pending enrichment.
                # Await actual worker completion outside its lock, then read
                # the public contract again; no sleep or synchronous bypass.
                with market._cache_lock:
                    futures = [entry.future for entry in market._enrichment.values()
                               if entry.future is not None]
                for future in futures:
                    future.result(timeout=5)
                rest = client.get(f"/api/market/instruments/{uid}", params={"period": "1m"},
                                  headers={"X-Omnicio-Profile": "000000123"})
                assert rest.status_code == 200, rest.text
                assert "no-store" in rest.headers["cache-control"]
                snapshot = rest.json()
                assert snapshot["history_status"] == "available", snapshot["errors"]
            quotes = client.get("/api/market/quotes", params={"instrument_uids": uid},
                                headers={"X-Omnicio-Profile": "000000123"})
            assert quotes.status_code == 200, quotes.text
            assert "no-store" in quotes.headers["cache-control"]
            current_price = price
            # A completed common collector cycle replaces the cached price for
            # every guest and member before the next real SSE serialization.
            market._collect_quotes()
            public_market = client.get("/api/public/market", params={"limit": 100, "offset": 0})
            public_status = client.get("/api/public/market-status")
            assert public_market.status_code == 200, public_market.text
            assert public_status.status_code == 200, public_status.text
            assert "no-store" in public_market.headers["cache-control"]
            assert "no-store" in public_status.headers["cache-control"]
            assert public_market.json()["items"][0]["last_price"] == price
            assert public_status.json()["coverage"]["quote_instruments"] == 1
            response = client.get(f"/api/market/instruments/{uid}/stream",
                                  params={"profile_context": "000000123"})
        finally:
            client.close()
            market.close()
    assert response.status_code == 200, response.text
    auth.refresh_session.assert_not_called()
    broker.status.assert_not_called()
    assert response.headers["content-type"].startswith("text/event-stream")
    blocks = response.text.split("\n\n")
    market_event = next(block for block in blocks if block.startswith("event: market\n"))
    status_event = next(block for block in blocks if block.startswith("event: status\n"))
    result = {"instrument_stream": response.text,
            "instrument_market_event": market_event + "\n\n",
            "instrument_status_event": status_event + "\n\n", "market_quotes": quotes.json(),
            "public_market": public_market.json(), "public_market_status": public_status.json()}
    if snapshot is not None:
        result["market"] = snapshot
    return result


def market_contract() -> dict[str, Any]:
    metadata = TBankInstrumentMetadata(
        "synthetic-a", "Synthetic contract company", "SYNA", "", "share", "other", "RU", False,
        currency="rub", lot=1,
    )
    now = datetime.now(UTC)
    current_bar = now.replace(hour=now.hour - now.hour % 4, minute=0, second=0, microsecond=0)
    candles: tuple[dict[str, object], ...] = (
        {"open": _wire_quotation("245"), "high": _wire_quotation("249"),
         "low": _wire_quotation("242"), "close": _wire_quotation("248"),
         "time": (current_bar - timedelta(hours=4)).isoformat(), "volume": "10",
         "isComplete": True, "candleSource": "CANDLE_SOURCE_EXCHANGE"},
        {"open": _wire_quotation("248"), "high": _wire_quotation("251"),
         "low": _wire_quotation("247"), "close": _wire_quotation("250.25"),
         "time": current_bar.isoformat(), "candleSource": "CANDLE_SOURCE_EXCHANGE"},
    )
    # ProtoJSON omits false/zero scalars on the unfinished bar. A dataclass
    # fixture previously concealed rejection of this valid provider response.
    result = _market_http_contract(
        price="251.75", metadata=metadata, candles=candles, snapshot_price="250.25",
    )
    rows = result["market"]["candles"]
    assert len(rows) == 2
    assert rows[1]["is_complete"] is False and rows[1]["volume_lots"] == 0
    assert [rows[1][key] for key in ("open", "high", "low", "close")] == [
        "248", "251", "247", "250.25",
    ]
    return result


def market_precision_contract() -> list[dict[str, Any]]:
    """Synthetic provider quotations retain all nine decimals through real REST and SSE."""
    cases = (
        ("tiny", "share", 0, 3450000, 3450003, 3450001, "currency", "RUB", "0.00345"),
        ("nano", "share", 0, 1, 3, 1, "currency", "RUB", "0.000000001"),
        ("percent", "bond", 99, 999000000, 999000003, 999000001,
         "percent_nominal", None, "999.990"),
        ("points", "futures", 123456, 1, 3, 1, "points", None, None),
        ("large", "share", 10000000, 1, 2, 1, "currency", "RUB", "10000000.000000001"),
        ("int64", "share", 9223372036854775807, 999999999, 999999998, 999999997,
         "currency", "RUB", "9223372036854775807.999999999"),
    )
    result = []
    now = datetime.now(UTC)
    for key, kind, units, price_nano, first_nano, last_nano, unit, currency, cash in cases:
        price, first, last = (
            _quotation({"units": str(units), "nano": nano})
            for nano in (price_nano, first_nano, last_nano)
        )
        assert price is not None and first is not None and last is not None
        metadata = TBankInstrumentMetadata(
            "synthetic-a", "Synthetic precision contract", "SYNA", "", kind, "other", "RU", False,
            currency="RUB", lot=1, nominal=TBankMoney("RUB", "1000") if kind == "bond" else None,
        )
        candles: tuple[dict[str, object], ...] = tuple(
            {"open": _wire_quotation(first), "high": _wire_quotation(first),
             "low": _wire_quotation(last), "close": _wire_quotation(close),
             "volume": "1", "time": (now - timedelta(hours=hours)).isoformat(),
             "isComplete": True, "candleSource": "CANDLE_SOURCE_EXCHANGE"}
            for close, hours in ((first, 8), (last, 4))
        )
        payload = _market_http_contract(
            price=price, metadata=metadata, candles=candles, snapshot_price=first,
        )
        expected = {"last_price": price, "first_close": first, "last_close": last,
                    "high": first, "low": last, "price_unit": unit, "price_currency": currency,
                    "cash_price": cash,
                    "absolute_change": format((Decimal(price) - Decimal(first)).normalize(), "f")}
        stream_data = json.loads(payload["instrument_market_event"].split("data: ", 1)[1])
        assert all(stream_data[name] == expected[name] for name in (
            "last_price", "price_unit", "price_currency", "cash_price",
        ))
        assert payload["market"]["last_price"] == first
        assert [row["close"] for row in payload["market"]["candles"]] == [first, last]
        result.append({"key": key, "market_event": payload["instrument_market_event"],
                       "market": payload["market"], "expected": expected})
    return result


def _broker_snapshot_contract(now: datetime) -> tuple[dict[str, Any], dict[str, Any]]:
    """Capture actual INSERT values; all balances are invented isolated test data."""
    uid, account_id = "synthetic-a", "synthetic-account"

    def money(value: str) -> dict[str, str | int]:
        return {"currency": "RUB", **_wire_quotation(value)}

    payloads = {
        "GetPositions": {
            "accountId": account_id, "money": [money("749.70")],
            "securities": [{"instrumentUid": uid, "figi": "SYNTHETIC-FIGI",
                            "instrumentType": "share", "balance": "2", "blocked": "0"}],
        },
        "GetWithdrawLimits": {"money": [money("749.70")]},
    }

    def response(request: Request, **_kwargs: object) -> io.BytesIO:
        assert request.get_method() == "POST" and isinstance(request.data, bytes)
        body = json.loads(request.data)
        assert body["accountId"] == account_id
        return io.BytesIO(json.dumps(payloads[request.full_url.rsplit("/", 1)[-1]]).encode())

    provider = TBankInvestClient(purpose="portfolio")
    with patch("urllib.request.OpenerDirector.open", side_effect=response):
        balances = provider.get_positions("synthetic-contract-only", "prod", account_id)
        limits = provider.get_withdraw_limits("synthetic-contract-only", "prod", account_id)
    balances = replace(
        balances, money=limits.money, blocked_money=limits.blocked_money,
        blocked_guarantee_money=limits.blocked_guarantee_money, withdraw_limits_available=True,
    )
    metadata = TBankInstrumentMetadata(
        uid, "Синтетический актив", "SYNA", "", "share", "other", "RU", False,
        figi="SYNTHETIC-FIGI", currency="RUB", lot=10,
    )
    portfolio = value_current_positions(
        balances, (metadata,), (TBankLastPrice(uid, "125.19", now),),
    )
    analysis = analyze_portfolio(portfolio, balances, (metadata,))
    bundle = BrokerObservationBundle(
        account_id, "Синтетический счёт", "prod", now,
        portfolio, balances, (metadata,), analysis, (),
    )
    cursor, connection, database = Mock(), Mock(), Mock()
    database.pool.connection.return_value = nullcontext(connection)
    connection.transaction.return_value = nullcontext()
    connection.cursor.return_value = nullcontext(cursor)
    context = {"account_id": account_id, "environment": "prod", "verified_at": now.isoformat()}
    cursor.fetchone.side_effect = [
        {**context, "verified_at": now, "job_type": "portfolio_refresh", "details": {
            "connection": context, "legal_versions": {key: "synthetic" for key in (
                "privacy_policy", "personal_data_consent", "terms",
            )},
        }},
        {"accepted": True}, {"id": UUID(int=456)},
    ]
    PortfolioStore(database).save_snapshot(UUID(int=123), job_run_id=UUID(int=789), bundle=bundle)
    records = {}
    # Project the emitted INSERT column names and bound values. SQL execution is
    # verified by PostgreSQL integration tests, not by this in-memory transport.
    for call in cursor.execute.call_args_list:
        statement, *arguments = call.args
        if not statement.strip().startswith("INSERT INTO portfolio_snapshot"):
            continue
        names = statement.split("(", 1)[1].split(")", 1)[0].split(",")
        columns = [column.strip() for column in names]
        records[statement.strip().split()[2]] = dict(zip(columns, arguments[0], strict=True))
    snapshot = records["portfolio_snapshots"]
    snapshot.update(id=UUID(int=456), created_at=now, evidence=json.loads(snapshot["evidence"]))
    position = records["portfolio_snapshot_positions"]
    for storage_key in ("user_id", "snapshot_id", "quantity_lots",
                        "current_nkd_value", "current_nkd_currency"):
        position.pop(storage_key)
    position.update(name=metadata.name, catalog_instrument_uid=uid, asset_uid="",
                    currency=metadata.currency, assessed_at=None, risk_state="data_missing")
    return snapshot, position


def broker_portfolio_contract() -> dict[str, Any]:
    """Serialize quantities and current value without collecting purchase history."""
    now = datetime.now(UTC)
    snapshot, position = _broker_snapshot_contract(now)
    opening = {**snapshot, "id": UUID(int=455), "captured_at": now - timedelta(days=7),
               "created_at": now - timedelta(days=7), "nav_rub": Decimal("800.08")}
    basis = _Basis({"account_id": snapshot["account_id"], "environment": "prod",
                    "account_name": "Инвестиционный счёт"}, snapshot)
    history = _History([opening, snapshot], [opening, snapshot], {
        "status": "complete", "period": "1y",
        "requested_from": (now - timedelta(days=365)).isoformat(),
        "requested_to": now.isoformat(), "returned_from": opening["captured_at"].isoformat(),
        "returned_to": now.isoformat(), "returned_observations": 2, "total_observations": 2,
    })
    cursor, connection, database = Mock(), Mock(), Mock()
    database.pool.connection.return_value = nullcontext(connection)
    connection.transaction.return_value = nullcontext()
    connection.cursor.return_value = nullcontext(cursor)
    cursor.fetchone.return_value = snapshot
    cursor.fetchall.side_effect = [[snapshot, opening], [position]]
    auth = Mock(spec=AuthService)
    auth.refresh_session.return_value = UserRecord(UUID(int=123), 123, "active", "user")
    preferences = {"version": 0, "document": default_preferences()}
    with (
        patch.object(main.app.state, "auth_service", auth, create=True),
        patch.object(main.app.state, "portfolio_store", PortfolioStore(database), create=True),
        patch.object(main.app.state, "workspace_store", WorkspaceStore(Mock()), create=True),
        patch.object(WorkspaceStore, "_transaction", return_value=nullcontext(Mock())),
        patch.object(WorkspaceStore, "_basis", return_value=basis),
        patch.object(WorkspaceStore, "_history", return_value=history),
        patch.object(WorkspaceStore, "_preferences", return_value=preferences),
        patch.object(WorkspaceStore, "_goal_rows", return_value=[]),
        patch.object(WorkspaceStore, "_sync_events"),
        patch.object(WorkspaceStore, "_events_payload", return_value={"items": [], "unread": 0}),
    ):
        client = TestClient(main.app, base_url=main.CANONICAL_ORIGIN,
                            cookies={"omnicio_session": "synthetic-session"})
        try:
            result = {}
            for key, path in (
                ("broker_portfolio_visualization", "/api/portfolio/visualization"),
                ("broker_workspace", "/api/workspace?history_period=1y"),
                ("broker_instrument_visualization",
                 "/api/portfolio/instruments/synthetic-a/visualization"),
            ):
                if key == "broker_instrument_visualization":
                    cursor.fetchone.return_value = {
                        "current_snapshot_id": snapshot["id"], "current_snapshot_at": now,
                        "account_id": snapshot["account_id"], "environment": "prod",
                    }
                    cursor.fetchall.side_effect = [[{
                        **position, "snapshot_id": snapshot["id"], "captured_at": now,
                        "recorded_at": now, "analysis_status": snapshot["analysis_status"],
                    }], [], []]
                response = client.get(path, headers={"X-Omnicio-Profile": "000000123"})
                assert response.status_code == 200, response.text
                assert "no-store" in response.headers["cache-control"]
                result[key] = response.json()
        finally:
            client.close()
    assert "broker_statistics" not in result["broker_workspace"]["overview"]
    assert "broker_statistics" not in result["broker_portfolio_visualization"]["latest"]
    actual_position = result["broker_portfolio_visualization"]["latest"]["positions"][0]
    assert Decimal(actual_position["quantity"]) == 2
    assert "average_price" not in actual_position
    assert "expected_yield_amount" not in actual_position
    instrument = result["broker_instrument_visualization"]
    assert instrument["current_holding"]["status"] == "held"
    assert "average_price" not in instrument["latest"]
    historical = result["broker_workspace"]["value_change"]
    assert Decimal(historical["nav_change_rub"]) == 200
    assert "return_percent" not in historical
    return result


def goal_contract() -> dict[str, Any]:
    """Use the goal calculator's real output, including its stale-source refusal."""
    now = datetime.now(UTC)
    progress = {"status": "available", "amount_rub": "100", "percent": "10",
                "remaining_rub": "900", "source": "manual", "as_of": now.isoformat()}
    goal = {
        "id": "00000000-0000-4000-8000-000000000901", "version": 1,
        "title": "Тестовая цель источника", "kind": "capital", "status": "active",
        "target_amount_rub": "1000", "target_date": (now + timedelta(days=365)).date().isoformat(),
        "start_date": now.date().isoformat(), "progress_source": "manual",
        "manual_amount_rub": "100", "allocation_percent": "100", "progress": progress,
    }
    stale_goal = {**goal, "progress_source": "portfolio", "manual_amount_rub": None,
                  "progress": {**progress, "status": "stale", "source": "portfolio",
                               "as_of": (now - timedelta(days=60)).isoformat()}}
    plan = {"monthly_contribution_rub": "100", "monthly_income_rub": "0",
            "annual_return_percent": "0", "annual_volatility_percent": "0",
            "annual_inflation_percent": "0", "target_in_today_money": True, "seed": 42}
    return {
        "goal_plan_document": plan,
        "goal_available": goal,
        "goal_stale": stale_goal,
        "goal_forecast_available": goal_forecast(goal, plan, today=now.date()),
        "goal_forecast_stale": goal_forecast(stale_goal, plan, today=now.date()),
    }


def research_contract() -> dict[str, Any]:
    """Render the mathematical engine's real DTOs, never a separately invented response."""
    asset = prices()
    asset = replace(asset, candles=tuple(
        replace(bar, open="100", high="103", low="99",
                close="102" if index % 2 == 0 else "100") if index >= 140 else bar
        for index, bar in enumerate(asset.candles)
    ))
    outcomes = run_strategy_backtest(
        research_document(), [asset], from_at=START, to_at=END, now=END,
        initial_capital_rub=Decimal(10000), costs=ZERO_COSTS,
    )
    daily, weekly, monthly = outcomes["historical_outcomes"]["horizons"]
    assert outcomes["status"] == "computed"
    assert daily["windows"] == 60 and Decimal(daily["profit_frequency_percent"]) == 50
    assert weekly["status"] == monthly["status"] == "insufficient_data"
    cash_document = research_document()
    cash_document["allocation"].update(shares=0, cash=100)
    cash_document["policy"]["securities_tax_rate_percent"] = "0"
    cash = run_strategy_backtest(
        cash_document, [], from_at=START, to_at=END, now=END,
        initial_capital_rub=Decimal(10000), costs=ZERO_COSTS,
    )
    incomplete_document = {
        **cash_document, "profile": {**cash_document["profile"], "reserve_rub": None},
    }
    incomplete = run_strategy_backtest(
        incomplete_document, [], from_at=START, to_at=END, now=END,
        initial_capital_rub=Decimal(10000), costs=ZERO_COSTS,
    )
    assert cash["status"] == "computed" and cash["basis"] == "cash_balance_model"
    assert incomplete["status"] == "insufficient_data"
    assert "profile.reserve_rub" in incomplete["missing_requirements"]
    return {
        "research_outcomes_result": outcomes,
        "research_cash_result": cash,
        "research_cash_incomplete_result": incomplete,
    }


def preset_math_contract() -> dict[str, Any]:
    """The real selector emits the rung schedule and linked cashflow calculations."""
    from test_research_store import dividend_evidence_document
    from test_strategy_assessment import ladder_candidate, ladder_document

    from omnicio.research_store import normalize_research_evidence
    from omnicio.strategy_service import _user_asset_evidence

    split = START + (END - START) * 0.7
    bonds = [
        replace(prices(uid), candidate=ladder_candidate(
            uid, split + timedelta(days=days), as_of=split,
        ))
        for uid, days in (("rung-a", 300), ("rung-b", 700))
    ]
    evidence = normalize_research_evidence(dividend_evidence_document())["assets"][0]
    dividend = _user_asset_evidence(prices(), evidence, START, END)
    common = {
        "from_at": START, "to_at": END, "now": END,
        "initial_capital_rub": Decimal(10000), "costs": ZERO_COSTS,
    }
    ladder_result = run_strategy_backtest(ladder_document(), bonds, **common)
    dividend_result = run_strategy_backtest(research_document("dividends"), [dividend], **common)
    assert len(ladder_result["selection"]["ladder_rungs"]) == 5
    assert Decimal(ladder_result["selection"]["cash_weight_percent"]) == 60
    assert dividend_result["selection"]["status"] == "ready"
    assert Decimal(dividend_result["selection"]["selected"][0][
        "dividend_cashflow_coverage"
    ]["coverage_ratio"]) == 1
    return {
        "research_ladder_result": ladder_result,
        "research_dividend_result": dividend_result,
    }


def billing_contract() -> dict[str, Any]:
    """Keep the offer and entitlements aligned with the actual billing service."""
    cursor = Mock()
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = {"valid_until": None}
    enabled = BillingConfig(
        enabled=True, terminal_key="synthetic-terminal", password="synthetic-test-only",
        amount_kopecks=12345, description="Изолированное тестовое предложение",
        offer_version="synthetic-test-offer", taxation="usn_income", tax="none",
    )
    with patch.object(WorkspaceStore, "_transaction", return_value=nullcontext(cursor)):
        disabled_status = BillingService(Mock(), BillingConfig()).status(UUID(int=123))
        enabled_status = BillingService(Mock(), enabled).status(UUID(int=123))
    return {"billing_disabled": disabled_status, "billing_enabled": enabled_status}


def refresh_news_contract() -> dict[str, Any]:
    """Use the actual refresh serializer; broker cursors remain server-side."""
    now = datetime(2026, 10, 8, 10, tzinfo=UTC)
    connection = {"account_id": "synthetic-account", "environment": "prod",
                  "verified_at": now, "server_now": now + timedelta(minutes=5)}
    context = {"account_id": connection["account_id"], "environment": "prod",
               "verified_at": now.isoformat()}
    cases = {}
    store = PortfolioStore(Mock())
    for status in ("not_requested", "not_applicable", "received", "partial", "unavailable"):
        details: dict[str, Any] = {"connection": context, "refresh_scope": "quick",
                                   "history_status": "complete", "valuation_status": "complete"}
        if status != "not_requested":
            received = status in {"received", "partial"}
            details["news"] = {
                "status": status, "scope": "held_instrument_links",
                "observed_at": now.isoformat() if status != "not_applicable" else None,
                "pages": 1 if received else 0, "scanned_items": 18 if received else 0,
                "documents_new": 2 if received else 0,
                "next_cursor": "synthetic-private-provider-cursor", "error": "internal-detail",
            }
        row = {"id": UUID(int=456), "status": "succeeded", "requested_at": now,
               "started_at": now, "finished_at": now, "snapshot_at": now, "details": details}
        cursor = Mock()
        cursor.fetchone.side_effect = [{"captured_at": now}, row]
        cases[status] = store._refresh_status(cursor, UUID(int=123), connection)
    return {"refresh_news_cases": cases}


def payout_display_contract() -> dict[str, Any]:
    """Serialize stored payout dates and uncertainty through the actual private routes."""
    now = datetime(2026, 10, 8, 10, tzinfo=UTC)
    expected = datetime(2026, 10, 20, tzinfo=UTC)
    actual = datetime(2026, 9, 24, tzinfo=UTC)
    record = datetime(2026, 9, 15, tzinfo=UTC)
    snapshot_id = UUID(int=456)
    uid = "synthetic-a"
    position = {
        "snapshot_id": snapshot_id, "captured_at": now, "recorded_at": now,
        "analysis_status": "complete", "instrument_uid": uid, "quantity": Decimal(10),
        "current_price_value": Decimal(100), "current_price_currency": "RUB",
        "value_rub": Decimal(1000), "nav_percent": Decimal(100),
        "blocked": False, "blocked_lots": Decimal(0),
    }
    payouts = []
    for key, status, planned, paid, ambiguous in (
        ("scheduled", "scheduled", expected, actual, False),
        ("paid", "paid", actual - timedelta(days=1), actual, False),
        ("paid_expected", "paid", expected, None, False),
        ("record_only", "scheduled", None, None, False),
        ("undated", "observed", None, None, False),
        ("ambiguous_scheduled", "scheduled", expected, None, True),
        ("ambiguous_paid", "paid", actual - timedelta(days=1), actual, True),
    ):
        payouts.append({
            "provider": "tbank", "instrument_uid": uid,
            "event_type": {"record_only": "coupon", "undated": "bond_event"}.get(key, "dividend"),
            "provider_key": key, "announced_at": now - timedelta(days=30),
            "record_at": None if key == "undated" else record,
            "expected_at": planned, "actual_at": paid, "amount": Decimal("12.34"),
            "currency": "RUB", "status": status, "source_url": "https://example.test/payout",
            "first_retrieved_at": now, "retrieved_at": now, "identity_ambiguous": ambiguous,
        })
    cursor, connection, database = Mock(), Mock(), Mock()
    database.pool.connection.return_value = nullcontext(connection)
    connection.transaction.return_value = nullcontext()
    connection.cursor.return_value = nullcontext(cursor)
    cursor.fetchone.return_value = {
        "current_snapshot_id": snapshot_id, "current_snapshot_at": now,
        "account_id": "synthetic-account", "environment": "prod",
    }
    cursor.fetchall.side_effect = [[position], payouts, []]
    auth = Mock(spec=AuthService)
    auth.refresh_session.return_value = UserRecord(UUID(int=123), 123, "active", "user")
    with (
        patch.object(main.app.state, "auth_service", auth, create=True),
        patch.object(main.app.state, "portfolio_store", PortfolioStore(database), create=True),
        patch.object(main.app.state, "workspace_store", WorkspaceStore(Mock()), create=True),
    ):
        client = TestClient(main.app, base_url=main.CANONICAL_ORIGIN,
                            cookies={"omnicio_session": "synthetic-session"})
        try:
            response = client.get(f"/api/portfolio/instruments/{uid}/visualization",
                                  headers={"X-Omnicio-Profile": "000000123"})
            assert response.status_code == 200, response.text
            assert "no-store" in response.headers["cache-control"]
            visualization = response.json()
            event_cases = _payout_event_contract(client, uid, now, expected)
        finally:
            client.close()
    return {"payout_visualization": visualization, "payout_event_cases": event_cases}


def _payout_event_contract(
    client: TestClient, uid: str, now: datetime, expected: datetime,
) -> dict[str, Any]:
    source = {
        "type": "payout", "instrument_uid": uid, "amount_per_security": "999.19",
        "currency": "RUB", "expected_at": expected.isoformat(), "status": "scheduled",
        "url": "https://example.test/payout",
    }
    uncertain = {"identity_status": "ambiguous",
                 "identity_reason": "co_observed_anchor_collision"}
    cases = {}
    for key, ident, event_source in (
        ("normal", "a" * 64, source),
        ("superseded", "b" * 64, {**source, "superseded_by": "c" * 64,
                                  "supersession_reason": "identity_ambiguous"}),
        ("ambiguous", "c" * 64, {"type": "payout", "instrument_uid": uid, **uncertain}),
    ):
        cursor = Mock()
        cursor.fetchone.return_value = {
            "id": ident, "category": "payments", "severity": "warning",
            "kind": "payout_identity_ambiguous" if key == "ambiguous" else "payout_calendar",
            "title": "Synthetic source payout 999.19",
            "detail": "Synthetic payment terms 999.19", "occurred_at": expected,
            "read_at": now, "target": "asset", "source": event_source, "revision": 1,
        }
        with patch.object(WorkspaceStore, "_transaction", return_value=nullcontext(cursor)):
            response = client.get(f"/api/events/{ident}",
                                  headers={"X-Omnicio-Profile": "000000123"})
        assert response.status_code == 200, response.text
        assert "no-store" in response.headers["cache-control"]
        cases[key] = response.json()
    return cases


if __name__ == "__main__":
    print(json.dumps({**market_contract(), "market_precision_cases": market_precision_contract(),
                      **broker_portfolio_contract(),
                      **goal_contract(), **research_contract(), **preset_math_contract(),
                      **billing_contract(), **refresh_news_contract(), **payout_display_contract()},
                     ensure_ascii=True))
