from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, InstanceOf, field_validator, model_validator

from omni_cio.contracts.v1.capacity import OrderSide
from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.decision import DecisionAction
from omni_cio.contracts.v1.decision_capacity import CapacityDecisionGateStatus
from omni_cio.contracts.v1.decision_capacity_intent import (
    CapacityIntentDecisionGateV1,
)
from omni_cio.contracts.v1.decision_capacity_pretrade import (
    CapacityPreTradeDecisionGateV1,
)
from omni_cio.contracts.v1.decision_capacity_sell_pretrade import (
    CapacitySellPreTradeDecisionGateV1,
)


NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]


class CapacityDirectionalPreTradeReviewBlocker(StrEnum):
    MIXED_INTENT_DIRECTIONS = "mixed_intent_directions"
    SOURCE_GATE_DIRECTION_MISMATCH = "source_gate_direction_mismatch"
    SOURCE_GATE_NOT_READY = "source_gate_not_ready"
    SOURCE_COVERAGE_INCOMPLETE = "source_coverage_incomplete"
    SOURCE_INTENT_BINDING_INCOMPLETE = "source_intent_binding_incomplete"


class CapacityDirectionalPreTradeReviewWarning(StrEnum):
    HOMOGENEOUS_DIRECTION_ONLY = "homogeneous_direction_only"
    SOURCE_GATE_RETAINED = "source_gate_retained"
    REVIEW_ONLY_NO_ORDER_CREATED = "review_only_no_order_created"


