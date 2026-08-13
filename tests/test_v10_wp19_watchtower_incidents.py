from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from omni_cio.contracts.v1.domain import OWNER_TENANT_ID, OWNER_USER_ID
from omni_cio.contracts.v1.observability import ObservabilitySeverity
from omni_cio.contracts.v1.watchtower import (
    WatchtowerActionKind,
    WatchtowerAlertV1,
    WatchtowerSignalKind,
    watchtower_alert_id,
)
from omni_cio.web.api_v1 import SESSION_COOKIE
from omni_cio.web.session_v1 import SessionScopeV1
from omni_cio.web.watchtower_incidents_v1 import (
    WatchtowerIncidentReadServiceV1,
    _bounded_rows,
    _lifecycle_reopened,
    _watchtower_alert,
    install_watchtower_incident_routes,
)

NOW = datetime(2026, 8, 13, 14, 0, tzinfo=timezone.utc)
INCIDENT = "incident:v1:" + "1" * 64
EVIDENCE = "evidence:v1:" + "2" * 64
EVIDENCE_ALT = "evidence:v1:" + "9" * 64
DECISION = "decision:v1:" + "3" * 64
PLAN = "plan:v1:" + "4" * 64


class _Cursor:
    def __init__(self, rows: Sequence[Sequence[Any]]) -> None:
        self._rows = list(rows)
        self.rowcount = len(self._rows)

    def fetchall(self) -> list[Sequence[Any]]:
        return list(self._rows)

    def fetchone(self) -> Sequence[Any] | None:
        return self._rows[0] if self._rows else None


class _FixtureConnection:
    def __init__(
        self,
        alert_payload: bytes | None,
        *,
        additional_alert_payload: bytes | None = None,
    ) -> None:
        self.alert_payload = alert_payload
        self.additional_alert_payload = additional_alert_payload
        self.seen_tenants: list[str] = []

    def execute(
        self,
        query: Any,
        params: Sequence[Any] | None = None,
        *,
        prepare: bool | None = None,
    ) -> _Cursor:
        del prepare
        text = str(query)
        values = tuple(params or ())
        if values and isinstance(values[0], str) and values[0].startswith("tenant:"):
            self.seen_tenants.append(values[0])
        if "FROM omni_cio_v10.incidents WHERE tenant_id" in text:
            return _Cursor(((INCIDENT, "portfolio-safe", "policy-safe", NOW),))
        if "FROM omni_cio_v10.incident_revisions r" in text:
            return _Cursor(
                (
                    (1, "open", NOW),
                    (2, "closed", NOW + timedelta(minutes=3)),
                    (3, "open", NOW + timedelta(minutes=8)),
                )
            )
        if (
            "FROM omni_cio_v10.incident_evidence" in text
            and "incident_revision" in text
        ):
            return _Cursor(((EVIDENCE,),))
        if "SELECT DISTINCT e.evidence_id" in text:
            rows: list[Sequence[Any]] = [
                (
                    EVIDENCE,
                    "system",
                    NOW - timedelta(minutes=1),
                    NOW,
                    NOW,
                    "5" * 64,
                    None,
                    None,
                    None,
                    "application/json" if self.alert_payload else None,
                    "WatchtowerAlertV1" if self.alert_payload else None,
                    self.alert_payload,
                )
            ]
            if self.additional_alert_payload is not None:
                rows.append(
                    (
                        EVIDENCE_ALT,
                        "system",
                        NOW - timedelta(seconds=30),
                        NOW,
                        NOW,
                        "a" * 64,
                        None,
                        None,
                        None,
                        "application/json",
                        "WatchtowerAlertV1",
                        self.additional_alert_payload,
                    )
                )
            return _Cursor(rows)
        if "SELECT decision_id, plan_id FROM omni_cio_v10.journal" in text:
            return _Cursor(((DECISION, PLAN),))
        raise AssertionError(f"unexpected query: {text}")

    def transaction(self) -> Any:
        raise AssertionError("WP19 read service must not start write transactions")


class _NoSession:
    def resolve(self, token: str | None, *, now: datetime) -> None:
        del token, now
        return None


class _OwnerSession:
    def resolve(
        self,
        token: str | None,
        *,
        now: datetime,
    ) -> SessionScopeV1 | None:
        del now
        if not token:
            return None
        return SessionScopeV1(
            user_id=OWNER_USER_ID,
            tenant_id=OWNER_TENANT_ID,
            expires_at=NOW + timedelta(hours=1),
        )


def _alert_payload(*, fingerprint: str = "6" * 64) -> bytes:
    provisional = WatchtowerAlertV1.model_construct(
        alert_id="0" * 64,
        fingerprint_sha256=fingerprint,
        kind=WatchtowerSignalKind.CONCENTRATION_BREACH,
        severity=ObservabilitySeverity.ERROR,
        subject_key="portfolio:owner",
        effective_at=NOW,
        evidence_sha256s=("5" * 64,),
        message_code="WATCHTOWER_CONCENTRATION_BREACH",
        requires_owner_attention=True,
        action=WatchtowerActionKind.REVIEW,
        execution_authorized=False,
        trading_methods=False,
    )
    alert = WatchtowerAlertV1(
        **{
            **provisional.model_dump(mode="python"),
            "alert_id": watchtower_alert_id(provisional),
        }
    )
    return alert.model_dump_json().encode("utf-8")


def test_wp19_reopened_lifecycle_is_explicit() -> None:
    assert _lifecycle_reopened(("open", "closed", "open")) is True
    assert _lifecycle_reopened(("open", "acknowledged", "closed")) is False


