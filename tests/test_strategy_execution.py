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
from omnicio.strategy_assessment import StrategyFact, select_strategy_candidates
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


@pytest.mark.parametrize("kind", ["share", "bond"])
def test_coarse_price_tick_cannot_widen_the_selected_slippage_bound(kind):
    now = datetime.now(UTC)
    metadata = instrument(instrument_type=kind, min_price_increment="1")
    if kind == "bond":
        metadata = replace(
            metadata,
            nominal=TBankMoney("RUB", "1000"),
            accrued_interest=TBankMoney("RUB", "15"),
        )
    quote = execution_quote(metadata, book(now), slippage_bps=Decimal(10), now=now)
    factor = Decimal(10) if kind == "bond" else Decimal(1)
    assert quote["buy_limit"] == quote["sell_limit"] == Decimal(100) * factor
    assert quote["buy_limit"] <= Decimal("100.1") * factor
    assert quote["sell_limit"] >= Decimal("99.9") * factor


def observed_position(*, quantity="100", blocked="0"):
    """Use the real provider parser; deprecated quantityLots is intentionally absent."""
    response = {
        "totalAmountPortfolio": {"currency": "rub", "units": "10000", "nano": 0},
        "positions": [{
            "instrumentUid": "a", "instrumentType": "share",
            "quantity": {"units": quantity, "nano": 0},
            "blockedLots": {"units": str(int(Decimal(blocked))),
                            "nano": int(Decimal(blocked) % 1 * 10**9)},
            "currentPrice": {"currency": "rub", "units": "100", "nano": 0},
        }],
    }
    client = TBankInvestClient()
    with patch.object(TBankInvestClient, "_post", return_value=response):
        return client.get_portfolio("fixture", "sandbox", "account").positions[0]


def sized_plan(document, *, candidates=None, positions=(), cash="10000", blocked="0",
               weights=None, fee="0", price="100", lot=1, slippage="0", ask=None):
    now = datetime.now(UTC)
    rows = candidates or [history_candidate(prices(lot=lot).candidate, prices().candles, as_of=now)]
    quotes = {
        row.instrument_uid: execution_quote(
            instrument(uid=row.instrument_uid, lot=lot),
            TBankOrderBook(
                row.instrument_uid,
                (TBankOrderLevel(price, 10**12),),
                (TBankOrderLevel(ask or price, 10**12),), now, True,
            ),
            slippage_bps=Decimal(slippage), now=now,
        )
        for row in rows
    }
    selected = weights if weights is not None else [("a", "100")]
    return strategy_order_plan(
        document, rows,
        [{"instrument_uid": uid, "target_weight_percent": weight} for uid, weight in selected],
        positions, quotes, cash=Decimal(cash), blocked_cash=Decimal(blocked),
        commission_bps=Decimal(fee), now=now,
        max_order=Decimal("1e12"), max_daily=Decimal("1e12"),
    )


@pytest.mark.parametrize("blocked,expected_reserve", [("0", "5000"), ("700", "5000"),
                                                    ("4000", "7000")])
def test_cash_target_reserve_and_withdrawal_have_the_same_meaning_in_order_sizing(
    blocked, expected_reserve
):
    document = research_document()
    document["allocation"] = {"shares": 70, "bonds": 0, "funds": 0, "cash": 30}
    document["profile"].update(reserve_rub="1000", planned_withdrawal_rub="2000")
    document["policy"]["securities_tax_rate_percent"] = "0"
    result = sized_plan(document, weights=[("a", "70")], blocked=blocked)
    assert result["blockers"] == []
    assert Decimal(result["reserve_rub"]) == Decimal(expected_reserve)
    assert Decimal(result["cash_after_rub"]) == Decimal(expected_reserve)


