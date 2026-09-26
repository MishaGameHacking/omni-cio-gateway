from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import Any

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
from omni_cio.research import build_research_dossier
from omni_cio.web.api_v1 import SESSION_COOKIE
from omni_cio.web.research_dossiers_v1 import (
    _DOSSIER_SCHEMA_REF,
    ResearchDossierReadServiceV1,
    _research_dossier,
    _safe_source_location,
    install_research_dossier_routes,
)
from omni_cio.web.session_v1 import SessionScopeV1

NOW = datetime(2026, 8, 13, 18, 0, tzinfo=timezone.utc)


class _Cursor:
    def __init__(self, rows: Sequence[Sequence[Any]]) -> None:
        self.rows = list(rows)

    def fetchall(self) -> list[Sequence[Any]]:
        return list(self.rows)

    def fetchone(self) -> Sequence[Any] | None:
        return self.rows[0] if self.rows else None


class _FixtureConnection:
    def __init__(self, rows: Sequence[Sequence[Any]]) -> None:
        self.rows = list(rows)
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
        if "FROM omni_cio_v10.research_cache rc" in text:
            return _Cursor(self.rows)
        raise AssertionError(text)

    def transaction(self) -> Any:
        raise AssertionError("WP20 read service is read-only")


class _NoSession:
    def resolve(self, value: str | None, *, now: datetime) -> None:
        del value, now
        return None


class _OwnerSession:
    def resolve(self, value: str | None, *, now: datetime) -> SessionScopeV1 | None:
        del now
        if not value:
            return None
        return SessionScopeV1(
            user_id=OWNER_USER_ID,
            tenant_id=OWNER_TENANT_ID,
            expires_at=NOW + timedelta(hours=1),
        )


def _source(
    source_class: EvidenceSourceClass = EvidenceSourceClass.BROKER,
    *,
    authority: SourceAuthority = SourceAuthority.PRIMARY,
    provider: str = "T-Invest",
    source_id: str = "source-1",
    source_location: str | None = "https://example.test/source",
    retrieved_at: datetime = NOW,
) -> ResearchSourceV1:
    return ResearchSourceV1(
        provider=provider,
        source_class=source_class,
        authority=authority,
        source_id=source_id,
        source_location=source_location,
        retrieved_at=retrieved_at,
    )


def _target() -> ResearchTargetV1:
    return ResearchTargetV1(
        funnel_sha256="a" * 64,
        candidate_id="uid:instrument-1",
        instrument_uid="instrument-1",
        instrument_type=InstrumentType.SHARE,
    )


def _requirement(*, max_age_seconds: int = 86_400) -> EvidenceRequirementV1:
    return EvidenceRequirementV1(
        requirement_id="req_fundamental",
        fact_type=EvidenceFactType.FUNDAMENTAL,
        fact_key_prefix="fundamental.revenue_ttm",
        source_classes=(EvidenceSourceClass.BROKER, EvidenceSourceClass.ISSUER),
        minimum_decision_grade_records=1,
        max_age_seconds=max_age_seconds,
        importance=RequirementImportance.CRITICAL,
    )


def _record(
    *,
    value: str,
    source: ResearchSourceV1,
    source_record_id: str,
    fact_type: EvidenceFactType = EvidenceFactType.FUNDAMENTAL,
    fact_key: str = "fundamental.revenue_ttm",
    effective_at: datetime | None = NOW,
    use: EvidenceUse = EvidenceUse.DECISION_GRADE,
):
    return make_evidence_record(
        instrument_uid="instrument-1",
        fact_type=fact_type,
        fact_key=fact_key,
        value=EvidenceValueV1(
            value_type=(
                EvidenceValueType.TEXT
                if fact_type is EvidenceFactType.MATERIAL_EVENT
                else EvidenceValueType.DECIMAL
            ),
            canonical_value=value,
        ),
        source=source,
        use=use,
        source_record_id=source_record_id,
        effective_at=effective_at,
        published_at=effective_at,
    )


def _contradictory_payload() -> bytes:
    broker = _record(
        value="100",
        source=_source(source_id="broker"),
        source_record_id="broker-row",
    )
    issuer = _record(
        value="120",
        source=_source(
            EvidenceSourceClass.ISSUER,
            authority=SourceAuthority.OFFICIAL,
            provider="Issuer",
            source_id="issuer",
            source_location="https://issuer.example/report",
        ),
        source_record_id="issuer-row",
    )
    event = _record(
        value="<em>UNTRUSTED MARKUP</em> Board approved dividend",
        source=_source(
            EvidenceSourceClass.ISSUER,
            authority=SourceAuthority.OFFICIAL,
            provider="<b>Issuer</b>",
            source_id="event",
            source_location="ftp://unsafe.example/source",
        ),
        source_record_id="event-row",
        fact_type=EvidenceFactType.MATERIAL_EVENT,
        fact_key="material_event.board_dividend",
    )
    dossier = build_research_dossier(
        target=_target(),
        records=(broker, issuer, event),
        probes=(),
        requirements=(_requirement(),),
        assessed_at=NOW,
    )
    return dossier.model_dump_json().encode()


