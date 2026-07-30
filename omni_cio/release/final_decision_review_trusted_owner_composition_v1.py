from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from itertools import islice

from omni_cio.contracts.v1.capacity import (
    CapacityAssessmentV1,
    CapacityOrderRequestV1,
    OrderSide,
)
from omni_cio.contracts.v1.decision import DecisionSetV1
from omni_cio.contracts.v1.decision_capacity_intent import (
    CapacityIntentDecisionGateRequestV1,
)
from omni_cio.contracts.v1.decision_pro_forma_risk_binding import (
    ProFormaRiskScenarioMethod,
    ProFormaRiskScenarioV1,
    calculate_pro_forma_intent_fingerprint,
)
from omni_cio.contracts.v1.final_decision_review_approved_invocation import (
    ApprovedCalculatorInvocationRequestV1,
    ApprovedCalculatorInvocationResultV1,
    ApprovedCalculatorOperation,
)
from omni_cio.contracts.v1.pretrade import PreTradePreviewV1
from omni_cio.contracts.v1.risk import RiskPolicyEvaluationV1
from omni_cio.contracts.v1.sell_pretrade import SellPreTradePreviewV1
from omni_cio.release.final_decision_review_calculator_provider_registry_v1 import (
    FinalDecisionReviewCalculatorProviderRegistryError,
    FinalDecisionReviewCalculatorProviderRegistryV1,
)
from omni_cio.release.final_decision_review_existing_calculator_providers_v1 import (
    PURCHASE_PROVIDER_ID,
    SELL_PROVIDER_ID,
    ApprovedCalculatorCommonOwnersV1,
    ApprovedPurchaseCalculatorOwnersV1,
    ApprovedSellCalculatorOwnersV1,
)
from omni_cio.release.final_decision_review_production_owner_callables_v1 import (
    FinalDecisionReviewProductionOwnerCallableError,
    FinalDecisionReviewProductionOwnerCallablePublicationV1,
    FinalDecisionReviewProductionOwnerCallableStoreV1,
)


MAX_DIRECTIONAL_ROWS = 100


class FinalDecisionReviewTrustedOwnerCompositionError(ValueError):
    """Trusted calculator owners cannot be composed or invoked safely."""


TrustedDecisionOwnerV1 = Callable[
    [ApprovedCalculatorInvocationRequestV1],
    DecisionSetV1,
]
TrustedIntentOwnerV1 = Callable[
    [ApprovedCalculatorInvocationRequestV1],
    CapacityIntentDecisionGateRequestV1,
]
TrustedCapacityOwnerV1 = Callable[
    [ApprovedCalculatorInvocationRequestV1],
    Iterable[CapacityAssessmentV1],
]
TrustedProFormaScenarioOwnerV1 = Callable[
    [ApprovedCalculatorInvocationRequestV1],
    ProFormaRiskScenarioV1,
]
TrustedPurchasePreviewOwnerV1 = Callable[
    [ApprovedCalculatorInvocationRequestV1],
    Iterable[PreTradePreviewV1],
]
TrustedSellPreviewOwnerV1 = Callable[
    [ApprovedCalculatorInvocationRequestV1],
    Iterable[SellPreTradePreviewV1],
]


@dataclass(frozen=True, slots=True)
class FinalDecisionReviewTrustedCommonOwnerPortsV1:
    decision: TrustedDecisionOwnerV1
    intent: TrustedIntentOwnerV1
    capacity: TrustedCapacityOwnerV1
    pro_forma_scenario: TrustedProFormaScenarioOwnerV1

    def __post_init__(self) -> None:
        owners = (
            self.decision,
            self.intent,
            self.capacity,
            self.pro_forma_scenario,
        )
        if any(not callable(owner) for owner in owners):
            raise FinalDecisionReviewTrustedOwnerCompositionError(
                "FINAL_DECISION_REVIEW_TRUSTED_OWNER_NOT_CALLABLE"
            )


