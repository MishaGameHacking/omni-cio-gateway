"""Isolated strategy/account and cost controls, never real broker calls."""
from copy import deepcopy
from contextlib import closing
from datetime import datetime, timezone
from decimal import localcontext
import pytest

from backend import volume_state as state
from backend.strategy_profiles import catalogue, research_tuning
from backend.decision_views import project, prune_obsolete_events
from backend.ai_budget import MoneyLedger, BudgetDenied, micro_rub
from backend.tests.test_volume_workspace import fixture, config, activate
from backend.tests.test_portfolio_mandate import configured


def test_five_profiles_keep_stricter_limits_and_loss_capacity(fixture):
    cfg = configured()
    cfg["limits"]["issuer_percent"] = "2.5"
    cfg["mandate"]["loss_capacity_percent"] = "0"
    cfg["mandate"]["max_discretionary_turnover_percent"] = "0"
    active = {"config": cfg}
    original = deepcopy(active)
    result = catalogue(active, fixture["snapshot"])
    assert len(result["items"]) == 5
    assert len({item["id"] for item in result["items"]}) == 5
    for item in result["items"]:
        value = state.validate_config(item["config"])
        assert value["limits"]["issuer_percent"] == "2.5"
        assert value["mandate"]["loss_capacity_percent"] == "0"
        assert value["mandate"]["max_discretionary_turnover_percent"] == "0"
        assert "loss_capacity_required" in item["missing"]
    assert active == original
    assert result["paid_calls_on_read"] == 0


def test_two_accounts_are_not_chosen_arbitrarily(fixture):
    result = catalogue(None, fixture["snapshot"])
    assert all("account_required" in row["missing"] for row in result["items"])
    assert all(row["config"]["mandate"]["account_id"] == "" for row in result["items"])
    assert state.active_strategy(fixture["user"]["id"]) is None


def test_profiles_are_read_only_and_preserve_existing_strategy(fixture):
    activate(fixture, configured())
    before = state.active_strategy(fixture["user"]["id"])
    response = fixture["client"].get("/workspace/strategy")
    assert response.status_code == 200
    assert len(response.json()["profiles"]["items"]) == 5
    assert state.active_strategy(fixture["user"]["id"]) == before
    selected = response.json()["profiles"]["items"][0]["config"]
    preview = fixture["client"].post("/workspace/strategy/preview",
        json={"expected_version":1, "config":selected})
    assert preview.status_code == 200
    assert state.active_strategy(fixture["user"]["id"]) == before


def test_older_client_cannot_erase_tuning(fixture):
    cfg = configured()
    cfg["tuning"] = {"profile_id":"balanced", "enabled":True}
    activate(fixture, cfg)
    activate(fixture, config(), expected=1, request="legacy-profile-edit")
    assert state.active_strategy(fixture["user"]["id"])["config"]["tuning"] == cfg["tuning"]


def test_bounded_tuning_respects_class_and_never_lowers_risk(fixture):
    cfg = configured()
    cfg["tuning"] = {"profile_id":"coupon", "enabled":True}
    cfg["mandate"].update(asset_mode="bonds", bond_target_percent="100", share_target_percent="0")
    old = deepcopy(cfg)
    result = research_tuning(cfg, fixture["snapshot"])
    assert result["candidate_batch"] == 2
    assert result["asset_classes"] == ["bond"]
    assert result["limits_widened"] is False
    assert result["paid_model_required"] is False
    assert cfg == old


def test_profile_money_ignores_caller_decimal_precision(fixture):
    expected = catalogue({"config":configured()}, fixture["snapshot"])
    with localcontext() as ctx:
        ctx.prec = 3
        assert catalogue({"config":configured()}, fixture["snapshot"]) == expected


