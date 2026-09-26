from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from hashlib import sha256
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
    _MAX_WATCHTOWER_ALERT_BLOB_BYTES,
    WatchtowerIncidentReadServiceV1,
    _bounded_rows,
    _lifecycle_reopened,
    _watchtower_alert,
    install_watchtower_incident_routes,
)

NOW = datetime(2026, 8, 13, 14, 0, tzinfo=timezone.utc)


def _digest(seed: str) -> str:
    return sha256(seed.encode()).hexdigest()


def _identity(kind: str, seed: str) -> str:
    return f"{kind}:v1:{_digest(seed)}"


INCIDENT = _identity("incident", "incident")
EVIDENCE = _identity("evidence", "evidence")
EVIDENCE_ALT = _identity("evidence", "evidence-alt")
DECISION = _identity("decision", "decision")
PLAN = _identity("plan", "plan")


class _Cursor:
    def __init__(self, rows: Sequence[Sequence[Any]]) -> None:
        self.rows = list(rows)

    def fetchall(self) -> list[Sequence[Any]]:
        return list(self.rows)

    def fetchone(self) -> Sequence[Any] | None:
        return self.rows[0] if self.rows else None


class _FixtureConnection:
    def __init__(self, payload: bytes | None, *, extra: bytes | None = None) -> None:
        self.payload = payload
        self.extra = extra
        self.queries: list[str] = []
        self.tenants: list[str] = []

    def execute(
        self,
        query: Any,
        params: Sequence[Any] | None = None,
        *,
        prepare: bool | None = None,
    ) -> _Cursor:
        del prepare
        text = str(query)
        self.queries.append(text)
        for value in tuple(params or ()):
            if isinstance(value, str) and value.startswith("tenant:"):
                self.tenants.append(value)
        if "FROM omni_cio_v10.incidents WHERE tenant_id" in text:
            return _Cursor(((INCIDENT, "portfolio-safe", "policy-safe", NOW),))
        if "FROM omni_cio_v10.incident_revisions r" in text:
            return _Cursor(
                (
                    (INCIDENT, 1, "open", NOW),
                    (INCIDENT, 2, "closed", NOW + timedelta(minutes=3)),
                    (INCIDENT, 3, "open", NOW + timedelta(minutes=8)),
                )
            )
        if "SELECT incident_id, incident_revision, evidence_id" in text:
            return _Cursor(
                (
                    (INCIDENT, 1, EVIDENCE),
                    (INCIDENT, 2, EVIDENCE),
                    (INCIDENT, 3, EVIDENCE),
                )
            )
        if "SELECT DISTINCT ie.incident_id" in text:
            rows: list[Sequence[Any]] = [
                (
                    INCIDENT,
                    EVIDENCE,
                    "system",
                    NOW - timedelta(minutes=1),
                    NOW,
                    NOW,
                    _digest("payload"),
                    None,
                    None,
                    None,
                    self.payload is not None,
                    self.payload,
                )
            ]
            if self.extra is not None:
                rows.append(
                    (
                        INCIDENT,
                        EVIDENCE_ALT,
                        "system",
                        NOW,
                        NOW,
                        NOW,
                        _digest("payload-alt"),
                        None,
                        None,
                        None,
                        True,
                        self.extra,
                    )
                )
            return _Cursor(rows)
        if "SELECT incident_id, decision_id, plan_id" in text:
            return _Cursor(((INCIDENT, DECISION, PLAN),))
        raise AssertionError(text)

    def transaction(self) -> Any:
        raise AssertionError("WP19 read service is read-only")


class _NoSession:
    def resolve(self, value: str | None, *, now: datetime) -> None:
        del value, now
        return None


class _OwnerSession:
    def resolve(
        self,
        value: str | None,
        *,
        now: datetime,
    ) -> SessionScopeV1 | None:
        del now
        if not value:
            return None
        return SessionScopeV1(
            user_id=OWNER_USER_ID,
            tenant_id=OWNER_TENANT_ID,
            expires_at=NOW + timedelta(hours=1),
        )


def _alert(*, fingerprint: str | None = None) -> bytes:
    provisional = WatchtowerAlertV1.model_construct(
        alert_id=_digest("provisional"),
        fingerprint_sha256=fingerprint or _digest("fingerprint"),
        kind=WatchtowerSignalKind.CONCENTRATION_BREACH,
        severity=ObservabilitySeverity.ERROR,
        subject_key="portfolio:owner",
        effective_at=NOW,
        evidence_sha256s=(_digest("payload"),),
        message_code="WATCHTOWER_CONCENTRATION_BREACH",
        requires_owner_attention=True,
        action=WatchtowerActionKind.REVIEW,
        execution_authorized=False,
        trading_methods=False,
    )
    value = WatchtowerAlertV1(
        **{
            **provisional.model_dump(mode="python"),
            "alert_id": watchtower_alert_id(provisional),
        }
    )
    return value.model_dump_json().encode()


