"""HTTP authority for explicit, version-bound execution; no provider orders."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from test_execution_service import _run

from omnicio.billing import BillingService
from omnicio.db import Database, UserRecord
from omnicio.execution import ExecutionStateError
from omnicio.execution_service import ExecutionServiceError, PortfolioExecutionService
from omnicio.execution_store import ExecutionLedgerError
from omnicio.main import CANONICAL_ORIGIN, app
from omnicio.security import session_digest
from omnicio.service import AuthService
from omnicio.tbank import TBankUnavailable
from omnicio.workspace_store import WorkspaceNotFound

USER = UserRecord(UUID(int=501), 501, "active", "user")
OTHER = UserRecord(UUID(int=502), 502, "active", "user")
REFERENCE = UUID(int=601)
HEADERS = {"origin": CANONICAL_ORIGIN, "X-Omnicio-Profile": "000000501"}
PLAN = {
    "expected_version": 4,
    "research_run_id": str(REFERENCE),
    "commission_bps": "10",
    "slippage_bps": "5",
    "mode": "shadow",
}
CONFIRM = {"proposal_version": 1, "proposal_hash": "a" * 64, "expected_strategy_version": 4}
MANDATE = {
    "expected_version": 4,
    "max_order_notional_rub": "1000",
    "max_daily_notional_rub": "2000",
    "expires_at": "2026-10-07T12:00:00Z",
}
WRITES = (
    ("/api/portfolio/proposals/plan", PLAN, "plan"),
    (f"/api/portfolio/proposals/{REFERENCE}/confirm", CONFIRM, "confirm"),
    (f"/api/portfolio/executions/{REFERENCE}/dispatch",
     {"expected_leg_id": str(REFERENCE)}, "dispatch"),
    ("/api/portfolio/live-execution/mandate", MANDATE, "create_mandate"),
)


@pytest.fixture
def execution_http():
    auth = Mock(spec=AuthService)
    auth.refresh_session.side_effect = lambda token: USER if token == "owner" else None
    auth.legal_versions.return_value = {"terms": "test"}
    database = Mock(spec=Database)
    database.has_legal_versions.return_value = True
    executor = Mock(spec=PortfolioExecutionService)
    for method in ("plan", "confirm", "dispatch", "create_mandate"):
        getattr(executor, method).return_value = {"fixture": method}
    with (
        patch.object(app.state, "auth_service", auth, create=True),
        patch.object(app.state, "database", database, create=True),
        patch.object(app.state, "execution_service", executor, create=True),
    ):
        client = TestClient(app, base_url=CANONICAL_ORIGIN, cookies={"omnicio_session": "owner"})
        try:
            yield client, auth, database, executor
        finally:
            client.close()


@pytest.mark.parametrize(("path", "body", "method"), WRITES)
def test_execution_requires_origin_profile_consent_and_server_session(
    execution_http, path, body, method
):
    client, auth, database, executor = execution_http
    action = getattr(executor, method)
    response = client.post(path, json=body, headers={"X-Omnicio-Profile": "000000501"})
    assert response.status_code == 403
    assert client.post(path, json=body, headers={"origin": CANONICAL_ORIGIN}).status_code == 409
    stale = {**HEADERS, "X-Omnicio-Profile": "000000502"}
    assert client.post(path, json=body, headers=stale).status_code == 409
    database.has_legal_versions.return_value = False
    assert client.post(path, json=body, headers=HEADERS).status_code == 409
    action.assert_not_called()
    database.has_legal_versions.return_value = True
    response = client.post(path, json=body, headers=HEADERS)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "private, no-store"
    assert action.call_args.args[0] == USER.id
    assert action.call_args.kwargs["session_digest"] == session_digest("owner")
    auth.refresh_session.return_value = OTHER
    auth.refresh_session.side_effect = [USER, OTHER]
    response = client.post(path, json=body, headers=HEADERS)
    assert response.status_code == 409
    assert "fixture" not in response.text


@pytest.mark.parametrize("kind", ["execution", "payment"])
def test_old_client_can_reconcile_only_with_current_authority(execution_http, kind):
    client, _, database, executor = execution_http
    billing = Mock(spec=BillingService)
    billing.reconcile.return_value = {"id": str(REFERENCE), "status": "pending"}
    executor.reconcile.return_value = (replace(_run(), id=REFERENCE, user_id=USER.id), ())
    path = (
        f"/api/portfolio/executions/{REFERENCE}/reconcile" if kind == "execution"
        else f"/api/billing/payments/{REFERENCE}/reconcile"
    )
    action = executor.reconcile if kind == "execution" else billing.reconcile
    headers = {**HEADERS, "X-Omnicio-Client-Build": "b" * 12}
    with (
        patch.object(app.state, "settings", SimpleNamespace(release_build="a" * 12), create=True),
        patch.object(app.state, "billing_service", billing, create=True),
    ):
        result = client.post(path, json={}, headers=headers)
        assert result.status_code == 200, result.text
        action.assert_called_once_with(USER.id, REFERENCE)
        action.reset_mock()
        assert client.post(path, json={}, headers={
            key: value for key, value in headers.items() if key != "origin"
        }).status_code == 403
        assert client.post(path, json={}, headers={
            **headers, "X-Omnicio-Profile": "000000502",
        }).status_code == 409
        database.has_legal_versions.return_value = False
        assert client.post(path, json={}, headers=headers).status_code == 409
        database.has_legal_versions.return_value = True
        action.assert_not_called()
        action.side_effect = (
            ExecutionLedgerError("execution_not_found") if kind == "execution"
            else WorkspaceNotFound("billing_payment_not_found")
        )
        assert client.post(path, json={}, headers=headers).status_code == 404
        client.cookies.clear()
        action.reset_mock()
        assert client.post(path, json={}, headers=headers).status_code == 401
        action.assert_not_called()
    executor.plan.assert_not_called()
    executor.confirm.assert_not_called()
    executor.dispatch.assert_not_called()
    billing.checkout.assert_not_called()


@pytest.mark.parametrize("path", [
    *(path for path, _, _ in WRITES),
    "/api/billing/checkout", "/api/anything/reconcile",
    "/api/portfolio/executions/not-a-uuid/reconcile",
    f"/api/portfolio/proposals/{REFERENCE}/reconcile",
    f"/api/billing/payments/{REFERENCE}/reconcile/extra",
])
def test_old_client_reconciliation_exception_cannot_create_work(execution_http, path):
    client, _, _, executor = execution_http
    with patch.object(
        app.state, "settings", SimpleNamespace(release_build="a" * 12), create=True,
    ):
        response = client.post(
            path, json={}, headers={**HEADERS, "X-Omnicio-Client-Build": "b" * 12},
        )
    assert response.status_code == 409
    assert response.json()["detail"] == "client_build_changed"
    assert executor.mock_calls == []


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("expected_version", True),
        ("expected_version", "4"),
        ("expected_version", 0),
        ("commission_bps", "NaN"),
        ("slippage_bps", "Infinity"),
        ("research_run_id", "not-a-uuid"),
        ("mode", "automatic"),
        ("user_id", str(OTHER.id)),
        ("session_digest", "forged"),
    ),
)
def test_plan_rejects_ambiguous_or_authority_bearing_input(execution_http, field, value):
    client, _, _, executor = execution_http
    response = client.post(
        "/api/portfolio/proposals/plan", json={**PLAN, field: value}, headers=HEADERS
    )
    assert response.status_code == 422
    executor.plan.assert_not_called()


@pytest.mark.parametrize(
    ("error", "code"),
    (
        (ExecutionServiceError("execution_proposal_expired"), 409),
        (ExecutionStateError("execution_quote_incomplete_or_stale"), 409),
        (TBankUnavailable("private provider detail"), 503),
    ),
)
def test_execution_conflicts_and_unavailability_are_actionable(execution_http, error, code):
    client, _, _, executor = execution_http
    executor.plan.side_effect = error
    response = client.post("/api/portfolio/proposals/plan", json=PLAN, headers=HEADERS)
    assert response.status_code == code
    assert "private provider detail" not in response.text


@pytest.mark.parametrize(("path", "body", "method", "error"), (
    (f"/api/portfolio/proposals/{REFERENCE}/confirm", CONFIRM, "confirm",
     ExecutionLedgerError("execution_proposal_not_found")),
    (f"/api/portfolio/executions/{REFERENCE}/dispatch",
     {"expected_leg_id": str(REFERENCE)}, "dispatch",
     ExecutionServiceError("execution_leg_not_found")),
))
def test_missing_or_foreign_execution_objects_use_actual_store_error_codes(
    execution_http, path, body, method, error,
):
    client, _, _, executor = execution_http
    getattr(executor, method).side_effect = error
    response = client.post(path, json=body, headers=HEADERS)
    assert response.status_code == 404
    assert response.json()["detail"] == error.code


def test_dispatch_does_not_accept_order_replacement_or_client_costs(execution_http):
    client, _, _, executor = execution_http
    response = client.post(
        f"/api/portfolio/executions/{REFERENCE}/dispatch",
        json={"lots": 100, "price": "1"},
        headers=HEADERS,
    )
    assert response.status_code == 422
    executor.dispatch.assert_not_called()


def test_mandate_requires_timezone_and_confirmation_exact_hash(execution_http):
    client, _, _, executor = execution_http
    response = client.post(
        "/api/portfolio/live-execution/mandate",
        json={
            **MANDATE,
            "expires_at": "2026-10-07T12:00:00",
        },
        headers=HEADERS,
    )
    assert response.status_code == 422
    executor.create_mandate.assert_not_called()
    response = client.post(
        f"/api/portfolio/proposals/{REFERENCE}/confirm",
        json={
            **CONFIRM,
            "proposal_hash": "а" * 64,
        },
        headers=HEADERS,
    )
    assert response.status_code == 422
    executor.confirm.assert_not_called()