def test_current_and_pending_exclude_obsolete_duplicate_candidates():
    now = int(datetime.now(timezone.utc).timestamp())
    at = datetime.fromtimestamp(now-60, timezone.utc).isoformat()
    old = datetime.fromtimestamp(now-90000, timezone.utc).isoformat()
    rows = [{"instrument_uid":"a","as_of":at,"evidence_current":True},
            {"instrument_uid":"a","as_of":at,"evidence_current":False},
            {"instrument_uid":"b","as_of":at,"evidence_current":False},
            {"instrument_uid":"c","as_of":old,"evidence_current":True},
            {"instrument_uid":"d","as_of":None,"evidence_current":True}]
    output = project({"candidates":rows}, [], now)
    assert [x["instrument_uid"] for x in output["current"]] == ["a"]
    assert [x["instrument_uid"] for x in output["pending"]] == ["b"]
    assert output["hidden_obsolete_count"] == 3


def test_event_history_deduplicates_and_expires_without_refreshing_dates():
    now = int(datetime.now(timezone.utc).timestamp())
    current = datetime.fromtimestamp(now-60, timezone.utc).isoformat()
    old = datetime.fromtimestamp(now-31*86400, timezone.utc).isoformat()
    event = {"kind":"candidate_research","title":"Result","summary":"Checked","at":current}
    output = project({}, [event, dict(event), {**event,"title":"old","at":old}], now)
    assert output["history"] == [event]


def test_cleanup_preserves_recent_events_and_financial_history(fixture):
    from backend import app, autonomous_controller
    autonomous_controller.initialize()
    now = int(datetime.now(timezone.utc).timestamp())
    uid = fixture["user"]["id"]
    with closing(app.connect()) as db, db:
        for identifier, kind, at in [("old","candidate_research",now-31*86400),
            ("recent","candidate_research",now),("protected","financial_decision",now-31*86400)]:
            db.execute("INSERT INTO automation_events VALUES (?,?,?,?,?,?)",
                (uid, "connection", identifier, kind, "{}", at))
        assert prune_obsolete_events(db, uid, now) == 1
        assert {row[0] for row in db.execute("SELECT id FROM automation_events")} == {"recent","protected"}
    assert state.saved_snapshot(fixture["user"]) is not None


def test_monthly_budget_keeps_uncertain_reservation_across_months(fixture):
    from backend import app
    ledger=MoneyLedger(app.connect); ledger.initialize()
    first=int(datetime(2026,10,1,tzinfo=timezone.utc).timestamp())
    next_day=first+86400
    kwargs=dict(user_id=fixture["user"]["id"],route="route",model="model",
        ceiling=micro_rub("6"),user_cap=micro_rub("10"),project_cap=micro_rub("10"),
        user_month_cap=micro_rub("10"),project_month_cap=micro_rub("10"))
    ledger.reserve(key="first",at=first,**kwargs)
    assert ledger.settle("first",model="model",cost=micro_rub("6"),input_tokens=1,output_tokens=1)
    with pytest.raises(BudgetDenied,match="monthly_budget_exhausted"):
        ledger.reserve(key="second",at=next_day,**kwargs)
    ledger.reserve(key="november",at=int(datetime(2026,11,1,tzinfo=timezone.utc).timestamp()),**kwargs)
    ledger.uncertain("november")
    december = int(datetime(2026,12,1,tzinfo=timezone.utc).timestamp())
    with pytest.raises(BudgetDenied,match="monthly_budget_exhausted|user_budget_exhausted"):
        ledger.reserve(key="december",at=december,**kwargs)


@pytest.mark.parametrize("cap",[0,-1,True,"10"])
def test_invalid_monthly_cap_blocks_before_dispatch(fixture,cap):
    from backend import app
    ledger=MoneyLedger(app.connect); ledger.initialize()
    with pytest.raises(BudgetDenied,match="monthly_budget_disabled_or_invalid"):
        ledger.reserve(user_id=fixture["user"]["id"],key="invalid",route="route",model="model",
            ceiling=1,user_cap=10,project_cap=10,user_month_cap=cap)
