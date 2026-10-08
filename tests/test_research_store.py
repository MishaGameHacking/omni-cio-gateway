"""Research provenance, offline replay and tenant-bound persistence."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import sql
from test_backtest import END, SOURCE, START, ZERO_COSTS, prices, research_document, run
from test_workspace_postgres import user
from test_workspace_postgres import workspace_database as workspace_database

from omnicio.portfolio_store import PortfolioStore, SettingsVersionConflict
from omnicio.research_store import (
    MAX_ARCHIVE_DOCUMENT_BYTES,
    MAX_EVIDENCE_DOCUMENT_BYTES,
    ResearchNotFound,
    ResearchStore,
    normalize_research_evidence,
)
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


@pytest.mark.parametrize("value", ["1e1000000", "-1e1000000", "1e-1000000", "0e1000000"])
def test_extreme_decimal_exponents_are_rejected_before_arithmetic_or_expansion(value):
    data = evidence_document()
    data["assets"][0]["facts"]["roe_percent"]["value"] = value
    with pytest.raises(ValueError, match="research_evidence_number_invalid"):
        normalize_research_evidence(data)


@pytest.mark.parametrize("value", ["1e15", "-1e15", "1e-28", "0"])
def test_bounded_evidence_decimals_keep_their_exact_value(value):
    data = evidence_document()
    data["assets"][0]["facts"]["roe_percent"]["value"] = value
    normalized = normalize_research_evidence(data)
    actual = normalized["assets"][0]["facts"]["roe_percent"]["value"]
    assert Decimal(actual) == Decimal(value)


def test_confirmed_user_zero_debt_remains_distinct_from_provider_missing_zero():
    data = evidence_document()
    data["assets"][0]["facts"] = {
        "debt_to_ebitda": {"value": "0", "available_at": START.isoformat(), "source_url": SOURCE},
    }
    normalized = normalize_research_evidence(data)["assets"][0]
    asset = _user_asset_evidence(prices(), normalized, START, END)
    fact = asset.candidate.facts["debt_to_ebitda"]
    assert fact.value == 0
    assert fact.source_url == SOURCE
    assert fact.available_at == START


def dividend_evidence_document():
    """Synthetic annual issuer statement; never a production market observation."""
    document = evidence_document()
    facts = document["assets"][0]["facts"]
    facts["dividend_cashflow_coverage"] = {
        "value": {
            "issuer_id": "issuer-a",
            "scope": "consolidated_issuer_all_equity",
            "currency": "USD",
            "period_start": (START - timedelta(days=365)).isoformat(),
            "period_end": START.isoformat(),
            "operating_cashflow": "1000.01",
            "capital_expenditure": "400.01",
            "gross_dividends_paid": "600",
            "cashflows_complete": True,
        },
        "available_at": START.isoformat(),
        "source_url": SOURCE,
    }
    for name, value in (
        ("dividend_yield_percent", "6"), ("payout_ratio_percent", "40"),
        ("debt_to_ebitda", "1"), ("free_cashflow_yield_percent", "8"),
        ("dividend_declared", True),
    ):
        facts[name] = {"value": value, "available_at": START.isoformat(), "source_url": SOURCE}
    return document


def test_linked_issuer_cashflows_survive_import_archive_and_replay_without_currency_conversion():
    evidence = normalize_research_evidence(dividend_evidence_document())["assets"][0]
    asset = _user_asset_evidence(prices(), evidence, START, END)
    coverage = asset.candidate.facts["dividend_cashflow_coverage"]
    assert coverage.value["currency"] == "USD"
    assert coverage.value["operating_cashflow"] == "1000.01"
    assert coverage.source_url == SOURCE
    document = research_document("dividends")
    expected = run([asset], document=document)
    assert expected["selection"]["status"] == "ready"
    inputs = research_inputs(
        document, [asset], from_at=START, to_at=END, capital=Decimal(10000),
        costs=ZERO_COSTS, observed=END,
    )
    # PostgreSQL JSONB may change object-key order. The semantic fingerprint and
    # every result must survive the same reorder on nested structured facts.
    replay = replay_research_inputs(json.loads(json.dumps(inputs, default=str, sort_keys=True)))
    assert replay["data_hash"] == expected["data_hash"]
    assert replay["selection"] == expected["selection"]
    assert replay["metrics"] == expected["metrics"]


@pytest.mark.parametrize("field,value", [
    ("capital_expenditure", "-0.01"), ("gross_dividends_paid", "1e1000000"),
    ("scope", "one_share_class"), ("currency", "usd"),
    ("period_end", (START + timedelta(days=1)).isoformat()),
    ("cashflows_complete", "true"),
])
def test_linked_dividend_evidence_rejects_incompatible_or_malformed_values(field, value):
    document = dividend_evidence_document()
    document["assets"][0]["facts"]["dividend_cashflow_coverage"]["value"][field] = value
    with pytest.raises(ValueError, match="research_dividend_coverage_invalid"):
        normalize_research_evidence(document)


@pytest.mark.parametrize("explicit_units", [False, True])
def test_cashflow_units_are_archived_only_when_the_user_explicitly_declares_them(explicit_units):
    raw = evidence_document()
    raw["assets"][0]["coverage"] = {
        "from": (START - timedelta(days=365)).isoformat(), "to": END.isoformat(),
        "cashflows_complete": True, "corporate_actions_complete": True,
        "lot_history_complete": True, "source_url": SOURCE,
    }
    if explicit_units:
        raw["assets"][0]["coverage"]["cashflow_unit_basis"] = "entitlement_security"
    evidence = normalize_research_evidence(raw)["assets"][0]
    asset = _user_asset_evidence(prices(), evidence, START, END)
    recorded = asset.provider_observations.get("user_cashflow_coverage")
    if explicit_units:
        assert recorded == evidence["coverage"]
        inputs = research_inputs(
            research_document(), [asset], from_at=START, to_at=END, capital=Decimal(10000),
            costs=ZERO_COSTS, observed=END,
        )
        from omnicio.strategy_service import research_assets_from_inputs

        restored = research_assets_from_inputs(json.loads(json.dumps(inputs, default=str)))[0]
        assert restored.provider_observations["user_cashflow_coverage"] == recorded
    else:
        assert recorded is None


def test_cashflow_unit_declaration_cannot_use_an_ambiguous_current_share_basis():
    raw = evidence_document()
    raw["assets"][0]["coverage"] = {"cashflow_unit_basis": "current_share"}
    with pytest.raises(ValueError, match="research_cashflow_unit_basis_invalid"):
        normalize_research_evidence(raw)


@pytest.mark.parametrize("field", ["available_at", "maturity_date"])
def test_extreme_timezone_cannot_overflow_evidence_utc_normalization(field):
    raw = evidence_document()
    impossible = "0001-01-01T00:00:00+01:00"
    if field == "available_at":
        raw["assets"][0]["facts"]["roe_percent"]["available_at"] = impossible
    else:
        raw["assets"][0]["facts"]["maturity_date"] = {
            "value": impossible, "available_at": START.isoformat(), "source_url": SOURCE,
        }
    with pytest.raises(ValueError, match="research_evidence_time_invalid"):
        normalize_research_evidence(raw)


@pytest.mark.parametrize("changed", ["paid_at", "entitlement_at", "both"])
def test_complete_user_cashflows_replace_corrected_dates_without_doubling_nav(changed):
    from omnicio.backtest import HistoricalCashflow

    entitlement, paid = START + timedelta(days=160), START + timedelta(days=165)
    original = HistoricalCashflow(entitlement, paid, Decimal(10), SOURCE)
    outside = HistoricalCashflow(
        START - timedelta(days=3), START - timedelta(days=1), Decimal(5), SOURCE
    )
    unchanged = HistoricalCashflow(
        START + timedelta(days=170), START + timedelta(days=175), Decimal(7), SOURCE
    )
    asset = replace(prices(), observed_cashflows=(outside, original, unchanged))
    correction = replace(
        original,
        entitlement_at=entitlement + timedelta(days=int(changed in {"entitlement_at", "both"})),
        paid_at=paid + timedelta(days=int(changed in {"paid_at", "both"})),
    )
    raw = evidence_document()
    row = raw["assets"][0]
    row["cashflows"] = [
        {
            "entitlement_at": event.entitlement_at.isoformat(),
            "paid_at": event.paid_at.isoformat(),
            "kind": event.kind,
            "amount_per_unit_rub": str(event.amount_per_unit_rub),
            "source_url": event.source_url,
        }
        for event in (correction, unchanged)
    ]
    partial = normalize_research_evidence(raw)["assets"][0]
    with pytest.raises(ValueError, match="research_cashflow_overlap_requires_complete_history"):
        _user_asset_evidence(asset, partial, START, END)
    row["coverage"] = {
        "from": START.isoformat(),
        "to": END.isoformat(),
        "source_url": SOURCE,
        "cashflows_complete": True,
        "corporate_actions_complete": True,
        "lot_history_complete": True,
    }
    evidence = normalize_research_evidence(raw)["assets"][0]
    corrected = _user_asset_evidence(asset, evidence, START, END)
    assert corrected.observed_cashflows == (outside, correction, unchanged)
    assert corrected.cashflows == corrected.observed_cashflows
    assert original not in corrected.cashflows
    result = run([corrected])
    assert result["status"] == "computed"
    # Only the two post-purchase payments reach NAV. Neither date correction
    # adds a second version; the earlier outside-range payment is preserved.
    assert Decimal(result["metrics"]["ending_nav_rub"]) == 11700


def test_partial_cashflow_amount_correction_preserves_unmodified_provider_events():
    from omnicio.backtest import HistoricalCashflow

    first = HistoricalCashflow(START, START + timedelta(days=1), Decimal(10), SOURCE)
    other = HistoricalCashflow(
        START + timedelta(days=3), START + timedelta(days=4), Decimal(7), SOURCE
    )
    asset = replace(prices(), observed_cashflows=(first, other))
    raw = evidence_document()
    raw["assets"][0]["cashflows"] = [
        {
            "entitlement_at": first.entitlement_at.isoformat(),
            "paid_at": first.paid_at.isoformat(),
            "kind": "income",
            "amount_per_unit_rub": "3",
            "source_url": SOURCE,
        }
    ]
    evidence = normalize_research_evidence(raw)["assets"][0]
    corrected = _user_asset_evidence(asset, evidence, START, END)
    assert corrected.observed_cashflows == (replace(first, amount_per_unit_rub=Decimal(3)), other)
    assert corrected.cashflows == ()


@pytest.mark.parametrize("changed", ["paid_at", "entitlement_at"])
def test_corrected_cashflow_cannot_duplicate_a_matching_event_just_outside_complete_coverage(
    changed,
):
    from omnicio.backtest import HistoricalCashflow
    from omnicio.strategy_service import _research_cashflows

    original = HistoricalCashflow(START, START + timedelta(days=2), Decimal(10), SOURCE)
    if changed == "paid_at":
        correction = replace(original, paid_at=START + timedelta(days=3))
        begin, end = START + timedelta(days=3), START + timedelta(days=6)
    else:
        correction = replace(original, entitlement_at=START - timedelta(days=1))
        begin, end = START - timedelta(days=2), START - timedelta(seconds=1)
    coverage = {"from": begin.isoformat(), "to": end.isoformat(), "cashflows_complete": True}
    with pytest.raises(ValueError, match="research_cashflow_overlap_requires_complete_history"):
        _research_cashflows((original,), (correction,), coverage)


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


@pytest.mark.parametrize("engine_version", ["1.1.0", "1.2.0", "1.3.0", "1.3.1"])
def test_archive_replay_keeps_versioned_allocation_and_dated_observations(engine_version):
    from omnicio.backtest import HistoricalCashflow

    document = research_document()
    first, second = prices("a", increasing=True), prices("b")
    document["policy"]["max_instrument_percent"] = "60"
    first = replace(
        first,
        candidate=replace(
            first.candidate,
            fact_history={
                "roe_percent": (StrategyFact(Decimal(20), START, SOURCE),),
            },
        ),
        observed_cashflows=(HistoricalCashflow(START, START, Decimal(3), SOURCE),),
        provider_observations={
            "facts": {
                "roe_percent": {
                    "value": "20",
                    "available_at": START.isoformat(),
                    "source_url": SOURCE,
                }
            }
        },
    )
    assets = [first, second]
    if engine_version == "1.1.0":
        assets = [
            replace(
                asset,
                candidate=replace(asset.candidate, fact_history={}),
                observed_cashflows=(),
                provider_observations={},
            )
            for asset in assets
        ]
    expected = run(assets, document=document, engine_version=engine_version)
    serialized = research_inputs(
        document,
        assets,
        from_at=START,
        to_at=END,
        capital=Decimal(10000),
        costs=ZERO_COSTS,
        observed=END,
    )
    serialized["engine_version"] = engine_version
    if engine_version == "1.1.0":
        # These fields did not exist in the accepted 1.1.0 schema. Its fingerprint
        # and allocator must remain reproducible after upgrading the runtime.
        for asset in serialized["assets"]:
            asset["candidate"].pop("fact_history")
            asset.pop("observed_cashflows")
            asset.pop("provider_observations")
    replay = replay_research_inputs(json.loads(json.dumps(serialized, default=str)))
    assert replay["engine_version"] == engine_version
    assert replay["data_hash"] == expected["data_hash"]
    assert replay["selection"] == expected["selection"]
    assert replay["equity_curve"] == expected["equity_curve"]
    assert replay["metrics"] == expected["metrics"]


def research_archive_case(database):
    owner = user(database, account=True)
    store = ResearchStore(database)
    document, assets = research_document(), [prices()]
    draft = PortfolioStore(database).save_strategy_draft(owner, document, expected_version=0)
    return (
        owner,
        store,
        {
            "result": run(assets, document=document),
            "inputs": research_inputs(
                document,
                assets,
                from_at=START,
                to_at=END,
                capital=Decimal(10000),
                costs=ZERO_COSTS,
                observed=END,
            ),
            "account_id": str(owner),
            "environment": "prod",
            "connection_verified_at": database.tbank_connection(owner).verified_at,
            "strategy_version": draft["version"],
            "evidence_version": 0,
        },
    )


@pytest.mark.skipif(
    not os.environ.get("OMNICIO_TEST_DATABASE_URL"), reason="ephemeral PostgreSQL is required"
)
def test_research_requests_are_atomic_owner_bound_and_keep_deleted_tombstones(workspace_database):
    database = workspace_database[0]
    owner, store, archive = research_archive_case(database)
    other, other_store, other_archive = research_archive_case(database)
    request_id, input_hash = uuid4(), archive["result"]["data_hash"]
    first = store.begin_request(owner, request_id, input_hash)
    assert first["created"] is True
    assert first["status"] == "running"
    assert first["expires_at"] > first["created_at"]
    assert "created" not in store.begin_request(owner, request_id, input_hash)
    with pytest.raises(ResearchNotFound, match="research_request_not_found"):
        store.request(other, request_id)
    with pytest.raises(SettingsVersionConflict, match="research_request_parameters_changed"):
        store.begin_request(owner, request_id, "0" * 64)
    with store._transaction(owner) as cur:
        cur.execute(
            "UPDATE strategy_research_requests SET expires_at = now() - interval '1 second' "
            "WHERE user_id=%s AND id=%s",
            (owner, request_id),
        )
    assert store.request(owner, request_id)["status"] == "expired"
    with pytest.raises(SettingsVersionConflict, match="research_request_expired"):
        store.save_run(owner, request_id=request_id, **archive)
    assert store.capacity(owner)["runs_used"] == 0  # archive and completion roll back together
    complete_id = uuid4()
    store.begin_request(owner, complete_id, input_hash)
    saved = store.save_run(owner, request_id=complete_id, **archive)
    run_id = UUID(saved["id"])
    assert store.request(owner, complete_id)["run_id"] == run_id
    assert store.begin_request(owner, complete_id, input_hash)["status"] == "completed"
    with store._transaction(owner) as cur:
        cur.execute(
            "UPDATE strategy_research_requests SET updated_at=now()-interval '31 days' "
            "WHERE user_id=%s AND id=%s",
            (owner, complete_id),
        )
    active_id, failed_id = uuid4(), uuid4()
    store.begin_request(owner, active_id, input_hash)
    store.begin_request(owner, failed_id, input_hash)
    store.fail_request(owner, failed_id, "research_failed")
    assert store.runs_page(owner)["recent_request"]["id"] == active_id
    assert store.request(owner, complete_id)["status"] == "completed"
    other_store.begin_request(other, complete_id, other_archive["result"]["data_hash"])
    with pytest.raises(psycopg.errors.ForeignKeyViolation), other_store._transaction(other) as cur:
        cur.execute(
            "UPDATE strategy_research_requests SET status='completed',run_id=%s "
            "WHERE user_id=%s AND id=%s",
            (run_id, other, complete_id),
        )
    with store._transaction(other) as cur:
        cur.execute("SELECT id FROM strategy_research_requests WHERE user_id=%s", (owner,))
        assert cur.fetchall() == []
    store.delete_run(owner, run_id)
    assert store.request(owner, complete_id)["status"] == "deleted"
    assert "created" not in store.begin_request(owner, complete_id, input_hash)
    with store._transaction(owner) as cur:
        cur.execute(
            "UPDATE strategy_research_requests SET updated_at=now()-interval '31 days' "
            "WHERE user_id=%s AND id=%s",
            (owner, complete_id),
        )
    # The documented dedupe window is bounded; expiry of a deleted tombstone
    # requires a fresh explicit POST to begin the same ID again.
    assert store.begin_request(owner, complete_id, input_hash)["created"] is True
    store.fail_request(owner, complete_id, "research_failed")
    assert store.request(owner, complete_id)["status"] == "failed"


@pytest.mark.skipif(
    not os.environ.get("OMNICIO_TEST_DATABASE_URL"), reason="ephemeral PostgreSQL is required"
)
def test_archive_capacity_and_all_pages_follow_paid_entitlement_and_survive_expiry(
    workspace_database,
):
    owner, store, archive = research_archive_case(workspace_database[0])
    other = user(workspace_database[0], account=True)
    initial = store.save_run(owner, **archive)
    with store._transaction(owner) as cur:
        cur.execute(
            "INSERT INTO strategy_research_runs (user_id,id,account_id,environment,"
            "strategy_version,evidence_version,data_hash,result,inputs) "
            "SELECT user_id,gen_random_uuid(),account_id,environment,strategy_version,"
            "evidence_version,data_hash,result,inputs FROM strategy_research_runs "
            "CROSS JOIN generate_series(1,199) WHERE user_id=%s AND id=%s",
            (owner, UUID(initial["id"])),
        )
    assert store.capacity(owner)["runs_used"] == 200
    with pytest.raises(ValueError, match="research_archive_capacity"):
        store.save_run(owner, **archive)
    ident = uuid4()
    with store._transaction(owner) as cur:
        cur.execute(
            "INSERT INTO billing_payments(user_id,id,order_id,terminal_key,amount_kopecks,"
            "period_days,offer_version,status,entitlement_from,entitlement_until) "
            "VALUES (%s,%s,%s,'test-only',100,30,'test-only','paid',"
            "now()-interval '1 day',now()+interval '1 day')",
            (owner, ident, "123456789-" + ident.hex),
        )
    paid = store.capacity(owner)
    assert paid["runs_limit"] == 400
    assert paid["storage_limit_bytes"] == 512 * 1024 * 1024
    added = store.save_run(owner, **archive)
    added_id = UUID(added["id"])
    page = store.runs_page(owner, limit=50)
    identifiers = {row["id"] for row in page["items"]}
    while page["next_cursor"] is not None:
        page = store.runs_page(owner, limit=50, cursor=UUID(page["next_cursor"]))
        ids = {row["id"] for row in page["items"]}
        assert not identifiers & ids
        identifiers.update(ids)
    assert len(identifiers) == 201
    with pytest.raises(ResearchNotFound, match="research_cursor_not_found"):
        store.runs_page(other, cursor=added_id)
    with store._transaction(owner) as cur:
        cur.execute(
            "UPDATE billing_payments SET entitlement_from=now()-interval '2 days',"
            "entitlement_until=now()-interval '1 day' WHERE user_id=%s AND id=%s",
            (owner, ident),
        )
    expired = store.capacity(owner)
    assert expired["runs_limit"] == 200
    assert expired["storage_limit_bytes"] == 256 * 1024 * 1024
    assert (
        store.run(owner, UUID(added["id"]))["result"]["data_hash"] == archive["result"]["data_hash"]
    )
    with pytest.raises(ValueError, match="research_archive_capacity"):
        store.save_run(owner, **archive)
    store.delete_run(owner, UUID(added["id"]))
    assert store.capacity(owner)["runs_used"] == 200


@pytest.mark.skipif(
    not os.environ.get("OMNICIO_TEST_DATABASE_URL"), reason="ephemeral PostgreSQL is required"
)
def test_research_size_upgrade_reapplies_and_enforces_real_jsonb_storage(workspace_database):
    database, dsn, schema = workspace_database
    owner, store, archive = research_archive_case(database)
    raw = evidence_document()
    raw["assets"][0]["bond_valuations"] = [
        {
            "time": (datetime.now(UTC) - timedelta(days=1100 - i)).isoformat(),
            "nominal_rub": "1000",
            "accrued_interest_open_rub": "0",
            "accrued_interest_close_rub": "1",
            "source_url": SOURCE + "?source=" + "x" * 1500,
        }
        for i in range(1000)
    ]
    record = store.save_evidence(owner, raw, expected_version=0)
    normalized_bytes = len(json.dumps(record["document"], ensure_ascii=False).encode())
    assert 1024 * 1024 < normalized_bytes < MAX_EVIDENCE_DOCUMENT_BYTES
    archive["evidence_version"] = record["version"]
    archive["inputs"]["source_payload"] = "x" * (5 * 1024 * 1024)
    saved = store.save_run(owner, **archive)
    migration = (
        Path(__file__).resolve().parents[1] / "migrations/0026_strategy_research_capacity.sql"
    )
    with psycopg.connect(dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema)))
        admin.execute(migration.read_text())
    assert store.run(owner, UUID(saved["id"]))["inputs"] == json.loads(
        json.dumps(archive["inputs"], default=str)
    )
    with store._transaction(owner) as cur:
        cur.execute(
            "SELECT octet_length(document::text) AS bytes FROM strategy_research_evidence "
            "WHERE user_id=%s",
            (owner,),
        )
        assert cur.fetchone()["bytes"] == normalized_bytes
    actual = store.capacity(owner)
    with (
        patch(
            "omnicio.billing.entitlement_limits",
            return_value={
                "research_runs": 200,
                "research_storage_bytes": actual["storage_used_bytes"] + 1,
            },
        ),
        pytest.raises(ValueError, match="research_archive_storage_capacity"),
    ):
        store.save_run(owner, **archive)
    assert store.capacity(owner)["runs_used"] == 1
    archive["inputs"]["source_payload"] = "x" * MAX_ARCHIVE_DOCUMENT_BYTES
    with pytest.raises(ValueError, match="research_archive_too_large"):
        store.save_run(owner, **archive)


@pytest.mark.skipif(
    not os.environ.get("OMNICIO_TEST_DATABASE_URL"), reason="ephemeral PostgreSQL is required"
)
def test_automatic_observed_fact_history_is_chronological_and_scoped_to_current_account(
    workspace_database,
):
    owner, store, archive = research_archive_case(workspace_database[0])
    first = {"value": "20", "available_at": START.isoformat(), "source_url": SOURCE}
    source = archive["inputs"]["assets"][0].setdefault("provider_observations", {})
    source["facts"] = {"roe_percent": first}
    store.save_run(owner, **archive)
    source["facts"] = {
        "roe_percent": {**first, "available_at": (START + timedelta(days=1)).isoformat()}
    }
    store.save_run(owner, **archive)
    changed = {**first, "value": "21", "available_at": (START + timedelta(days=2)).isoformat()}
    source["facts"] = {"roe_percent": changed}
    store.save_run(owner, **archive)
    observed = store.observed_facts(owner, account_id=str(owner), environment="prod")
    assert observed["a"]["roe_percent"] == [first, changed]
    assert store.observed_facts(owner, account_id="other-account", environment="prod") == {}
    assert store.observed_facts(owner, account_id=str(owner), environment="sandbox") == {}
    other = user(workspace_database[0], account=True)
    assert store.observed_facts(other, account_id=str(owner), environment="prod") == {}


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
