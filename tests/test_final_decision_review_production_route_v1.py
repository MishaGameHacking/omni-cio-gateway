from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

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
    FinalDecisionReviewAcceptanceCheckCode,
    FinalDecisionReviewRouteImplementationPlanV1,
    FinalDecisionReviewRoutePlanStatus,
)
from omni_cio.contracts.v1.final_decision_review_route_readiness import (
    FinalDecisionReviewRouteReadinessDossierV1,
)
from omni_cio.contracts.v1.risk import RiskOverallStatus
from omni_cio.release.final_decision_review_route_v1 import (
    FINAL_REVIEW_OPERATION_ID,
    FINAL_REVIEW_PATH,
    FinalDecisionReviewRouteError,
    FinalDecisionReviewSourceLookupStatus,
    FinalDecisionReviewSourceRegistryV1,
)


NOW = datetime(2026, 7, 30, 2, 0, tzinfo=timezone.utc)
client = TestClient(gateway_module.app)


@pytest.fixture(autouse=True)
def clear_production_registry() -> None:
    gateway_module.final_decision_review_registry.clear()
    yield
    gateway_module.final_decision_review_registry.clear()


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
    values = [
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


def _headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer regression-test-gateway-key",
        "X-Correlation-ID": "corr:12345678",
        "X-Request-ID": "request:12345678",
    }


def _replace_param(
    params: list[tuple[str, str]],
    name: str,
    value: str,
) -> list[tuple[str, str]]:
    return [
        (key, value if key == name else current)
        for key, current in params
    ]


def test_empty_registry_returns_503_after_authentication() -> None:
    _, binding = _sources()

    result = client.get(
        FINAL_REVIEW_PATH,
        params=_params(binding),
        headers=_headers(),
    )

    assert result.status_code == 503
    assert result.json()["error"]["code"] == "FINAL_REVIEW_SOURCE_UNAVAILABLE"
    assert result.json()["trading_methods"] is False


def test_exact_published_source_returns_only_compact_response() -> None:
    plan, binding = _sources()
    gateway_module.final_decision_review_registry.publish(plan, binding)

    result = client.get(
        FINAL_REVIEW_PATH,
        params=_params(binding),
        headers=_headers(),
    )

    assert result.status_code == 200
    assert result.json() == plan.readiness_dossier.response.model_dump(mode="json")
    assert result.json()["account"]["masked_id"] == "****1234"
    assert result.json()["trade_authorized"] is False
    assert result.json()["trading_methods"] is False


def test_context_substitution_returns_409_without_response_data() -> None:
    plan, binding = _sources()
    gateway_module.final_decision_review_registry.publish(plan, binding)
    params = _replace_param(_params(binding), "final_option_id", "option.changed")

    result = client.get(FINAL_REVIEW_PATH, params=params, headers=_headers())

    assert result.status_code == 409
    assert result.json()["error"]["code"] == "FINAL_REVIEW_SOURCE_CONFLICT"
    assert "account" not in result.json()


def test_digest_substitution_returns_409() -> None:
    plan, binding = _sources()
    gateway_module.final_decision_review_registry.publish(plan, binding)
    params = _replace_param(_params(binding), "response_sha256", "f" * 64)

    result = client.get(FINAL_REVIEW_PATH, params=params, headers=_headers())

    assert result.status_code == 409
    assert result.json()["error"]["code"] == "FINAL_REVIEW_SOURCE_CONFLICT"


def test_unmasked_account_returns_400() -> None:
    _, binding = _sources()
    params = _replace_param(_params(binding), "account", "12345678")

    result = client.get(FINAL_REVIEW_PATH, params=params, headers=_headers())

    assert result.status_code == 400
    assert result.json()["error"]["code"] == "FINAL_REVIEW_INVALID_REQUEST"


def test_missing_required_query_parameter_returns_422() -> None:
    _, binding = _sources()
    params = [item for item in _params(binding) if item[0] != "intent_fingerprint"]

    result = client.get(FINAL_REVIEW_PATH, params=params, headers=_headers())

    assert result.status_code == 422