@dataclass(frozen=True, slots=True)
class FinalDecisionReviewTrustedPurchaseOwnerPortsV1:
    common: FinalDecisionReviewTrustedCommonOwnerPortsV1
    previews: TrustedPurchasePreviewOwnerV1

    def __post_init__(self) -> None:
        if not isinstance(
            self.common,
            FinalDecisionReviewTrustedCommonOwnerPortsV1,
        ):
            raise FinalDecisionReviewTrustedOwnerCompositionError(
                "FINAL_DECISION_REVIEW_TRUSTED_COMMON_OWNERS_TYPE_INVALID"
            )
        if not callable(self.previews):
            raise FinalDecisionReviewTrustedOwnerCompositionError(
                "FINAL_DECISION_REVIEW_TRUSTED_PURCHASE_OWNER_NOT_CALLABLE"
            )


@dataclass(frozen=True, slots=True)
class FinalDecisionReviewTrustedSellOwnerPortsV1:
    common: FinalDecisionReviewTrustedCommonOwnerPortsV1
    previews: TrustedSellPreviewOwnerV1

    def __post_init__(self) -> None:
        if not isinstance(
            self.common,
            FinalDecisionReviewTrustedCommonOwnerPortsV1,
        ):
            raise FinalDecisionReviewTrustedOwnerCompositionError(
                "FINAL_DECISION_REVIEW_TRUSTED_COMMON_OWNERS_TYPE_INVALID"
            )
        if not callable(self.previews):
            raise FinalDecisionReviewTrustedOwnerCompositionError(
                "FINAL_DECISION_REVIEW_TRUSTED_SELL_OWNER_NOT_CALLABLE"
            )


@dataclass(frozen=True, slots=True)
class FinalDecisionReviewTrustedOwnerCompositionResultV1:
    request: ApprovedCalculatorInvocationRequestV1
    provider_id: str
    owner_publication: FinalDecisionReviewProductionOwnerCallablePublicationV1
    invocation: ApprovedCalculatorInvocationResultV1
    materialized_owner_call_count: int = 5
    owner_bundle_discarded: bool = True
    owner_pin_present_after_cleanup: bool = False
    internal_only: bool = True
    raw_payload_accepted: bool = False
    credentials_accepted: bool = False
    full_account_accepted: bool = False
    request_body_accepted: bool = False
    http_route_created: bool = False
    broker_write_called: bool = False
    trade_authorized: bool = False
    order_created: bool = False
    execution_ready: bool = False
    trading_methods: bool = False

    def __post_init__(self) -> None:
        expected_provider = (
            PURCHASE_PROVIDER_ID
            if self.request.operation is ApprovedCalculatorOperation.PURCHASE_REVIEW
            else SELL_PROVIDER_ID
        )
        if self.provider_id != expected_provider:
            raise FinalDecisionReviewTrustedOwnerCompositionError(
                "FINAL_DECISION_REVIEW_TRUSTED_OWNER_PROVIDER_MISMATCH"
            )
        if self.owner_publication.scenario_id != self.request.scenario_id:
            raise FinalDecisionReviewTrustedOwnerCompositionError(
                "FINAL_DECISION_REVIEW_TRUSTED_OWNER_SCENARIO_MISMATCH"
            )
        if self.owner_publication.correlation_id != self.request.correlation_id:
            raise FinalDecisionReviewTrustedOwnerCompositionError(
                "FINAL_DECISION_REVIEW_TRUSTED_OWNER_CORRELATION_MISMATCH"
            )
        if self.owner_publication.operation is not self.request.operation:
            raise FinalDecisionReviewTrustedOwnerCompositionError(
                "FINAL_DECISION_REVIEW_TRUSTED_OWNER_OPERATION_MISMATCH"
            )
        if self.invocation.request != self.request:
            raise FinalDecisionReviewTrustedOwnerCompositionError(
                "FINAL_DECISION_REVIEW_TRUSTED_OWNER_INVOCATION_MISMATCH"
            )


@dataclass(frozen=True, slots=True)
class _MaterializedCommonOwnersV1:
    decision: DecisionSetV1
    intent: CapacityIntentDecisionGateRequestV1
    capacity: tuple[CapacityAssessmentV1, ...]
    pro_forma_scenario: ProFormaRiskScenarioV1


