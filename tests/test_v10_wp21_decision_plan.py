from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import json
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from omni_cio.contracts.v1.common import (
    AccountReference,
    Completeness,
    ContractMetadata,
    DataQuality,
    QualityMetadata,
    SourceReference,
)
from omni_cio.contracts.v1.decision import (
    DecisionAction,
    DecisionBlocker,
    DecisionConfidence,
    DecisionEvidenceKind,
    DecisionEvidenceV1,
    DecisionOptionKind,
    DecisionOptionStatus,
    DecisionOptionV1,
    DecisionSetV1,
)
from omni_cio.contracts.v1.domain import OWNER_TENANT_ID, OWNER_USER_ID
from omni_cio.contracts.v1.portfolio_optimizer import (
    OptimizerRebalanceLegV1,
    OptimizerTargetPositionV1,
)
from omni_cio.contracts.v1.portfolio_plan import (
    PortfolioPlanAction,
    PortfolioPlanLegV1,
    PortfolioPlanV1,
)
from omni_cio.web.api_v1 import SESSION_COOKIE
from omni_cio.web.decision_plan_v1 import (
    _DECISION_SCHEMA_REF,
    _PLAN_SCHEMA_REF,
    DecisionPlanReadServiceV1,
    _main_decision,
    install_decision_plan_routes,
)
from omni_cio.web.session_v1 import SessionScopeV1
from tests.v9_plan_fixture import NOW, build_fixture


class _Cursor:
    def __init__(self, rows: Sequence[Sequence[Any]]) -> None:
        self.rows = list(rows)

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
        if "FROM omni_cio_v10.decisions d" in text:
            return _Cursor(self.rows)
        raise AssertionError(text)

    def transaction(self) -> Any:
        raise AssertionError("WP21 read service is read-only")


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


def _metadata() -> ContractMetadata:
    return ContractMetadata(
        schema_name="decision_set",
        retrieved_at=NOW,
        account=AccountReference(masked_id="***1234"),
        provenance=(
            SourceReference(
                provider="fixture",
                operation="decision",
                retrieved_at=NOW,
                source_id="wp21-test",
            ),
        ),
        quality=QualityMetadata(
            quality=DataQuality.VERIFIED,
            completeness=Completeness.COMPLETE,
        ),
    )


def _evidence() -> DecisionEvidenceV1:
    return DecisionEvidenceV1(
        evidence_id="fact.portfolio",
        kind=DecisionEvidenceKind.FACT,
        statement="Verified decision evidence.",
        source_schema="portfolio_risk_assessment",
    )


def _decision(*, change: bool) -> DecisionSetV1:
    evidence = _evidence()
    no_action = DecisionOptionV1(
        option_id="option.no_action",
        kind=DecisionOptionKind.NO_ACTION,
        status=(
            DecisionOptionStatus.AVAILABLE if change else DecisionOptionStatus.PREFERRED
        ),
        action=DecisionAction.HOLD,
        title="Hold",
        rationale="No portfolio change is required.",
        confidence=DecisionConfidence.HIGH,
        evidence_ids=(evidence.evidence_id,),
    )
    limited = DecisionOptionV1(
        option_id="option.limited_change",
        kind=DecisionOptionKind.LIMITED_CHANGE,
        status=(
            DecisionOptionStatus.PREFERRED if change else DecisionOptionStatus.AVAILABLE
        ),
        action=DecisionAction.REVIEW_LIMITED_CHANGE,
        title="Review limited change",
        rationale="A bounded exact plan is available for review.",
        confidence=DecisionConfidence.HIGH,
        evidence_ids=(evidence.evidence_id,),
    )
    strategic = DecisionOptionV1(
        option_id="option.strategic_rebalance",
        kind=DecisionOptionKind.STRATEGIC_REBALANCE,
        status=DecisionOptionStatus.REVIEW_ONLY,
        action=DecisionAction.REVIEW_STRATEGIC_REBALANCE,
        title="Strategic alternative",
        rationale="A larger rebalance remains an alternative.",
        confidence=DecisionConfidence.MEDIUM,
        evidence_ids=(evidence.evidence_id,),
    )
    return DecisionSetV1(
        metadata=_metadata(),
        evidence=(evidence,),
        options=(no_action, limited, strategic),
        preferred_option_id=limited.option_id if change else no_action.option_id,
        abstain=False,
        recommendation_ready=True,
        confidence=DecisionConfidence.HIGH,
        global_blockers=(),
        accepted_news_count=1,
        context_news_count=0,
        rejected_news_count=0,
        required_market_count=1,
        market_coverage_count=1,
    )


