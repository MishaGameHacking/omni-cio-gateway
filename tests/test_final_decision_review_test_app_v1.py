from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient

from omni_cio.contracts.v1.capacity import OrderSide
from omni_cio.contracts.v1.common import AccountReference
from omni_cio.contracts.v1.decision import DecisionAction
from omni_cio.contracts.v1.decision_capacity import CapacityDecisionGateStatus
from omni_cio.contracts.v1.final_decision_review import (
    FinalDecisionReviewDisposition,
    FinalDecisionReviewIntentV1,
    FinalDecisionReviewResponseV1,
    FinalDecisionReviewRiskSummaryV1,
    FinalDecisionReviewSourceV1,
    FinalDecisionReviewWarning,
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
from omni_cio.release.final_decision_review_test_app_v1 import (
    TEST_APP_SERVER,
    TEST_APP_VERSION,
    build_isolated_final_decision_review_test_app,
)
from omni_cio.release.read_only_contract_v1 import build_read_only_release_manifest


NOW = datetime(2026, 7, 29, 23, 30, tzinfo=timezone.utc)


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
        account=AccountReference(masked_id="****1234"),
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
    policy = FinalDecisionReviewInputPolicyV1()
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
        policy=policy,
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
    values: list[tuple[str, str]] = [
        ("account", query.account.masked_id),
        ("requested_option_id", query.requested_option_id),
        ("final_option_id", query.final_option_id),
        ("intent_fingerprint", query.intent_fingerprint),
        ("instrument_count", str(query.instrument_count)),
        ("response_sha256", query.response_sha256),
        ("action_candidate_sha256", query.action_candidate_sha256),
    ]
    values.extend(("instrument_keys", item) for item in query.instrument_keys)
    return values


def _client(*, source_available: bool = True) -> tuple[
    TestClient,
    FinalDecisionReviewRouteImplementationPlanV1,
    FinalDecisionReviewInputBindingV1,
]:
    plan, binding = _sources()
    app = build_isolated_final_decision_review_test_app(
        plan,
        binding,
        authentication_validator=lambda value: value == "allow",
        source_available=source_available,
    )
    return TestClient(app), plan, binding


def _headers(*, authenticated: bool = True) -> dict[str, str]:
    headers = {
        "X-Correlation-ID": "corr:12345678",
        "X-Request-ID": "request:12345678",
    }
    if authenticated:
        headers["X-Gateway-API-Key"] = "allow"
    return headers


def _replace_param(
    params: list[tuple[str, str]],
    name: str,
    value: str,
) -> list[tuple[str, str]]:
    return [
        (key, value if key == name else current)
        for key, current in params
    ]


def test_exact_authenticated_query_returns_only_compact_response() -> None:
    client, plan, binding = _client()

    result = client.get(
        "/decision/final-review",
        params=_params(binding),
        headers=_headers(),
    )

    assert result.status_code == 200
    assert result.json() == plan.readiness_dossier.response.model_dump(mode="json")
    assert result.json()["account"]["masked_id"] == "****1234"
    assert result.json()["trading_methods"] is False


def test_unmasked_account_maps_to_400() -> None:
    client, _, binding = _client()
    params = _replace_param(_params(binding), "account", "12345678")

    result = client.get(
        "/decision/final-review",
        params=params,
        headers=_headers(),
    )

    assert result.status_code == 400
    assert result.json()["error"]["code"] == "FINAL_REVIEW_INVALID_REQUEST"
    assert result.json()["trading_methods"] is False


def test_missing_required_query_parameter_maps_to_422() -> None:
    client, _, binding = _client()
    params = [item for item in _params(binding) if item[0] != "intent_fingerprint"]

    result = client.get(
        "/decision/final-review",
        params=params,
        headers=_headers(),
    )

    assert result.status_code == 422


def test_missing_authentication_maps_to_401() -> None:
    client, _, binding = _client()

    result = client.get(
        "/decision/final-review",
        params=_params(binding),
        headers=_headers(authenticated=False),
    )

    assert result.status_code == 401
    assert (
        result.json()["error"]["code"]
        == "FINAL_REVIEW_AUTHENTICATION_REQUIRED"
    )
    assert "response" not in result.json()


def test_option_substitution_maps_to_409() -> None:
    client, _, binding = _client()
    params = _replace_param(
        _params(binding),
        "final_option_id",
        "option.substituted",
    )

    result = client.get(
        "/decision/final-review",
        params=params,
        headers=_headers(),
    )

    assert result.status_code == 409
    assert result.json()["error"]["code"] == "FINAL_REVIEW_SOURCE_CONFLICT"


def test_unavailable_source_maps_to_503() -> None:
    client, _, binding = _client(source_available=False)

    result = client.get(
        "/decision/final-review",
        params=_params(binding),
        headers=_headers(),
    )

    assert result.status_code == 503
    assert result.json()["error"]["code"] == "FINAL_REVIEW_SOURCE_UNAVAILABLE"


def test_isolated_openapi_matches_reviewed_candidate_and_release_guard() -> None:
    client, plan, _ = _client()
    app = client.app
    schema: dict[str, Any] = app.openapi()

    manifest = build_read_only_release_manifest(
        schema,
        expected_app_version=TEST_APP_VERSION,
        approved_hosts=frozenset({"omni-cio-gateway.onrender.com"}),
        generated_at=NOW,
    )

    assert schema["servers"] == [{"url": TEST_APP_SERVER}]
    operation = schema["paths"]["/decision/final-review"]["get"]
    assert operation["operationId"] == "getFinalDecisionReview"
    assert operation["security"] == [{"ApiKeyAuth": []}]
    assert "post" not in schema["paths"]["/decision/final-review"]
    assert manifest.action_count == 1
    assert manifest.public_action_count == 0
    assert manifest.authenticated_action_count == 1
    assert manifest.get_only is True
    assert manifest.trading_methods is False
    assert plan.proposed_route.path == "/decision/final-review"
    assert plan.proposed_route.method == "get"
    assert plan.proposed_route.operation_id == "getFinalDecisionReview"
    assert app.state.isolated_candidate is True
    assert app.state.production_app_imported is False
    assert app.state.production_app_mutated is False
    assert app.state.trading_methods is False