def test_current_broker_cash_blocks_recompute_the_same_cash_constraint_before_dispatch():
    from test_execution_service import _leg

    now = datetime.now(UTC)
    owner = UUID(int=42)
    document = research_document()
    document["allocation"] = {"shares": 70, "bonds": 0, "funds": 0, "cash": 30}
    document["profile"].update(reserve_rub="1000", planned_withdrawal_rub="2000")
    document["policy"]["securities_tax_rate_percent"] = "0"
    payload = sized_plan(document, weights=[("a", "70")], blocked="700")
    payload.update(document=document, account_id="account")
    broker = broker_fixture("account", now)
    broker.portfolio.return_value.positions = TBankPositions(
        (TBankMoney("RUB", "10000"),), (TBankMoney("RUB", "2000"),), False,
    )
    broker.estimate_limit_order.side_effect = None
    broker.estimate_limit_order.return_value = TBankOrderEstimate(
        50, TBankMoney("RUB", "5000"), TBankMoney("RUB", "5000"), TBankMoney("RUB", "0"),
    )
    details = payload["legs"][0]
    leg = replace(
        _leg(), instrument_uid="a", lots_requested=50, limit_price=Decimal(100),
        limit_price_type="currency", max_spend_rub=Decimal(5000),
    )
    service = PortfolioExecutionService(store=Mock(), broker=broker)
    service._dispatch_preflight(owner, leg, details, payload, (leg,), "shadow")
    broker.portfolio.return_value.positions = replace(
        broker.portfolio.return_value.positions, blocked_money=(TBankMoney("RUB", "4000"),),
    )
    with pytest.raises(ExecutionServiceError, match="execution_free_cash_changed"):
        service._dispatch_preflight(owner, leg, details, payload, (leg,), "shadow")
    broker.portfolio.return_value.positions = replace(
        broker.portfolio.return_value.positions, blocked_money=(TBankMoney("RUB", "-1"),),
    )
    with pytest.raises(ExecutionServiceError, match="execution_cash_inconsistent"):
        service._dispatch_preflight(owner, leg, details, payload, (leg,), "shadow")
    broker.submit_limit_order.assert_not_called()


@pytest.mark.parametrize("blocked,free_lots", [("0", 10), ("10", 9), ("10.5", 8)])
def test_position_pieces_and_blocked_pieces_are_converted_to_whole_order_lots(blocked, free_lots):
    document = research_document()
    document["policy"]["securities_tax_rate_percent"] = "0"
    result = sized_plan(
        document, positions=(observed_position(blocked=blocked),),
        weights=[], cash="0", lot=10,
    )
    assert result["initial_lots"] == {"a": 10}
    assert result["lot_sizes"] == {"a": 10}
    assert result["legs"][0]["action"] == "sell"
    assert result["legs"][0]["lots"] == free_lots


def test_preflight_rechecks_piece_units_and_a_new_partial_lot_block_without_deprecated_quantity():
    from test_execution_service import _leg

    now = datetime.now(UTC)
    owner = UUID(int=42)
    document = research_document()
    document["policy"]["securities_tax_rate_percent"] = "0"
    position = observed_position(blocked="10")
    payload = sized_plan(document, positions=(position,), weights=[], cash="0", lot=10)
    payload["account_id"] = "account"
    broker = broker_fixture("account", now)
    broker.execution_instrument.return_value = instrument(lot=10)
    broker.portfolio.return_value.portfolio = replace(
        broker.portfolio.return_value.portfolio, positions=(position,),
    )
    broker.portfolio.return_value.positions = TBankPositions((TBankMoney("RUB", "0"),), (), False)
    broker.estimate_limit_order.side_effect = None
    broker.estimate_limit_order.return_value = TBankOrderEstimate(
        9, TBankMoney("RUB", "9000"), TBankMoney("RUB", "9000"), TBankMoney("RUB", "0"),
    )
    details = payload["legs"][0]
    leg = replace(
        _leg(action="sell"), instrument_uid="a", lots_requested=9,
        limit_price=Decimal(100), limit_price_type="currency", min_proceeds_rub=Decimal(9000),
    )
    service = PortfolioExecutionService(store=Mock(), broker=broker)
    service._dispatch_preflight(owner, leg, details, payload, (leg,), "shadow")
    broker.portfolio.return_value.portfolio = replace(
        broker.portfolio.return_value.portfolio,
        positions=(observed_position(blocked="10.5"),),
    )
    with pytest.raises(ExecutionServiceError, match="execution_free_inventory_changed"):
        service._dispatch_preflight(owner, leg, details, payload, (leg,), "shadow")
    broker.submit_limit_order.assert_not_called()