def _waiting_decision() -> DecisionSetV1:
    evidence = _evidence()
    blocker = DecisionBlocker.MARKET_NOT_READY
    no_action = DecisionOptionV1(
        option_id="option.no_action",
        kind=DecisionOptionKind.NO_ACTION,
        status=DecisionOptionStatus.PREFERRED,
        action=DecisionAction.WAIT_FOR_DATA,
        title="Wait for data",
        rationale="Canonical data is not ready for a recommendation.",
        confidence=DecisionConfidence.LOW,
        evidence_ids=(evidence.evidence_id,),
    )
    limited = DecisionOptionV1(
        option_id="option.limited_change",
        kind=DecisionOptionKind.LIMITED_CHANGE,
        status=DecisionOptionStatus.BLOCKED,
        action=DecisionAction.REVIEW_LIMITED_CHANGE,
        title="Limited change blocked",
        rationale="Change remains blocked until data recovers.",
        confidence=DecisionConfidence.LOW,
        evidence_ids=(evidence.evidence_id,),
        blockers=(blocker,),
    )
    strategic = DecisionOptionV1(
        option_id="option.strategic_rebalance",
        kind=DecisionOptionKind.STRATEGIC_REBALANCE,
        status=DecisionOptionStatus.BLOCKED,
        action=DecisionAction.REVIEW_STRATEGIC_REBALANCE,
        title="Strategic change blocked",
        rationale="Strategic review remains blocked until data recovers.",
        confidence=DecisionConfidence.LOW,
        evidence_ids=(evidence.evidence_id,),
        blockers=(blocker,),
    )
    return DecisionSetV1(
        metadata=_metadata(),
        evidence=(evidence,),
        options=(no_action, limited, strategic),
        preferred_option_id=no_action.option_id,
        abstain=True,
        recommendation_ready=False,
        confidence=DecisionConfidence.LOW,
        global_blockers=(blocker,),
        accepted_news_count=0,
        context_news_count=0,
        rejected_news_count=0,
        required_market_count=1,
        market_coverage_count=0,
    )


def _blob(value: Any) -> tuple[str, bytes]:
    payload = value.model_dump_json().encode("utf-8")
    return hashlib.sha256(payload).hexdigest(), payload


def _row(
    decision: DecisionSetV1,
    plan: PortfolioPlanV1 | None,
    *,
    decision_schema_ref: str = _DECISION_SCHEMA_REF,
    plan_schema_ref: str = _PLAN_SCHEMA_REF,
    plan_payload_override: bytes | None = None,
    snapshot_source_payload_sha256: str | None = None,
    policy_source_id: str | None = None,
) -> tuple[Any, ...]:
    decision_sha, decision_payload = _blob(decision)
    snapshot_sha = snapshot_source_payload_sha256 or (
        plan.portfolio_snapshot_sha256 if plan is not None else "e" * 64
    )
    source_policy_id = policy_source_id or (
        plan.policy_reference.policy_id if plan is not None else "ips_test_policy"
    )
    canonical_policy_id = "policy:v1:canonical"
    if plan is None:
        return (
            "decision:v1:test",
            "portfolio:v1:test",
            canonical_policy_id,
            "snapshot:v1:test",
            "1.0",
            1,
            decision_sha,
            NOW,
            decision_schema_ref,
            decision_payload,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            snapshot_sha,
            source_policy_id,
        )
    plan_sha, plan_payload = _blob(plan)
    if plan_payload_override is not None:
        plan_payload = plan_payload_override
        plan_sha = hashlib.sha256(plan_payload).hexdigest()
    return (
        "decision:v1:test",
        "portfolio:v1:test",
        canonical_policy_id,
        "snapshot:v1:test",
        "1.0",
        1,
        decision_sha,
        NOW,
        decision_schema_ref,
        decision_payload,
        "plan:v1:test",
        "1.0",
        1,
        plan_sha,
        plan.created_at,
        plan_schema_ref,
        plan_payload,
        snapshot_sha,
        source_policy_id,
    )


