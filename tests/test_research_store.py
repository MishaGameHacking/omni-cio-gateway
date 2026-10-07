"""Research provenance, offline replay and tenant-bound persistence."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from test_backtest import END, SOURCE, START, ZERO_COSTS, prices, research_document, run
from test_workspace_postgres import user
from test_workspace_postgres import workspace_database as workspace_database

from omnicio.portfolio_store import PortfolioStore, SettingsVersionConflict
from omnicio.research_store import ResearchNotFound, ResearchStore, normalize_research_evidence
from omnicio.strategy_assessment import StrategyFact
from omnicio.strategy_service import (
    _research_price_bars,
    _user_asset_evidence,
    replay_research_inputs,
    research_inputs,
)


def evidence_document():
    return {
        "assets": [
            {
                "instrument_uid": "a",
                "facts": {
                    "roe_percent": {
                        "value": "20",
                        "available_at": START.isoformat(),
                        "source_url": SOURCE,
                    }
                },
                "constituents": [],
                "cashflows": [],
                "coverage": None,
                "corporate_action_dates": [],
            }
        ]
    }


@pytest.mark.parametrize("mutation", ["owner", "future", "credentials", "nonfinite", "duplicate"])
def test_import_is_bounded_and_cannot_assert_owner_or_future_knowledge(mutation):
    data = evidence_document()
    fact = data["assets"][0]["facts"]["roe_percent"]
    if mutation == "owner":
        data["user_id"] = str(UUID(int=123))
    elif mutation == "future":
        fact["available_at"] = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    elif mutation == "credentials":
        fact["source_url"] = "https://user:secret@example.invalid/source"
    elif mutation == "nonfinite":
        fact["value"] = "NaN"
    else:
        data["assets"].append(deepcopy(data["assets"][0]))
    with pytest.raises(ValueError):
        normalize_research_evidence(data)


def test_user_facts_keep_declared_date_and_do_not_claim_complete_cashflow_history():
    evidence = normalize_research_evidence(evidence_document())["assets"][0]
    asset = _user_asset_evidence(prices(), evidence, START, END)
    fact = asset.candidate.facts["roe_percent"]
    assert fact.available_at == START
    assert fact.value == Decimal(20)
    assert asset.basis == "unadjusted_price"
    assert asset.cashflow_history_verified is False


def test_archive_roundtrip_reproduces_exact_hash_metrics_and_curve_without_provider():
    document, assets = research_document(), [prices(increasing=True)]
    expected = run(assets, document=document)
    serialized = research_inputs(
        document,
        assets,
        from_at=START,
        to_at=END,
        capital=Decimal(10000),
        costs=ZERO_COSTS,
        observed=END,
    )
    inputs = json.loads(json.dumps(serialized, default=str))
    replay = replay_research_inputs(inputs)
    assert replay["data_hash"] == expected["data_hash"]
    assert replay["metrics"] == expected["metrics"]
    assert replay["equity_curve"] == expected["equity_curve"]
    inputs["engine_version"] = "unknown-future-version"
    with pytest.raises(ValueError, match="version_unsupported"):
        replay_research_inputs(inputs)


def test_bond_amortization_needs_per_date_values_and_principal_is_not_income():
    raw = evidence_document()
    data = raw["assets"][0]
    data["coverage"] = {
        "from": START.isoformat(),
        "to": END.isoformat(),
        "cashflows_complete": True,
        "corporate_actions_complete": True,
        "lot_history_complete": True,
        "source_url": SOURCE,
    }
    when = START + timedelta(days=165)
    data["cashflows"] = [
        {
            "entitlement_at": when.isoformat(),
            "paid_at": when.isoformat(),
            "amount_per_unit_rub": "10",
            "kind": "principal",
            "source_url": SOURCE,
        }
    ]
    data["bond_valuations"] = [
        {
            "time": bar.time.isoformat(),
            "nominal_rub": "100" if bar.time < when else "90",
            "accrued_interest_open_rub": "0",
            "accrued_interest_close_rub": "0",
            "source_url": SOURCE,
        }
        for bar in prices().candles
    ]
    evidence = normalize_research_evidence(raw)["assets"][0]
    bars = _research_price_bars(
        {"instrument_type": "bond", "amortization": True}, prices().candles, evidence
    )
    asset = _user_asset_evidence(replace(prices(), candles=bars), evidence, START, END)
    facts = dict(asset.candidate.facts)
    facts.update(
        {
            key: StrategyFact(value, START, SOURCE)
            for key, value in (
                ("rating", "AAA"),
                ("maturity_date", END + timedelta(days=100)),
                ("perpetual", False),
            )
        }
    )
    asset = replace(asset, candidate=replace(asset.candidate, asset_class="bonds", facts=facts))
    document = research_document()
    document["allocation"].update(shares=0, bonds=100)
    document["policy"]["max_bond_percent"] = "100"
    document["policy"]["securities_tax_rate_percent"] = "13"
    result = run([asset], document=document)
    assert result["status"] == "computed", result["missing_requirements"]
    assert Decimal(result["metrics"]["ending_nav_rub"]) == 10000
    assert Decimal(result["metrics"]["taxes_rub"]) == 0
    assert bars[-1].close == "90"
    partial = {**evidence, "bond_valuations": evidence["bond_valuations"][:-1]}
    assert _research_price_bars({"instrument_type": "bond"}, prices().candles, partial) == ()
    serialized = research_inputs(
        document,
        [asset],
        from_at=START,
        to_at=END,
        capital=Decimal(10000),
        costs=ZERO_COSTS,
        observed=END,
    )
    replay = replay_research_inputs(json.loads(json.dumps(serialized, default=str)))
    assert replay["data_hash"] == result["data_hash"]
    assert replay["metrics"] == result["metrics"]


@pytest.mark.skipif(
    not os.environ.get("OMNICIO_TEST_DATABASE_URL"), reason="ephemeral PostgreSQL is required"
)
def test_research_archive_and_evidence_are_owner_scoped_and_versioned(workspace_database):
    database = workspace_database[0]
    owner, other = user(database, account=True), user(database, account=True)
    store = ResearchStore(database)
    assert store.evidence(owner)["version"] == 0
    record = store.save_evidence(owner, evidence_document(), expected_version=0)
    assert record["version"] == 1
    assert record["provenance"] == "user_supplied"
    assert record["independently_verified"] is False
    assert record["received_at"] > START
    assert store.evidence(other)["version"] == 0
    with pytest.raises(SettingsVersionConflict):
        store.save_evidence(owner, {"assets": []}, expected_version=0)
    document, assets = research_document(), [prices(increasing=True)]
    draft = PortfolioStore(database).save_strategy_draft(owner, document, expected_version=0)
    result = run(assets, document=document)
    inputs = research_inputs(
        document,
        assets,
        from_at=START,
        to_at=END,
        capital=Decimal(10000),
        costs=ZERO_COSTS,
        observed=END,
    )
    saved = store.save_run(
        owner,
        result=result,
        inputs=inputs,
        account_id=str(owner),
        environment="prod",
        connection_verified_at=database.tbank_connection(owner).verified_at,
        strategy_version=draft["version"],
        evidence_version=1,
    )
    run_id = UUID(saved["id"])
    assert len(store.runs(owner)) == 1
    assert store.runs(other) == []
    with pytest.raises(ResearchNotFound):
        store.run(other, run_id)
    with pytest.raises(ResearchNotFound):
        store.delete_run(other, run_id)
    archived = store.run(owner, run_id)
    assert replay_research_inputs(archived["inputs"])["data_hash"] == result["data_hash"]
    store.save_evidence(owner, {"assets": []}, expected_version=1)
    owner_account = str(owner)
    verified_at = database.tbank_connection(owner).verified_at
    with pytest.raises(SettingsVersionConflict):
        store.save_run(
            owner,
            result=result,
            inputs=inputs,
            account_id=owner_account,
            environment="prod",
            connection_verified_at=verified_at,
            strategy_version=draft["version"],
            evidence_version=1,
        )
    store.delete_run(owner, run_id)
    assert store.runs(owner) == []


@pytest.mark.skipif(
    not os.environ.get("OMNICIO_TEST_DATABASE_URL"), reason="ephemeral PostgreSQL is required"
)
def test_candidate_limit_does_not_let_large_bond_catalog_hide_other_classes(workspace_database):
    database = workspace_database[0]
    owner = user(database, account=True)
    with database.pool.connection() as conn, conn.transaction():
        conn.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(owner),))
        conn.execute(
            "INSERT INTO portfolio_snapshots (user_id, account_id, environment, captured_at, "
            "analysis_status, nav_rub, rub_cash_total, rub_cash_blocked, rub_cash_unblocked, "
            "limits_loading_in_progress, evidence) "
            "VALUES (%s, %s, 'prod', now(), 'observed', 100, 100, 0, 100, false, '{}'::jsonb)",
            (owner, str(owner)),
        )
        for index in range(110):
            kind = "share" if index == 108 else "etf" if index == 109 else "bond"
            uid = f"{owner}-{index}"
            conn.execute(
                "INSERT INTO instrument_catalog (provider, instrument_uid, ticker, "
                "instrument_type, currency, provider_retrieved_at) "
                "VALUES ('tbank', %s, %s, %s, 'RUB', now())",
                (uid, uid, kind),
            )
            conn.execute(
                "INSERT INTO account_instrument_access (user_id, account_id, provider, "
                "instrument_uid, observed_at) VALUES (%s, %s, 'tbank', %s, now())",
                (owner, str(owner), uid),
            )
    result = PortfolioStore(database).latest_balancing_context(owner, candidate_limit=3)
    assert {row["instrument_type"] for row in result["candidates"]} == {"bond", "share", "etf"}