@pytest.mark.parametrize("price,cash", [("100", "10000"), ("0.01", "1000000")])
def test_feasible_equal_weight_plan_reserves_later_fees_before_sizing_the_first_buy(price, cash):
    now = datetime.now(UTC)
    document = research_document()
    document["policy"].update(max_instrument_percent="50", securities_tax_rate_percent="0")
    candidates = []
    for uid in ("a", "b"):
        row = history_candidate(prices(uid).candidate, prices(uid).candles, as_of=now)
        candidates.append(replace(row, facts={
            **row.facts,
            "daily_volume_lots": StrategyFact(Decimal("1e12"), now, "https://synthetic.example"),
        }))
    result = sized_plan(
        document, candidates=candidates, weights=[("a", "50"), ("b", "50")],
        price=price, cash=cash, fee="10",
    )
    assert result["blockers"] == []
    assert len(result["legs"]) == 2
    assert all(Decimal(value) <= 50 for value in result["projected_weights"].values())
    total_mark = sum(Decimal(leg["gross_amount_rub"]) for leg in result["legs"])
    assert total_mark >= Decimal(cash) * Decimal("0.98")
    after_nav = Decimal(result["cash_after_rub"]) + total_mark
    assert after_nav >= Decimal(result["allocation_nav_floor_rub"])


@pytest.mark.parametrize("action,minimum,lots", [
    ("buy", "8500", None), ("buy", "8100", 90),
    ("sell", "9500", None), ("sell", "9000", 100),
])
def test_minimum_effect_deducts_actual_adverse_price_cost_after_order_quantity_limits(
    action, minimum, lots
):
    document = research_document()
    document["policy"].update(securities_tax_rate_percent="0", min_replace_benefit_rub=minimum)
    result = sized_plan(
        document, slippage="1000", cash="10000" if action == "buy" else "0",
        positions=() if action == "buy" else (observed_position(),),
        weights=[("a", "100")] if action == "buy" else [],
    )
    assert result["blockers"] == []
    assert [leg["lots"] for leg in result["legs"]] == ([] if lots is None else [lots])


def test_zero_selected_slippage_does_not_hide_the_observed_bid_ask_spread_from_minimum_effect():
    document = research_document()
    document["policy"].update(securities_tax_rate_percent="0", min_replace_benefit_rub="8500")
    result = sized_plan(document, ask="110")
    assert result["legs"] == []


@pytest.mark.parametrize("days,expected_legs", [("2", []), ("1", [("sell", 10)])])
def test_liquidity_horizon_limits_the_whole_position_not_only_the_next_order(days, expected_legs):
    now = datetime.now(UTC)
    document = research_document()
    document["profile"]["liquidity_horizon_days"] = days
    document["policy"].update(securities_tax_rate_percent="0", min_replace_benefit_rub="0")
    row = history_candidate(prices().candidate, prices().candles, as_of=now)
    row = replace(row, facts={
        **row.facts,
        "daily_volume_lots": StrategyFact(Decimal(10), now, "https://synthetic.example"),
    })
    result = sized_plan(
        document, candidates=[row], positions=(observed_position(quantity="20"),), cash="8000",
    )
    assert result["blockers"] == []
    assert [(leg["action"], leg["lots"]) for leg in result["legs"]] == expected_legs
    document["profile"]["liquidity_horizon_days"] = "0"
    no_holdings = sized_plan(document, candidates=[row])
    assert no_holdings["legs"] == []


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
    archive.run.return_value["result"]["current_selection"] = select_strategy_candidates(
        payload["document"],
        [history_candidate(asset.candidate, asset.candles, as_of=now)],
        as_of=now,
    )
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
        metadata=(instrument(),),
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


