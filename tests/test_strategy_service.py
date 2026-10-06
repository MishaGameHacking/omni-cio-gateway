"""Exercise the HTTP/session boundary, not browser-supplied capital or account IDs."""

from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from test_strategy_assessment import document, position, snapshot

from omnicio import main
from omnicio.broker import (
    AnalysisSource,
    BrokerAssessmentBusy,
    BrokerConnectionError,
    BrokerConnectionStatus,
    BrokerNotConnected,
    BrokerObservationBundle,
    BrokerService,
)
from omnicio.db import Database, UserRecord
from omnicio.portfolio_store import PortfolioStore
from omnicio.strategy_service import current_account_assessment
from omnicio.tbank import TBankPortfolio, TBankPositions, TBankTokenRejected, TBankUnavailable

A, B = UUID(int=501), UUID(int=502)
PATH = "/api/profile/strategy/account-assessment"
ORIGIN = {"Origin": "https://omnicio.ru", "X-Omnicio-Profile": "000000123"}
BODY = {"expected_public_id": "000000123", "expected_version": 4}


@pytest.fixture
def runtime(monkeypatch):
    database = Mock(spec=Database)
    database.has_legal_versions.return_value = True
    auth = Mock()
    users = {"a": UserRecord(A, 123, "active", "user"), "b": UserRecord(B, 456, "active", "user")}
    auth.refresh_session.side_effect = lambda token: users.get(token)
    store = Mock(spec=PortfolioStore)
    selection = {"version": 4, "document": document()}
    store.current_strategy_draft.return_value = selection
    store.latest_balancing_context.return_value = None
    broker = Mock(spec=BrokerService)
    now = datetime.now(UTC)
    connection = BrokerConnectionStatus(True, "prod", "synthetic-a", "Owned account", now)
    broker.status.return_value = connection
    bundle = BrokerObservationBundle(
        "synthetic-a",
        "Owned account",
        "prod",
        now,
        Mock(spec=TBankPortfolio),
        Mock(spec=TBankPositions),
        (),
        snapshot(position()),
        (
            AnalysisSource(
                "portfolio",
                "T-Invest",
                "https://developer.tbank.ru/invest/",
                ("GetPortfolio", "GetPositions"),
                now,
                "available",
            ),
        ),
    )
    broker.strategy_observation.return_value = (bundle, {})
    monkeypatch.setattr(main, "service", lambda request: auth)
    monkeypatch.setattr(main, "portfolio_store", lambda request: store)
    monkeypatch.setattr(main, "broker_service", lambda request: broker)
    monkeypatch.setattr(main.app.state, "database", database, raising=False)
    return users, store, broker, bundle, connection


def client(token="a"):
    return TestClient(main.app, cookies={"omnicio_session": token})


def test_actual_account_is_session_bound_exact_and_read_only(runtime):
    _, store, broker, _, _ = runtime
    before = deepcopy(store.current_strategy_draft.return_value)
    response = client().post(PATH + f"?account_id=other&user_id={B}", headers=ORIGIN, json=BODY)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["public_id"] == "000000123"
    assert payload["account_id"] == "synthetic-a"
    assert payload["nav_rub"] == "100000"
    assert payload["cash"]["allocation_capacity_rub"] == "50000"
    assert payload["strategy_version"] == 4
    assert payload["execution_enabled"] is False
    assert payload["proposed_trades"] == []
    assert payload["rating_source"]["complete"] is False
    assert response.headers["Cache-Control"] == "private, no-store"
    assert store.current_strategy_draft.return_value == before
    assert [call.args[0] for call in store.current_strategy_draft.call_args_list] == [A, A]
    broker.strategy_observation.assert_called_once_with(A)
    assert {call[0] for call in broker.mock_calls} <= {"status", "strategy_observation"}
    assert {call[0] for call in store.mock_calls} <= {
        "current_strategy_draft",
        "latest_balancing_context",
    }


@pytest.mark.parametrize(
    "extra",
    [
        {"account_id": "other"},
        {"user_id": str(B)},
        {"nav_rub": "100000000"},
        {"lot_cost_rub": "1"},
        {"document": document()},
        {"expected_version": True},
        {"expected_version": "4"},
        {"expected_version": 0},
    ],
)
def test_client_cannot_supply_account_capital_or_substitute_strategy(runtime, extra):
    _, store, broker, _, _ = runtime
    response = client().post(PATH, headers=ORIGIN, json={**BODY, **extra})
    assert response.status_code == 422
    store.current_strategy_draft.assert_not_called()
    broker.strategy_observation.assert_not_called()


@pytest.mark.parametrize(
    "token,headers,body,status",
    [
        ("unknown", ORIGIN, BODY, 401),
        ("b", ORIGIN, BODY, 409),
        ("a", {**ORIGIN, "Origin": "https://evil.example"}, BODY, 403),
        ("a", ORIGIN, {**BODY, "expected_public_id": "000000456"}, 409),
    ],
)
def test_owner_and_origin_are_checked_before_network(runtime, token, headers, body, status):
    _, store, broker, _, _ = runtime
    response = client(token).post(PATH, headers=headers, json=body)
    assert response.status_code == status
    store.current_strategy_draft.assert_not_called()
    broker.strategy_observation.assert_not_called()


