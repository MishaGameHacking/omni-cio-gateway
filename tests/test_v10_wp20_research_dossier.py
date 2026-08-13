from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256

from fastapi import FastAPI
from fastapi.testclient import TestClient

from omni_cio.contracts.v1.domain import OWNER_TENANT_ID, OWNER_USER_ID
from omni_cio.contracts.v1.market import SourceAuthority
from omni_cio.contracts.v1.portfolio import InstrumentType
from omni_cio.contracts.v1.research_evidence import (
    EvidenceFactType,
    EvidenceRequirementV1,
    EvidenceSourceClass,
    EvidenceUse,
    EvidenceValueType,
    EvidenceValueV1,
    RequirementImportance,
    ResearchSourceV1,
    ResearchTargetV1,
    make_evidence_record,
)
from omni_cio.research.engine_v1 import build_research_dossier
from omni_cio.web.api_v1 import SESSION_COOKIE
from omni_cio.web.research_dossier_v1 import (
    AiNarrativeProjectionV1,
    ResearchDossierProjectionInputV1,
    ResearchDossierReadServiceV1,
    ResearchRelatedLinkV1,
    _safe_source_href,
    install_research_dossier_routes,
)
from omni_cio.web.session_v1 import SessionScopeV1


NOW = datetime(2026, 8, 13, 18, 0, tzinfo=timezone.utc)
UID = "wp20-synthetic-bond-uid"


def _digest(seed: str) -> str:
    return sha256(seed.encode()).hexdigest()


def _target() -> ResearchTargetV1:
    return ResearchTargetV1(
        funnel_sha256=_digest("wp20-funnel"),
        candidate_id=f"uid:{UID}",
        instrument_uid=UID,
        instrument_type=InstrumentType.BOND,
    )


def _record(
    *,
    value: str,
    source_location: str = "https://issuer.example.test/report/20",
    retrieved_at: datetime = NOW - timedelta(minutes=5),
    source_id: str = "issuer-report-20",
    fact_key: str = "report.revenue",
):
    return make_evidence_record(
        instrument_uid=UID,
        fact_type=EvidenceFactType.REPORT,
        fact_key=fact_key,
        value=EvidenceValueV1(
            value_type=EvidenceValueType.TEXT,
            canonical_value=value,
        ),
        source=ResearchSourceV1(
            provider="wp20_issuer",
            source_class=EvidenceSourceClass.ISSUER,
            authority=SourceAuthority.OFFICIAL,
            source_id=source_id,
            source_location=source_location,
            retrieved_at=retrieved_at,
        ),
        use=EvidenceUse.DECISION_GRADE,
        source_record_id=source_id,
        published_at=retrieved_at,
        effective_at=retrieved_at,
        material=True,
    )


def _requirement(*, max_age_seconds: int = 3600) -> EvidenceRequirementV1:
    return EvidenceRequirementV1(
        requirement_id="req_wp20_report",
        fact_type=EvidenceFactType.REPORT,
        fact_key_prefix="report.",
        source_classes=(EvidenceSourceClass.ISSUER,),
        minimum_decision_grade_records=1,
        max_age_seconds=max_age_seconds,
        importance=RequirementImportance.MATERIAL,
    )


def _dossier(*, records, max_age_seconds: int = 3600):
    return build_research_dossier(
        target=_target(),
        records=tuple(records),
        probes=(),
        requirements=(_requirement(max_age_seconds=max_age_seconds),),
        assessed_at=NOW,
    )


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


def test_wp20_safe_source_href_is_fail_closed() -> None:
    assert _safe_source_href("https://example.test/a") == "https://example.test/a"
    assert _safe_source_href("http://example.test/a") == "http://example.test/a"
    assert _safe_source_href("ftp://example.test/file") is None
    assert _safe_source_href("data:text/plain,external") is None
    assert _safe_source_href("https://user:pass@example.test/private") is None
    assert _safe_source_href("not a url") is None


def test_wp20_projects_source_fact_and_separate_ai_narrative() -> None:
    dossier = _dossier(records=(_record(value="Revenue grew 12%"),))
    service = ResearchDossierReadServiceV1(
        lambda tenant_id: (
            ResearchDossierProjectionInputV1(
                dossier=dossier,
                ai_narrative=AiNarrativeProjectionV1(
                    dossier_sha256=dossier.dossier_sha256,
                    generated_at=NOW,
                    text="Interpretation only; verify source facts above.",
                ),
                related_links=(
                    ResearchRelatedLinkV1(
                        kind="credit",
                        label="Credit view",
                        path="/risks?instrument=wp20",
                    ),
                ),
            ),
        ),
        clock=lambda: NOW,
    )
    payload = service.read(tenant_id=OWNER_TENANT_ID)
    assert payload["state"] == "READY"
    dossier_view = payload["dossiers"][0]
    fact = dossier_view["facts"][0]
    assert fact["fact_key"] == "report.revenue"
    assert fact["freshness"] == "FRESH"
    assert fact["confidence_state"] == "SUPPORTED"
    assert fact["source"]["href"] == "https://issuer.example.test/report/20"
    assert dossier_view["ai_summary"]["kind"] == "AI_GENERATED_NON_AUTHORITATIVE"
    assert dossier_view["ai_summary"]["authoritative"] is False
    assert "source" not in dossier_view["ai_summary"]


