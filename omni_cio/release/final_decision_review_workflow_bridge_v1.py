from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
from typing import Any
from urllib.parse import urlparse

from omni_cio.contracts.v1.capacity import CapacityOrderRequestV1
from omni_cio.contracts.v1.decision_pro_forma_risk_binding import ProFormaRiskIntentBindingV1
from omni_cio.contracts.v1.decision_risk_pretrade_explanation import (
    RiskPreTradeExplanationEnvelopeV1,
)
from omni_cio.contracts.v1.final_decision_review_workflow_bridge import (
    FinalDecisionReviewWorkflowBridgeResultV1,
    FinalDecisionReviewWorkflowBridgeStage,
    FinalDecisionReviewWorkflowBridgeStatus,
)
from omni_cio.contracts.v1.risk import RiskPolicyEvaluationV1
from omni_cio.decision.pro_forma_risk_binding_v1 import (
    bind_pro_forma_risk_to_intent,
    build_pro_forma_risk_scenario,
)
from omni_cio.release.final_decision_review_orchestration_v1 import (
    FinalDecisionReviewOrchestrationError,
    orchestrate_final_decision_review_publication,
)
from omni_cio.release.final_decision_review_route_v1 import (
    FinalDecisionReviewSourceRegistryV1,
)


class FinalDecisionReviewWorkflowBridgeError(ValueError):
    """The internal production workflow bridge cannot be configured safely."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise FinalDecisionReviewWorkflowBridgeError(
            "FINAL_DECISION_REVIEW_WORKFLOW_BRIDGE_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)


def _approved_hosts_from_openapi(schema: Mapping[str, Any]) -> frozenset[str]:
    servers = schema.get("servers")
    if not isinstance(servers, list) or not servers:
        raise FinalDecisionReviewWorkflowBridgeError(
            "FINAL_DECISION_REVIEW_WORKFLOW_BRIDGE_SERVERS_REQUIRED"
        )
    hosts: set[str] = set()
    for row in servers:
        if not isinstance(row, Mapping):
            continue
        raw_url = row.get("url")
        if not isinstance(raw_url, str):
            continue
        parsed = urlparse(raw_url.strip())
        try:
            port = parsed.port
        except ValueError:
            continue
        if (
            parsed.scheme == "https"
            and parsed.hostname
            and port in {None, 443}
            and not parsed.username
            and not parsed.password
            and parsed.path in {"", "/"}
            and not parsed.query
            and not parsed.fragment
        ):
            hosts.add(parsed.hostname)
    if not hosts:
        raise FinalDecisionReviewWorkflowBridgeError(
            "FINAL_DECISION_REVIEW_WORKFLOW_BRIDGE_HTTPS_HOST_REQUIRED"
        )
    return frozenset(hosts)


def _blocked_result(
    *,
    bridged_at: datetime,
    stage: FinalDecisionReviewWorkflowBridgeStage,
    blocker: str,
    registry: FinalDecisionReviewSourceRegistryV1,
    scenario: Any = None,
    source_binding: ProFormaRiskIntentBindingV1 | None = None,
) -> FinalDecisionReviewWorkflowBridgeResultV1:
    return FinalDecisionReviewWorkflowBridgeResultV1(
        bridged_at=bridged_at,
        status=FinalDecisionReviewWorkflowBridgeStatus.BLOCKED,
        completed_stage=stage,
        published=False,
        primary_blocker=blocker,
        scenario=scenario,
        source_binding=source_binding,
        registry_active_sources=registry.active_source_count(checked_at=bridged_at),
    )


class FinalDecisionReviewWorkflowBridgeV1:
    """Process-local bridge from validated risk evidence to PR-63 publication."""

    def __init__(
        self,
        *,
        registry: FinalDecisionReviewSourceRegistryV1,
        openapi_provider: Callable[[], Mapping[str, Any]],
        expected_app_version: str,
    ) -> None:
        if not expected_app_version or len(expected_app_version) > 32:
            raise FinalDecisionReviewWorkflowBridgeError(
                "FINAL_DECISION_REVIEW_WORKFLOW_BRIDGE_VERSION_INVALID"
            )
        self._registry = registry
        self._openapi_provider = openapi_provider
        self._expected_app_version = expected_app_version
        self._lock = RLock()

    @property
    def registry(self) -> FinalDecisionReviewSourceRegistryV1:
        return self._registry

    @property
    def expected_app_version(self) -> str:
        return self._expected_app_version

    def publish(
        self,
        *,
        scenario_id: str,
        base_explanation: RiskPreTradeExplanationEnvelopeV1,
        capacity_requests: tuple[CapacityOrderRequestV1, ...],
        pro_forma_risk_evaluation: RiskPolicyEvaluationV1,
        correlation_id: str,
        request_id: str | None = None,
        bridged_at: datetime | None = None,
    ) -> FinalDecisionReviewWorkflowBridgeResultV1:
        now = _aware_utc(bridged_at)
        with self._lock:
            try:
                scenario = build_pro_forma_risk_scenario(
                    scenario_id=scenario_id,
                    account=base_explanation.risk_evaluation.metadata.account,
                    requested_option_id=(
                        base_explanation.directional_review.base_intent_gate.request
                        .requested_option_id
                    ),
                    direction=base_explanation.direction,
                    capacity_requests=capacity_requests,
                    risk_evaluation=pro_forma_risk_evaluation,
                    generated_at=now,
                )
            except ValueError:
                return _blocked_result(
                    bridged_at=now,
                    stage=FinalDecisionReviewWorkflowBridgeStage.SCENARIO,
                    blocker="FINAL_DECISION_REVIEW_WORKFLOW_SCENARIO_INVALID",
                    registry=self._registry,
                )

            try:
                source_binding = bind_pro_forma_risk_to_intent(
                    base_explanation,
                    scenario,
                    assessed_at=now,
                )
            except ValueError:
                return _blocked_result(
                    bridged_at=now,
                    stage=FinalDecisionReviewWorkflowBridgeStage.BINDING,
                    blocker="FINAL_DECISION_REVIEW_WORKFLOW_BINDING_INVALID",
                    registry=self._registry,
                    scenario=scenario,
                )

            try:
                current_schema = deepcopy(dict(self._openapi_provider()))
                approved_hosts = _approved_hosts_from_openapi(current_schema)
                orchestration = orchestrate_final_decision_review_publication(
                    source_binding,
                    current_schema,
                    self._registry,
                    expected_app_version=self._expected_app_version,
                    approved_hosts=approved_hosts,
                    correlation_id=correlation_id,
                    request_id=request_id,
                    orchestrated_at=now,
                )
            except FinalDecisionReviewWorkflowBridgeError as exc:
                return _blocked_result(
                    bridged_at=now,
                    stage=FinalDecisionReviewWorkflowBridgeStage.ORCHESTRATION,
                    blocker=str(exc),
                    registry=self._registry,
                    scenario=scenario,
                    source_binding=source_binding,
                )
            except FinalDecisionReviewOrchestrationError:
                return _blocked_result(
                    bridged_at=now,
                    stage=FinalDecisionReviewWorkflowBridgeStage.ORCHESTRATION,
                    blocker="FINAL_DECISION_REVIEW_WORKFLOW_ORCHESTRATION_INVALID",
                    registry=self._registry,
                    scenario=scenario,
                    source_binding=source_binding,
                )

            published = orchestration.published
            return FinalDecisionReviewWorkflowBridgeResultV1(
                bridged_at=now,
                status=(
                    FinalDecisionReviewWorkflowBridgeStatus.PUBLISHED
                    if published
                    else FinalDecisionReviewWorkflowBridgeStatus.BLOCKED
                ),
                completed_stage=FinalDecisionReviewWorkflowBridgeStage.ORCHESTRATION,
                published=published,
                primary_blocker=orchestration.primary_blocker,
                scenario=scenario,
                source_binding=source_binding,
                orchestration=orchestration,
                registry_active_sources=self._registry.active_source_count(
                    checked_at=now
                ),
            )
