from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("TINVEST_TOKEN", "regression-test-tinvest-token")
os.environ.setdefault("GATEWAY_API_KEY", "regression-test-gateway-key")
os.environ.setdefault(
    "RENDER_EXTERNAL_URL",
    "https://omni-cio-gateway.onrender.com",
)

import app as gateway_module
from omni_cio.contracts.v1.capacity import OrderSide
from omni_cio.contracts.v1.common import AccountReference
from omni_cio.contracts.v1.decision import DecisionAction
from omni_cio.contracts.v1.decision_capacity import CapacityDecisionGateStatus
from omni_cio.contracts.v1.decision_pro_forma_risk_binding import (
    ProFormaRiskIntentBindingV1,
)
from omni_cio.contracts.v1.final_decision_review import (
    FinalDecisionReviewDisposition,
    FinalDecisionReviewIntentV1,
    FinalDecisionReviewResponseV1,
    FinalDecisionReviewRiskSummaryV1,
    FinalDecisionReviewSourceV1,
    FinalDecisionReviewWarning,
)
from omni_cio.contracts.v1.final_decision_review_approved_invocation import (
    ApprovedCalculatorOperation,
)
from omni_cio.contracts.v1.final_decision_review_input import (
    FinalDecisionReviewInputBindingV1,
    FinalDecisionReviewInputPolicyV1,
    FinalDecisionReviewInputStatus,
    FinalDecisionReviewReadOnlyQueryV1,
)
from omni_cio.contracts.v1.final_decision_review_route_plan import (
    FinalDecisionReviewProposedRouteV1,
    FinalDecisionReviewRouteImplementationPlanV1,
    FinalDecisionReviewRoutePlanStatus,
)
from omni_cio.contracts.v1.final_decision_review_route_readiness import (
    FinalDecisionReviewRouteReadinessDossierV1,
)
from omni_cio.contracts.v1.risk import RiskOverallStatus
from omni_cio.release.final_decision_review_authenticated_route_context_v1 import (
    FinalDecisionReviewApprovedRouteContextSeedV1,
    FinalDecisionReviewApprovedRouteContextStoreV1,
    FinalDecisionReviewAuthenticatedRouteContextError,
    build_final_decision_review_approved_route_context_seed,
    build_final_decision_review_authenticated_server_context,
)
from omni_cio.release.final_decision_review_route_v1 import FINAL_REVIEW_PATH


ACCOUNT = AccountReference(masked_id="****1234")
NOW = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
client = TestClient(gateway_module.app)


@pytest.fixture(autouse=True)
def clear_context_state() -> None:
    gateway_module.final_decision_review_registry.clear()
    gateway_module.final_decision_review_production_runtime.approved_route_context_store.clear()
    yield
    gateway_module.final_decision_review_registry.clear()
    gateway_module.final_decision_review_production_runtime.approved_route_context_store.clear()


def _response() -> FinalDecisionReviewResponseV1:
    intent = FinalDecisionReviewIntentV1(
        request_id="request-1",
        instrument_key="uid:instrument-1",
        side=OrderSide.BUY,
        currency="RUB",
        quantity_lots=1,
        lot_size=10,
        reference_price=Decimal("100"),
        intended_execution_days=1,
        units=10,
        order_notional=Decimal("1000"),
    )
    return FinalDecisionReviewResponseV1(
        generated_at=NOW,
        status=CapacityDecisionGateStatus.READY,
        disposition=FinalDecisionReviewDisposition.REVIEW_READY,
        review_ready=True,
        abstain=False,
        account=ACCOUNT,
        requested_option_id="option.limited",
        final_option_id="option.limited",
        final_action=DecisionAction.REVIEW_LIMITED_CHANGE,
        direction=OrderSide.BUY,
        intent_fingerprint="a" * 64,
        instrument_count=1,
        intents=(intent,),
        risk=FinalDecisionReviewRiskSummaryV1(
            current_status=RiskOverallStatus.PASS,
            pro_forma_status=RiskOverallStatus.PASS,
            current_breach_count=0,
            pro_forma_breach_count=0,
            breach_count_delta=0,
            current_warning_count=0,
            pro_forma_warning_count=0,
            warning_count_delta=0,
            current_unknown_count=0,
            pro_forma_unknown_count=0,
            unknown_count_delta=0,
            status_changed=False,
        ),
        risk_change_approval_confirmed=True,
        response_warnings=tuple(FinalDecisionReviewWarning),
        source_count=1,
        provenance=(
            FinalDecisionReviewSourceV1(
                provider="broker",
                operation="read_only_preview",
                retrieved_at=NOW,
            ),
        ),
    )


