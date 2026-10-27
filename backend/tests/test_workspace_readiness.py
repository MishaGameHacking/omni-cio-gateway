"""Hierarchy, read-only status, scope isolation and API regression scenarios."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import json
import pytest
from fastapi.testclient import TestClient
from backend import app as backend
from backend import application_hierarchy as graph, workspace_readiness as readiness
from backend.tests.test_volume_workspace import fixture

NOW=datetime(2026,10,27,9,tzinfo=timezone.utc)


def test_hierarchy_has_every_stage_and_a_valid_dependency_order():
    order=graph.dependency_order()
    assert set(order)=={f"N{i:02d}" for i in range(12)}
    positions={key:i for i,key in enumerate(order)}
    for node in graph.COMPONENTS:
        assert all(positions[parent]<positions[node.identifier] for parent in node.dependencies)
    assert graph.hierarchy()["all_stages_complete"] is False
    assert all(node["completion_percentage"] is None for node in graph.hierarchy()["components"])

@pytest.mark.parametrize("kind",["duplicate","unknown","cycle","duplicate_edge"])
def test_invalid_dependency_graph_is_rejected(kind):
    nodes=list(graph.COMPONENTS)
    if kind=="duplicate":nodes.append(nodes[0])
    elif kind=="unknown":nodes[0]=replace(nodes[0],dependencies=("N99",))
    elif kind=="cycle":nodes[0]=replace(nodes[0],dependencies=("N11",))
    else:nodes[1]=replace(nodes[1],dependencies=("N00","N00"))
    with pytest.raises(ValueError):graph.dependency_order(tuple(nodes))

def test_module_paths_refer_to_actual_files():
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    assert all((root/path).is_file() for node in graph.COMPONENTS for path in node.source_paths)

@pytest.mark.parametrize("connected",[True,False])
def test_readiness_never_grants_financial_execution(connected):
    value=readiness.build_status(None,None,connected=connected,now=NOW)
    assert value["real_orders_enabled"] is False
    assert value["complete_autonomous_portfolio"] is False
    assert value["accounting"]["live_performance_calculated"] is False
    assert value["accounting"]["missing_data_is_zero"] is False
    assert value["network_started_by_read"] is False
    assert len(value["blockers"])>=7

def test_disconnected_broker_cannot_inherit_previous_snapshot():
    value=readiness.build_status({"snapshot_id":"old-connection","as_of":NOW.isoformat()},None,connected=False,now=NOW)
    assert value["snapshot_id"] is None and value["valuation_as_of"] is None

def test_new_evaluation_clock_does_not_relabel_old_valuation():
    old="2020-01-01T00:00:00+00:00"
    snapshot={"snapshot_id":"synthetic", "as_of":old,"positions":[],"accounts":[],"sources":[]}
    original=deepcopy(snapshot)
    value=readiness.build_status(snapshot,None,connected=True,now=NOW)
    assert value["valuation_as_of"]==old and snapshot==original
    assert value["evaluated_at"]==NOW.isoformat()

def test_missing_selected_account_is_not_a_confirmed_mandate():
    strategy={"version":3,"config":{"mandate":{"account_id":"other"}}}
    value=readiness.build_status({"accounts":[{"id":"owned"}],"positions":[]},strategy,connected=True,now=NOW)
    assert value["mandate"]["selected_account_in_snapshot"] is False
    assert "mandate_account_not_in_snapshot" in {row["code"] for row in value["blockers"]}

def test_authenticated_status_uses_saved_snapshot_without_network_or_writes(fixture,monkeypatch):
    from backend import portfolio_details
    import httpx
    def forbidden(*args,**kwargs):raise AssertionError("status initiated external collection")
    monkeypatch.setattr(portfolio_details,"BrokerReader",forbidden)
    monkeypatch.setattr(httpx,"Client",forbidden)
    statements=[];connect=backend.connect
    def read_connection():
        db=connect();db.set_trace_callback(statements.append);return db
    monkeypatch.setattr(backend,"connect",read_connection)
    response=fixture["client"].get("/workspace/system-readiness")
    assert response.status_code==200
    value=response.json()
    assert value["snapshot_id"]==fixture["snapshot"]["snapshot_id"]
    assert not any(sql.lstrip().split()[0].upper() in {"INSERT","UPDATE","DELETE","CREATE","ALTER","REPLACE","DROP"} for sql in statements if sql.strip())
    assert "synthetic-encrypted-placeholder" not in response.text
    assert "broker_key" not in response.text

def test_readiness_isolated_between_users_and_connection_changes(fixture,monkeypatch):
    backend.app.dependency_overrides[backend.current_user]=lambda:fixture["other"]
    assert fixture["client"].get("/workspace/system-readiness").json()["snapshot_id"] is None
    changed=dict(fixture["user"]);changed["tinvest_token_encrypted"]=b"synthetic-changed-token"
    backend.app.dependency_overrides[backend.current_user]=lambda:changed
    assert fixture["client"].get("/workspace/system-readiness").json()["snapshot_id"] is None

def test_status_endpoint_requires_authentication(fixture):
    backend.app.dependency_overrides.pop(backend.current_user,None)
    assert fixture["client"].get("/workspace/system-readiness").status_code==401

def test_workspace_exposes_additive_capabilities_without_enabling_execution(fixture):
    response=fixture["client"].get("/workspace")
    assert response.status_code==200
    value=response.json()
    assert value["capabilities"]["system_readiness"] is True
    assert value["capabilities"]["public_sources"] is True
    assert value["capabilities"]["cash_ledger"] is True
    assert value["sections"]["system"]["data"]["real_orders_enabled"] is False
    assert value["capabilities"]["read_only_broker"] is True
