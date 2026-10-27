"""Synthetic provenance fixtures; not owner records and not a truth attestation."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import pytest
from backend.source_observability import freshness, lane_inventory, provenance_inventory, news_inventory

NOW = datetime(2026, 10, 27, 9, tzinfo=timezone.utc)

def stamp(delta=0):
    return (NOW + timedelta(seconds=delta)).isoformat()

def source(identifier="source-1", **changes):
    return {"id": identifier, "observed_at": stamp(-10), "expires_at": stamp(100), "published_at": stamp(-30), **changes}

def snapshot():
    return {"snapshot_id": "synthetic-snapshot", "as_of": stamp(-20),
        "position_coverage": {"complete": True}, "positions": [{"source_ids": ["source-1"]}],
        "sources": [source()], "events": {"items": [], "complete": True},
        "operations": {"items": [], "complete": True, "end": stamp(-20)},
        "payouts": {"items": [], "complete": True},
        "calendar": {"state": "available", "data": {"as_of": stamp(-10), "exchanges": []}}}

@pytest.mark.parametrize("age,state,current", [(0,"fresh",True),(899,"fresh",True),(900,"stale",False),(901,"stale",False),(-1,"future",False)])
def test_freshness_boundary(age,state,current):
    result=freshness(stamp(-age),now=NOW,max_age_seconds=900)
    assert (result["state"],result["current"])==(state,current)

@pytest.mark.parametrize("value,state", [(None,"missing"),("2026-10-27T09:00:00","invalid"),(False,"invalid"),(5,"invalid"),("bad","invalid"),("x"*65,"invalid")])
def test_invalid_clock_is_not_refreshed(value,state):
    result=freshness(value,now=NOW,max_age_seconds=900)
    assert result["state"]==state
    assert result["as_of"] is None

@pytest.mark.parametrize("maximum", [True,0,-1,31536001,1.5])
def test_bad_age_limit_rejected(maximum):
    observed=stamp()
    with pytest.raises(ValueError):
        freshness(observed,now=NOW,max_age_seconds=maximum)

def test_clock_requires_timezone_and_accepts_equivalent_offsets():
    observed=stamp()
    naive_now=NOW.replace(tzinfo=None)
    with pytest.raises(ValueError):
        freshness(observed,now=naive_now,max_age_seconds=900)
    assert freshness("2026-10-27T12:00:00+03:00",now=NOW,max_age_seconds=900)["age_seconds"]==0

def test_event_refresh_does_not_refresh_valuation_or_operations():
    data=snapshot();data["as_of"]=stamp(-4000)
    data["section_as_of"]={"events":stamp(-2),"operations":stamp(-2000),"payouts":stamp(-200)}
    data["event_monitor"]={"checked_at":stamp(),"complete":True}
    lanes={row["id"]:row for row in lane_inventory(data,now=NOW)}
    assert lanes["events"]["state"]=="current"
    assert lanes["valuation"]["state"]=="stale"
    assert lanes["operations"]["state"]=="stale"
    assert lanes["payouts"]["state"]=="current"

def test_explicit_missing_section_clock_cannot_fall_back_to_fresh_valuation():
    data=snapshot();data["section_as_of"]={"events":None}
    assert next(row for row in lane_inventory(data,now=NOW) if row["id"]=="events")["state"]=="missing"

def test_fresh_but_incomplete_collection_remains_incomplete():
    data=snapshot();data["operations"]["complete"]=False
    assert next(row for row in lane_inventory(data,now=NOW) if row["id"]=="operations")["state"]=="incomplete"

def test_latest_failed_attempt_is_separate_from_age_of_retained_evidence():
    data=snapshot();data["event_monitor"]={"calendar":"unavailable"}
    lane=next(row for row in lane_inventory(data,now=NOW) if row["id"]=="calendar")
    assert lane["latest_attempt"]=="unavailable"
    assert lane["freshness"]["as_of"]==stamp(-10)

@pytest.mark.parametrize("changes,issue", [
    ({"expires_at":stamp(-1)},"some_source_observations_stale"),
    ({"observed_at":stamp(1)},"source_clocks_in_future"),
    ({"published_at":stamp(1)},"source_clocks_in_future"),
    ({"expires_at":None},"source_clocks_invalid"),
    ({"published_at":"unknown"},"source_clocks_invalid"),
])
def test_source_clock_defects_are_visible(changes,issue):
    data=snapshot();data["sources"]=[source(**changes)]
    assert issue in provenance_inventory(data,now=NOW)["reasons"]

def test_missing_publication_is_unknown_not_an_invented_date():
    data=snapshot();data["sources"]=[source(published_at=None)]
    result=provenance_inventory(data,now=NOW)
    assert result["counts"]["publication_time_unknown"]==1
    assert result["financial_facts_verified"] is False

def test_duplicate_source_ids_with_different_content_are_not_resolved():
    data=snapshot();data["sources"].append(source(published_at=stamp(-40)))
    result=provenance_inventory(data,now=NOW)
    assert result["counts"]["conflicting_ids"]==1
    assert result["unresolved_reference_count"]==1
    assert result["reference_resolution_complete"] is False

def test_equal_source_observations_count_once_and_references_must_exist():
    data=snapshot();data["sources"]*=2
    assert provenance_inventory(data,now=NOW)["source_count"]==1
    data["positions"].append({"source_ids":["missing"]})
    assert provenance_inventory(data,now=NOW)["unresolved_reference_count"]==1

def test_reference_depth_and_registry_limits_fail_closed(monkeypatch):
    from backend import source_observability as module
    data=snapshot();monkeypatch.setattr(module,"MAX_REFERENCE_DEPTH",1)
    data["positions"]=[{"nested":{"more":{"source_ids":["source-1"]}}}]
    assert "source_reference_resource_limit" in provenance_inventory(data,now=NOW)["reasons"]
    monkeypatch.setattr(module,"MAX_SOURCE_ROWS",0)
    assert provenance_inventory(data,now=NOW)["state"]=="incomplete"

def test_news_duplicates_are_not_independent_confirmations():
    data=snapshot();item={"id":"story", "published_at":stamp(-20),"title":"Synthetic public story"}
    data["events"]["items"]=[item,deepcopy(item)]
    result=news_inventory(data,now=NOW)
    assert result["event_groups"]==1
    assert result["independent_confirmations"] is None
    data["events"]["items"].append({**item,"published_at":stamp(-19)})
    assert news_inventory(data,now=NOW)["conflicting_event_ids"]==1

def test_status_reads_never_mutate_snapshot():
    data=snapshot();before=deepcopy(data)
    lane_inventory(data,now=NOW);provenance_inventory(data,now=NOW);news_inventory(data,now=NOW)
    assert data==before
