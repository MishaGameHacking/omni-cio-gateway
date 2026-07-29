from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.capacity import CapacityOrderRequestV1
from omni_cio.contracts.v1.common import ContractModel, CurrencyCode
from omni_cio.contracts.v1.decision import DecisionAction
from omni_cio.contracts.v1.decision_capacity import (
    CapacityDecisionGateStatus,
)
from omni_cio.contracts.v1.decision_capacity_intent import (
    CapacityIntentDecisionGateV1,
)
from omni_cio.contracts.v1.pretrade import (
    PreTradeBlocker,
    PreTradePreviewV1,
    PreviewPriceBasis,
)


NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), allow_inf_nan=False),
]
NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]


class CapacityPreTradeMismatch(StrEnum):
    SIDE = "side"
    CURRENCY = "currency"
    LOT_SIZE = "lot_size"
    QUANTITY_LOTS = "quantity_lots"
    REFERENCE_PRICE = "reference_price"


class CapacityPreTradeDecisionGateBlocker(StrEnum):
    BASE_INTENT_GATE_NOT_READY = "base_intent_gate_not_ready"
    PREVIEW_COVERAGE_INCOMPLETE = "preview_coverage_incomplete"
    PREVIEW_NOT_READY = "preview_not_ready"
    PREVIEW_STALE = "preview_stale"
    PREVIEW_FROM_FUTURE = "preview_from_future"
    PREVIEW_INTENT_MISMATCH = "preview_intent_mismatch"


class CapacityPreTradeDecisionGateWarning(StrEnum):
    PURCHASE_PREVIEW_ONLY = "purchase_preview_only"
    BROKER_PREVIEW_IS_POINT_IN_TIME = "broker_preview_is_point_in_time"
    BROKER_TOTALS_NOT_RECOMPUTED_BY_GATE = "broker_totals_not_recomputed_by_gate"
    COMMISSION_AND_ACCRUED_INTEREST_FROM_PREVIEW = (
        "commission_and_accrued_interest_from_preview"
    )
    REVIEW_ONLY_NO_ORDER_CREATED = "review_only_no_order_created"


class CapacityPreTradeDecisionGatePolicyV1(ContractModel):
    preview_max_age_seconds: Annotated[int, Field(ge=1, le=86_400)] = 180
    future_tolerance_seconds: Annotated[int, Field(ge=0, le=3_600)] = 60