def _require_request(
    value: ApprovedCalculatorInvocationRequestV1,
    *,
    operation: ApprovedCalculatorOperation,
) -> ApprovedCalculatorInvocationRequestV1:
    if not isinstance(value, ApprovedCalculatorInvocationRequestV1):
        raise FinalDecisionReviewTrustedOwnerCompositionError(
            "FINAL_DECISION_REVIEW_TRUSTED_OWNER_REQUEST_TYPE_INVALID"
        )
    if value.operation is not operation:
        raise FinalDecisionReviewTrustedOwnerCompositionError(
            "FINAL_DECISION_REVIEW_TRUSTED_OWNER_OPERATION_MISMATCH"
        )
    return value


def _bounded_rows[T](
    value: Iterable[T],
    *,
    expected_type: type[T],
    invalid_code: str,
) -> tuple[T, ...]:
    try:
        rows = tuple(islice(iter(value), MAX_DIRECTIONAL_ROWS + 1))
    except Exception as exc:
        raise FinalDecisionReviewTrustedOwnerCompositionError(invalid_code) from exc
    if (
        not rows
        or len(rows) > MAX_DIRECTIONAL_ROWS
        or any(not isinstance(row, expected_type) for row in rows)
    ):
        raise FinalDecisionReviewTrustedOwnerCompositionError(invalid_code)
    return rows


def _materialize_common(
    request: ApprovedCalculatorInvocationRequestV1,
    owners: FinalDecisionReviewTrustedCommonOwnerPortsV1,
) -> _MaterializedCommonOwnersV1:
    try:
        decision = owners.decision(request)
        intent = owners.intent(request)
        capacity = _bounded_rows(
            owners.capacity(request),
            expected_type=CapacityAssessmentV1,
            invalid_code=(
                "FINAL_DECISION_REVIEW_TRUSTED_OWNER_CAPACITY_OUTPUT_INVALID"
            ),
        )
        scenario = owners.pro_forma_scenario(request)
    except FinalDecisionReviewTrustedOwnerCompositionError:
        raise
    except Exception as exc:
        raise FinalDecisionReviewTrustedOwnerCompositionError(
            "FINAL_DECISION_REVIEW_TRUSTED_OWNER_CALL_FAILED"
        ) from exc
    if not isinstance(decision, DecisionSetV1):
        raise FinalDecisionReviewTrustedOwnerCompositionError(
            "FINAL_DECISION_REVIEW_TRUSTED_OWNER_DECISION_OUTPUT_INVALID"
        )
    if not isinstance(intent, CapacityIntentDecisionGateRequestV1):
        raise FinalDecisionReviewTrustedOwnerCompositionError(
            "FINAL_DECISION_REVIEW_TRUSTED_OWNER_INTENT_OUTPUT_INVALID"
        )
    if not isinstance(scenario, ProFormaRiskScenarioV1):
        raise FinalDecisionReviewTrustedOwnerCompositionError(
            "FINAL_DECISION_REVIEW_TRUSTED_OWNER_PRO_FORMA_OUTPUT_INVALID"
        )
    return _MaterializedCommonOwnersV1(
        decision=decision,
        intent=intent,
        capacity=capacity,
        pro_forma_scenario=scenario,
    )


def _capacity_requests(
    capacity: tuple[CapacityAssessmentV1, ...],
) -> tuple[CapacityOrderRequestV1, ...]:
    try:
        return tuple(row.request for row in capacity)
    except AttributeError as exc:
        raise FinalDecisionReviewTrustedOwnerCompositionError(
            "FINAL_DECISION_REVIEW_TRUSTED_OWNER_CAPACITY_OUTPUT_INVALID"
        ) from exc