def test_second_owner_uses_only_second_owner_context(runtime):
    _, store, broker, bundle, connection = runtime
    broker.status.return_value = replace(connection, account_id="synthetic-b")
    broker.strategy_observation.return_value = (replace(bundle, account_id="synthetic-b"), {})
    response = client("b").post(
        PATH,
        headers={**ORIGIN, "X-Omnicio-Profile": "000000456"},
        json={**BODY, "expected_public_id": "000000456"},
    )
    assert response.status_code == 200
    assert response.json()["account_id"] == "synthetic-b"
    assert "synthetic-a" not in response.text
    broker.strategy_observation.assert_called_once_with(B)
    assert all(call.args[0] == B for call in store.current_strategy_draft.call_args_list)


@pytest.mark.parametrize("change", ["strategy_version", "strategy_hash", "account", "revocation"])
def test_mutation_during_read_never_releases_stale_or_revoked_data(runtime, change):
    users, store, broker, bundle, connection = runtime
    initial = deepcopy(store.current_strategy_draft.return_value)

    def read(owner):
        assert owner == A
        if change.startswith("strategy"):
            changed = deepcopy(initial)
            if change == "strategy_version":
                changed["version"] += 1
            else:
                changed["document"]["profile"]["reserve_rub"] = "30000"
            store.current_strategy_draft.return_value = changed
        elif change == "account":
            broker.status.return_value = replace(connection, account_id="synthetic-b")
        else:
            users.pop("a")
        return bundle, {}

    broker.strategy_observation.side_effect = read
    response = client().post(PATH, headers=ORIGIN, json=BODY)
    assert response.status_code in {401, 409, 503}
    assert "nav_rub" not in response.text
    assert "synthetic-a" not in response.text
    assert response.headers["Cache-Control"] == "private, no-store"


@pytest.mark.parametrize(
    "error,status",
    [
        (BrokerNotConnected("hidden account"), 409),
        (BrokerConnectionError("hidden credential"), 503),
        (TBankUnavailable("hidden upstream"), 503),
        (TBankTokenRejected("hidden token"), 409),
        (BrokerAssessmentBusy("busy"), 429),
    ],
)
def test_failure_is_safe_and_never_fabricates_zero(runtime, error, status):
    _, _, broker, _, _ = runtime
    broker.strategy_observation.side_effect = error
    response = client().post(PATH, headers=ORIGIN, json=BODY)
    assert response.status_code == status
    assert "hidden" not in response.text
    assert "nav_rub" not in response.text
    if status == 429:
        assert response.headers["Retry-After"] == "10"


@pytest.mark.parametrize("delta", [timedelta(minutes=-6), timedelta(minutes=1)])
def test_stale_or_future_snapshot_is_not_refreshed_by_response_time(runtime, delta):
    _, _, broker, bundle, _ = runtime
    broker.strategy_observation.return_value = (
        replace(bundle, refreshed_at=datetime.now(UTC) + delta),
        {},
    )
    response = client().post(PATH, headers=ORIGIN, json=BODY)
    assert response.status_code == 503
    assert "nav_rub" not in response.text


def test_missing_draft_has_no_network_or_default_save(runtime):
    _, store, broker, _, _ = runtime
    store.current_strategy_draft.return_value = None
    result = current_account_assessment(user_id=A, expected_version=4, store=store, broker=broker)
    assert result == {"status": "draft_required", "execution_enabled": False}
    broker.strategy_observation.assert_not_called()
    store.save_strategy_draft.assert_not_called()


@pytest.mark.parametrize("prefix", ["issuer", "mapping", "group"])
@pytest.mark.parametrize("bad", ["missing", "naive", "future", "stale"])
def test_relationship_times_are_independent_and_never_borrowed(runtime, prefix, bad):
    _, store, _, _, _ = runtime
    now = datetime.now(UTC)
    row = {"instrument_uid": "bond-a", "issuer_id": "issuer", "group_id": "group"}
    for name in ("issuer", "mapping", "group"):
        row[name + "_source_url"] = "https://issuer.example/" + name
        row[name + "_verified_at"] = now
        row[name + "_effective_at"] = now
    invalid = {
        "missing": None,
        "naive": now.replace(tzinfo=None),
        "future": now + timedelta(days=1),
        "stale": now - timedelta(days=31),
    }[bad]
    row[prefix + "_verified_at"] = invalid
    store.latest_balancing_context.return_value = {"account_id": "synthetic-a", "holdings": [row]}
    response = client().post(PATH, headers=ORIGIN, json=BODY)
    assert response.status_code == 200
    values = {item["key"]: item["state"] for item in response.json()["checks"]}
    assert values["max_group_percent"] == "unknown"
    if prefix != "group":
        assert values["max_issuer_percent"] == "unknown"


def test_relationship_producer_preserves_three_sources(runtime):
    from omnicio.strategy_service import _issuer_mappings

    now = datetime.now(UTC)
    row = {"instrument_uid": "bond-a", "issuer_id": "issuer", "group_id": "group"}
    for name in ("issuer", "mapping", "group"):
        row[name + "_source_url"] = "https://issuer.example/" + name
        row[name + "_verified_at"] = now
        row[name + "_effective_at"] = now
    context = {"account_id": "synthetic-a", "holdings": [row]}
    (mapping,) = _issuer_mappings(context, "synthetic-a")
    assert mapping.source_url.endswith("/issuer")
    assert mapping.mapping_source_url.endswith("/mapping")
    assert mapping.group_source_url.endswith("/group")
    assert _issuer_mappings(context, "synthetic-b") == ()