class CapacityPreTradeCoverageV1(ContractModel):
    instrument_key: Annotated[str, Field(min_length=3, max_length=256)]
    expected_request: CapacityOrderRequestV1
    preview: PreTradePreviewV1
    mismatch_fields: tuple[CapacityPreTradeMismatch, ...] = ()
    exact_match: bool
    preview_ready: bool
    preview_evaluated_at: datetime
    preview_currency: CurrencyCode
    preview_price_basis: PreviewPriceBasis
    preview_unit_price: NonNegativeDecimal | None = None
    preview_lot_size: PositiveInt | None = None
    preview_quantity_lots: PositiveInt | None = None
    preview_blockers: tuple[PreTradeBlocker, ...] = ()

    @field_validator("preview_currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("preview_evaluated_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("capacity pretrade timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_coverage(self) -> CapacityPreTradeCoverageV1:
        if self.expected_request.instrument_key != self.instrument_key:
            raise ValueError("expected pretrade instrument mismatch")
        if self.preview.stable_key != self.instrument_key:
            raise ValueError("preview instrument mismatch")
        if self.preview_evaluated_at != self.preview.evaluated_at:
            raise ValueError("preview timestamp does not reconcile")
        if self.preview_currency != self.preview.currency:
            raise ValueError("preview currency does not reconcile")
        if self.preview_price_basis != self.preview.price_basis:
            raise ValueError("preview price basis does not reconcile")
        if self.preview_unit_price != self.preview.unit_price:
            raise ValueError("preview unit price does not reconcile")
        if self.preview_lot_size != self.preview.lot_size:
            raise ValueError("preview lot size does not reconcile")
        if self.preview_quantity_lots != self.preview.quantity_lots:
            raise ValueError("preview quantity does not reconcile")
        if self.preview_blockers != self.preview.blockers:
            raise ValueError("preview blockers do not reconcile")
        if self.preview_ready is not self.preview.preview_ready:
            raise ValueError("preview readiness does not reconcile")
        if len(set(self.mismatch_fields)) != len(self.mismatch_fields):
            raise ValueError("capacity pretrade mismatch fields must be unique")
        if self.exact_match is bool(self.mismatch_fields):
            raise ValueError("capacity pretrade exact-match state is inconsistent")
        return self


class CapacityPreTradeDecisionGateV1(ContractModel):
    schema_name: Literal["capacity_pretrade_decision_gate"] = (
        "capacity_pretrade_decision_gate"
    )
    schema_version: Literal["1.0"] = "1.0"
    assessed_at: datetime
    status: CapacityDecisionGateStatus
    gate_ready: bool
    abstain: bool
    base_intent_gate: CapacityIntentDecisionGateV1
    policy: CapacityPreTradeDecisionGatePolicyV1
    no_action_option_id: Annotated[str, Field(min_length=3, max_length=256)]
    final_option_id: Annotated[str, Field(min_length=3, max_length=256)]
    final_action: DecisionAction
    required_preview_count: PositiveInt
    preview_coverage_count: NonNegativeInt
    preview_ready_count: NonNegativeInt
    exact_match_count: NonNegativeInt
    coverage: tuple[CapacityPreTradeCoverageV1, ...]
    blockers: tuple[CapacityPreTradeDecisionGateBlocker, ...] = ()
    warnings: tuple[CapacityPreTradeDecisionGateWarning, ...] = ()
    broker_preview_coverage_complete: bool
    affordability_confirmed: bool
    commission_integrity_confirmed: bool
    order_total_recomputed_by_gate: Literal[False] = False
    option_selected_by_gate: Literal[False] = False
    order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("assessed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("capacity pretrade gate timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_gate(self) -> CapacityPreTradeDecisionGateV1:
        expected_requests = self.base_intent_gate.request.expected_capacity_requests
        expected_keys = tuple(row.instrument_key for row in expected_requests)
        if self.no_action_option_id != self.base_intent_gate.no_action_option_id:
            raise ValueError("capacity pretrade no-action option does not reconcile")
        if self.required_preview_count != len(expected_requests):
            raise ValueError("required preview count does not reconcile")
        if self.preview_coverage_count != len(self.coverage):
            raise ValueError("preview coverage count does not reconcile")
        if self.preview_ready_count != sum(row.preview_ready for row in self.coverage):
            raise ValueError("ready preview count does not reconcile")
        if self.exact_match_count != sum(row.exact_match for row in self.coverage):
            raise ValueError("exact preview count does not reconcile")

        coverage_keys = tuple(row.instrument_key for row in self.coverage)
        if len(set(coverage_keys)) != len(coverage_keys):
            raise ValueError("capacity pretrade coverage instruments must be unique")
        if any(key not in expected_keys for key in coverage_keys):
            raise ValueError("capacity pretrade coverage contains unexpected instrument")
        if len(set(self.blockers)) != len(self.blockers):
            raise ValueError("capacity pretrade blockers must be unique")
        if len(set(self.warnings)) != len(self.warnings):
            raise ValueError("capacity pretrade warnings must be unique")

        coverage_complete = self.preview_coverage_count == self.required_preview_count
        if self.broker_preview_coverage_complete is not coverage_complete:
            raise ValueError("broker preview coverage status is inconsistent")
        expected_affordability = coverage_complete and all(
            row.preview.affordable
            and PreTradeBlocker.AFFORDABILITY_UNCONFIRMED not in row.preview_blockers
            for row in self.coverage
        )
        if self.affordability_confirmed is not expected_affordability:
            raise ValueError("affordability confirmation is inconsistent")
        expected_commission_integrity = coverage_complete and all(
            row.preview.integrity_confirmed
            and row.preview.canonical_commission is not None
            for row in self.coverage
        )
        if self.commission_integrity_confirmed is not expected_commission_integrity:
            raise ValueError("commission integrity confirmation is inconsistent")

        base_blocked = not self.base_intent_gate.gate_ready
        has_base_blocker = (
            CapacityPreTradeDecisionGateBlocker.BASE_INTENT_GATE_NOT_READY
            in self.blockers
        )
        if has_base_blocker != base_blocked:
            raise ValueError("capacity pretrade base blocker is inconsistent")

        coverage_incomplete = not coverage_complete
        has_coverage_blocker = (
            CapacityPreTradeDecisionGateBlocker.PREVIEW_COVERAGE_INCOMPLETE
            in self.blockers
        )
        if has_coverage_blocker != coverage_incomplete:
            raise ValueError("capacity pretrade coverage blocker is inconsistent")

        preview_not_ready = any(not row.preview_ready for row in self.coverage)
        has_ready_blocker = (
            CapacityPreTradeDecisionGateBlocker.PREVIEW_NOT_READY in self.blockers
        )
        if has_ready_blocker != preview_not_ready:
            raise ValueError("capacity pretrade readiness blocker is inconsistent")

        mismatch_present = any(not row.exact_match for row in self.coverage)
        has_mismatch_blocker = (
            CapacityPreTradeDecisionGateBlocker.PREVIEW_INTENT_MISMATCH
            in self.blockers
        )
        if has_mismatch_blocker != mismatch_present:
            raise ValueError("capacity pretrade mismatch blocker is inconsistent")

        ages = tuple(
            (self.assessed_at - row.preview_evaluated_at).total_seconds()
            for row in self.coverage
        )
        stale_present = any(
            age > self.policy.preview_max_age_seconds for age in ages
        )
        has_stale_blocker = (
            CapacityPreTradeDecisionGateBlocker.PREVIEW_STALE in self.blockers
        )
        if has_stale_blocker != stale_present:
            raise ValueError("capacity pretrade stale blocker is inconsistent")

        future_present = any(
            age < -self.policy.future_tolerance_seconds for age in ages
        )
        has_future_blocker = (
            CapacityPreTradeDecisionGateBlocker.PREVIEW_FROM_FUTURE in self.blockers
        )
        if has_future_blocker != future_present:
            raise ValueError("capacity pretrade future blocker is inconsistent")

        expected_ready = not self.blockers
        if self.gate_ready is not expected_ready:
            raise ValueError("capacity pretrade readiness is inconsistent")
        if self.abstain is expected_ready:
            raise ValueError("capacity pretrade abstain state is inconsistent")
        expected_status = (
            CapacityDecisionGateStatus.READY
            if expected_ready
            else CapacityDecisionGateStatus.ABSTAIN
        )
        if self.status is not expected_status:
            raise ValueError("capacity pretrade status is inconsistent")

        if expected_ready:
            if not self.base_intent_gate.gate_ready:
                raise ValueError("ready pretrade gate requires ready intent gate")
            if not self.broker_preview_coverage_complete:
                raise ValueError("ready pretrade gate requires complete preview coverage")
            if not self.affordability_confirmed:
                raise ValueError("ready pretrade gate requires confirmed affordability")
            if not self.commission_integrity_confirmed:
                raise ValueError("ready pretrade gate requires commission integrity")
            if self.preview_ready_count != self.required_preview_count:
                raise ValueError("ready pretrade gate requires ready previews")
            if self.exact_match_count != self.required_preview_count:
                raise ValueError("ready pretrade gate requires exact intent binding")
            if self.final_option_id != self.base_intent_gate.final_option_id:
                raise ValueError("ready pretrade gate changed final option")
            if self.final_action is not self.base_intent_gate.final_action:
                raise ValueError("ready pretrade gate changed final action")
        else:
            if self.final_option_id != self.no_action_option_id:
                raise ValueError("blocked pretrade gate must select no action")
            if self.final_action is not DecisionAction.WAIT_FOR_DATA:
                raise ValueError("blocked pretrade gate must wait for data")
        return self
