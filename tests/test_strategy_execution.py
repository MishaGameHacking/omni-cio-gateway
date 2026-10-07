"""Actual sizing and ledger boundaries; provider side effects are always mocked."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import UUID

import psycopg
import pytest
from test_backtest import prices, research_document
from test_workspace_postgres import user
from test_workspace_postgres import workspace_database as workspace_database

from omnicio.backtest import ResearchCosts, history_candidate, run_strategy_backtest
from omnicio.broker import BrokerConnectionStatus, BrokerService
from omnicio.execution import ExecutionStateError, execution_quote, strategy_order_plan
from omnicio.execution_service import ExecutionServiceError, PortfolioExecutionService
from omnicio.execution_store import ExecutionLedgerError, ExecutionStore
from omnicio.portfolio_store import PortfolioStore
from omnicio.research_store import ResearchStore
from omnicio.strategy import document_hash
from omnicio.strategy_service import research_inputs
from omnicio.tbank import (
    TBankInstrumentMetadata,
    TBankInvestClient,
    TBankMoney,
    TBankOrderBook,
    TBankOrderEstimate,
    TBankOrderLevel,
    TBankPortfolio,
    TBankPositions,
    TBankTradingStatus,
)

DIGEST = b"s" * 32
LEGAL = {"terms": "test"}


def instrument(**changes):
    return replace(
        TBankInstrumentMetadata(
            "a",
            "Fixture",
            "TEST",
            "",
            "share",
            "a",
            "RU",
            False,
            currency="RUB",
            lot=1,
            api_trade_available=True,
            buy_available=True,
            sell_available=True,
            min_price_increment="0.01",
        ),
        **changes,
    )


def book(now):
    return TBankOrderBook(
        "a", (TBankOrderLevel("100", 1000),), (TBankOrderLevel("100", 1000),), now, True
    )


def plan_payload(now):
    document = research_document()
    document["policy"]["securities_tax_rate_percent"] = "0"
    candidate = history_candidate(prices().candidate, prices().candles, as_of=now)
    quote = execution_quote(instrument(), book(now), slippage_bps=Decimal(0), now=now)
    payload = strategy_order_plan(
        document,
        [candidate],
        [{"instrument_uid": "a", "target_weight_percent": "100"}],
        (),
        {"a": quote},
        cash=Decimal(10000),
        blocked_cash=Decimal(0),
        commission_bps=Decimal(10),
        now=now,
        max_order=Decimal(100000),
        max_daily=Decimal(100000),
    )
    return {
        **payload,
        "engine": "strategy_execution_1",
        "document": document,
        "strategy_version": 1,
        "strategy_hash": document_hash(document),
        "mode": "shadow",
        "environment": "prod",
        "evidence_version": 0,
        "legal_versions": LEGAL,
        "expires_at": (now + timedelta(minutes=2)).isoformat(),
    }


def broker_fixture(account_id, now):
    broker = Mock(spec=BrokerService)
    broker.execution_instrument.return_value = instrument()
    broker.market_trading_status.return_value = TBankTradingStatus(
        "a", "normal", True, False, True, False, False
    )
    broker.candidate_order_book.return_value = book(now)
    broker.estimate_limit_order.side_effect = lambda owner, **args: TBankOrderEstimate(
        args["lots"],
        TBankMoney("RUB", str(args["lots"] * 100 * Decimal("1.001"))),
        TBankMoney("RUB", str(args["lots"] * 100)),
        TBankMoney("RUB", str(args["lots"] * Decimal("0.1"))),
    )
    broker.portfolio.return_value = Mock(
        account_id=account_id,
        portfolio=TBankPortfolio(TBankMoney("RUB", "10000"), None, None, "0", (), ()),
        positions=TBankPositions((TBankMoney("RUB", "10000"),), (), False),
    )
    return broker


def test_native_bond_points_tick_and_nkd_are_separate_from_cash_order_price():
    now = datetime.now(UTC)
    metadata = instrument(
        instrument_type="bond",
        lot=10,
        min_price_increment="0.1",
        nominal=TBankMoney("RUB", "1000"),
        accrued_interest=TBankMoney("RUB", "15"),
    )
    quote = execution_quote(metadata, book(now), slippage_bps=Decimal(10), now=now)
    assert quote["buy_limit"] == Decimal(1001)
    assert quote["sell_limit"] == Decimal(999)
    assert quote["mark"] == Decimal(1015)
    assert quote["nkd"] == 15
    stale_book = book(now - timedelta(seconds=31))
    current_book = book(now)
    no_slippage = Decimal(0)
    foreign_nominal = replace(metadata, nominal=TBankMoney("USD", "1000"))
    with pytest.raises(ExecutionStateError, match="stale"):
        execution_quote(metadata, stale_book, slippage_bps=no_slippage, now=now)
    with pytest.raises(ExecutionStateError, match="nominal_or_accrual"):
        execution_quote(foreign_nominal, current_book, slippage_bps=no_slippage, now=now)


def test_integer_sizing_respects_cash_fees_caps_and_post_trade_exposure():
    payload = plan_payload(datetime.now(UTC))
    assert payload["blockers"] == []
    assert payload["legs"][0]["lots"] == 99
    assert Decimal(payload["cash_after_rub"]) == Decimal("90.1")
    assert Decimal(payload["legs"][0]["max_spend_rub"]) == Decimal("9909.9")
    assert payload["initial_lots"] == {}


def shadow_planning_runtime():
    now = datetime.now(UTC)
    owner, archive_id = UUID(int=1), UUID(int=2)
    payload = plan_payload(now)
    asset = prices()
    offset = (
        now.replace(hour=0, minute=0, second=0, microsecond=0)
        - asset.candles[-1].time
        - timedelta(days=1)
    )
    asset = replace(
        asset, candles=tuple(replace(bar, time=bar.time + offset) for bar in asset.candles)
    )
    inputs = research_inputs(
        payload["document"],
        [asset],
        from_at=asset.candles[0].time,
        to_at=now,
        capital=Decimal("9999999"),
        costs=ResearchCosts(Decimal(10), Decimal(0)),
        observed=now,
    )
    archive = Mock(spec=ResearchStore)
    archive.run.return_value = {
        "account_id": "account",
        "environment": "prod",
        "strategy_version": 1,
        "evidence_version": 0,
        "inputs": json.loads(json.dumps(inputs, default=str)),
        "result": run_strategy_backtest(
            payload["document"],
            [asset],
            from_at=asset.candles[0].time,
            to_at=now,
            initial_capital_rub=Decimal("9999999"),
            costs=ResearchCosts(Decimal(10), Decimal(0)),
            now=now,
        ),
    }
    archive.evidence.return_value = {"version": 0}
    portfolio = Mock(spec=PortfolioStore)
    portfolio.current_strategy_draft.return_value = {"version": 1, "document": payload["document"]}
    portfolio.latest_balancing_context.return_value = {
        "account_id": "account",
        "snapshot_id": str(UUID(int=3)),
        "captured_at": now,
    }
    broker = broker_fixture("account", now)
    broker.status.return_value = BrokerConnectionStatus(True, "prod", "account", "Fixture", now)
    broker.user_info.return_value = Mock(qualified=False)
    broker.observation_bundle.return_value = Mock(
        account_id="account",
        environment="prod",
        portfolio=broker.portfolio.return_value.portfolio,
        positions=broker.portfolio.return_value.positions,
        analysis=Mock(status="observed", nav_rub="10000"),
    )
    store = Mock(spec=ExecutionStore)
    store.save_strategy_proposal.side_effect = lambda user_id, **args: {
        "status": "ready",
        "payload": args["payload"],
    }
    service = PortfolioExecutionService(
        store=store,
        broker=broker,
        portfolio_store=portfolio,
        research_store=archive,
        legal_versions=LEGAL,
    )
    return service, owner, archive_id, store, broker, archive


def test_shadow_plan_uses_real_cash_and_works_with_deployment_caps_zero():
    service, owner, archive_id, store, broker, _ = shadow_planning_runtime()
    result = service.plan(
        owner,
        expected_version=1,
        research_run_id=archive_id,
        session_digest=DIGEST,
        commission_bps=Decimal(10),
        slippage_bps=Decimal(0),
        mode="shadow",
    )
    assert result["status"] == "ready"
    assert result["payload"]["nav_rub"] == "10000"
    assert result["payload"]["legs"][0]["lots"] == 99
    broker.submit_limit_order.assert_not_called()
    store.authorize_strategy.assert_called_once()
    assert store.save_strategy_proposal.call_args.args[0] == owner


@pytest.mark.parametrize("invalid", ["insufficient_data", "missing_metrics", "old_engine"])
def test_server_refuses_noncomputed_or_obsolete_research_before_account_and_quote_reads(invalid):
    service, owner, archive_id, store, broker, archive = shadow_planning_runtime()
    saved = archive.run.return_value
    if invalid == "old_engine":
        saved["inputs"]["engine_version"] = "1.1.0"
    elif invalid == "missing_metrics":
        saved["result"]["metrics"] = None
    else:
        saved["result"]["status"] = invalid
    with pytest.raises(ExecutionServiceError, match="execution_computed_research_required"):
        service.plan(owner, expected_version=1, research_run_id=archive_id, session_digest=DIGEST,
                     commission_bps=Decimal(10), slippage_bps=Decimal(0))
    broker.observation_bundle.assert_not_called()
    broker.candidate_order_book.assert_not_called()
    broker.submit_limit_order.assert_not_called()
    store.save_strategy_proposal.assert_not_called()


def test_planning_reads_all_thirteen_held_instruments_without_artificial_twelve_asset_cap():
    from test_strategy_assessment import candidate_facts

    service, owner, _, _, broker, _ = shadow_planning_runtime()
    now = datetime.now(UTC)
    candidates = [candidate_facts(str(index)) for index in range(13)]
    bundle = Mock(portfolio=Mock(positions=tuple(
        Mock(instrument_uid=item.instrument_uid, instrument_type="share", quantity="1")
        for item in candidates
    )))
    broker.execution_instrument.side_effect = lambda user_id, uid: instrument(uid=uid)
    broker.candidate_order_book.side_effect = lambda user_id, uid, **kwargs: replace(
        book(now), instrument_uid=uid,
    )
    quotes = service._planning_quotes(owner, {"selected": []}, bundle, candidates, Decimal(0))
    assert set(quotes) == {str(index) for index in range(13)}
    assert broker.candidate_order_book.call_count == 13


def test_provider_submission_has_one_durable_key_limit_price_and_no_margin():
    request_id = str(UUID(int=100))
    response = {
        "orderId": "exchange-one",
        "orderRequestId": request_id,
        "instrumentUid": "a",
        "executionReportStatus": "EXECUTION_REPORT_STATUS_NEW",
        "lotsRequested": "2",
        "lotsExecuted": "0",
        "direction": "ORDER_DIRECTION_BUY",
        "orderType": "ORDER_TYPE_LIMIT",
    }
    client = TBankInvestClient()
    with patch.object(TBankInvestClient, "_post", return_value=response) as post:
        result = client.submit_limit_order(
            "fixture",
            "sandbox",
            "account",
            instrument_uid="a",
            lots=2,
            price=Decimal("100.25"),
            action="buy",
            request_id=request_id,
        )
    assert result.order_request_id == request_id
    body = post.call_args.kwargs["body"]
    assert body["orderId"] == request_id
    assert body["price"] == {"units": "100", "nano": 250000000}
    assert body["confirmMarginTrade"] is False
    assert body["timeInForce"] == "TIME_IN_FORCE_FILL_AND_KILL"
    assert post.call_args.kwargs["method"] == "PostSandboxOrder"


@pytest.mark.skipif(
    not os.environ.get("OMNICIO_TEST_DATABASE_URL"), reason="ephemeral PostgreSQL is required"
)
def test_shadow_lifecycle_is_idempotent_owner_bound_and_rechecks_session(workspace_database):
    database = workspace_database[0]
    owner, other = user(database, account=True), user(database, account=True)
    now = datetime.now(UTC)
    payload = plan_payload(now)
    PortfolioStore(database).save_strategy_draft(owner, payload["document"], expected_version=0)
    with database.pool.connection() as conn, conn.transaction():
        conn.execute("SELECT set_config('omnicio.user_id',%s,true)", (str(owner),))
        conn.execute(
            "INSERT INTO sessions (user_id,token_digest,client_ip_hash,expires_at) "
            "VALUES (%s,%s,%s,now()+interval '1 hour')",
            (owner, DIGEST, b"i" * 32),
        )
        conn.execute(
            "INSERT INTO legal_acceptances "
            "(user_id,document_type,document_version,client_ip_hash) VALUES (%s,'terms','test',%s)",
            (owner, b"i" * 32),
        )
        row = conn.execute(
            "INSERT INTO portfolio_snapshots "
            "(user_id,account_id,environment,captured_at,analysis_status,nav_rub,rub_cash_total,"
            "rub_cash_blocked,rub_cash_unblocked,limits_loading_in_progress,evidence) "
            "VALUES (%s,%s,'prod',now(),'observed',10000,10000,0,10000,false,'{}') RETURNING id",
            (owner, str(owner)),
        ).fetchone()
        payload["source_snapshot_id"] = str(row["id"])
    connection = database.tbank_connection(owner)
    payload.update(account_id=str(owner), connection_verified_at=connection.verified_at.isoformat())
    store = ExecutionStore(database)
    saved = store.save_strategy_proposal(
        owner, payload=payload, session_digest=DIGEST, legal_versions=LEGAL
    )
    broker = broker_fixture(str(owner), now)
    service = PortfolioExecutionService(
        store=store,
        broker=broker,
        research_store=ResearchStore(database),
        legal_versions=LEGAL,
        max_order_rub=Decimal(100000),
        max_daily_rub=Decimal(100000),
    )
    kwargs = {
        "proposal_version": saved["version"],
        "proposal_hash": saved["proposal_hash"],
        "expected_strategy_version": 1,
        "session_digest": DIGEST,
    }
    with pytest.raises(ExecutionLedgerError):
        service.confirm(other, UUID(saved["id"]), **kwargs)
    confirmed = service.confirm(owner, UUID(saved["id"]), **kwargs)
    duplicate = service.confirm(owner, UUID(saved["id"]), **kwargs)
    assert confirmed["run"]["id"] == duplicate["run"]["id"]
    run_id = UUID(confirmed["run"]["id"])
    with database.pool.connection() as conn, conn.transaction():
        conn.execute("SELECT set_config('omnicio.user_id',%s,true)", (str(owner),))
        with pytest.raises(psycopg.Error), conn.transaction():
            conn.execute(
                "UPDATE portfolio_execution_legs SET lots_requested=10000 WHERE run_id=%s",
                (run_id,),
            )
        conn.execute("UPDATE sessions SET revoked_at=now() WHERE user_id=%s", (owner,))
    with pytest.raises(ExecutionLedgerError, match="session_revoked"):
        service.dispatch(
            owner, run_id, session_digest=DIGEST, expected_leg_id=UUID(confirmed["legs"][0]["id"])
        )
    broker.submit_limit_order.assert_not_called()
    with database.pool.connection() as conn:
        conn.execute("UPDATE sessions SET revoked_at=NULL WHERE user_id=%s", (owner,))
    finished = service.dispatch(
        owner, run_id, session_digest=DIGEST, expected_leg_id=UUID(confirmed["legs"][0]["id"])
    )
    assert finished["run"]["status"] == "succeeded"
    assert finished["legs"][0]["status"] == "shadow_filled"
    assert finished["legs"][0]["lots_executed"] == 99
    assert (
        service.dispatch(
            owner, run_id, session_digest=DIGEST, expected_leg_id=UUID(confirmed["legs"][0]["id"])
        )["run"]["status"]
        == "succeeded"
    )
    broker.submit_limit_order.assert_not_called()


@pytest.mark.skipif(
    not os.environ.get("OMNICIO_TEST_DATABASE_URL"), reason="ephemeral PostgreSQL is required"
)
@pytest.mark.parametrize("session_timezone", ["UTC", "America/Los_Angeles", "Pacific/Auckland"])
def test_live_daily_budget_counts_carryover_and_moscow_day_in_any_session_timezone(
    workspace_database, session_timezone
):
    """Run the production aggregation over isolated ledger projections in native SQL."""
    from zoneinfo import ZoneInfo

    from psycopg.types.json import Jsonb

    database = workspace_database[0]
    owner = UUID(int=42)
    day = datetime.now(ZoneInfo("Europe/Moscow")).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday, today = day - timedelta(seconds=1), day + timedelta(seconds=1)
    with database.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("SELECT set_config('TimeZone',%s,true)", (session_timezone,))
        cur.execute(
            "CREATE TEMP TABLE portfolio_live_execution_mandates "
            "(id uuid,user_id uuid,account_id text,revoked_at timestamptz,expires_at timestamptz,"
            "created_at timestamptz,max_order_notional_rub numeric,max_daily_notional_rub numeric) "
            "ON COMMIT DROP"
        )
        cur.execute("CREATE TEMP TABLE portfolio_proposals (id uuid,payload jsonb) ON COMMIT DROP")
        cur.execute(
            "CREATE TEMP TABLE portfolio_execution_runs (id uuid,proposal_id uuid,user_id uuid,"
            "mode text,status text,created_at timestamptz) ON COMMIT DROP"
        )
        cur.execute(
            "CREATE TEMP TABLE portfolio_execution_legs (run_id uuid,user_id uuid,"
            "executed_amount_rub numeric,max_spend_rub numeric,min_proceeds_rub numeric,"
            "executed_commission_rub numeric,submitted_at timestamptz,terminal_at timestamptz) "
            "ON COMMIT DROP"
        )
        cur.execute(
            "INSERT INTO portfolio_live_execution_mandates VALUES "
            "(%s,%s,'account',NULL,now()+interval '1 hour',now(),1000,1000)",
            (UUID(int=1), owner),
        )
        # Carryover 300 + yesterday's order submitted today 200 + late fill 100
        # + today's plan 100 = 700. A completed old 400 must not count today.
        rows = [
            (1, "running", yesterday, None, None, 300),
            (2, "succeeded", yesterday, today, today, 200),
            (3, "succeeded", yesterday, yesterday, today, 100),
            (4, "succeeded", yesterday, yesterday, yesterday, 400),
            (5, "cancelled", today, None, today, 100),
        ]
        for ident, status, created, submitted, terminal, amount in rows:
            uid = UUID(int=ident)
            cur.execute(
                "INSERT INTO portfolio_proposals VALUES (%s,%s)",
                (uid, Jsonb({"engine": "strategy_execution_1", "gross_turnover_rub": str(amount)})),
            )
            cur.execute(
                "INSERT INTO portfolio_execution_runs VALUES (%s,%s,%s,'live',%s,%s)",
                (uid, uid, owner, status, created),
            )
            cur.execute(
                "INSERT INTO portfolio_execution_legs VALUES (%s,%s,%s,%s,NULL,0,%s,%s)",
                (uid, owner, amount, amount, submitted, terminal),
            )
        plan = {
            "mode": "live",
            "account_id": "account",
            "gross_turnover_rub": "300",
            "legs": [{"gross_amount_rub": "300"}],
        }
        cap = Decimal(1000)
        assert ExecutionStore._validate_plan_budget(cur, owner, plan, cap, cap) == UUID(int=1)
        plan["gross_turnover_rub"] = "301"
        with pytest.raises(ExecutionLedgerError, match="live_notional_cap_exceeded"):
            ExecutionStore._validate_plan_budget(cur, owner, plan, cap, cap)
        # Rechecking the carryover run must not reserve its own plan twice.
        assert ExecutionStore._validate_plan_budget(
            cur, owner, plan, cap, cap, exclude_run_id=UUID(int=1)
        ) == UUID(int=1)


def test_dispatch_depth_uses_saved_limit_not_only_best_level():
    from test_execution_service import _leg

    now = datetime.now(UTC)
    owner = UUID(int=42)
    payload = plan_payload(now)
    payload["account_id"] = "account"
    broker = broker_fixture("account", now)
    broker.candidate_order_book.return_value = replace(
        book(now),
        asks=(TBankOrderLevel("100", 1), TBankOrderLevel("100.5", 1), TBankOrderLevel("101", 1000)),
    )
    broker.estimate_limit_order.side_effect = None
    broker.estimate_limit_order.return_value = TBankOrderEstimate(
        2, TBankMoney("RUB", "201.201"), TBankMoney("RUB", "201"), TBankMoney("RUB", "0.201")
    )
    service = PortfolioExecutionService(store=Mock(), broker=broker)
    leg = replace(
        _leg(),
        instrument_uid="a",
        limit_price=Decimal("100.5"),
        limit_price_type="currency",
        max_spend_rub=Decimal(202),
    )
    details = {**payload["legs"][0], "lots": 2, "limit_price": "100.5", "max_spend_rub": "202"}
    service._dispatch_preflight(owner, leg, details, payload, (leg,), "shadow")
    broker.candidate_order_book.return_value = replace(
        book(now), asks=(TBankOrderLevel("100", 1), TBankOrderLevel("100.6", 1000))
    )
    with pytest.raises(ExecutionServiceError, match="execution_quote_moved_outside_limit"):
        service._dispatch_preflight(owner, leg, details, payload, (leg,), "shadow")
    broker.submit_limit_order.assert_not_called()


def test_current_sell_estimate_below_confirmed_proceeds_blocks_before_submission():
    broker = Mock(spec=BrokerService)
    broker.estimate_limit_order.return_value = TBankOrderEstimate(
        2, TBankMoney("RUB", "199.5"), TBankMoney("RUB", "200"), TBankMoney("RUB", "0.5")
    )
    service = PortfolioExecutionService(store=Mock(), broker=broker)
    leg = {
        "instrument_uid": "a",
        "lots": 2,
        "lot_size": 1,
        "limit_price": "100",
        "action": "sell",
        "commission_cap_rub": "1",
        "min_proceeds_rub": "200",
    }
    with pytest.raises(ExecutionServiceError, match="execution_provider_cost_exceeds_cap"):
        service._check_order_estimate(UUID(int=42), leg)
    broker.submit_limit_order.assert_not_called()


def test_depth_converts_bond_points_at_exact_saved_clean_currency_limit():
    from omnicio.execution import execution_depth

    now = datetime.now(UTC)
    quote_book = replace(
        book(now),
        asks=(
            TBankOrderLevel("100", 1),
            TBankOrderLevel("100.5", 2),
            TBankOrderLevel("100.6", 1000),
        ),
    )
    assert (
        execution_depth(
            quote_book, action="buy", limit_price=Decimal(1005), cash_price_factor=Decimal(10)
        )
        == 3
    )
