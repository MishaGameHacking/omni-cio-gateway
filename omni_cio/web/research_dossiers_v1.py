from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import json
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from omni_cio.contracts.v1.research_evidence import (
    EvidenceRecordV1,
    EvidenceRequirementV1,
    EvidenceUse,
    ResearchDossierV1,
)
from omni_cio.persistence.migration import ConnectionLike
from omni_cio.web.api_v1 import SESSION_COOKIE, SessionRegistryLike
from omni_cio.web.session_v1 import SessionScopeV1


_MAX_DOSSIERS = 100
_MAX_DOSSIER_BLOB_BYTES = 1024 * 1024
_MAX_FACTS_PER_DOSSIER = 2000
_MAX_TIMELINE_EVENTS = 1000
_MAX_SOURCE_LOCATION = 2048
_DOSSIER_SCHEMA_REF = "omni_cio.contracts.v1.research_evidence.ResearchDossierV1"
_EVENT_FACT_TYPES = {
    "report",
    "dividend",
    "coupon",
    "corporate_event",
    "sanction",
    "litigation",
    "auditor_warning",
    "material_event",
}


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("WP20 timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def _timestamp(value: datetime | None) -> str | None:
    return _utc(value).isoformat() if value is not None else None


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


def _research_dossier(value: object | None) -> ResearchDossierV1 | None:
    payload = _safe_payload_bytes(value)
    if payload is None or len(payload) > _MAX_DOSSIER_BLOB_BYTES:
        return None
    try:
        decoded = json.loads(payload.decode("utf-8"))
        return ResearchDossierV1.model_validate(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError):
        return None


def _safe_source_location(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.strip()
    if not candidate or len(candidate) > _MAX_SOURCE_LOCATION:
        return None
    parsed = urlparse(candidate)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    if parsed.username is not None or parsed.password is not None:
        return None
    return candidate


def _record_effective_time(record: EvidenceRecordV1) -> datetime:
    return record.published_at or record.effective_at or record.source.retrieved_at


def _matches_requirement(
    record: EvidenceRecordV1,
    requirement: EvidenceRequirementV1,
) -> bool:
    if record.fact_type is not requirement.fact_type:
        return False
    if (
        requirement.fact_key_prefix is not None
        and not record.fact_key.startswith(requirement.fact_key_prefix)
    ):
        return False
    return record.source.source_class in requirement.source_classes


def _freshness(
    record: EvidenceRecordV1,
    dossier: ResearchDossierV1,
) -> str:
    requirements = tuple(
        item for item in dossier.requirements if _matches_requirement(record, item)
    )
    if not requirements:
        return "UNKNOWN"
    effective_at = _record_effective_time(record)
    age_seconds = (dossier.assessed_at - effective_at).total_seconds()
    max_age_seconds = min(item.max_age_seconds for item in requirements)
    if age_seconds < -60:
        return "UNKNOWN"
    return "FRESH" if age_seconds <= max_age_seconds else "STALE"


def _confidence(
    record: EvidenceRecordV1,
    dossier: ResearchDossierV1,
) -> str:
    if record.use is EvidenceUse.REJECTED:
        return "REJECTED"
    if record.use is EvidenceUse.CONTEXT_ONLY:
        return "CONTEXT_ONLY"
    conflict_hashes = {
        record_sha
        for contradiction in dossier.contradictions
        if contradiction.unresolved
        for record_sha in contradiction.record_sha256s
    }
    if record.record_sha256 in conflict_hashes:
        return "LIMITED"
    matching_requirements = tuple(
        item for item in dossier.requirements if _matches_requirement(record, item)
    )
    if not matching_requirements:
        return "DECISION_GRADE"
    matching_ids = {item.requirement_id for item in matching_requirements}
    if any(gap.requirement_id in matching_ids for gap in dossier.coverage_gaps):
        return "LIMITED"
    return "DECISION_GRADE"


def _fact_view(record: EvidenceRecordV1, dossier: ResearchDossierV1) -> dict[str, Any]:
    contradiction = next(
        (
            item
            for item in dossier.contradictions
            if record.record_sha256 in item.record_sha256s and item.unresolved
        ),
        None,
    )
    source_location = _safe_source_location(record.source.source_location)
    return {
        "record_sha256": record.record_sha256,
        "fact_type": record.fact_type.value,
        "fact_key": record.fact_key,
        "value": {
            "type": record.value.value_type.value,
            "canonical": record.value.canonical_value,
            "currency": record.value.currency,
        },
        "use": record.use.value,
        "confidence": _confidence(record, dossier),
        "freshness": _freshness(record, dossier),
        "source": {
            "provider": record.source.provider,
            "class": record.source.source_class.value,
            "authority": record.source.authority.value,
            "source_id": record.source.source_id,
            "location": source_location,
            "location_rejected": (
                record.source.source_location is not None and source_location is None
            ),
            "retrieved_at": _timestamp(record.source.retrieved_at),
            "published_at": _timestamp(record.published_at),
            "effective_at": _timestamp(record.effective_at),
        },
        "contradiction": (
            {
                "severity": contradiction.severity.value,
                "comparison_period": contradiction.comparison_period,
                "distinct_values": list(contradiction.distinct_values),
            }
            if contradiction is not None
            else None
        ),
    }


def _timeline(dossier: ResearchDossierV1) -> list[dict[str, Any]]:
    rows = [
        record
        for record in dossier.records
        if record.fact_type.value in _EVENT_FACT_TYPES
    ]
    rows.sort(
        key=lambda record: (
            _record_effective_time(record),
            record.fact_type.value,
            record.fact_key,
            record.record_sha256,
        ),
        reverse=True,
    )
    result = []
    for record in rows[:_MAX_TIMELINE_EVENTS]:
        result.append(
            {
                "record_sha256": record.record_sha256,
                "fact_type": record.fact_type.value,
                "fact_key": record.fact_key,
                "value": record.value.canonical_value,
                "currency": record.value.currency,
                "at": _timestamp(_record_effective_time(record)),
                "source_label": (
                    f"{record.source.provider} · {record.source.source_class.value}"
                ),
                "confidence": _confidence(record, dossier),
            }
        )
    return result


def _dossier_state(dossier: ResearchDossierV1, *, cache_fresh: bool) -> str:
    if not cache_fresh:
        return "STALE"
    if dossier.coverage_gaps or dossier.contradictions:
        return "PARTIAL"
    return "READY"


class ResearchDossierReadServiceV1:
    """Tenant-scoped WP20 projection over accepted research-cache/dossier contracts.

    Raw content blobs never leave this service. Only blobs explicitly bound to the
    accepted ResearchDossierV1 schema and fully validating against that contract
    can contribute canonical facts.
    """

    def __init__(
        self,
        connection: ConnectionLike,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._connection = connection
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def read(self, *, tenant_id: str) -> dict[str, Any]:
        now = _utc(self._clock())
        rows = list(
            self._connection.execute(
                "SELECT rc.cache_key, rc.source_identity, rc.content_sha256, "
                "rc.retrieved_at, rc.expires_at, rc.instrument_id, "
                "ins.broker_uid, ins.figi, ins.isin, ins.ticker, ins.name, "
                "cb.schema_ref, "
                "CASE WHEN octet_length(cb.payload) <= %s THEN cb.payload ELSE NULL END "
                "FROM omni_cio_v10.research_cache rc "
                "LEFT JOIN omni_cio_v10.instruments ins "
                "ON ins.instrument_id = rc.instrument_id "
                "LEFT JOIN omni_cio_v10.content_blobs cb "
                "ON cb.tenant_id = rc.tenant_id AND cb.payload_sha256 = rc.content_sha256 "
                "WHERE rc.tenant_id = %s "
                "ORDER BY rc.retrieved_at DESC, rc.cache_key LIMIT %s",
                (_MAX_DOSSIER_BLOB_BYTES, tenant_id, _MAX_DOSSIERS + 1),
            ).fetchall()
        )
        truncated = len(rows) > _MAX_DOSSIERS
        represented_rows = rows[:_MAX_DOSSIERS]
        dossiers: list[dict[str, Any]] = []
        invalid_count = 0
        duplicate_count = 0
        seen: set[str] = set()

        for row in represented_rows:
            schema_ref = None if row[11] is None else str(row[11])
            dossier = (
                _research_dossier(row[12])
                if schema_ref == _DOSSIER_SCHEMA_REF
                else None
            )
            if dossier is None:
                invalid_count += 1
                continue
            if len(dossier.records) > _MAX_FACTS_PER_DOSSIER:
                invalid_count += 1
                continue

            broker_uid = None if row[6] is None else str(row[6])
            instrument_id = None if row[5] is None else str(row[5])
            if instrument_id is not None:
                if broker_uid is None or dossier.target.instrument_uid != broker_uid:
                    invalid_count += 1
                    continue

            if dossier.dossier_sha256 in seen:
                duplicate_count += 1
                continue
            seen.add(dossier.dossier_sha256)

            expires_at = row[4]
            if not isinstance(expires_at, datetime):
                raise ValueError("WP20 research_cache expires_at must be datetime")
            retrieved_at = row[3]
            if not isinstance(retrieved_at, datetime):
                raise ValueError("WP20 research_cache retrieved_at must be datetime")
            cache_fresh = _utc(expires_at) >= now
            facts = [_fact_view(record, dossier) for record in dossier.records]
            contradictions = [
                {
                    "fact_key": item.fact_key,
                    "comparison_period": item.comparison_period,
                    "severity": item.severity.value,
                    "record_sha256s": list(item.record_sha256s),
                    "distinct_values": list(item.distinct_values),
                    "unresolved": item.unresolved,
                }
                for item in dossier.contradictions
            ]
            unknowns = [
                {
                    "requirement_id": gap.requirement_id,
                    "fact_type": gap.fact_type.value,
                    "importance": gap.importance.value,
                    "reason": gap.reason.value,
                }
                for gap in dossier.coverage_gaps
            ]
            dossiers.append(
                {
                    "cache_key": str(row[0]),
                    "source_identity": str(row[1]),
                    "content_sha256": str(row[2]),
                    "cache_retrieved_at": _timestamp(_utc(retrieved_at)),
                    "cache_expires_at": _timestamp(_utc(expires_at)),
                    "cache_freshness": "FRESH" if cache_fresh else "STALE",
                    "dossier_sha256": dossier.dossier_sha256,
                    "assessed_at": _timestamp(dossier.assessed_at),
                    "state": _dossier_state(dossier, cache_fresh=cache_fresh),
                    "decision_ready": dossier.decision_ready,
                    "strong_recommendation_allowed": dossier.strong_recommendation_allowed,
                    "security": {
                        "instrument_id": instrument_id,
                        "instrument_uid": dossier.target.instrument_uid,
                        "instrument_type": dossier.target.instrument_type.value,
                        "ticker": None if row[9] is None else str(row[9]),
                        "name": None if row[10] is None else str(row[10]),
                        "figi": None if row[7] is None else str(row[7]),
                        "isin": None if row[8] is None else str(row[8]),
                    },
                    "facts": facts,
                    "contradictions": contradictions,
                    "unknowns": unknowns,
                    "timeline": _timeline(dossier),
                    "links": {
                        "credit": f"/risks?instrument_uid={dossier.target.instrument_uid}",
                        "fund": (
                            f"/assets?instrument_uid={dossier.target.instrument_uid}"
                            if dossier.target.instrument_type.value == "etf"
                            else None
                        ),
                    },
                    "ai_summary": {
                        "state": "NOT_AVAILABLE",
                        "non_authoritative": True,
                        "text": None,
                        "generated_at": None,
                        "model_label": None,
                        "confidence": None,
                    },
                }
            )

        if not dossiers:
            state = "PARTIAL" if invalid_count or truncated else "EMPTY"
        elif any(item["state"] == "STALE" for item in dossiers):
            state = "STALE"
        elif invalid_count or truncated or any(
            item["state"] == "PARTIAL" for item in dossiers
        ):
            state = "PARTIAL"
        else:
            state = "READY"

        return {
            "schema_version": "1.0.0",
            "generated_at": now.isoformat(),
            "state": state,
            "truncated": truncated,
            "invalid_dossier_count": invalid_count,
            "duplicate_dossier_count": duplicate_count,
            "dossiers": dossiers,
        }


def install_research_dossier_routes(
    app: FastAPI,
    *,
    sessions: SessionRegistryLike,
    service: ResearchDossierReadServiceV1,
    now: Callable[[], datetime] | None = None,
) -> None:
    clock = now or (lambda: datetime.now(timezone.utc))

    @app.get("/api/v10/web/research-dossiers")
    def read_research_dossiers(request: Request) -> JSONResponse:
        raw_session = request.cookies.get(SESSION_COOKIE)
        scope: SessionScopeV1 | None = sessions.resolve(
            raw_session,
            now=_utc(clock()),
        )
        if scope is None:
            raise HTTPException(status_code=401, detail="WEB_SESSION_REQUIRED")
        payload = service.read(tenant_id=scope.tenant_id)
        return JSONResponse(
            payload,
            headers={
                "Cache-Control": "no-store",
                "Pragma": "no-cache",
            },
        )