def _validate_materialized_binding(
    *,
    request: ApprovedCalculatorInvocationRequestV1,
    common: _MaterializedCommonOwnersV1,
    previews: tuple[PreTradePreviewV1, ...] | tuple[SellPreTradePreviewV1, ...],
    direction: OrderSide,
) -> RiskPolicyEvaluationV1:
    try:
        scenario = common.pro_forma_scenario
        risk = scenario.risk_evaluation
        expected_requests = common.intent.expected_capacity_requests
        actual_requests = _capacity_requests(common.capacity)
        expected_by_key = {row.instrument_key: row for row in expected_requests}
        actual_by_key = {row.instrument_key: row for row in actual_requests}
        preview_keys = tuple(row.stable_key for row in previews)
        preview_accounts = tuple(row.metadata.account for row in previews)
        expected_fingerprint = calculate_pro_forma_intent_fingerprint(
            account_masked_id=scenario.account.masked_id,
            requested_option_id=common.intent.requested_option_id,
            direction=direction,
            capacity_requests=expected_requests,
        )
        risk_policy = risk.policy
        age_seconds = (request.invoked_at - scenario.generated_at).total_seconds()
        expected_operation = (
            ApprovedCalculatorOperation.PURCHASE_REVIEW
            if direction is OrderSide.BUY
            else ApprovedCalculatorOperation.SELL_REVIEW
        )
        valid = all(
            (
                request.operation is expected_operation,
                scenario.scenario_id == request.scenario_id,
                scenario.direction is direction,
                scenario.requested_option_id == common.intent.requested_option_id,
                scenario.capacity_requests == expected_requests,
                all(row.side is direction for row in expected_requests),
                len(expected_by_key) == len(expected_requests),
                len(actual_by_key) == len(actual_requests),
                actual_by_key == expected_by_key,
                len(set(preview_keys)) == len(preview_keys),
                set(preview_keys) == set(expected_by_key),
                all(account == scenario.account for account in preview_accounts),
                common.decision.metadata.account == scenario.account,
                isinstance(risk, RiskPolicyEvaluationV1),
                risk.metadata.account == scenario.account,
                risk.metadata.retrieved_at == scenario.generated_at,
                scenario.intent_fingerprint == expected_fingerprint,
                scenario.method
                is ProFormaRiskScenarioMethod.EXACT_CAPACITY_INTENT_POST_CHANGE,
                scenario.current_portfolio_risk is False,
                scenario.pro_forma_post_change is True,
                scenario.order_created is False,
                scenario.execution_ready is False,
                scenario.trading_methods is False,
                risk_policy.allow_margin is False,
                risk_policy.allow_short_sales is False,
                risk_policy.allow_derivatives is False,
                risk_policy.allow_currency_operations is False,
                age_seconds <= 300,
                age_seconds >= -30,
            )
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise FinalDecisionReviewTrustedOwnerCompositionError(
            "FINAL_DECISION_REVIEW_TRUSTED_OWNER_OUTPUT_BINDING_INVALID"
        ) from exc
    if not valid:
        raise FinalDecisionReviewTrustedOwnerCompositionError(
            "FINAL_DECISION_REVIEW_TRUSTED_OWNER_OUTPUT_BINDING_INVALID"
        )
    return risk


def _exact_request(
    expected: ApprovedCalculatorInvocationRequestV1,
    actual: ApprovedCalculatorInvocationRequestV1,
) -> None:
    if not isinstance(actual, ApprovedCalculatorInvocationRequestV1):
        raise FinalDecisionReviewTrustedOwnerCompositionError(
            "FINAL_DECISION_REVIEW_TRUSTED_OWNER_SNAPSHOT_REQUEST_INVALID"
        )
    if actual != expected:
        raise FinalDecisionReviewTrustedOwnerCompositionError(
            "FINAL_DECISION_REVIEW_TRUSTED_OWNER_SNAPSHOT_REQUEST_MISMATCH"
        )


def _snapshot_common_owners(
    *,
    request: ApprovedCalculatorInvocationRequestV1,
    common: _MaterializedCommonOwnersV1,
    risk: RiskPolicyEvaluationV1,
) -> ApprovedCalculatorCommonOwnersV1:
    def decision(actual: ApprovedCalculatorInvocationRequestV1) -> DecisionSetV1:
        _exact_request(request, actual)
        return common.decision

    def intent(
        actual: ApprovedCalculatorInvocationRequestV1,
    ) -> CapacityIntentDecisionGateRequestV1:
        _exact_request(request, actual)
        return common.intent

    def capacity(
        actual: ApprovedCalculatorInvocationRequestV1,
    ) -> tuple[CapacityAssessmentV1, ...]:
        _exact_request(request, actual)
        return common.capacity

    def pro_forma(
        actual: ApprovedCalculatorInvocationRequestV1,
    ) -> RiskPolicyEvaluationV1:
        _exact_request(request, actual)
        return risk

    return ApprovedCalculatorCommonOwnersV1(
        decision=decision,
        intent=intent,
        capacity=capacity,
        pro_forma_risk=pro_forma,
    )


class FinalDecisionReviewTrustedOwnerCompositionV1:
    """Materialize, bind and invoke exact read-only owners once."""

    def __init__(
        self,
        *,
        registry: FinalDecisionReviewCalculatorProviderRegistryV1,
        store: FinalDecisionReviewProductionOwnerCallableStoreV1,
    ) -> None:
        if not isinstance(registry, FinalDecisionReviewCalculatorProviderRegistryV1):
            raise FinalDecisionReviewTrustedOwnerCompositionError(
                "FINAL_DECISION_REVIEW_TRUSTED_OWNER_REGISTRY_TYPE_INVALID"
            )
        if not isinstance(store, FinalDecisionReviewProductionOwnerCallableStoreV1):
            raise FinalDecisionReviewTrustedOwnerCompositionError(
                "FINAL_DECISION_REVIEW_TRUSTED_OWNER_STORE_TYPE_INVALID"
            )
        self._registry = registry
        self._store = store

    @property
    def registry(self) -> FinalDecisionReviewCalculatorProviderRegistryV1:
        return self._registry

    @property
    def store(self) -> FinalDecisionReviewProductionOwnerCallableStoreV1:
        return self._store

    def _invoke(
        self,
        *,
        request: ApprovedCalculatorInvocationRequestV1,
        provider_id: str,
        published_at: datetime,
        purchase: ApprovedPurchaseCalculatorOwnersV1 | None = None,
        sell: ApprovedSellCalculatorOwnersV1 | None = None,
        completed_at: datetime | None = None,
    ) -> FinalDecisionReviewTrustedOwnerCompositionResultV1:
        try:
            if purchase is not None:
                publication = self._store.publish_purchase(
                    scenario_id=request.scenario_id,
                    correlation_id=request.correlation_id,
                    owners=purchase,
                    published_at=published_at,
                )
            elif sell is not None:
                publication = self._store.publish_sell(
                    scenario_id=request.scenario_id,
                    correlation_id=request.correlation_id,
                    owners=sell,
                    published_at=published_at,
                )
            else:
                raise FinalDecisionReviewTrustedOwnerCompositionError(
                    "FINAL_DECISION_REVIEW_TRUSTED_OWNER_DIRECTION_INVALID"
                )
        except FinalDecisionReviewProductionOwnerCallableError as exc:
            raise FinalDecisionReviewTrustedOwnerCompositionError(
                "FINAL_DECISION_REVIEW_TRUSTED_OWNER_PUBLICATION_FAILED"
            ) from exc

        try:
            invocation = self._registry.invoke(
                provider_id=provider_id,
                request=request,
                completed_at=completed_at,
            )
        except FinalDecisionReviewCalculatorProviderRegistryError as exc:
            raise FinalDecisionReviewTrustedOwnerCompositionError(
                "FINAL_DECISION_REVIEW_TRUSTED_OWNER_INVOCATION_FAILED"
            ) from exc
        finally:
            self._store.release_for_request(request)
            discarded = self._store.discard_for_request(request)

        if not discarded:
            raise FinalDecisionReviewTrustedOwnerCompositionError(
                "FINAL_DECISION_REVIEW_TRUSTED_OWNER_CLEANUP_FAILED"
            )
        return FinalDecisionReviewTrustedOwnerCompositionResultV1(
            request=request,
            provider_id=provider_id,
            owner_publication=publication,
            invocation=invocation,
        )

    def invoke_purchase(
        self,
        *,
        request: ApprovedCalculatorInvocationRequestV1,
        owners: FinalDecisionReviewTrustedPurchaseOwnerPortsV1,
        completed_at: datetime | None = None,
    ) -> FinalDecisionReviewTrustedOwnerCompositionResultV1:
        approved = _require_request(
            request,
            operation=ApprovedCalculatorOperation.PURCHASE_REVIEW,
        )
        if not isinstance(owners, FinalDecisionReviewTrustedPurchaseOwnerPortsV1):
            raise FinalDecisionReviewTrustedOwnerCompositionError(
                "FINAL_DECISION_REVIEW_TRUSTED_PURCHASE_OWNERS_TYPE_INVALID"
            )
        common = _materialize_common(approved, owners.common)
        try:
            previews = _bounded_rows(
                owners.previews(approved),
                expected_type=PreTradePreviewV1,
                invalid_code=(
                    "FINAL_DECISION_REVIEW_TRUSTED_OWNER_PURCHASE_OUTPUT_INVALID"
                ),
            )
        except FinalDecisionReviewTrustedOwnerCompositionError:
            raise
        except Exception as exc:
            raise FinalDecisionReviewTrustedOwnerCompositionError(
                "FINAL_DECISION_REVIEW_TRUSTED_OWNER_CALL_FAILED"
            ) from exc
        risk = _validate_materialized_binding(
            request=approved,
            common=common,
            previews=previews,
            direction=OrderSide.BUY,
        )
        snapshot_common = _snapshot_common_owners(
            request=approved,
            common=common,
            risk=risk,
        )

        def snapshot_previews(
            actual: ApprovedCalculatorInvocationRequestV1,
        ) -> tuple[PreTradePreviewV1, ...]:
            _exact_request(approved, actual)
            return previews

        return self._invoke(
            request=approved,
            provider_id=PURCHASE_PROVIDER_ID,
            published_at=approved.invoked_at,
            purchase=ApprovedPurchaseCalculatorOwnersV1(
                common=snapshot_common,
                previews=snapshot_previews,
            ),
            completed_at=completed_at,
        )

    def invoke_sell(
        self,
        *,
        request: ApprovedCalculatorInvocationRequestV1,
        owners: FinalDecisionReviewTrustedSellOwnerPortsV1,
        completed_at: datetime | None = None,
    ) -> FinalDecisionReviewTrustedOwnerCompositionResultV1:
        approved = _require_request(
            request,
            operation=ApprovedCalculatorOperation.SELL_REVIEW,
        )
        if not isinstance(owners, FinalDecisionReviewTrustedSellOwnerPortsV1):
            raise FinalDecisionReviewTrustedOwnerCompositionError(
                "FINAL_DECISION_REVIEW_TRUSTED_SELL_OWNERS_TYPE_INVALID"
            )
        common = _materialize_common(approved, owners.common)
        try:
            previews = _bounded_rows(
                owners.previews(approved),
                expected_type=SellPreTradePreviewV1,
                invalid_code=(
                    "FINAL_DECISION_REVIEW_TRUSTED_OWNER_SELL_OUTPUT_INVALID"
                ),
            )
        except FinalDecisionReviewTrustedOwnerCompositionError:
            raise
        except Exception as exc:
            raise FinalDecisionReviewTrustedOwnerCompositionError(
                "FINAL_DECISION_REVIEW_TRUSTED_OWNER_CALL_FAILED"
            ) from exc
        risk = _validate_materialized_binding(
            request=approved,
            common=common,
            previews=previews,
            direction=OrderSide.SELL,
        )
        snapshot_common = _snapshot_common_owners(
            request=approved,
            common=common,
            risk=risk,
        )

        def snapshot_previews(
            actual: ApprovedCalculatorInvocationRequestV1,
        ) -> tuple[SellPreTradePreviewV1, ...]:
            _exact_request(approved, actual)
            return previews

        return self._invoke(
            request=approved,
            provider_id=SELL_PROVIDER_ID,
            published_at=approved.invoked_at,
            sell=ApprovedSellCalculatorOwnersV1(
                common=snapshot_common,
                previews=snapshot_previews,
            ),
            completed_at=completed_at,
        )