def _read(connection: _FixtureConnection) -> dict[str, Any]:
    return WatchtowerIncidentReadServiceV1(
        connection,
        clock=lambda: NOW,
    ).read(tenant_id=OWNER_TENANT_ID)


def test_wp19_lifecycle_and_bounds_helpers() -> None:
    assert _lifecycle_reopened(("open", "closed", "open")) is True
    assert _lifecycle_reopened(("open", "acknowledged", "closed")) is False
    rows: list[Sequence[Any]] = [(1,), (2,), (3,)]
    assert _bounded_rows(rows[:2], maximum=2, reason="bounded") == rows[:2]
    try:
        _bounded_rows(rows, maximum=2, reason="bounded")
    except ValueError as exc:
        assert str(exc) == "bounded"
    else:
        raise AssertionError("overflow accepted")


def test_wp19_watchtower_payload_validation_is_bounded() -> None:
    assert _watchtower_alert(_alert()) is not None
    assert _watchtower_alert(b"not-json") is None
    oversized = b"x" * (_MAX_WATCHTOWER_ALERT_BLOB_BYTES + 1)
    assert _watchtower_alert(oversized) is None


def test_wp19_read_model_is_reopened_critical_and_bulk_scoped() -> None:
    connection = _FixtureConnection(_alert())
    payload = _read(connection)
    incident = payload["incidents"][0]
    assert payload["state"] == "READY"
    assert payload["counts"] == {
        "total": 1,
        "active": 1,
        "resolved": 0,
        "critical": 1,
        "reopened": 1,
        "missing_alert_metadata": 0,
    }
    assert incident["current_state"] == "open"
    assert incident["risk_impact"] == "OWNER_ATTENTION_REQUIRED"
    assert incident["subject"] == "portfolio:owner"
    assert incident["requested_action"] == "review"
    assert incident["dedup"]["state"] == "VERIFIED"
    assert incident["dedup"]["reopened"] is True
    assert [row["state"] for row in incident["timeline"]] == ["open", "closed", "open"]
    assert incident["links"] == {"decisions": [DECISION], "plans": [PLAN]}
    assert "payload" not in incident["evidence"][0]
    assert len(connection.queries) == 5
    assert sum("ANY(%s)" in query for query in connection.queries) == 4
    assert set(connection.tenants) == {OWNER_TENANT_ID}


def test_wp19_duplicate_and_conflict_fingerprints_are_fail_closed() -> None:
    fingerprint = _digest("same")
    same = _alert(fingerprint=fingerprint)
    duplicate = _read(_FixtureConnection(same, extra=same))["incidents"][0]
    assert duplicate["dedup"]["state"] == "VERIFIED"
    assert duplicate["dedup"]["fingerprint_sha256"] == fingerprint

    conflict = _read(
        _FixtureConnection(
            _alert(fingerprint=_digest("a")),
            extra=_alert(fingerprint=_digest("b")),
        )
    )
    incident = conflict["incidents"][0]
    assert conflict["state"] == "PARTIAL"
    assert incident["alert_metadata_state"] == "CONFLICT"
    assert incident["severity"] == "unknown"
    assert incident["risk_impact"] == "UNKNOWN"
    assert incident["subject"] is None
    assert incident["requested_action"] is None


def test_wp19_missing_alert_content_remains_partial() -> None:
    payload = _read(_FixtureConnection(None))
    incident = payload["incidents"][0]
    assert payload["state"] == "PARTIAL"
    assert payload["counts"]["missing_alert_metadata"] == 1
    assert incident["alert_metadata_state"] == "MISSING"
    assert incident["risk_impact"] == "UNKNOWN"
    assert incident["subject"] is None


def test_wp19_route_requires_session_and_uses_tenant_scope() -> None:
    denied = FastAPI()
    service = WatchtowerIncidentReadServiceV1(
        _FixtureConnection(_alert()),
        clock=lambda: NOW,
    )
    install_watchtower_incident_routes(
        denied,
        sessions=_NoSession(),
        service=service,
        now=lambda: NOW,
    )
    assert (
        TestClient(denied).get("/api/v10/web/watchtower-incidents").status_code == 401
    )

    connection = _FixtureConnection(_alert())
    allowed = FastAPI()
    install_watchtower_incident_routes(
        allowed,
        sessions=_OwnerSession(),
        service=WatchtowerIncidentReadServiceV1(connection, clock=lambda: NOW),
        now=lambda: NOW,
    )
    client = TestClient(allowed)
    client.cookies.set(SESSION_COOKIE, "test")
    response = client.get("/api/v10/web/watchtower-incidents")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert set(connection.tenants) == {OWNER_TENANT_ID}