def test_wp21_actionable_projection_is_exact_read_only_and_tenant_scoped() -> None:
    fixture = build_fixture()
    connection = _FixtureConnection((_row(_decision(change=True), fixture.plan),))
    payload = DecisionPlanReadServiceV1(
        connection,
        clock=lambda: NOW + timedelta(minutes=1),
    ).read(tenant_id=OWNER_TENANT_ID)

    assert payload["state"] == "READY"
    assert payload["main_decision"] == "REALLOCATE"
    assert payload["execution_authorized"] is False
    assert payload["trading_methods"] is False
    assert payload["decision"]["retrieved_at"] == NOW.isoformat()
    assert "decided_at" not in payload["decision"]
    assert payload["record"]["decided_at"] == NOW.isoformat()
    assert set(connection.tenants) == {OWNER_TENANT_ID}
    assert len(connection.queries) == 1
    assert "JOIN omni_cio_v10.portfolio_snapshots s" in connection.queries[0]
    assert "JOIN omni_cio_v10.policies pol" in connection.queries[0]

    plan = payload["plan"]
    assert plan["plan_sha256"] == fixture.plan.plan_sha256
    assert plan["approval_subject"]["state"] == "PREVIEW_ONLY"
    assert plan["approval_subject"]["can_approve"] is False
    assert plan["approval_subject"]["phrase"] == fixture.plan.owner_approval_phrase
    assert plan["targets"][0]["target_lots"] == fixture.plan.targets[0].target_lots
    assert plan["risk"]["before"]["cash_weight"] == format(
        fixture.plan.risk_before.cash_weight, "f"
    )
    assert plan["risk"]["after"]["cash_weight"] == format(
        fixture.plan.risk_after.cash_weight, "f"
    )
    trade = next(row["trade"] for row in plan["legs"] if row["trade"] is not None)
    exact_leg = next(
        row.optimizer_leg for row in fixture.plan.legs if row.optimizer_leg
    )
    assert trade["quantity_lots"] == exact_leg.quantity_lots
    assert trade["commission_base"] == format(exact_leg.commission_base, "f")


def test_wp21_material_plan_mutation_invalidates_approval_ui() -> None:
    fixture = build_fixture()
    raw = fixture.plan.model_dump(mode="json")
    raw["target_cash_base"] = str(Decimal(str(raw["target_cash_base"])) + Decimal("1"))
    mutated_payload = json.dumps(raw, ensure_ascii=False).encode("utf-8")
    payload = DecisionPlanReadServiceV1(
        _FixtureConnection(
            (
                _row(
                    _decision(change=True),
                    fixture.plan,
                    plan_payload_override=mutated_payload,
                ),
            )
        ),
        clock=lambda: NOW,
    ).read(tenant_id=OWNER_TENANT_ID)

    assert payload["state"] == "INVALID"
    assert payload["reason"] == "PLAN_PAYLOAD_INVALID"
    assert payload["plan"] is None
    assert payload["main_decision"] is None
    assert payload["execution_authorized"] is False


def test_wp21_hold_needs_no_plan_and_actionable_decision_fails_partial_without_one() -> (
    None
):
    hold = DecisionPlanReadServiceV1(
        _FixtureConnection((_row(_decision(change=False), None),)),
        clock=lambda: NOW,
    ).read(tenant_id=OWNER_TENANT_ID)
    assert hold["state"] == "READY"
    assert hold["main_decision"] == "HOLD"
    assert hold["plan"] is None

    partial = DecisionPlanReadServiceV1(
        _FixtureConnection((_row(_decision(change=True), None),)),
        clock=lambda: NOW,
    ).read(tenant_id=OWNER_TENANT_ID)
    assert partial["state"] == "PARTIAL"
    assert partial["reason"] == "ACTIONABLE_DECISION_PLAN_MISSING"
    assert partial["main_decision"] is None


def test_wp21_no_change_decisions_cannot_expose_a_bound_plan() -> None:
    fixture = build_fixture()

    hold_with_plan = DecisionPlanReadServiceV1(
        _FixtureConnection((_row(_decision(change=False), fixture.plan),)),
        clock=lambda: NOW,
    ).read(tenant_id=OWNER_TENANT_ID)
    assert hold_with_plan["state"] == "INVALID"
    assert hold_with_plan["reason"] == "NO_CHANGE_DECISION_CANNOT_BIND_PLAN"
    assert hold_with_plan["main_decision"] is None
    assert hold_with_plan["plan"] is None
    assert hold_with_plan["execution_authorized"] is False

    wait_with_plan = DecisionPlanReadServiceV1(
        _FixtureConnection((_row(_waiting_decision(), fixture.plan),)),
        clock=lambda: NOW,
    ).read(tenant_id=OWNER_TENANT_ID)
    assert wait_with_plan["state"] == "INVALID"
    assert wait_with_plan["reason"] == "NO_CHANGE_DECISION_CANNOT_BIND_PLAN"
    assert wait_with_plan["main_decision"] is None
    assert wait_with_plan["plan"] is None
    assert wait_with_plan["execution_authorized"] is False


