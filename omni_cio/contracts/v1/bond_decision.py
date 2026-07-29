from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel, CurrencyCode, FiniteDecimal
from omni_cio.contracts.v1.decision import (
    DecisionAction,
    DecisionBlocker,
    DecisionConfidence,
    DecisionEvidenceKind,
    DecisionOptionKind,
    DecisionOptionStatus,
    DecisionSetV1,
)


NonNegativeInt = Annotated[int, Field(ge=0)]
UnitInterval = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("1"), allow_inf_nan=False),
]


class BondDecisionBlocker(StrEnum):
    CREDIT_COVERAGE_INCOMPLETE = "credit_coverage_incomplete"
    CREDIT_NOT_READY = "credit_not_ready"
    DURATION_POLICY_BREACH = "duration_policy_breach"
    STRESS_COVERAGE_INCOMPLETE = "stress_coverage_incomplete"
    STRESS_INSTRUMENT_COVERAGE_MISMATCH = "stress_instrument_coverage_mismatch"
    STRESS_CURRENT_VALUE_MISMATCH = "stress_current_value_mismatch"
    STRESS_POLICY_BREACH = "stress_policy_breach"


class BondDecisionWarning(StrEnum):
    RECENT_DOWNGRADE = "recent_downgrade"
    RATING_LABELS_DIVERGE = "rating_labels_diverge"
    SINGLE_AGENCY_COVERAGE = "single_agency_coverage"
    CROSS_AGENCY_SCALE_NOT_NORMALIZED = "cross_agency_scale_not_normalized"
    INACTIVE_RATING_PRESENT = "inactive_rating_present"


class BondDecisionEvidenceV1(ContractModel):
    evidence_id: Annotated[
        str,
        Field(pattern=r"^[a-z0-9][a-z0-9_.:-]{2,255}$"),
    ]
    kind: DecisionEvidenceKind
    statement: Annotated[str, Field(min_length=1, max_length=1024)]
    source_schema: Annotated[str, Field(min_length=1, max_length=128)]
    source_id: Annotated[str | None, Field(max_length=256)] = None
    observed_value: FiniteDecimal | None = None
    limit_value: FiniteDecimal | None = None
    currency: CurrencyCode | None = None
    instrument_key: Annotated[str | None, Field(max_length=256)] = None

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_values(self) -> BondDecisionEvidenceV1:
        if self.limit_value is not None and self.observed_value is None:
            raise ValueError("bond decision evidence limit requires observed value")
        return self


class BondDecisionOptionV1(ContractModel):
    option_id: Annotated[
        str,
        Field(pattern=r"^[a-z0-9][a-z0-9_.:-]{2,255}$"),
    ]
    source_option_id: Annotated[
        str,
        Field(pattern=r"^[a-z0-9][a-z0-9_.:-]{2,255}$"),
    ]
    kind: DecisionOptionKind
    status: DecisionOptionStatus
    action: DecisionAction
    title: Annotated[str, Field(min_length=1, max_length=256)]
    rationale: Annotated[str, Field(min_length=1, max_length=1024)]
    confidence: DecisionConfidence
    base_status: DecisionOptionStatus
    base_action: DecisionAction
    base_blockers: tuple[DecisionBlocker, ...] = ()
    bond_blockers: tuple[BondDecisionBlocker, ...] = ()
    review_conditions: tuple[
        Annotated[str, Field(min_length=1, max_length=512)], ...
    ] = ()
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @model_validator(mode="after")
    def validate_option(self) -> BondDecisionOptionV1:
        if len(self.base_blockers) != len(set(self.base_blockers)):
            raise ValueError("base blockers must be unique")
        if len(self.bond_blockers) != len(set(self.bond_blockers)):
            raise ValueError("bond blockers must be unique")
        blocked = bool(self.base_blockers or self.bond_blockers)
        if self.status == DecisionOptionStatus.BLOCKED and not blocked:
            raise ValueError("blocked bond-aware option requires a blocker")
        if self.status != DecisionOptionStatus.BLOCKED and blocked:
            raise ValueError("only blocked bond-aware options may contain blockers")
        if self.kind == DecisionOptionKind.NO_ACTION:
            if self.action not in (DecisionAction.HOLD, DecisionAction.WAIT_FOR_DATA):
                raise ValueError("bond-aware no-action option has invalid action")
        elif self.kind == DecisionOptionKind.LIMITED_CHANGE:
            if self.action != DecisionAction.REVIEW_LIMITED_CHANGE:
                raise ValueError("bond-aware limited option has invalid action")
        elif self.action != DecisionAction.REVIEW_STRATEGIC_REBALANCE:
            raise ValueError("bond-aware strategic option has invalid action")
        return self