def test_wp19_only_fully_valid_watchtower_payload_projects_alert_metadata() -> None:
    assert _watchtower_alert(_alert_payload()) is not None
    assert _watchtower_alert(b'{"alert_id":"not-canonical"}') is None
    assert _watchtower_alert(b"not-json") is None


def test_wp19_nested_read_bound_rejects_overflow() -> None:
    rows: list[Sequence[Any]] = [(1,), (2,), (3,)]
    assert _bounded_rows(rows[:2], maximum=2, reason="bounded") == rows[:2]
    try:
        _bounded_rows(rows, maximum=2, reason="bounded")
    except ValueError as exc:
        assert str(exc) == "bounded"
    else:
        raise AssertionError("WP19 accepted an over-limit nested read")


def test_wp19_read_model_explains_reopened_critical_incident_and_downstream_links() -> None:
    connection = _FixtureConnection(_alert_payload())
    payload = WatchtowerIncidentReadServiceV1(
        connection,
        clock=lambda: NOW,
    ).read(tenant_id=OWNER_TENANT_ID)

    assert payload["state"] == "READY"
    assert payload["counts"] == {
        "total": 1,
        "active": 1,
        "resolved": 0,
        "critical": 1,
        "reopened": 1,
        "missing_alert_metadata": 0,
    }
    incident = payload["incidents"][0]
    assert incident["current_state"] == "open"
    assert incident["lifecycle_state"] == "ACTIVE"
    assert incident["severity"] == "error"
    assert incident["risk_impact"] == "CRITICAL"
    assert incident["subject"] == "portfolio:owner"
    assert incident["message_code"] == "WATCHTOWER_CONCENTRATION_BREACH"
    assert incident["requested_action"] == "review"
    assert incident["dedup"]["state"] == "VERIFIED"
    assert incident["dedup"]["reopened"] is True
    assert [row["state"] for row in incident["timeline"]] == [
        "open",
        "closed",
        "open",
    ]
    assert incident["links"] == {"decisions": [DECISION], "plans": [PLAN]}
    assert incident["evidence"][0]["watchtower_alert_verified"] is True
    assert "payload" not in incident["evidence"][0]
    assert set(connection.seen_tenants) == {OWNER_TENANT_ID}


def test_wp19_duplicate_same_fingerprint_stays_one_verified_incident() -> None:
    payload = _alert_payload(fingerprint="7" * 64)
    result = WatchtowerIncidentReadServiceV1(
        _FixtureConnection(payload, additional_alert_payload=payload),
        clock=lambda: NOW,
    ).read(tenant_id=OWNER_TENANT_ID)

    assert result["state"] == "READY"
    assert result["counts"]["total"] == 1
    incident = result["incidents"][0]
    assert incident["dedup"]["state"] == "VERIFIED"
    assert incident["dedup"]["fingerprint_sha256"] == "7" * 64


def test_wp19_conflicting_fingerprints_fail_closed() -> None:
    result = WatchtowerIncidentReadServiceV1(
        _FixtureConnection(
            _alert_payload(fingerprint="7" * 64),
            additional_alert_payload=_alert_payload(fingerprint="8" * 64),
        ),
        clock=lambda: NOW,
    ).read(tenant_id=OWNER_TENANT_ID)

    assert result["state"] == "PARTIAL"
    assert result["counts"]["critical"] == 0
    assert result["counts"]["missing_alert_metadata"] == 1
    incident = result["incidents"][0]
    assert incident["alert_metadata_state"] == "CONFLICT"
    assert incident["dedup"]["state"] == "CONFLICT"
    assert incident["dedup"]["fingerprint_sha256"] is None
    assert incident["severity"] == "unknown"
    assert incident["risk_impact"] == "UNKNOWN"
    assert incident["subject"] is None
    assert incident["message_code"] is None
    assert incident["requested_action"] is None


def test_wp19_missing_alert_content_is_partial_and_never_fabricates_reason() -> None:
    payload = WatchtowerIncidentReadServiceV1(
        _FixtureConnection(None),
        clock=lambda: NOW,
    ).read(tenant_id=OWNER_TENANT_ID)

    assert payload["state"] == "PARTIAL"
    assert payload["counts"]["missing_alert_metadata"] == 1
    incident = payload["incidents"][0]
    assert incident["severity"] == "unknown"
    assert incident["risk_impact"] == "UNKNOWN"
    assert incident["subject"] is None
    assert incident["message_code"] is None
    assert incident["requested_action"] is None
    assert incident["alert_metadata_state"] == "MISSING"
    assert incident["dedup"]["state"] == "MISSING"


def test_wp19_route_requires_server_side_session() -> None:
    app = FastAPI()
    service = WatchtowerIncidentReadServiceV1(
        _FixtureConnection(_alert_payload()),
        clock=lambda: NOW,
    )
    install_watchtower_incident_routes(
        app,
        sessions=_NoSession(),
        service=service,
        now=lambda: NOW,
    )

    response = TestClient(app).get("/api/v10/web/watchtower-incidents")

    assert response.status_code == 401
    assert response.json()["detail"] == "AUTHENTICATION_REQUIRED"


def test_wp19_route_uses_session_tenant_and_returns_no_store() -> None:
    connection = _FixtureConnection(_alert_payload())
    app = FastAPI()
    service = WatchtowerIncidentReadServiceV1(connection, clock=lambda: NOW)
    install_watchtower_incident_routes(
        app,
        sessions=_OwnerSession(),
        service=service,
        now=lambda: NOW,
    )

    response = TestClient(app).get(
        "/api/v10/web/watchtower-incidents",
        cookies={SESSION_COOKIE: "synthetic-session"},
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["counts"]["total"] == 1
    assert set(connection.seen_tenants) == {OWNER_TENANT_ID}
