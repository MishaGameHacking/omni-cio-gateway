from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from omni_cio.contracts.v1.research_evidence import (
    EvidenceRecordV1,
    EvidenceUse,
    ResearchDossierV1,
)
from omni_cio.web.api_v1 import SESSION_COOKIE, SessionRegistryLike
from omni_cio.web.session_v1 import SessionScopeV1


_MAX_DOSSIERS = 64
_MAX_FACTS_PER_DOSSIER = 512
_MAX_CONTRADICTIONS_PER_DOSSIER = 128
_MAX_GAPS_PER_DOSSIER = 128
_MAX_RELATED_LINKS_PER_DOSSIER = 16
_MAX_AI_NARRATIVE_CHARS = 32_768
_SAFE_LINK_SCHEMES = {"http", "https"}


@dataclass(frozen=True, slots=True)
class AiNarrativeProjectionV1:
    dossier_sha256: str
    generated_at: datetime
    text: str


@dataclass(frozen=True, slots=True)
class ResearchRelatedLinkV1:
    kind: Literal["credit", "fund"]
    label: str
    path: str


@dataclass(frozen=True, slots=True)
class ResearchDossierProjectionInputV1:
    dossier: ResearchDossierV1
    ai_narrative: AiNarrativeProjectionV1 | None = None
    related_links: tuple[ResearchRelatedLinkV1, ...] = ()