class BondAwareDecisionSetV1(ContractModel):
    evaluated_at: datetime
    base_decision: DecisionSetV1
    required_bond_count: NonNegativeInt
    credit_present_count: NonNegativeInt
    credit_ready_count: NonNegativeInt
    required_stress_currency_count: NonNegativeInt
    stress_currency_coverage_count: NonNegativeInt
    stress_covered_bond_count: NonNegativeInt
    evidence: tuple[BondDecisionEvidenceV1, ...]
    options: tuple[BondDecisionOptionV1, ...]
    preferred_option_id: Annotated[str, Field(min_length=3, max_length=256)]
    base_blockers: tuple[DecisionBlocker, ...]
    bond_blockers: tuple[BondDecisionBlocker, ...]
    warnings: tuple[BondDecisionWarning, ...] = ()
    max_observed_stress_loss_ratio: UnitInterval | None = None
    stress_loss_limit: UnitInterval
    abstain: bool
    recommendation_ready: bool
    confidence: DecisionConfidence
    no_cross_currency_aggregation: Literal[True] = True
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("evaluated_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("bond-aware decision timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_decision(self) -> BondAwareDecisionSetV1:
        if self.base_blockers != self.base_decision.global_blockers:
            raise ValueError("base blockers do not match base decision")
        if len(self.bond_blockers) != len(set(self.bond_blockers)):
            raise ValueError("bond decision blockers must be unique")
        if len(self.warnings) != len(set(self.warnings)):
            raise ValueError("bond decision warnings must be unique")
        evidence_ids = [item.evidence_id for item in self.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("bond decision evidence IDs must be unique")
        if self.credit_present_count > self.required_bond_count:
            raise ValueError("credit presence cannot exceed required bonds")
        if self.credit_ready_count > self.credit_present_count:
            raise ValueError("ready credit count cannot exceed present credit count")
        if self.stress_currency_coverage_count > self.required_stress_currency_count:
            raise ValueError("stress currency coverage exceeds required currencies")
        if self.stress_covered_bond_count > self.required_bond_count:
            raise ValueError("stress bond coverage exceeds required bonds")
        if self.required_bond_count == 0 and any(
            (
                self.credit_present_count,
                self.credit_ready_count,
                self.required_stress_currency_count,
                self.stress_currency_coverage_count,
                self.stress_covered_bond_count,
            )
        ):
            raise ValueError("cash or non-bond decision cannot contain bond coverage")

        option_ids = [option.option_id for option in self.options]
        if len(option_ids) != len(set(option_ids)):
            raise ValueError("bond-aware option IDs must be unique")
        option_kinds = [option.kind for option in self.options]
        if set(option_kinds) != set(DecisionOptionKind) or len(option_kinds) != 3:
            raise ValueError("bond-aware decision requires exactly three option kinds")
        preferred = [
            option
            for option in self.options
            if option.status == DecisionOptionStatus.PREFERRED
        ]
        if len(preferred) != 1:
            raise ValueError("bond-aware decision requires one preferred option")
        if preferred[0].option_id != self.preferred_option_id:
            raise ValueError("bond-aware preferred option does not reconcile")

        expected_abstain = self.base_decision.abstain or bool(self.bond_blockers)
        if self.abstain != expected_abstain:
            raise ValueError("bond-aware abstain state does not reconcile")
        if self.recommendation_ready != (not expected_abstain):
            raise ValueError("bond-aware recommendation readiness does not reconcile")
        if expected_abstain:
            if self.confidence != DecisionConfidence.LOW:
                raise ValueError("blocked bond-aware decision must have low confidence")
            if preferred[0].kind != DecisionOptionKind.NO_ACTION:
                raise ValueError("blocked bond-aware decision must prefer no action")
            if preferred[0].action != DecisionAction.WAIT_FOR_DATA:
                raise ValueError("blocked bond-aware decision must wait for data")
            if any(
                option.kind != DecisionOptionKind.NO_ACTION
                and option.status != DecisionOptionStatus.BLOCKED
                for option in self.options
            ):
                raise ValueError("blocked bond-aware decision must block changes")
        else:
            if self.confidence == DecisionConfidence.LOW:
                raise ValueError("ready bond-aware decision cannot have low confidence")
            if self.warnings and self.confidence == DecisionConfidence.HIGH:
                raise ValueError("bond warnings must reduce high confidence")
            source_by_id = {
                option.option_id: option for option in self.base_decision.options
            }
            for option in self.options:
                source = source_by_id.get(option.source_option_id)
                if source is None:
                    raise ValueError("bond-aware option references unknown source option")
                if (
                    option.kind != source.kind
                    or option.status != source.status
                    or option.action != source.action
                    or option.base_status != source.status
                    or option.base_action != source.action
                ):
                    raise ValueError("ready bond-aware option does not mirror base option")
        return self
