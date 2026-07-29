from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.capacity import CapacityOrderRequestV1
from omni_cio.contracts.v1.common import ContractModel, CurrencyCode
from omni_cio.contracts.v1.decision import DecisionAction
from omni_cio.contracts.v1.decision_capacity import CapacityDecisionGateStatus
from omni_cio.contracts.v1.decision_capacity_intent import (
    CapacityIntentDecisionGateV1,
)
from omni_cio.contracts.v1.sell_pretrade import (
    SellPreTradeBlocker,
    SellPreTradePreviewV1,
    SellPreviewPriceBasis,
)


NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), allow_inf_nan=False),
]
NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]


class CapacitySellPreTradeMismatch(StrEnum):
    SIDE = "side"
    CURRENCY = "currency"
    LOT_SIZE = "lot_size"
    QUANTITY_LOTS = "quantity_lots"
    REFERENCE_PRICE = "reference_price"


class CapacitySellPreTradeDecisionGateBlocker(StrEnum):
    BASE_INTENT_GATE_NOT_READY = "base_intent_gate_not_ready"
    PREVIEW_COVERAGE_INCOMPLETE = "preview_coverage_incomplete"
    PREVIEW_NOT_READY = "preview_not_ready"
    PREVIEW_STALE = "preview_stale"
    PREVIEW_FROM_FUTURE = "preview_from_future"
    PREVIEW_INTENT_MISMATCH = "preview_intent_mismatch"
    POSITION_AVAILABILITY_UNCONFIRMED = "position_availability_unconfirmed"
    OPEN_ORDERS_UNCONFIRMED = "open_orders_unconfirmed"
    TAX_BASIS_UNCONFIRMED = "tax_basis_unconfirmed"
    COMMISSION_INTEGRITY_UNCONFIRMED = "commission_integrity_unconfirmed"


class CapacitySellPreTradeDecisionGateWarning(StrEnum):
    SELL_PREVIEW_ONLY = "sell_preview_only"
    BROKER_PREVIEW_IS_POINT_IN_TIME = "broker_preview_is_point_in_time"
    BROKER_NET_PROCEEDS_NOT_RECOMPUTED_BY_GATE = (
        "broker_net_proceeds_not_recomputed_by_gate"
    )
    COMMISSION_TAX_AND_ACCRUED_INTEREST_FROM_PREVIEW = (
        "commission_tax_and_accrued_interest_from_preview"
    )
    REVIEW_ONLY_NO_ORDER_CREATED = "review_only_no_order_created"


class CapacitySellPreTradeDecisionGatePolicyV1(ContractModel):
    preview_max_age_seconds: Annotated[int, Field(ge=1, le=86_400)] = 180
    future_tolerance_seconds: Annotated[int, Field(ge=0, le=3_600)] = 60