@pytest.mark.parametrize(
    "invalid", ["insufficient_data", "missing_metrics", "old_engine", "previous_candidate_engine"]
)
def test_server_refuses_noncomputed_or_obsolete_research_before_account_and_quote_reads(invalid):
    service, owner, archive_id, store, broker, archive = shadow_planning_runtime()
    saved = archive.run.return_value
    if invalid == "old_engine":
        saved["inputs"]["engine_version"] = "1.1.0"
    elif invalid == "previous_candidate_engine":
        saved["inputs"]["engine_version"] = "1.3.0"
    elif invalid == "missing_metrics":
        saved["result"]["metrics"] = None
    else:
        saved["result"]["status"] = invalid
    commission, slippage = Decimal(10), Decimal(0)
    with pytest.raises(ExecutionServiceError, match="execution_computed_research_required"):
        service.plan(
            owner,
            expected_version=1,
            research_run_id=archive_id,
            session_digest=DIGEST,
            commission_bps=commission,
            slippage_bps=slippage,
        )
    broker.observation_bundle.assert_not_called()
    broker.candidate_order_book.assert_not_called()
    broker.submit_limit_order.assert_not_called()
    store.save_strategy_proposal.assert_not_called()


@pytest.mark.parametrize("current", ["missing", "unavailable", "stale", "future"])
def test_historical_result_cannot_override_an_unavailable_or_expired_current_selection(current):
    service, owner, archive_id, store, broker, archive = shadow_planning_runtime()
    result = archive.run.return_value["result"]
    if current == "missing":
        del result["current_selection"]
    elif current == "unavailable":
        result["current_selection"].update(
            status="insufficient_data", candidate_selection_ready=False, selected=[],
            missing_requirements=["fresh_account_instrument_catalog"],
        )
    else:
        offset = timedelta(days=-2) if current == "stale" else timedelta(hours=1)
        result["current_selection"]["as_of"] = (datetime.now(UTC) + offset).isoformat()
    commission, slippage = Decimal(10), Decimal(0)
    with pytest.raises(ExecutionServiceError, match="execution_current_research_required"):
        service.plan(
            owner, expected_version=1, research_run_id=archive_id, session_digest=DIGEST,
            commission_bps=commission, slippage_bps=slippage,
        )
    broker.observation_bundle.assert_not_called()
    broker.candidate_order_book.assert_not_called()
    broker.submit_limit_order.assert_not_called()
    store.save_strategy_proposal.assert_not_called()


@pytest.mark.parametrize("invalid", ["nonfinite_price", "zero_split"])
def test_execution_revalidates_archived_evidence_before_current_candidate_arithmetic(invalid):
    service, owner, archive_id, store, broker, archive = shadow_planning_runtime()
    asset = archive.run.return_value["inputs"]["assets"][0]
    if invalid == "nonfinite_price":
        asset["candles"][0]["close"] = "NaN"
    else:
        asset["splits"] = [{
            "time": asset["candles"][1]["time"], "ratio": "0",
            "source_url": "https://synthetic.example",
        }]
    commission, slippage = Decimal(10), Decimal(0)
    with pytest.raises(ExecutionServiceError, match="execution_current_research_required"):
        service.plan(
            owner, expected_version=1, research_run_id=archive_id, session_digest=DIGEST,
            commission_bps=commission, slippage_bps=slippage,
        )
    broker.observation_bundle.assert_not_called()
    broker.candidate_order_book.assert_not_called()
    broker.submit_limit_order.assert_not_called()
    store.save_strategy_proposal.assert_not_called()