def test_missing_gateway_key_is_rejected_before_registry_lookup() -> None:
    _, binding = _sources()

    result = client.get(FINAL_REVIEW_PATH, params=_params(binding))

    assert result.status_code == 401
    assert result.json()["detail"]["code"] == "INVALID_GATEWAY_KEY"
    assert gateway_module.final_decision_review_registry.active_source_count() == 0


def test_registry_prunes_expired_sources() -> None:
    plan, binding = _sources()
    registry = FinalDecisionReviewSourceRegistryV1(ttl_seconds=1)
    registry.publish(plan, binding, published_at=NOW)

    result = registry.lookup(
        account=binding.query.account.masked_id,
        requested_option_id=binding.query.requested_option_id,
        final_option_id=binding.query.final_option_id,
        intent_fingerprint=binding.query.intent_fingerprint,
        instrument_count=binding.query.instrument_count,
        instrument_keys=binding.query.instrument_keys,
        requested_at=NOW + timedelta(seconds=2),
    )

    assert result.status is FinalDecisionReviewSourceLookupStatus.EMPTY
    assert result.source is None
    assert result.active_source_count == 0


def test_registry_is_bounded_and_evicts_oldest_context() -> None:
    plan, binding = _sources()
    registry = FinalDecisionReviewSourceRegistryV1(max_entries=1)
    registry.publish(plan, binding, published_at=NOW)
    changed_query = binding.query.model_copy(
        update={
            "requested_option_id": "option.second",
            "final_option_id": "option.second",
        }
    )
    changed_binding = binding.model_copy(update={"query": changed_query})
    changed_dossier = plan.readiness_dossier.model_copy(
        update={"input_binding": changed_binding}
    )
    changed_plan = plan.model_copy(update={"readiness_dossier": changed_dossier})
    registry.publish(
        changed_plan,
        changed_binding,
        published_at=NOW + timedelta(seconds=1),
    )

    first = registry.lookup(
        account=binding.query.account.masked_id,
        requested_option_id=binding.query.requested_option_id,
        final_option_id=binding.query.final_option_id,
        intent_fingerprint=binding.query.intent_fingerprint,
        instrument_count=binding.query.instrument_count,
        instrument_keys=binding.query.instrument_keys,
        requested_at=NOW + timedelta(seconds=2),
    )

    assert first.status is FinalDecisionReviewSourceLookupStatus.CONFLICT
    assert registry.active_source_count(checked_at=NOW + timedelta(seconds=2)) == 1


def test_registry_rejects_unready_plan() -> None:
    plan, binding = _sources()
    blocked = plan.model_copy(
        update={
            "status": FinalDecisionReviewRoutePlanStatus.BLOCKED,
            "ready_for_implementation_review": False,
            "blockers": (FinalDecisionReviewAcceptanceCheckCode.SOURCE_DOSSIER,),
        }
    )

    with pytest.raises(
        FinalDecisionReviewRouteError,
        match="FINAL_DECISION_REVIEW_ROUTE_PLAN_NOT_READY",
    ):
        FinalDecisionReviewSourceRegistryV1().publish(blocked, binding)


def test_openapi_exposes_exact_private_get_candidate() -> None:
    gateway_module.app.openapi_schema = None
    schema = gateway_module.app.openapi()
    operation = schema["paths"][FINAL_REVIEW_PATH]["get"]

    assert operation["operationId"] == FINAL_REVIEW_OPERATION_ID
    assert operation["security"] == [{"ApiKeyAuth": []}]
    assert "requestBody" not in operation
    query_parameters = [
        parameter for parameter in operation["parameters"] if parameter["in"] == "query"
    ]
    assert tuple(parameter["name"] for parameter in query_parameters) == (
        "account",
        "requested_option_id",
        "final_option_id",
        "intent_fingerprint",
        "instrument_count",
        "instrument_keys",
        "response_sha256",
        "action_candidate_sha256",
    )
    assert all(parameter["required"] for parameter in query_parameters)
    response_schema = operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    assert response_schema == {
        "$ref": "#/components/schemas/FinalDecisionReviewResponseV1"
    }
    component = schema["components"]["schemas"]["FinalDecisionReviewResponseV1"]
    assert component["type"] == "object"
    assert "trading_methods" in component["properties"]
    assert schema["components"]["securitySchemes"]["ApiKeyAuth"] == {
        "type": "http",
        "scheme": "bearer",
    }