def test_wp21_wait_for_data_is_no_action_but_never_ready() -> None:
    payload = DecisionPlanReadServiceV1(
        _FixtureConnection((_row(_waiting_decision(), None),)),
        clock=lambda: NOW,
    ).read(tenant_id=OWNER_TENANT_ID)

    assert payload["state"] == "PARTIAL"
    assert payload["reason"] == "DECISION_ABSTAINS_WAIT_FOR_DATA"
    assert payload["main_decision"] == "NO_ACTION"
    assert payload["decision"]["abstain"] is True
    assert payload["execution_authorized"] is False


def test_wp21_persisted_snapshot_and_source_policy_bindings_fail_closed() -> None:
    fixture = build_fixture()
    decision = _decision(change=True)

    wrong_snapshot = DecisionPlanReadServiceV1(
        _FixtureConnection(
            (
                _row(
                    decision,
                    fixture.plan,
                    snapshot_source_payload_sha256="9" * 64,
                ),
            )
        ),
        clock=lambda: NOW,
    ).read(tenant_id=OWNER_TENANT_ID)
    assert wrong_snapshot["state"] == "INVALID"
    assert wrong_snapshot["reason"] == "PLAN_RECORD_BINDING_INVALID"

    wrong_policy = DecisionPlanReadServiceV1(
        _FixtureConnection(
            (
                _row(
                    decision,
                    fixture.plan,
                    policy_source_id="ips_wrong_policy",
                ),
            )
        ),
        clock=lambda: NOW,
    ).read(tenant_id=OWNER_TENANT_ID)
    assert wrong_policy["state"] == "INVALID"
    assert wrong_policy["reason"] == "PLAN_RECORD_BINDING_INVALID"


def test_wp21_limited_sell_projection_distinguishes_reduce_and_exit() -> None:
    decision = _decision(change=True)
    sell_leg = OptimizerRebalanceLegV1.model_construct(stable_key="asset-1")
    leg = PortfolioPlanLegV1.model_construct(
        sequence=1,
        action=PortfolioPlanAction.SELL,
        optimizer_leg=sell_leg,
    )
    exit_target = OptimizerTargetPositionV1.model_construct(
        stable_key="asset-1", target_lots=0
    )
    reduce_target = OptimizerTargetPositionV1.model_construct(
        stable_key="asset-1", target_lots=2
    )
    exit_plan = PortfolioPlanV1.model_construct(legs=(leg,), targets=(exit_target,))
    reduce_plan = PortfolioPlanV1.model_construct(legs=(leg,), targets=(reduce_target,))

    assert _main_decision(decision, exit_plan) == "EXIT"
    assert _main_decision(decision, reduce_plan) == "REDUCE"


def test_wp21_expiry_hides_approval_phrase_without_rewriting_plan() -> None:
    fixture = build_fixture()
    payload = DecisionPlanReadServiceV1(
        _FixtureConnection((_row(_decision(change=True), fixture.plan),)),
        clock=lambda: fixture.plan.expires_at + timedelta(seconds=1),
    ).read(tenant_id=OWNER_TENANT_ID)
    assert payload["state"] == "EXPIRED"
    assert payload["plan"]["approval_subject"]["state"] == "EXPIRED"
    assert payload["plan"]["approval_subject"]["phrase"] is None
    assert payload["plan"]["approval_subject"]["can_approve"] is False


def test_wp21_route_requires_session_and_returns_no_store() -> None:
    fixture = build_fixture()
    service = DecisionPlanReadServiceV1(
        _FixtureConnection((_row(_decision(change=True), fixture.plan),)),
        clock=lambda: NOW,
    )
    denied = FastAPI()
    install_decision_plan_routes(
        denied,
        sessions=_NoSession(),
        service=service,
        now=lambda: NOW,
    )
    assert TestClient(denied).get("/api/v10/web/decision-plan").status_code == 401

    connection = _FixtureConnection((_row(_decision(change=True), fixture.plan),))
    allowed = FastAPI()
    install_decision_plan_routes(
        allowed,
        sessions=_OwnerSession(),
        service=DecisionPlanReadServiceV1(connection, clock=lambda: NOW),
        now=lambda: NOW,
    )
    client = TestClient(allowed)
    client.cookies.set(SESSION_COOKIE, "test")
    response = client.get("/api/v10/web/decision-plan")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert set(connection.tenants) == {OWNER_TENANT_ID}