def test_wp20_stale_and_contradictory_evidence_remains_partial() -> None:
    stale_time = NOW - timedelta(hours=2)
    first = _record(value="100", retrieved_at=stale_time, source_id="issuer-a")
    second = _record(value="120", retrieved_at=stale_time, source_id="issuer-b")
    dossier = _dossier(records=(first, second), max_age_seconds=60)
    payload = ResearchDossierReadServiceV1(
        lambda tenant_id: (ResearchDossierProjectionInputV1(dossier=dossier),),
        clock=lambda: NOW,
    ).read(tenant_id=OWNER_TENANT_ID)
    assert payload["state"] == "PARTIAL"
    dossier_view = payload["dossiers"][0]
    assert dossier_view["unknowns"][0]["reason"] == "stale_record"
    assert dossier_view["contradictions"][0]["unresolved"] is True
    assert {fact["confidence_state"] for fact in dossier_view["facts"]} == {
        "CONTRADICTED"
    }


def test_wp20_html_like_text_is_plain_data_and_unsupported_url_is_not_linked() -> None:
    external_text = "<strong>External source text remains data</strong>"
    dossier = _dossier(
        records=(
            _record(
                value=external_text,
                source_location="ftp://example.test/untrusted-document",
            ),
        )
    )
    payload = ResearchDossierReadServiceV1(
        lambda tenant_id: (ResearchDossierProjectionInputV1(dossier=dossier),),
        clock=lambda: NOW,
    ).read(tenant_id=OWNER_TENANT_ID)
    fact = payload["dossiers"][0]["facts"][0]
    assert fact["value"]["canonical"] == external_text
    assert fact["source"]["location_text"].startswith("ftp:")
    assert fact["source"]["href"] is None


def test_wp20_ai_binding_internal_link_and_collection_bounds_fail_closed() -> None:
    dossier = _dossier(records=(_record(value="safe"),))
    bad_ai = ResearchDossierProjectionInputV1(
        dossier=dossier,
        ai_narrative=AiNarrativeProjectionV1(
            dossier_sha256=_digest("wrong-dossier"),
            generated_at=NOW,
            text="wrong binding",
        ),
    )
    try:
        ResearchDossierReadServiceV1(lambda tenant_id: (bad_ai,)).read(
            tenant_id=OWNER_TENANT_ID
        )
    except ValueError as exc:
        assert str(exc) == "WP20 AI narrative dossier binding mismatch"
    else:
        raise AssertionError("mismatched AI narrative was accepted")

    bad_link = ResearchDossierProjectionInputV1(
        dossier=dossier,
        related_links=(
            ResearchRelatedLinkV1(
                kind="fund",
                label="unsafe",
                path="https://example.test/fund",
            ),
        ),
    )
    try:
        ResearchDossierReadServiceV1(lambda tenant_id: (bad_link,)).read(
            tenant_id=OWNER_TENANT_ID
        )
    except ValueError as exc:
        assert str(exc) == "WP20 related link must be an internal path"
    else:
        raise AssertionError("external related link was accepted")

    safe = ResearchDossierProjectionInputV1(dossier=dossier)
    try:
        ResearchDossierReadServiceV1(lambda tenant_id: (safe,) * 65).read(
            tenant_id=OWNER_TENANT_ID
        )
    except ValueError as exc:
        assert str(exc) == "WP20 dossier count limit exceeded"
    else:
        raise AssertionError("oversized dossier collection was accepted")


def test_wp20_route_requires_session_and_uses_server_tenant_scope() -> None:
    dossier = _dossier(records=(_record(value="tenant scoped"),))
    seen_tenants: list[str] = []

    def provider(tenant_id: str):
        seen_tenants.append(tenant_id)
        return (ResearchDossierProjectionInputV1(dossier=dossier),)

    denied = FastAPI()
    install_research_dossier_routes(
        denied,
        sessions=_NoSession(),
        service=ResearchDossierReadServiceV1(provider, clock=lambda: NOW),
        now=lambda: NOW,
    )
    assert TestClient(denied).get("/api/v10/web/research-dossiers").status_code == 401
    assert seen_tenants == []

    allowed = FastAPI()
    install_research_dossier_routes(
        allowed,
        sessions=_OwnerSession(),
        service=ResearchDossierReadServiceV1(provider, clock=lambda: NOW),
        now=lambda: NOW,
    )
    response = TestClient(allowed).get(
        "/api/v10/web/research-dossiers",
        cookies={SESSION_COOKIE: "wp20-test"},
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert seen_tenants == [OWNER_TENANT_ID]


def test_wp20_empty_provider_is_truthful() -> None:
    payload = ResearchDossierReadServiceV1(
        lambda tenant_id: (),
        clock=lambda: NOW,
    ).read(tenant_id=OWNER_TENANT_ID)
    assert payload == {
        "schema_version": "1.0.0",
        "generated_at": NOW.isoformat(),
        "state": "EMPTY",
        "counts": {"dossiers": 0, "partial": 0},
        "dossiers": [],
    }