def _stale_payload() -> bytes:
    stale_at = NOW - timedelta(days=5)
    record = _record(
        value="90",
        source=_source(source_id="stale", retrieved_at=stale_at),
        source_record_id="stale-row",
        effective_at=stale_at,
    )
    dossier = build_research_dossier(
        target=_target(),
        records=(record,),
        probes=(),
        requirements=(_requirement(max_age_seconds=3600),),
        assessed_at=NOW,
    )
    return dossier.model_dump_json().encode()


def _row(
    payload: bytes | None,
    *,
    schema_ref: str | None = _DOSSIER_SCHEMA_REF,
    broker_uid: str | None = "instrument-1",
    expires_at: datetime = NOW + timedelta(hours=1),
    cache_key: str = "research:instrument-1",
) -> tuple[Any, ...]:
    return (
        cache_key,
        "research-evidence-v1",
        "b" * 64,
        NOW,
        expires_at,
        "instrument:v1:one",
        broker_uid,
        "BBG000000001",
        "RU000A000001",
        "TEST",
        "Test Issuer",
        schema_ref,
        payload,
    )


def _read(rows: Sequence[Sequence[Any]]) -> dict[str, Any]:
    return ResearchDossierReadServiceV1(
        _FixtureConnection(rows),
        clock=lambda: NOW,
    ).read(tenant_id=OWNER_TENANT_ID)


def test_wp20_source_location_and_payload_validation_are_fail_closed() -> None:
    assert _safe_source_location("https://issuer.example/report") == (
        "https://issuer.example/report"
    )
    assert _safe_source_location("ftp://unsafe.example/source") is None
    assert _research_dossier(b"not-json") is None
    assert _research_dossier(_contradictory_payload()) is not None


def test_wp20_projects_canonical_facts_conflict_timeline_and_no_ai_claim() -> None:
    connection = _FixtureConnection((_row(_contradictory_payload()),))
    payload = ResearchDossierReadServiceV1(
        connection,
        clock=lambda: NOW,
    ).read(tenant_id=OWNER_TENANT_ID)
    assert payload["state"] == "PARTIAL"
    assert payload["invalid_dossier_count"] == 0
    assert set(connection.tenants) == {OWNER_TENANT_ID}
    assert len(connection.queries) == 1
    dossier = payload["dossiers"][0]
    assert dossier["security"]["instrument_uid"] == "instrument-1"
    assert dossier["security"]["ticker"] == "TEST"
    assert dossier["decision_ready"] is True
    assert dossier["strong_recommendation_allowed"] is False
    assert len(dossier["contradictions"]) == 1
    assert dossier["contradictions"][0]["severity"] == "critical"
    event = next(
        row for row in dossier["facts"] if row["fact_type"] == "material_event"
    )
    assert event["value"]["canonical"].startswith("<em>")
    assert event["source"]["provider"] == "<b>Issuer</b>"
    assert event["source"]["location"] is None
    assert event["source"]["location_rejected"] is True
    assert dossier["timeline"][0]["fact_type"] == "material_event"
    assert dossier["ai_summary"]["state"] == "NOT_AVAILABLE"
    assert dossier["ai_summary"]["non_authoritative"] is True


def test_wp20_stale_and_unknown_states_remain_explicit() -> None:
    payload = _read((_row(_stale_payload(), expires_at=NOW - timedelta(seconds=1)),))
    assert payload["state"] == "STALE"
    dossier = payload["dossiers"][0]
    assert dossier["cache_freshness"] == "STALE"
    assert dossier["state"] == "STALE"
    assert dossier["unknowns"][0]["reason"] == "stale_record"
    assert dossier["facts"][0]["freshness"] == "STALE"


def test_wp20_invalid_schema_wrong_instrument_and_duplicate_are_not_silently_used() -> (
    None
):
    valid = _contradictory_payload()
    invalid = _read(
        (
            _row(valid, schema_ref="other.schema", cache_key="invalid-schema"),
            _row(valid, broker_uid="other-instrument", cache_key="wrong-binding"),
        )
    )
    assert invalid["state"] == "PARTIAL"
    assert invalid["dossiers"] == []
    assert invalid["invalid_dossier_count"] == 2
    duplicate = _read((_row(valid, cache_key="newer"), _row(valid, cache_key="older")))
    assert len(duplicate["dossiers"]) == 1
    assert duplicate["duplicate_dossier_count"] == 1


def test_wp20_route_requires_session_and_returns_no_store() -> None:
    service = ResearchDossierReadServiceV1(
        _FixtureConnection((_row(_contradictory_payload()),)),
        clock=lambda: NOW,
    )
    denied = FastAPI()
    install_research_dossier_routes(
        denied,
        sessions=_NoSession(),
        service=service,
        now=lambda: NOW,
    )
    assert TestClient(denied).get("/api/v10/web/research-dossiers").status_code == 401
    connection = _FixtureConnection((_row(_contradictory_payload()),))
    allowed = FastAPI()
    install_research_dossier_routes(
        allowed,
        sessions=_OwnerSession(),
        service=ResearchDossierReadServiceV1(connection, clock=lambda: NOW),
        now=lambda: NOW,
    )
    client = TestClient(allowed)
    client.cookies.set(SESSION_COOKIE, "test")
    response = client.get("/api/v10/web/research-dossiers")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert set(connection.tenants) == {OWNER_TENANT_ID}