def _sources() -> tuple[
    FinalDecisionReviewRouteImplementationPlanV1,
    FinalDecisionReviewInputBindingV1,
]:
    response = _response()
    query = FinalDecisionReviewReadOnlyQueryV1(
        account=response.account,
        requested_option_id=response.requested_option_id,
        final_option_id=response.final_option_id,
        intent_fingerprint=response.intent_fingerprint,
        instrument_count=1,
        instrument_keys=("uid:instrument-1",),
        response_sha256="1" * 64,
        action_candidate_sha256="2" * 64,
    )
    binding = FinalDecisionReviewInputBindingV1.model_construct(
        status=FinalDecisionReviewInputStatus.VALID,
        input_valid=True,
        blockers=(),
        policy=FinalDecisionReviewInputPolicyV1(),
        query=query,
        query_sha256="3" * 64,
        response_sha256="1" * 64,
        action_candidate_sha256="2" * 64,
    )
    dossier = FinalDecisionReviewRouteReadinessDossierV1.model_construct(
        response=response,
        input_binding=binding,
    )
    plan = FinalDecisionReviewRouteImplementationPlanV1.model_construct(
        status=FinalDecisionReviewRoutePlanStatus.READY_FOR_IMPLEMENTATION_REVIEW,
        ready_for_implementation_review=True,
        blockers=(),
        readiness_dossier=dossier,
        proposed_route=FinalDecisionReviewProposedRouteV1(),
    )
    return plan, binding


def _params(binding: FinalDecisionReviewInputBindingV1) -> list[tuple[str, str]]:
    query = binding.query
    result = [
        ("account", query.account.masked_id),
        ("requested_option_id", query.requested_option_id),
        ("final_option_id", query.final_option_id),
        ("intent_fingerprint", query.intent_fingerprint),
        ("instrument_count", str(query.instrument_count)),
        ("response_sha256", query.response_sha256),
        ("action_candidate_sha256", query.action_candidate_sha256),
    ]
    result.extend(("instrument_keys", value) for value in query.instrument_keys)
    return result


def _headers(*, authenticated: bool = True) -> dict[str, str]:
    result = {
        "X-Correlation-ID": "corr:route-request",
        "X-Request-ID": "request:route-request",
    }
    if authenticated:
        result["Authorization"] = "Bearer regression-test-gateway-key"
    return result


def _seed(observed_at: datetime) -> FinalDecisionReviewApprovedRouteContextSeedV1:
    return FinalDecisionReviewApprovedRouteContextSeedV1(
        scenario_id="scenario:trusted-1",
        correlation_id="corr:publication-1",
        operation=ApprovedCalculatorOperation.PURCHASE_REVIEW,
        account=ACCOUNT,
        observed_at=observed_at,
    )


def test_seed_is_derived_from_trusted_binding_only() -> None:
    scenario = SimpleNamespace(
        scenario_id="scenario:trusted-1",
        account=ACCOUNT,
        direction=OrderSide.BUY,
        intent_fingerprint="a" * 64,
    )
    source_binding = ProFormaRiskIntentBindingV1.model_construct(
        scenario=scenario,
        base_explanation=SimpleNamespace(
            risk_evaluation=SimpleNamespace(
                metadata=SimpleNamespace(account=ACCOUNT),
            ),
        ),
        direction=OrderSide.BUY,
        intent_fingerprint="a" * 64,
    )

    seed = build_final_decision_review_approved_route_context_seed(
        source_binding,
        correlation_id="corr:publication-1",
        observed_at=NOW,
    )

    assert seed.scenario_id == "scenario:trusted-1"
    assert seed.correlation_id == "corr:publication-1"
    assert seed.operation is ApprovedCalculatorOperation.PURCHASE_REVIEW
    assert seed.account == ACCOUNT
    assert seed.authenticated is False
    assert seed.credentials_present is False
    assert seed.trading_methods is False