class CapacitySellPreTradeCoverageV1(ContractModel):
    instrument_key: Annotated[str, Field(min_length=3, max_length=256)]
    expected_request: CapacityOrderRequestV1
    preview: SellPreTradePreviewV1
    mismatch_fields: tuple[CapacitySellPreTradeMismatch, ...] = ()
    exact_match: bool
    preview_ready: bool
    preview_evaluated_at: datetime
    preview_currency: CurrencyCode
    preview_price_basis: SellPreviewPriceBasis
    preview_unit_price: NonNegativeDecimal | None = None
    preview_lot_size: PositiveInt | None = None
    preview_quantity_lots: PositiveInt | None = None
    preview_blockers: tuple[SellPreTradeBlocker, ...] = ()

    @field_validator("preview_currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("preview_evaluated_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("capacity sell-pretrade timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_coverage(self) -> CapacitySellPreTradeCoverageV1:
        if self.expected_request.instrument_key != self.instrument_key:
            raise ValueError("expected sell-pretrade instrument mismatch")
        if self.preview.stable_key != self.instrument_key:
            raise ValueError("sell preview instrument mismatch")
        mirrored_values = (
            (self.preview_evaluated_at, self.preview.evaluated_at, "timestamp"),
            (self.preview_currency, self.preview.currency, "currency"),
            (self.preview_price_basis, self.preview.price_basis, "price basis"),
            (self.preview_unit_price, self.preview.unit_price, "unit price"),
            (self.preview_lot_size, self.preview.lot_size, "lot size"),
            (self.preview_quantity_lots, self.preview.quantity_lots, "quantity"),
            (self.preview_blockers, self.preview.blockers, "blockers"),
            (self.preview_ready, self.preview.preview_ready, "readiness"),
        )
        for observed, expected, label in mirrored_values:
            if observed != expected:
                raise ValueError(f"sell preview {label} does not reconcile")
        if len(set(self.mismatch_fields)) != len(self.mismatch_fields):
            raise ValueError("capacity sell-pretrade mismatch fields must be unique")
        if self.exact_match is bool(self.mismatch_fields):
            raise ValueError("capacity sell-pretrade exact-match state is inconsistent")
        return self


class CapacitySellPreTradeDecisionGateV1(ContractModel):
    schema_name: Literal["capacity_sell_pretrade_decision_gate"] = (
        "capacity_sell_pretrade_decision_gate"
    )
    schema_version: Literal["1.0"] = "1.0"
    assessed_at: datetime
    status: CapacityDecisionGateStatus
    gate_ready: bool
    abstain: bool
    base_intent_gate: CapacityIntentDecisionGateV1
    policy: CapacitySellPreTradeDecisionGatePolicyV1
    no_action_option_id: Annotated[str, Field(min_length=3, max_length=256)]
    final_option_id: Annotated[str, Field(min_length=3, max_length=256)]
    final_action: DecisionAction
    required_preview_count: PositiveInt
    preview_coverage_count: NonNegativeInt
    preview_ready_count: NonNegativeInt
    exact_match_count: NonNegativeInt
    coverage: tuple[CapacitySellPreTradeCoverageV1, ...]
    blockers: tuple[CapacitySellPreTradeDecisionGateBlocker, ...] = ()
    warnings: tuple[CapacitySellPreTradeDecisionGateWarning, ...] = ()
    broker_preview_coverage_complete: bool
    position_availability_confirmed: bool
    open_orders_confirmed: bool
    tax_basis_confirmed: bool
    commission_integrity_confirmed: bool
    net_proceeds_recomputed_by_gate: Literal[False] = False
    option_selected_by_gate: Literal[False] = False
    order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @property
    def broker_preview_checked(self) -> bool:
        return self.broker_preview_coverage_complete

    @property
    def position_availability_checked(self) -> bool:
        return self.position_availability_confirmed

    @property
    def open_orders_checked(self) -> bool:
        return self.open_orders_confirmed

    @property
    def tax_basis_checked(self) -> bool:
        return self.tax_basis_confirmed

    @property
    def commission_integrity_checked(self) -> bool:
        return self.commission_integrity_confirmed

    @field_validator("assessed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "capacity sell-pretrade gate timestamp must be timezone-aware"
            )
        return value.astimezone(timezone.utc)

    def _has(self, blocker: CapacitySellPreTradeDecisionGateBlocker) -> bool:
        return blocker in self.blockers

    @model_validator(mode="after")
    def validate_gate(self) -> CapacitySellPreTradeDecisionGateV1:
        expected_requests = self.base_intent_gate.request.expected_capacity_requests
        expected_keys = tuple(row.instrument_key for row in expected_requests)
        if self.no_action_option_id != self.base_intent_gate.no_action_option_id:
            raise ValueError(
                "capacity sell-pretrade no-action option does not reconcile"
            )
        if self.required_preview_count != len(expected_requests):
            raise ValueError("required sell-preview count does not reconcile")
        if self.preview_coverage_count != len(self.coverage):
            raise ValueError("sell-preview coverage count does not reconcile")
        if self.preview_ready_count != sum(row.preview_ready for row in self.coverage):
            raise ValueError("ready sell-preview count does not reconcile")
        if self.exact_match_count != sum(row.exact_match for row in self.coverage):
            raise ValueError("exact sell-preview count does not reconcile")

        coverage_keys = tuple(row.instrument_key for row in self.coverage)
        if len(set(coverage_keys)) != len(coverage_keys):
            raise ValueError(
                "capacity sell-pretrade coverage instruments must be unique"
            )
        if any(key not in expected_keys for key in coverage_keys):
            raise ValueError(
                "capacity sell-pretrade coverage contains unexpected instrument"
            )
        if len(set(self.blockers)) != len(self.blockers):
            raise ValueError("capacity sell-pretrade blockers must be unique")
        if len(set(self.warnings)) != len(self.warnings):
            raise ValueError("capacity sell-pretrade warnings must be unique")

        coverage_complete = self.preview_coverage_count == self.required_preview_count
        if self.broker_preview_coverage_complete is not coverage_complete:
            raise ValueError("sell broker-preview coverage status is inconsistent")
        expected_position = coverage_complete and all(
            row.preview.position_availability_confirmed
            and SellPreTradeBlocker.POSITION_INSUFFICIENT not in row.preview_blockers
            and SellPreTradeBlocker.SHORT_SALE_FORBIDDEN not in row.preview_blockers
            for row in self.coverage
        )
        if self.position_availability_confirmed is not expected_position:
            raise ValueError("sell position availability confirmation is inconsistent")
        expected_open_orders = coverage_complete and all(
            row.preview.open_orders_checked
            and SellPreTradeBlocker.OPEN_ORDERS_UNCHECKED not in row.preview_blockers
            and SellPreTradeBlocker.OPEN_ORDER_CONFLICT not in row.preview_blockers
            for row in self.coverage
        )
        if self.open_orders_confirmed is not expected_open_orders:
            raise ValueError("sell open-order confirmation is inconsistent")
        expected_tax = coverage_complete and all(
            row.preview.tax_basis_confirmed
            and row.preview.estimated_tax is not None
            and SellPreTradeBlocker.TAX_BASIS_UNAVAILABLE not in row.preview_blockers
            for row in self.coverage
        )
        if self.tax_basis_confirmed is not expected_tax:
            raise ValueError("sell tax-basis confirmation is inconsistent")
        expected_commission = coverage_complete and all(
            row.preview.integrity_confirmed
            and row.preview.canonical_commission is not None
            and SellPreTradeBlocker.COMMISSION_UNAVAILABLE not in row.preview_blockers
            and SellPreTradeBlocker.ARITHMETIC_INTEGRITY_FAILED
            not in row.preview_blockers
            for row in self.coverage
        )
        if self.commission_integrity_confirmed is not expected_commission:
            raise ValueError("sell commission integrity confirmation is inconsistent")

        expected_blocker_states = (
            (
                CapacitySellPreTradeDecisionGateBlocker.BASE_INTENT_GATE_NOT_READY,
                not self.base_intent_gate.gate_ready,
            ),
            (
                CapacitySellPreTradeDecisionGateBlocker.PREVIEW_COVERAGE_INCOMPLETE,
                not coverage_complete,
            ),
            (
                CapacitySellPreTradeDecisionGateBlocker.PREVIEW_NOT_READY,
                any(not row.preview_ready for row in self.coverage),
            ),
            (
                CapacitySellPreTradeDecisionGateBlocker.PREVIEW_INTENT_MISMATCH,
                any(not row.exact_match for row in self.coverage),
            ),
            (
                CapacitySellPreTradeDecisionGateBlocker.PREVIEW_STALE,
                any(
                    (self.assessed_at - row.preview_evaluated_at).total_seconds()
                    > self.policy.preview_max_age_seconds
                    for row in self.coverage
                ),
            ),
            (
                CapacitySellPreTradeDecisionGateBlocker.PREVIEW_FROM_FUTURE,
                any(
                    (self.assessed_at - row.preview_evaluated_at).total_seconds()
                    < -self.policy.future_tolerance_seconds
                    for row in self.coverage
                ),
            ),
            (
                CapacitySellPreTradeDecisionGateBlocker.POSITION_AVAILABILITY_UNCONFIRMED,
                not expected_position,
            ),
            (
                CapacitySellPreTradeDecisionGateBlocker.OPEN_ORDERS_UNCONFIRMED,
                not expected_open_orders,
            ),
            (
                CapacitySellPreTradeDecisionGateBlocker.TAX_BASIS_UNCONFIRMED,
                not expected_tax,
            ),
            (
                CapacitySellPreTradeDecisionGateBlocker.COMMISSION_INTEGRITY_UNCONFIRMED,
                not expected_commission,
            ),
        )
        for blocker, expected_present in expected_blocker_states:
            if self._has(blocker) != expected_present:
                raise ValueError(
                    f"capacity sell-pretrade {blocker.value} is inconsistent"
                )

        expected_ready = not self.blockers
        expected_status = (
            CapacityDecisionGateStatus.READY
            if expected_ready
            else CapacityDecisionGateStatus.ABSTAIN
        )
        if self.gate_ready is not expected_ready:
            raise ValueError("capacity sell-pretrade readiness is inconsistent")
        if self.abstain is expected_ready:
            raise ValueError("capacity sell-pretrade abstain state is inconsistent")
        if self.status is not expected_status:
            raise ValueError("capacity sell-pretrade status is inconsistent")

        if expected_ready:
            if not self.broker_preview_coverage_complete:
                raise ValueError("ready sell gate requires complete preview coverage")
            if not self.position_availability_confirmed:
                raise ValueError("ready sell gate requires confirmed position")
            if not self.open_orders_confirmed:
                raise ValueError("ready sell gate requires checked open orders")
            if not self.tax_basis_confirmed:
                raise ValueError("ready sell gate requires confirmed tax basis")
            if not self.commission_integrity_confirmed:
                raise ValueError("ready sell gate requires commission integrity")
            if self.preview_ready_count != self.required_preview_count:
                raise ValueError("ready sell gate requires ready previews")
            if self.exact_match_count != self.required_preview_count:
                raise ValueError("ready sell gate requires exact intent binding")
            if self.final_option_id != self.base_intent_gate.final_option_id:
                raise ValueError("ready sell gate changed final option")
            if self.final_action is not self.base_intent_gate.final_action:
                raise ValueError("ready sell gate changed final action")
        else:
            if self.final_option_id != self.no_action_option_id:
                raise ValueError("blocked sell gate must select no action")
            if self.final_action is not DecisionAction.WAIT_FOR_DATA:
                raise ValueError("blocked sell gate must wait for data")
        return self
