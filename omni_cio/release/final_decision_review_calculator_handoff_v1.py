from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from omni_cio.contracts.v1.decision_capacity_intent import (
    CapacityIntentDecisionGateV1,
)
from omni_cio.contracts.v1.decision_capacity_pretrade import (
    CapacityPreTradeDecisionGatePolicyV1,
)
from omni_cio.contracts.v1.decision_capacity_sell_pretrade import (
    CapacitySellPreTradeDecisionGatePolicyV1,
)
from omni_cio.contracts.v1.final_decision_review_trusted_scenario import (
    TrustedScenarioPublicationResultV1,
)
from omni_cio.contracts.v1.pretrade import PreTradePreviewV1
from omni_cio.contracts.v1.risk import RiskPolicyEvaluationV1
from omni_cio.contracts.v1.sell_pretrade import SellPreTradePreviewV1
from omni_cio.decision.capacity_pretrade_gate_v1 import (
    CapacityPreTradeDecisionGateError,
    apply_capacity_pretrade_decision_gate,
)
from omni_cio.decision.capacity_sell_pretrade_gate_v1 import (
    CapacitySellPreTradeDecisionGateError,
    apply_capacity_sell_pretrade_decision_gate,
)
from omni_cio.release.final_decision_review_trusted_scenario_publisher_v1 import (
    FinalDecisionReviewTrustedScenarioPublisherError,
    FinalDecisionReviewTrustedScenarioPublisherV1,
)


class FinalDecisionReviewCalculatorScenarioHandoffError(ValueError):
    """Calculator outputs cannot cross the trusted scenario boundary safely."""


def _require_base_intent(
    value: CapacityIntentDecisionGateV1,
) -> CapacityIntentDecisionGateV1:
    if not isinstance(value, CapacityIntentDecisionGateV1):
        raise FinalDecisionReviewCalculatorScenarioHandoffError(
            "FINAL_DECISION_REVIEW_HANDOFF_BASE_INTENT_TYPE_INVALID"
        )
    return value


def _require_risk(value: RiskPolicyEvaluationV1) -> RiskPolicyEvaluationV1:
    if not isinstance(value, RiskPolicyEvaluationV1):
        raise FinalDecisionReviewCalculatorScenarioHandoffError(
            "FINAL_DECISION_REVIEW_HANDOFF_PRO_FORMA_TYPE_INVALID"
        )
    return value


def _typed_purchase_previews(
    previews: Iterable[PreTradePreviewV1],
) -> tuple[PreTradePreviewV1, ...]:
    rows = tuple(previews)
    if not rows or any(not isinstance(row, PreTradePreviewV1) for row in rows):
        raise FinalDecisionReviewCalculatorScenarioHandoffError(
            "FINAL_DECISION_REVIEW_HANDOFF_PURCHASE_PREVIEWS_INVALID"
        )
    return rows


def _typed_sell_previews(
    previews: Iterable[SellPreTradePreviewV1],
) -> tuple[SellPreTradePreviewV1, ...]:
    rows = tuple(previews)
    if not rows or any(not isinstance(row, SellPreTradePreviewV1) for row in rows):
        raise FinalDecisionReviewCalculatorScenarioHandoffError(
            "FINAL_DECISION_REVIEW_HANDOFF_SELL_PREVIEWS_INVALID"
        )
    return rows


class FinalDecisionReviewCalculatorScenarioHandoffV1:
    """Build a typed directional gate and publish it through the PR-71 boundary."""

    def __init__(
        self,
        *,
        publisher: FinalDecisionReviewTrustedScenarioPublisherV1,
        purchase_policy: CapacityPreTradeDecisionGatePolicyV1 | None = None,
        sell_policy: CapacitySellPreTradeDecisionGatePolicyV1 | None = None,
    ) -> None:
        if not isinstance(publisher, FinalDecisionReviewTrustedScenarioPublisherV1):
            raise FinalDecisionReviewCalculatorScenarioHandoffError(
                "FINAL_DECISION_REVIEW_HANDOFF_PUBLISHER_TYPE_INVALID"
            )
        self._publisher = publisher
        self._purchase_policy = purchase_policy or CapacityPreTradeDecisionGatePolicyV1()
        self._sell_policy = sell_policy or CapacitySellPreTradeDecisionGatePolicyV1()

    @property
    def publisher(self) -> FinalDecisionReviewTrustedScenarioPublisherV1:
        return self._publisher

    def publish_purchase(
        self,
        *,
        scenario_id: str,
        base_intent_gate: CapacityIntentDecisionGateV1,
        previews: Iterable[PreTradePreviewV1],
        pro_forma_risk: RiskPolicyEvaluationV1,
        published_at: datetime | None = None,
    ) -> TrustedScenarioPublicationResultV1:
        intent = _require_base_intent(base_intent_gate)
        risk = _require_risk(pro_forma_risk)
        preview_rows = _typed_purchase_previews(previews)
        try:
            gate = apply_capacity_pretrade_decision_gate(
                intent,
                preview_rows,
                policy=self._purchase_policy,
                assessed_at=risk.metadata.retrieved_at,
            )
            return self._publisher.publish(
                scenario_id=scenario_id,
                purchase_gate=gate,
                pro_forma_risk=risk,
                provider="omni-cio-calculators",
                operation="purchase-gate-pro-forma-handoff",
                published_at=published_at,
            )
        except (
            CapacityPreTradeDecisionGateError,
            FinalDecisionReviewTrustedScenarioPublisherError,
            AttributeError,
            TypeError,
            ValueError,
        ) as exc:
            raise FinalDecisionReviewCalculatorScenarioHandoffError(str(exc)) from exc

    def publish_sell(
        self,
        *,
        scenario_id: str,
        base_intent_gate: CapacityIntentDecisionGateV1,
        previews: Iterable[SellPreTradePreviewV1],
        pro_forma_risk: RiskPolicyEvaluationV1,
        published_at: datetime | None = None,
    ) -> TrustedScenarioPublicationResultV1:
        intent = _require_base_intent(base_intent_gate)
        risk = _require_risk(pro_forma_risk)
        preview_rows = _typed_sell_previews(previews)
        try:
            gate = apply_capacity_sell_pretrade_decision_gate(
                intent,
                preview_rows,
                policy=self._sell_policy,
                assessed_at=risk.metadata.retrieved_at,
            )
            return self._publisher.publish(
                scenario_id=scenario_id,
                sell_gate=gate,
                pro_forma_risk=risk,
                provider="omni-cio-calculators",
                operation="sell-gate-pro-forma-handoff",
                published_at=published_at,
            )
        except (
            CapacitySellPreTradeDecisionGateError,
            FinalDecisionReviewTrustedScenarioPublisherError,
            AttributeError,
            TypeError,
            ValueError,
        ) as exc:
            raise FinalDecisionReviewCalculatorScenarioHandoffError(str(exc)) from exc
