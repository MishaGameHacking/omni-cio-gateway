from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

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
from omni_cio.contracts.v1.final_decision_review_publisher import (
    FinalDecisionReviewPublicationDisposition,
    FinalDecisionReviewPublicationResultV1,
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
from omni_cio.contracts.v1.observability import ExternalCallStatus
from omni_cio.contracts.v1.risk import RiskOverallStatus
from omni_cio.release.final_decision_review_publisher_v1 import (
    FinalDecisionReviewPublisherError,
    publish_final_decision_review_source,
    publisher_for_registry,
)
from omni_cio.release.final_decision_review_route_v1 import (
    FinalDecisionReviewSourceLookupStatus,
    FinalDecisionReviewSourceRegistryV1,
)


NOW = datetime(2026, 7, 30, 3, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def clear_production_registry() -> None:
    gateway_module.final_decision_review_registry.clear()
    yield
    gateway_module.final_decision_review_registry.clear()


def _response(
    *,
    option_id: str = "option.limited",
    instrument_key: str = "uid:instrument-1",
    fingerprint: str = "a" * 64,
) -> FinalDecisionReviewResponseV1:
    intent = FinalDecisionReviewIntentV1(
        request_id=f"request-{instrument_key.rsplit('-', maxsplit=1)[-1]}",
        instrument_key=instrument_key,
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
        requested_option_id=option_id,
        final_option_id=option_id,
        final_action=DecisionAction.REVIEW_LIMITED_CHANGE,
        direction=OrderSide.BUY,
        intent_fingerprint=fingerprint,
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


def _sources(
    *,
    option_id: str = "option.limited",
    instrument_key: str = "uid:instrument-1",
    fingerprint: str = "a" * 64,
    query_sha256: str = "3" * 64,
    response_sha256: str = "1" * 64,
    action_candidate_sha256: str = "2" * 64,
) -> tuple[
    FinalDecisionReviewRouteImplementationPlanV1,
    FinalDecisionReviewInputBindingV1,
]:
    response = _response(
        option_id=option_id,
        instrument_key=instrument_key,
        fingerprint=fingerprint,
    )
    query = FinalDecisionReviewReadOnlyQueryV1(
        account=response.account,
        requested_option_id=response.requested_option_id,
        final_option_id=response.final_option_id,
        intent_fingerprint=response.intent_fingerprint,
        instrument_count=1,
        instrument_keys=(instrument_key,),
        response_sha256=response_sha256,
        action_candidate_sha256=action_candidate_sha256,
    )
    binding = FinalDecisionReviewInputBindingV1.model_construct(
        status=FinalDecisionReviewInputStatus.VALID,
        input_valid=True,
        blockers=(),
        policy=FinalDecisionReviewInputPolicyV1(),
        query=query,
        query_sha256=query_sha256,
        response_sha256=response_sha256,
        action_candidate_sha256=action_candidate_sha256,
    )
    dossier = FinalDecisionReviewRouteReadinessDossierV1.model_construct(
        response=response,
        input_binding=binding,
        query_sha256=query_sha256,
        response_sha256=response_sha256,
        action_candidate_sha256=action_candidate_sha256,
    )
    plan = FinalDecisionReviewRouteImplementationPlanV1.model_construct(
        status=FinalDecisionReviewRoutePlanStatus.READY_FOR_IMPLEMENTATION_REVIEW,
        ready_for_implementation_review=True,
        blockers=(),
        readiness_dossier=dossier,
        proposed_route=FinalDecisionReviewProposedRouteV1(),
    )
    return plan, binding


def _lookup(
    registry: FinalDecisionReviewSourceRegistryV1,
    binding: FinalDecisionReviewInputBindingV1,
    *,
    requested_at: datetime = NOW,
):
    query = binding.query
    return registry.lookup(
        account=query.account.masked_id,
        requested_option_id=query.requested_option_id,
        final_option_id=query.final_option_id,
        intent_fingerprint=query.intent_fingerprint,
        instrument_count=query.instrument_count,
        instrument_keys=query.instrument_keys,
        requested_at=requested_at,
    )


def test_first_publication_is_internal_safe_and_retrievable() -> None:
    registry = FinalDecisionReviewSourceRegistryV1()
    plan, binding = _sources()

    result = publish_final_decision_review_source(
        registry,
        plan,
        binding,
        correlation_id="corr:publisher-0001",
        request_id="request:publisher-0001",
        published_at=NOW,
    )

    assert result.disposition is FinalDecisionReviewPublicationDisposition.PUBLISHED
    assert result.source_replaced is False
    assert result.registry_active_sources == 1
    assert result.registry_evicted_sources == 0
    assert result.account.masked_id == "****1234"
    assert result.expires_at > result.published_at
    assert result.internal_only is True
    assert result.http_publication_method_created is False
    assert result.external_broker_called is False
    assert result.trade_authorized is False
    assert result.trading_methods is False
    assert result.observability_event.external_call is not None
    assert (
        result.observability_event.external_call.status
        is ExternalCallStatus.NOT_CALLED
    )
    assert _lookup(registry, binding).status is FinalDecisionReviewSourceLookupStatus.FOUND


def test_second_publication_replaces_same_context() -> None:
    registry = FinalDecisionReviewSourceRegistryV1()
    plan, binding = _sources()
    first = publish_final_decision_review_source(
        registry,
        plan,
        binding,
        correlation_id="corr:publisher-0002",
        published_at=NOW,
    )
    second = publish_final_decision_review_source(
        registry,
        plan,
        binding,
        correlation_id="corr:publisher-0003",
        published_at=NOW + timedelta(seconds=1),
    )

    assert first.disposition is FinalDecisionReviewPublicationDisposition.PUBLISHED
    assert second.disposition is FinalDecisionReviewPublicationDisposition.REPLACED
    assert second.source_replaced is True
    assert second.registry_active_sources == 1
    assert second.registry_evicted_sources == 0


def test_bounded_registry_reports_eviction() -> None:
    registry = FinalDecisionReviewSourceRegistryV1(max_entries=1)
    first_plan, first_binding = _sources()
    second_plan, second_binding = _sources(
        option_id="option.second",
        instrument_key="uid:instrument-2",
        fingerprint="b" * 64,
        query_sha256="4" * 64,
        response_sha256="5" * 64,
        action_candidate_sha256="6" * 64,
    )
    publish_final_decision_review_source(
        registry,
        first_plan,
        first_binding,
        correlation_id="corr:publisher-0004",
        published_at=NOW,
    )

    result = publish_final_decision_review_source(
        registry,
        second_plan,
        second_binding,
        correlation_id="corr:publisher-0005",
        published_at=NOW + timedelta(seconds=1),
    )

    assert result.disposition is FinalDecisionReviewPublicationDisposition.PUBLISHED
    assert result.registry_active_sources == 1
    assert result.registry_evicted_sources == 1
    assert _lookup(
        registry,
        first_binding,
        requested_at=NOW + timedelta(seconds=2),
    ).status is FinalDecisionReviewSourceLookupStatus.CONFLICT
    assert _lookup(
        registry,
        second_binding,
        requested_at=NOW + timedelta(seconds=2),
    ).status is FinalDecisionReviewSourceLookupStatus.FOUND


def test_concurrent_publication_uses_one_publisher_lock_per_registry() -> None:
    registry = FinalDecisionReviewSourceRegistryV1()
    plan, binding = _sources()
    assert publisher_for_registry(registry) is publisher_for_registry(registry)

    def publish(index: int):
        return publish_final_decision_review_source(
            registry,
            plan,
            binding,
            correlation_id=f"corr:publisher-{index:04d}",
            published_at=NOW + timedelta(microseconds=index),
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(publish, range(8)))

    dispositions = [result.disposition for result in results]
    assert dispositions.count(FinalDecisionReviewPublicationDisposition.PUBLISHED) == 1
    assert dispositions.count(FinalDecisionReviewPublicationDisposition.REPLACED) == 7
    assert registry.active_source_count(checked_at=NOW + timedelta(seconds=1)) == 1


def test_expiry_and_restart_semantics_remain_fail_closed() -> None:
    registry = FinalDecisionReviewSourceRegistryV1(ttl_seconds=1)
    plan, binding = _sources()
    publish_final_decision_review_source(
        registry,
        plan,
        binding,
        correlation_id="corr:publisher-0006",
        published_at=NOW,
    )

    expired = _lookup(
        registry,
        binding,
        requested_at=NOW + timedelta(seconds=2),
    )
    restarted = FinalDecisionReviewSourceRegistryV1()

    assert expired.status is FinalDecisionReviewSourceLookupStatus.EMPTY
    assert restarted.active_source_count(checked_at=NOW) == 0


def test_blocked_plan_and_context_substitution_are_rejected() -> None:
    registry = FinalDecisionReviewSourceRegistryV1()
    plan, binding = _sources()
    blocked = plan.model_copy(
        update={
            "status": FinalDecisionReviewRoutePlanStatus.BLOCKED,
            "ready_for_implementation_review": False,
            "blockers": (FinalDecisionReviewAcceptanceCheckCode.SOURCE_DOSSIER,),
        }
    )
    with pytest.raises(
        FinalDecisionReviewPublisherError,
        match="FINAL_DECISION_REVIEW_ROUTE_PLAN_NOT_READY",
    ):
        publish_final_decision_review_source(
            registry,
            blocked,
            binding,
            correlation_id="corr:publisher-0007",
            published_at=NOW,
        )

    changed_query = binding.query.model_copy(update={"final_option_id": "option.changed"})
    changed_binding = binding.model_copy(update={"query": changed_query})
    with pytest.raises(
        FinalDecisionReviewPublisherError,
        match="FINAL_DECISION_REVIEW_PUBLISHER_CONTEXT_MISMATCH",
    ):
        publish_final_decision_review_source(
            registry,
            plan,
            changed_binding,
            correlation_id="corr:publisher-0008",
            published_at=NOW,
        )
    assert registry.active_source_count(checked_at=NOW) == 0


def test_invalid_trace_or_timestamp_does_not_mutate_registry() -> None:
    registry = FinalDecisionReviewSourceRegistryV1()
    plan, binding = _sources()

    with pytest.raises(
        FinalDecisionReviewPublisherError,
        match="FINAL_DECISION_REVIEW_PUBLISHER_CORRELATION_ID_INVALID",
    ):
        publish_final_decision_review_source(
            registry,
            plan,
            binding,
            correlation_id="bad",
            published_at=NOW,
        )
    with pytest.raises(
        FinalDecisionReviewPublisherError,
        match="FINAL_DECISION_REVIEW_PUBLISHER_TIMESTAMP_MUST_BE_AWARE",
    ):
        publish_final_decision_review_source(
            registry,
            plan,
            binding,
            correlation_id="corr:publisher-0009",
            published_at=NOW.replace(tzinfo=None),
        )
    assert registry.active_source_count(checked_at=NOW) == 0


def test_publication_result_tampering_is_rejected() -> None:
    registry = FinalDecisionReviewSourceRegistryV1()
    plan, binding = _sources()
    result = publish_final_decision_review_source(
        registry,
        plan,
        binding,
        correlation_id="corr:publisher-0010",
        published_at=NOW,
    )
    payload = result.model_dump(mode="python")
    payload["source_replaced"] = True

    with pytest.raises(ValidationError):
        FinalDecisionReviewPublicationResultV1.model_validate(payload)


def test_internal_publication_does_not_change_production_openapi() -> None:
    gateway_module.app.openapi_schema = None
    before = deepcopy(gateway_module.app.openapi())
    plan, binding = _sources()

    publish_final_decision_review_source(
        gateway_module.final_decision_review_registry,
        plan,
        binding,
        correlation_id="corr:publisher-0011",
        published_at=NOW,
    )

    gateway_module.app.openapi_schema = None
    after = gateway_module.app.openapi()
    assert after == before
    operation_ids = {
        operation["operationId"]
        for path_item in after["paths"].values()
        if isinstance(path_item, dict)
        for method, operation in path_item.items()
        if method == "get" and isinstance(operation, dict)
    }
    assert all("publish" not in operation_id.lower() for operation_id in operation_ids)
    assert all(
        set(path_item).intersection({"post", "put", "patch", "delete"}) == set()
        for path_item in after["paths"].values()
        if isinstance(path_item, dict)
    )