@pytest.mark.parametrize("unclosed_today", [False, True])
def test_fresh_archive_timestamps_cannot_make_stale_provider_candles_current_for_execution(
    unclosed_today
):
    service, owner, archive_id, store, broker, archive = shadow_planning_runtime()
    # A provider can return an old but internally valid series for a request ending
    # today. Request/collection timestamps do not make its last observation fresh.
    candles = archive.run.return_value["inputs"]["assets"][0]["candles"]
    for bar in candles:
        bar["time"] = (datetime.fromisoformat(bar["time"]) - timedelta(days=30)).isoformat()
    if unclosed_today:
        # Even a provider's premature complete flag cannot refresh observations
        # which the daily-history arithmetic correctly excludes until day end.
        opening = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        candles.append({**candles[-1], "time": opening.isoformat(), "is_complete": True})
    commission, slippage = Decimal(10), Decimal(0)
    with pytest.raises(ExecutionServiceError, match="execution_current_research_required"):
        service.plan(
            owner, expected_version=1, research_run_id=archive_id, session_digest=DIGEST,
            commission_bps=commission, slippage_bps=slippage,
        )
    broker.observation_bundle.assert_not_called()
    broker.candidate_order_book.assert_not_called()
    broker.submit_limit_order.assert_not_called()
    store.save_strategy_proposal.assert_not_called()


def test_planning_reads_all_thirteen_held_instruments_without_artificial_twelve_asset_cap():
    from test_strategy_assessment import candidate_facts

    service, owner, _, _, broker, _ = shadow_planning_runtime()
    now = datetime.now(UTC)
    candidates = [candidate_facts(str(index)) for index in range(13)]
    bundle = Mock(
        portfolio=Mock(
            positions=tuple(
                Mock(instrument_uid=item.instrument_uid, instrument_type="share", quantity="1")
                for item in candidates
            )
        ),
        metadata=tuple(instrument(uid=item.instrument_uid) for item in candidates),
    )
    broker.execution_instrument.side_effect = lambda user_id, uid: instrument(uid=uid)
    broker.candidate_order_book.side_effect = lambda user_id, uid, **kwargs: replace(
        book(now),
        instrument_uid=uid,
    )
    quotes = service._planning_quotes(owner, {"selected": []}, bundle, candidates, Decimal(0))
    assert set(quotes) == {str(index) for index in range(13)}
    assert broker.candidate_order_book.call_count == 13
    broker.execution_instrument.assert_not_called()


@pytest.mark.parametrize("failure", ["provider_budget", "quotes_expired_after_estimates"])
def test_slow_planning_never_saves_a_proposal_or_submits_an_order(failure):
    service, owner, archive_id, store, broker, _ = shadow_planning_runtime()
    origin = datetime.now(UTC)
    elapsed = [0]

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return origin + timedelta(seconds=elapsed[0])

    if failure == "provider_budget":
        snapshot = broker.observation_bundle.return_value

        def slow_snapshot(_owner):
            elapsed[0] = 36
            return snapshot

        broker.observation_bundle.side_effect = slow_snapshot
        code = "execution_planning_read_budget_exhausted"
    else:
        estimator = broker.estimate_limit_order.side_effect

        def slow_estimate(*args, **kwargs):
            elapsed[0] = 31
            return estimator(*args, **kwargs)

        broker.estimate_limit_order.side_effect = slow_estimate
        code = "execution_quote_expired_during_plan"
    def elapsed_seconds():
        return elapsed[0]

    commission, slippage = Decimal(10), Decimal(0)
    with (
        patch("omnicio.execution_service.datetime", Clock),
        patch("omnicio.execution_service.monotonic", elapsed_seconds),
        pytest.raises(ExecutionServiceError, match=code),
    ):
        service.plan(
            owner,
            expected_version=1,
            research_run_id=archive_id,
            session_digest=DIGEST,
            commission_bps=commission,
            slippage_bps=slippage,
        )
    store.save_strategy_proposal.assert_not_called()
    broker.submit_limit_order.assert_not_called()


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
