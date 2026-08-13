from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timezone
import json
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from omni_cio.contracts.v1.watchtower import WatchtowerAlertV1
from omni_cio.persistence.migration import ConnectionLike
from omni_cio.web.api_v1 import SESSION_COOKIE, SessionRegistryLike
from omni_cio.web.session_v1 import SessionScopeV1


_MAX_INCIDENTS = 500
_MAX_REVISIONS_PER_INCIDENT = 512
_MAX_EVIDENCE_IDS_PER_REVISION = 1024
_MAX_EVIDENCE_LINK_ROWS_PER_INCIDENT = 4096
_MAX_EVIDENCE_ROWS_PER_INCIDENT = 1024
_MAX_JOURNAL_LINK_ROWS_PER_INCIDENT = 1024
_MAX_WATCHTOWER_ALERT_BLOB_BYTES = 64 * 1024
_SEVERITY_ORDER = {"unknown": -1, "info": 0, "warning": 1, "error": 2}


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("WP19 timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def _text(value: object | None) -> str | None:
    return None if value is None else str(value)


def _timestamp(value: object | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, datetime):
        raise ValueError("WP19 persisted timestamp must be datetime")
    return _utc(value).isoformat()


def _safe_payload_bytes(value: object | None) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value
    if isinstance(value, memoryview):
        return value.tobytes()
    if isinstance(value, bytearray):
        return bytes(value)
    return None


def _watchtower_alert(value: object | None) -> WatchtowerAlertV1 | None:
    payload = _safe_payload_bytes(value)
    if payload is None or len(payload) > _MAX_WATCHTOWER_ALERT_BLOB_BYTES:
        return None
    try:
        decoded = json.loads(payload.decode("utf-8"))
        return WatchtowerAlertV1.model_validate(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError):
        return None


def _bounded_rows(
    rows: Sequence[Sequence[Any]],
    *,
    maximum: int,
    reason: str,
) -> list[Sequence[Any]]:
    materialized = list(rows)
    if len(materialized) > maximum:
        raise ValueError(reason)
    return materialized


def _severity(alerts: Sequence[WatchtowerAlertV1]) -> str:
    if not alerts:
        return "unknown"
    return max(
        (alert.severity.value for alert in alerts),
        key=lambda value: _SEVERITY_ORDER[value],
    )


def _risk_impact(severity: str) -> str:
    return {
        "error": "CRITICAL",
        "warning": "MATERIAL",
        "info": "INFORMATIONAL",
        "unknown": "UNKNOWN",
    }[severity]


def _lifecycle_reopened(statuses: Sequence[str]) -> bool:
    seen_closed = False
    for status in statuses:
        if status == "closed":
            seen_closed = True
        elif status == "open" and seen_closed:
            return True
    return False


class WatchtowerIncidentReadServiceV1:
    """Tenant-scoped WP19 read model over accepted canonical incident state.

    This service does not mutate incidents and does not create a second Watchtower
    state store. Raw evidence/content blobs never leave the process. A blob may
    contribute alert presentation metadata only after full WatchtowerAlertV1
    validation, including canonical alert identity validation.
    """

    def __init__(
        self,
        connection: ConnectionLike,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._connection = connection
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _revision_rows(
        self,
        *,
        tenant_id: str,
        incident_id: str,
    ) -> list[Sequence[Any]]:
        rows = self._connection.execute(
            "SELECT r.revision, r.status, r.revised_at "
            "FROM omni_cio_v10.incident_revisions r "
            "JOIN omni_cio_v10.incidents i ON i.incident_id = r.incident_id "
            "WHERE i.tenant_id = %s AND r.incident_id = %s "
            "ORDER BY r.revision LIMIT %s",
            (tenant_id, incident_id, _MAX_REVISIONS_PER_INCIDENT + 1),
        ).fetchall()
        return _bounded_rows(
            rows,
            maximum=_MAX_REVISIONS_PER_INCIDENT,
            reason="WP19 incident revision limit exceeded",
        )

    def _revision_evidence_by_revision(
        self,
        *,
        tenant_id: str,
        incident_id: str,
    ) -> dict[int, tuple[str, ...]]:
        rows = self._connection.execute(
            "SELECT incident_revision, evidence_id "
            "FROM omni_cio_v10.incident_evidence "
            "WHERE tenant_id = %s AND incident_id = %s "
            "ORDER BY incident_revision, evidence_id LIMIT %s",
            (
                tenant_id,
                incident_id,
                _MAX_EVIDENCE_LINK_ROWS_PER_INCIDENT + 1,
            ),
        ).fetchall()
        bounded = _bounded_rows(
            rows,
            maximum=_MAX_EVIDENCE_LINK_ROWS_PER_INCIDENT,
            reason="WP19 incident evidence link limit exceeded",
        )
        grouped: dict[int, list[str]] = {}
        for row in bounded:
            revision = int(row[0])
            values = grouped.setdefault(revision, [])
            values.append(str(row[1]))
            if len(values) > _MAX_EVIDENCE_IDS_PER_REVISION:
                raise ValueError("WP19 incident revision evidence limit exceeded")
        return {revision: tuple(values) for revision, values in grouped.items()}

    def _evidence_rows(
        self,
        *,
        tenant_id: str,
        incident_id: str,
    ) -> list[Sequence[Any]]:
        rows = self._connection.execute(
            "SELECT DISTINCT e.evidence_id, e.source_kind, e.published_at, "
            "e.retrieved_at, e.local_received_at, e.payload_sha256, "
            "e.instrument_id, ins.ticker, ins.name, cb.payload IS NOT NULL, "
            "CASE WHEN octet_length(cb.payload) <= %s THEN cb.payload ELSE NULL END "
            "FROM omni_cio_v10.incident_evidence ie "
            "JOIN omni_cio_v10.evidence e ON e.evidence_id = ie.evidence_id "
            "LEFT JOIN omni_cio_v10.instruments ins ON ins.instrument_id = e.instrument_id "
            "LEFT JOIN omni_cio_v10.content_blobs cb "
            "ON cb.tenant_id = e.tenant_id AND cb.payload_sha256 = e.payload_sha256 "
            "WHERE ie.tenant_id = %s AND ie.incident_id = %s "
            "ORDER BY e.evidence_id LIMIT %s",
            (
                _MAX_WATCHTOWER_ALERT_BLOB_BYTES,
                tenant_id,
                incident_id,
                _MAX_EVIDENCE_ROWS_PER_INCIDENT + 1,
            ),
        ).fetchall()
        return _bounded_rows(
            rows,
            maximum=_MAX_EVIDENCE_ROWS_PER_INCIDENT,
            reason="WP19 incident evidence limit exceeded",
        )

    def _links(self, *, tenant_id: str, incident_id: str) -> dict[str, list[str]]:
        rows = self._connection.execute(
            "SELECT decision_id, plan_id FROM omni_cio_v10.journal "
            "WHERE tenant_id = %s AND incident_id = %s "
            "ORDER BY recorded_at, journal_id LIMIT %s",
            (tenant_id, incident_id, _MAX_JOURNAL_LINK_ROWS_PER_INCIDENT + 1),
        ).fetchall()
        bounded = _bounded_rows(
            rows,
            maximum=_MAX_JOURNAL_LINK_ROWS_PER_INCIDENT,
            reason="WP19 incident journal link limit exceeded",
        )
        decisions = sorted({str(row[0]) for row in bounded if row[0] is not None})
        plans = sorted({str(row[1]) for row in bounded if row[1] is not None})
        return {"decisions": decisions, "plans": plans}

    def _incident(self, *, tenant_id: str, row: Sequence[Any]) -> dict[str, Any]:
        incident_id = str(row[0])
        revision_rows = self._revision_rows(
            tenant_id=tenant_id,
            incident_id=incident_id,
        )
        if not revision_rows:
            raise ValueError("WP19 incident has no durable lifecycle revision")
        evidence_by_revision = self._revision_evidence_by_revision(
            tenant_id=tenant_id,
            incident_id=incident_id,
        )

        timeline: list[dict[str, Any]] = []
        statuses: list[str] = []
        for revision_row in revision_rows:
            revision = int(revision_row[0])
            status = str(revision_row[1])
            statuses.append(status)
            timeline.append(
                {
                    "revision": revision,
                    "state": status,
                    "at": _timestamp(revision_row[2]),
                    "evidence_ids": list(evidence_by_revision.get(revision, ())),
                }
            )

        evidence_views: list[dict[str, Any]] = []
        alerts: list[WatchtowerAlertV1] = []
        for evidence_row in self._evidence_rows(
            tenant_id=tenant_id,
            incident_id=incident_id,
        ):
            alert = _watchtower_alert(evidence_row[10])
            if alert is not None:
                alerts.append(alert)
            evidence_views.append(
                {
                    "evidence_id": str(evidence_row[0]),
                    "source_kind": str(evidence_row[1]),
                    "published_at": _timestamp(evidence_row[2]),
                    "retrieved_at": _timestamp(evidence_row[3]),
                    "local_received_at": _timestamp(evidence_row[4]),
                    "payload_sha256": str(evidence_row[5]),
                    "instrument": (
                        {
                            "ticker": _text(evidence_row[7]),
                            "name": _text(evidence_row[8]),
                        }
                        if evidence_row[6] is not None
                        else None
                    ),
                    "content_available": bool(evidence_row[9]),
                    "watchtower_alert_verified": alert is not None,
                }
            )

        fingerprints = sorted({alert.fingerprint_sha256 for alert in alerts})
        dedup_state: Literal["VERIFIED", "MISSING", "CONFLICT"]
        if len(fingerprints) == 1:
            dedup_state = "VERIFIED"
        elif not fingerprints:
            dedup_state = "MISSING"
        else:
            dedup_state = "CONFLICT"

        selected_alert = (
            max(
                alerts,
                key=lambda alert: (_utc(alert.effective_at), alert.alert_id),
            )
            if alerts and dedup_state == "VERIFIED"
            else None
        )
        severity = _severity(alerts) if selected_alert is not None else "unknown"
        reopened = _lifecycle_reopened(statuses)
        current_state = statuses[-1]

        return {
            "incident_id": incident_id,
            "opened_at": _timestamp(row[3]),
            "current_state": current_state,
            "lifecycle_state": ("RESOLVED" if current_state == "closed" else "ACTIVE"),
            "severity": severity,
            "critical": severity == "error",
            "risk_impact": _risk_impact(severity),
            "subject": (
                selected_alert.subject_key if selected_alert is not None else None
            ),
            "message_code": (
                selected_alert.message_code if selected_alert is not None else None
            ),
            "requested_action": (
                selected_alert.action.value if selected_alert is not None else None
            ),
            "alert_effective_at": (
                _utc(selected_alert.effective_at).isoformat()
                if selected_alert is not None
                else None
            ),
            "alert_metadata_state": (
                "VERIFIED"
                if selected_alert is not None
                else "CONFLICT"
                if dedup_state == "CONFLICT"
                else "MISSING"
            ),
            "dedup": {
                "state": dedup_state,
                "fingerprint_sha256": (
                    fingerprints[0] if len(fingerprints) == 1 else None
                ),
                "reopened": reopened,
            },
            "timeline": timeline,
            "evidence": evidence_views,
            "links": self._links(tenant_id=tenant_id, incident_id=incident_id),
        }

    def read(self, *, tenant_id: str) -> dict[str, Any]:
        rows = list(
            self._connection.execute(
                "SELECT incident_id, portfolio_id, policy_id, opened_at "
                "FROM omni_cio_v10.incidents WHERE tenant_id = %s "
                "ORDER BY opened_at DESC, incident_id LIMIT %s",
                (tenant_id, _MAX_INCIDENTS + 1),
            ).fetchall()
        )
        truncated = len(rows) > _MAX_INCIDENTS
        incidents = [
            self._incident(tenant_id=tenant_id, row=row)
            for row in rows[:_MAX_INCIDENTS]
        ]
        incidents.sort(
            key=lambda item: (
                item["current_state"] != "closed",
                _SEVERITY_ORDER[item["severity"]],
                item["opened_at"],
                item["incident_id"],
            ),
            reverse=True,
        )
        active = sum(1 for item in incidents if item["current_state"] != "closed")
        resolved = sum(1 for item in incidents if item["current_state"] == "closed")
        critical = sum(1 for item in incidents if item["critical"])
        reopened = sum(1 for item in incidents if item["dedup"]["reopened"])
        missing_metadata = sum(
            1 for item in incidents if item["alert_metadata_state"] != "VERIFIED"
        )
        return {
            "schema_version": "1.0.0",
            "generated_at": _utc(self._clock()).isoformat(),
            "state": (
                "EMPTY"
                if not incidents
                else "PARTIAL"
                if truncated or missing_metadata
                else "READY"
            ),
            "truncated": truncated,
            "counts": {
                "total": len(incidents),
                "active": active,
                "resolved": resolved,
                "critical": critical,
                "reopened": reopened,
                "missing_alert_metadata": missing_metadata,
            },
            "incidents": incidents,
        }


def _require_incident_session(
    request: Request,
    *,
    sessions: SessionRegistryLike,
    now: Callable[[], datetime],
) -> SessionScopeV1:
    scope = sessions.resolve(request.cookies.get(SESSION_COOKIE), now=_utc(now()))
    if scope is None:
        raise HTTPException(status_code=401, detail="AUTHENTICATION_REQUIRED")
    return scope


def install_watchtower_incident_routes(
    app: FastAPI,
    *,
    sessions: SessionRegistryLike,
    service: WatchtowerIncidentReadServiceV1,
    now: Callable[[], datetime] | None = None,
) -> None:
    clock = now or (lambda: datetime.now(timezone.utc))

    @app.get("/api/v10/web/watchtower-incidents")
    def watchtower_incidents(request: Request) -> JSONResponse:
        scope = _require_incident_session(request, sessions=sessions, now=clock)
        payload = service.read(tenant_id=scope.tenant_id)
        return JSONResponse(payload, headers={"Cache-Control": "no-store"})