ResearchDossierProviderV1 = Callable[
    [str], Sequence[ResearchDossierProjectionInputV1]
]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("WP20 timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def _safe_source_href(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return None
    if parsed.scheme.lower() not in _SAFE_LINK_SCHEMES or not parsed.netloc:
        return None
    if parsed.username is not None or parsed.password is not None:
        return None
    return candidate


def _safe_related_path(value: str) -> str:
    candidate = value.strip()
    if (
        not candidate.startswith("/")
        or candidate.startswith("//")
        or "\\" in candidate
        or any(ord(character) < 32 for character in candidate)
    ):
        raise ValueError("WP20 related link must be an internal path")
    return candidate


def _matching_max_age_seconds(
    dossier: ResearchDossierV1,
    record: EvidenceRecordV1,
) -> int | None:
    matches = [
        requirement.max_age_seconds
        for requirement in dossier.requirements
        if requirement.fact_type is record.fact_type
        and record.source.source_class in requirement.source_classes
        and (
            requirement.fact_key_prefix is None
            or record.fact_key.startswith(requirement.fact_key_prefix)
        )
    ]
    return min(matches) if matches else None


def _freshness(
    dossier: ResearchDossierV1,
    record: EvidenceRecordV1,
) -> Literal["FRESH", "STALE", "UNKNOWN"]:
    max_age = _matching_max_age_seconds(dossier, record)
    if max_age is None:
        return "UNKNOWN"
    assessed_at = _utc(dossier.assessed_at)
    retrieved_at = _utc(record.source.retrieved_at)
    age_seconds = (assessed_at - retrieved_at).total_seconds()
    if age_seconds < 0:
        return "UNKNOWN"
    return "FRESH" if age_seconds <= max_age else "STALE"


def _confidence_state(
    *,
    record: EvidenceRecordV1,
    freshness: str,
    contradicted: bool,
) -> Literal["SUPPORTED", "CONTEXT_ONLY", "STALE", "CONTRADICTED", "UNKNOWN"]:
    if contradicted:
        return "CONTRADICTED"
    if freshness == "STALE":
        return "STALE"
    if record.use is EvidenceUse.CONTEXT_ONLY:
        return "CONTEXT_ONLY"
    if record.use is EvidenceUse.DECISION_GRADE and freshness == "FRESH":
        return "SUPPORTED"
    return "UNKNOWN"


def _event_at(record: EvidenceRecordV1) -> datetime:
    return _utc(
        record.effective_at
        or record.published_at
        or record.source.retrieved_at
    )


class ResearchDossierReadServiceV1:
    """WP20 presentation adapter over already-formed canonical research dossiers.

    The provider is intentionally narrow. WP20 does not fetch sources, run an LLM,
    write evidence, or define Block G generation semantics. A later accepted producer
    may supply canonical dossiers and an optional separately bound AI narrative.
    """

    def __init__(
        self,
        provider: ResearchDossierProviderV1,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._provider = provider
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _fact_view(
        self,
        dossier: ResearchDossierV1,
        record: EvidenceRecordV1,
        *,
        contradicted_hashes: set[str],
    ) -> dict[str, Any]:
        freshness = _freshness(dossier, record)
        contradicted = record.record_sha256 in contradicted_hashes
        return {
            "record_sha256": record.record_sha256,
            "fact_type": record.fact_type.value,
            "fact_key": record.fact_key,
            "value": {
                "type": record.value.value_type.value,
                "canonical": record.value.canonical_value,
                "currency": record.value.currency,
            },
            "material": record.material,
            "evidence_use": record.use.value,
            "freshness": freshness,
            "confidence_state": _confidence_state(
                record=record,
                freshness=freshness,
                contradicted=contradicted,
            ),
            "event_at": _event_at(record).isoformat(),
            "source": {
                "provider": record.source.provider,
                "source_class": record.source.source_class.value,
                "authority": record.source.authority.value,
                "source_id": record.source.source_id,
                "location_text": record.source.source_location,
                "href": _safe_source_href(record.source.source_location),
                "retrieved_at": _utc(record.source.retrieved_at).isoformat(),
                "published_at": (
                    _utc(record.published_at).isoformat()
                    if record.published_at is not None
                    else None
                ),
                "effective_at": (
                    _utc(record.effective_at).isoformat()
                    if record.effective_at is not None
                    else None
                ),
            },
        }

    def _dossier_view(
        self,
        item: ResearchDossierProjectionInputV1,
    ) -> dict[str, Any]:
        dossier = item.dossier
        visible_records = [
            record for record in dossier.records if record.use is not EvidenceUse.REJECTED
        ]
        if len(visible_records) > _MAX_FACTS_PER_DOSSIER:
            raise ValueError("WP20 dossier fact limit exceeded")
        if len(dossier.contradictions) > _MAX_CONTRADICTIONS_PER_DOSSIER:
            raise ValueError("WP20 dossier contradiction limit exceeded")
        if len(dossier.coverage_gaps) > _MAX_GAPS_PER_DOSSIER:
            raise ValueError("WP20 dossier coverage-gap limit exceeded")
        if len(item.related_links) > _MAX_RELATED_LINKS_PER_DOSSIER:
            raise ValueError("WP20 related-link limit exceeded")

        contradicted_hashes = {
            record_sha256
            for contradiction in dossier.contradictions
            if contradiction.unresolved
            for record_sha256 in contradiction.record_sha256s
        }
        facts = [
            self._fact_view(
                dossier,
                record,
                contradicted_hashes=contradicted_hashes,
            )
            for record in visible_records
        ]
        facts.sort(
            key=lambda fact: (
                fact["event_at"],
                fact["fact_key"],
                fact["record_sha256"],
            ),
            reverse=True,
        )

        contradictions = [
            {
                "fact_key": row.fact_key,
                "comparison_period": row.comparison_period,
                "severity": row.severity.value,
                "record_sha256s": list(row.record_sha256s),
                "distinct_values": list(row.distinct_values),
                "unresolved": row.unresolved,
            }
            for row in dossier.contradictions
        ]
        gaps = [
            {
                "requirement_id": gap.requirement_id,
                "fact_type": gap.fact_type.value,
                "importance": gap.importance.value,
                "reason": gap.reason.value,
            }
            for gap in dossier.coverage_gaps
        ]

        narrative = item.ai_narrative
        if narrative is None:
            ai_summary: dict[str, Any] = {"state": "UNAVAILABLE"}
        else:
            if narrative.dossier_sha256 != dossier.dossier_sha256:
                raise ValueError("WP20 AI narrative dossier binding mismatch")
            text = narrative.text.strip()
            if not text or len(text) > _MAX_AI_NARRATIVE_CHARS:
                raise ValueError("WP20 AI narrative size invalid")
            ai_summary = {
                "state": "AVAILABLE",
                "kind": "AI_GENERATED_NON_AUTHORITATIVE",
                "authoritative": False,
                "dossier_sha256": narrative.dossier_sha256,
                "generated_at": _utc(narrative.generated_at).isoformat(),
                "text": text,
            }

        related_links = [
            {
                "kind": link.kind,
                "label": link.label.strip(),
                "path": _safe_related_path(link.path),
            }
            for link in item.related_links
        ]
        if any(not link["label"] for link in related_links):
            raise ValueError("WP20 related link label cannot be blank")

        has_unresolved_conflict = any(row.unresolved for row in dossier.contradictions)
        stale_fact_count = sum(1 for fact in facts if fact["freshness"] == "STALE")
        unknown_fact_count = sum(1 for fact in facts if fact["freshness"] == "UNKNOWN")
        state: Literal["READY", "PARTIAL"] = (
            "READY"
            if dossier.decision_ready
            and not has_unresolved_conflict
            and stale_fact_count == 0
            else "PARTIAL"
        )
        return {
            "dossier_sha256": dossier.dossier_sha256,
            "state": state,
            "assessed_at": _utc(dossier.assessed_at).isoformat(),
            "decision_ready": dossier.decision_ready,
            "strong_recommendation_allowed": dossier.strong_recommendation_allowed,
            "identity": {
                "candidate_id": dossier.target.candidate_id,
                "instrument_uid": dossier.target.instrument_uid,
                "instrument_type": dossier.target.instrument_type.value,
                "issuer_identity_state": (
                    "SOURCE_BOUND"
                    if any(fact["fact_type"] == "identity" for fact in facts)
                    else "UNKNOWN"
                ),
            },
            "facts": facts,
            "timeline": [
                {
                    "event_at": fact["event_at"],
                    "record_sha256": fact["record_sha256"],
                    "fact_key": fact["fact_key"],
                    "value": fact["value"],
                    "source_class": fact["source"]["source_class"],
                }
                for fact in facts
            ],
            "contradictions": contradictions,
            "unknowns": gaps,
            "related_links": related_links,
            "ai_summary": ai_summary,
            "counts": {
                "facts": len(facts),
                "rejected_records_hidden": len(dossier.records) - len(visible_records),
                "contradictions": len(contradictions),
                "unknowns": len(gaps),
                "stale_facts": stale_fact_count,
                "unknown_freshness_facts": unknown_fact_count,
            },
        }

    def read(self, *, tenant_id: str) -> dict[str, Any]:
        items = list(self._provider(tenant_id))
        if len(items) > _MAX_DOSSIERS:
            raise ValueError("WP20 dossier count limit exceeded")
        dossiers = [self._dossier_view(item) for item in items]
        dossiers.sort(
            key=lambda dossier: (
                dossier["assessed_at"],
                dossier["dossier_sha256"],
            ),
            reverse=True,
        )
        return {
            "schema_version": "1.0.0",
            "generated_at": _utc(self._clock()).isoformat(),
            "state": (
                "EMPTY"
                if not dossiers
                else "PARTIAL"
                if any(dossier["state"] != "READY" for dossier in dossiers)
                else "READY"
            ),
            "counts": {
                "dossiers": len(dossiers),
                "partial": sum(1 for dossier in dossiers if dossier["state"] == "PARTIAL"),
            },
            "dossiers": dossiers,
        }


def empty_research_dossier_provider(
    tenant_id: str,
) -> Sequence[ResearchDossierProjectionInputV1]:
    del tenant_id
    return ()


def _require_research_session(
    request: Request,
    *,
    sessions: SessionRegistryLike,
    now: Callable[[], datetime],
) -> SessionScopeV1:
    scope = sessions.resolve(request.cookies.get(SESSION_COOKIE), now=_utc(now()))
    if scope is None:
        raise HTTPException(status_code=401, detail="AUTHENTICATION_REQUIRED")
    return scope


def install_research_dossier_routes(
    app: FastAPI,
    *,
    sessions: SessionRegistryLike,
    service: ResearchDossierReadServiceV1,
    now: Callable[[], datetime] | None = None,
) -> None:
    clock = now or (lambda: datetime.now(timezone.utc))

    @app.get("/api/v10/web/research-dossiers")
    def research_dossiers(request: Request) -> JSONResponse:
        scope = _require_research_session(request, sessions=sessions, now=clock)
        payload = service.read(tenant_id=scope.tenant_id)
        return JSONResponse(payload, headers={"Cache-Control": "no-store"})