class CapacityDirectionalPreTradeReviewV1(ContractModel):
    schema_name: Literal["capacity_directional_pretrade_review"] = (
        "capacity_directional_pretrade_review"
    )
    schema_version: Literal["1.0"] = "1.0"
    assessed_at: datetime
    direction: OrderSide
    status: CapacityDecisionGateStatus
    gate_ready: bool
    abstain: bool
    base_intent_gate: InstanceOf[CapacityIntentDecisionGateV1]
    source_gate: InstanceOf[
        CapacityPreTradeDecisionGateV1 | CapacitySellPreTradeDecisionGateV1
    ]
    no_action_option_id: Annotated[str, Field(min_length=3, max_length=256)]
    final_option_id: Annotated[str, Field(min_length=3, max_length=256)]
    final_action: DecisionAction
    required_instrument_count: PositiveInt
    reviewed_instrument_count: NonNegativeInt
    source_gate_ready: bool
    source_coverage_complete: bool
    exact_intent_binding_confirmed: bool
    affordability_confirmed: bool | None = None
    position_availability_confirmed: bool | None = None
    open_orders_confirmed: bool | None = None
    tax_basis_confirmed: bool | None = None
    commission_integrity_confirmed: bool
    blockers: tuple[CapacityDirectionalPreTradeReviewBlocker, ...] = ()
    warnings: tuple[CapacityDirectionalPreTradeReviewWarning, ...] = ()
    option_selected_by_review: Literal[False] = False
    order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("assessed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("directional pretrade timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    def _has(self, blocker: CapacityDirectionalPreTradeReviewBlocker) -> bool:
        return blocker in self.blockers

    @model_validator(mode="after")
    def validate_review(self) -> CapacityDirectionalPreTradeReviewV1:
        source = self.source_gate
        expected_requests = self.base_intent_gate.request.expected_capacity_requests
        expected_sides = {row.side for row in expected_requests}
        mixed_directions = len(expected_sides) != 1
        expected_direction = next(iter(expected_sides)) if not mixed_directions else None
        purchase_source = isinstance(source, CapacityPreTradeDecisionGateV1)
        source_direction = OrderSide.BUY if purchase_source else OrderSide.SELL
        direction_mismatch = (
            mixed_directions
            or expected_direction is not self.direction
            or source_direction is not self.direction
        )

        if source.base_intent_gate != self.base_intent_gate:
            raise ValueError("directional review base intent does not match source gate")
        if self.assessed_at != source.assessed_at:
            raise ValueError("directional review timestamp does not match source gate")
        if self.no_action_option_id != source.no_action_option_id:
            raise ValueError("directional review no-action option does not reconcile")
        if self.required_instrument_count != source.required_preview_count:
            raise ValueError("directional required instrument count does not reconcile")
        if self.reviewed_instrument_count != source.preview_coverage_count:
            raise ValueError("directional reviewed instrument count does not reconcile")
        if self.source_gate_ready is not source.gate_ready:
            raise ValueError("directional source readiness is inconsistent")
        if (
            self.source_coverage_complete
            is not source.broker_preview_coverage_complete
        ):
            raise ValueError("directional source coverage state is inconsistent")
        expected_exact_binding = (
            source.exact_match_count == source.required_preview_count
        )
        if self.exact_intent_binding_confirmed is not expected_exact_binding:
            raise ValueError("directional exact-intent state is inconsistent")

        if purchase_source:
            if self.affordability_confirmed is not source.affordability_confirmed:
                raise ValueError("directional affordability state is inconsistent")
            if self.position_availability_confirmed is not None:
                raise ValueError("purchase review cannot confirm sell position")
            if self.open_orders_confirmed is not None:
                raise ValueError("purchase review cannot confirm sell open orders")
            if self.tax_basis_confirmed is not None:
                raise ValueError("purchase review cannot confirm sell tax basis")
        else:
            if self.affordability_confirmed is not None:
                raise ValueError("sell review cannot confirm purchase affordability")
            if (
                self.position_availability_confirmed
                is not source.position_availability_confirmed
            ):
                raise ValueError("directional position state is inconsistent")
            if self.open_orders_confirmed is not source.open_orders_confirmed:
                raise ValueError("directional open-order state is inconsistent")
            if self.tax_basis_confirmed is not source.tax_basis_confirmed:
                raise ValueError("directional tax-basis state is inconsistent")
        if (
            self.commission_integrity_confirmed
            is not source.commission_integrity_confirmed
        ):
            raise ValueError("directional commission state is inconsistent")

        expected_blocker_states = (
            (
                CapacityDirectionalPreTradeReviewBlocker.MIXED_INTENT_DIRECTIONS,
                mixed_directions,
            ),
            (
                CapacityDirectionalPreTradeReviewBlocker.SOURCE_GATE_DIRECTION_MISMATCH,
                direction_mismatch,
            ),
            (
                CapacityDirectionalPreTradeReviewBlocker.SOURCE_GATE_NOT_READY,
                not source.gate_ready,
            ),
            (
                CapacityDirectionalPreTradeReviewBlocker.SOURCE_COVERAGE_INCOMPLETE,
                not source.broker_preview_coverage_complete,
            ),
            (
                CapacityDirectionalPreTradeReviewBlocker.SOURCE_INTENT_BINDING_INCOMPLETE,
                not expected_exact_binding,
            ),
        )
        for blocker, expected_present in expected_blocker_states:
            if self._has(blocker) != expected_present:
                raise ValueError(f"directional blocker {blocker.value} is inconsistent")

        if len(set(self.blockers)) != len(self.blockers):
            raise ValueError("directional review blockers must be unique")
        if len(set(self.warnings)) != len(self.warnings):
            raise ValueError("directional review warnings must be unique")

        expected_ready = not self.blockers
        expected_status = (
            CapacityDecisionGateStatus.READY
            if expected_ready
            else CapacityDecisionGateStatus.ABSTAIN
        )
        if self.gate_ready is not expected_ready:
            raise ValueError("directional review readiness is inconsistent")
        if self.abstain is expected_ready:
            raise ValueError("directional review abstain state is inconsistent")
        if self.status is not expected_status:
            raise ValueError("directional review status is inconsistent")

        if expected_ready:
            if self.final_option_id != source.final_option_id:
                raise ValueError("ready directional review changed final option")
            if self.final_action is not source.final_action:
                raise ValueError("ready directional review changed final action")
        else:
            if self.final_option_id != self.no_action_option_id:
                raise ValueError("blocked directional review must select no action")
            if self.final_action is not DecisionAction.WAIT_FOR_DATA:
                raise ValueError("blocked directional review must wait for data")
        return self