def test_authenticated_context_requires_existing_bearer_gate() -> None:
    with pytest.raises(
        FinalDecisionReviewAuthenticatedRouteContextError,
        match="FINAL_DECISION_REVIEW_ROUTE_CONTEXT_AUTHENTICATION_REQUIRED",
    ):
        build_final_decision_review_authenticated_server_context(
            _seed(NOW),
            account=ACCOUNT,
            direction=OrderSide.BUY,
            authentication_confirmed=False,
            authenticated_at=NOW,
        )


def test_context_store_is_bounded_and_expires() -> None:
    store = FinalDecisionReviewApprovedRouteContextStoreV1(
        ttl_seconds=60,
        capacity=1,
    )
    first = build_final_decision_review_authenticated_server_context(
        _seed(NOW),
        account=ACCOUNT,
        direction=OrderSide.BUY,
        authentication_confirmed=True,
        authenticated_at=NOW,
        invocation_id="invoke:first",
    )
    second = build_final_decision_review_authenticated_server_context(
        _seed(NOW + timedelta(seconds=1)),
        account=ACCOUNT,
        direction=OrderSide.BUY,
        authentication_confirmed=True,
        authenticated_at=NOW + timedelta(seconds=1),
        invocation_id="invoke:second",
    )

    assert store.capture(first).evicted is False
    assert store.capture(second).evicted is True
    assert store.get("invoke:first", checked_at=NOW + timedelta(seconds=1)) is None
    assert store.get("invoke:second", checked_at=NOW + timedelta(seconds=61)) is None


def test_unauthenticated_route_does_not_capture_context() -> None:
    plan, binding = _sources()
    published_at = datetime.now(timezone.utc)
    gateway_module.final_decision_review_registry.publish(
        plan,
        binding,
        approved_context_seed=_seed(published_at),
        published_at=published_at,
    )

    result = client.get(
        FINAL_REVIEW_PATH,
        params=_params(binding),
        headers=_headers(authenticated=False),
    )

    assert result.status_code == 401
    assert (
        gateway_module.final_decision_review_production_runtime
        .approved_route_context_store.active_context_count()
        == 0
    )


def test_exact_authenticated_route_captures_one_approved_context() -> None:
    plan, binding = _sources()
    published_at = datetime.now(timezone.utc)
    gateway_module.final_decision_review_registry.publish(
        plan,
        binding,
        approved_context_seed=_seed(published_at),
        published_at=published_at,
    )

    result = client.get(
        FINAL_REVIEW_PATH,
        params=_params(binding),
        headers=_headers(),
    )

    assert result.status_code == 200
    assert result.json() == plan.readiness_dossier.response.model_dump(mode="json")
    assert (
        gateway_module.final_decision_review_production_runtime
        .approved_route_context_store.active_context_count()
        == 1
    )


def test_stale_seed_does_not_capture_or_break_existing_read_only_response() -> None:
    plan, binding = _sources()
    published_at = datetime.now(timezone.utc) - timedelta(seconds=301)
    gateway_module.final_decision_review_registry.publish(
        plan,
        binding,
        approved_context_seed=_seed(published_at),
        published_at=published_at,
    )

    result = client.get(
        FINAL_REVIEW_PATH,
        params=_params(binding),
        headers=_headers(),
    )

    assert result.status_code == 200
    assert (
        gateway_module.final_decision_review_production_runtime
        .approved_route_context_store.active_context_count()
        == 0
    )


def test_route_context_lifecycle_adds_no_http_or_write_surface() -> None:
    paths = gateway_module.app.openapi()["paths"]
    operations = [
        (path, method, operation)
        for path, path_item in paths.items()
        for method, operation in path_item.items()
        if method.lower() in {"get", "post", "put", "patch", "delete"}
    ]
    assert len(operations) == 14
    assert all(method.lower() == "get" for _, method, _ in operations)
    assert all("requestBody" not in operation for _, _, operation in operations)

    source = Path(
        "omni_cio/release/final_decision_review_authenticated_route_context_v1.py"
    ).read_text(encoding="utf-8").lower()
    forbidden = (
        "@app.get",
        "@app.post",
        "@app.put",
        "@app.patch",
        "@app.delete",
        ".post_order(",
        ".replace_order(",
        ".cancel_order(",
        "authorization",
        "tinvest_token",
        "gateway_api_key",
    )
    assert all(marker not in source for marker in forbidden)
