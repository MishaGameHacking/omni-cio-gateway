from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import (
    ContractMetadata,
    ContractModel,
    CurrencyCode,
    FiniteDecimal,
)
from omni_cio.contracts.v1.market import MarketReadinessAssessmentV1


NonNegativeInt = Annotated[int, Field(ge=0)]


class DecisionEvidenceKind(StrEnum):
    FACT = "fact"
    CALCULATION = "calculation"
    INFERENCE = "inference"
    SCENARIO = "scenario"
    RECOMMENDATION = "recommendation"
    WARNING = "warning"
    MISSING_DATA = "missing_data"


class DecisionOptionKind(StrEnum):
    NO_ACTION = "no_action"
    LIMITED_CHANGE = "limited_change"
    STRATEGIC_REBALANCE = "strategic_rebalance"


class DecisionOptionStatus(StrEnum):
    PREFERRED = "preferred"
    AVAILABLE = "available"
    REVIEW_ONLY = "review_only"
    BLOCKED = "blocked"


class DecisionAction(StrEnum):
    HOLD = "hold"
    WAIT_FOR_DATA = "wait_for_data"
    REVIEW_LIMITED_CHANGE = "review_limited_change"
    REVIEW_STRATEGIC_REBALANCE = "review_strategic_rebalance"


class DecisionConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DecisionBlocker(StrEnum):
    PORTFOLIO_NOT_READY = "portfolio_not_ready"
    RISK_NOT_READY = "risk_not_ready"
    MARKET_NOT_READY = "market_not_ready"
    MARKET_COVERAGE_INCOMPLETE = "market_coverage_incomplete"
    NEWS_EVIDENCE_UNUSABLE = "news_evidence_unusable"
    NEWS_CONTRADICTION = "news_contradiction"
    REBALANCING_ENGINE_NOT_AVAILABLE = "rebalancing_engine_not_available"


class InstrumentMarketReadinessV1(ContractModel):
    instrument_key: Annotated[str, Field(min_length=3, max_length=256)]
    assessment: MarketReadinessAssessmentV1


class DecisionEvidenceV1(ContractModel):
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
    def validate_values(self) -> DecisionEvidenceV1:
        if self.limit_value is not None and self.observed_value is None:
            raise ValueError("limit_value requires observed_value")
        return self


class DecisionOptionV1(ContractModel):
    option_id: Annotated[
        str,
        Field(pattern=r"^[a-z0-9][a-z0-9_.:-]{2,255}$"),
    ]
    kind: DecisionOptionKind
    status: DecisionOptionStatus
    action: DecisionAction
    title: Annotated[str, Field(min_length=1, max_length=256)]
    rationale: Annotated[str, Field(min_length=1, max_length=1024)]
    confidence: DecisionConfidence
    evidence_ids: tuple[
        Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_.:-]{2,255}$")], ...
    ]
    blockers: tuple[DecisionBlocker, ...] = ()
    review_conditions: tuple[
        Annotated[str, Field(min_length=1, max_length=512)], ...
    ] = ()
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @model_validator(mode="after")
    def validate_option(self) -> DecisionOptionV1:
        if len(self.blockers) != len(set(self.blockers)):
            raise ValueError("option blockers must be unique")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("option evidence IDs must be unique")
        if self.status == DecisionOptionStatus.BLOCKED and not self.blockers:
            raise ValueError("blocked option requires a blocker")
        if self.status != DecisionOptionStatus.BLOCKED and self.blockers:
            raise ValueError("only blocked options may contain blockers")
        if self.kind == DecisionOptionKind.NO_ACTION:
            if self.action not in (DecisionAction.HOLD, DecisionAction.WAIT_FOR_DATA):
                raise ValueError("no-action option has an invalid action")
        elif self.kind == DecisionOptionKind.LIMITED_CHANGE:
            if self.action != DecisionAction.REVIEW_LIMITED_CHANGE:
                raise ValueError("limited-change option has an invalid action")
        elif self.action != DecisionAction.REVIEW_STRATEGIC_REBALANCE:
            raise ValueError("strategic-rebalance option has an invalid action")
        return self


class DecisionSetV1(ContractModel):
    metadata: ContractMetadata
    evidence: tuple[DecisionEvidenceV1, ...]
    options: tuple[DecisionOptionV1, ...]
    preferred_option_id: Annotated[str, Field(min_length=3, max_length=256)]
    abstain: bool
    recommendation_ready: bool
    confidence: DecisionConfidence
    global_blockers: tuple[DecisionBlocker, ...]
    accepted_news_count: NonNegativeInt
    context_news_count: NonNegativeInt
    rejected_news_count: NonNegativeInt
    required_market_count: NonNegativeInt
    market_coverage_count: NonNegativeInt
    trading_methods: Literal[False] = False

    @model_validator(mode="after")
    def validate_decision_set(self) -> DecisionSetV1:
        if self.metadata.schema_name != "decision_set":
            raise ValueError("schema_name must be decision_set")
        if len(self.global_blockers) != len(set(self.global_blockers)):
            raise ValueError("global blockers must be unique")

        evidence_ids = [row.evidence_id for row in self.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("evidence IDs must be unique")
        evidence_id_set = set(evidence_ids)

        option_ids = [option.option_id for option in self.options]
        if len(option_ids) != len(set(option_ids)):
            raise ValueError("option IDs must be unique")
        option_kinds = [option.kind for option in self.options]
        if set(option_kinds) != set(DecisionOptionKind) or len(option_kinds) != 3:
            raise ValueError("decision set requires exactly three option kinds")

        preferred = [
            option
            for option in self.options
            if option.status == DecisionOptionStatus.PREFERRED
        ]
        if len(preferred) != 1:
            raise ValueError("decision set requires exactly one preferred option")
        if preferred[0].option_id != self.preferred_option_id:
            raise ValueError("preferred_option_id does not match preferred option")
        if self.preferred_option_id not in set(option_ids):
            raise ValueError("preferred option is absent")
        if any(
            evidence_id not in evidence_id_set
            for option in self.options
            for evidence_id in option.evidence_ids
        ):
            raise ValueError("option references unknown evidence")

        expected_ready = not self.abstain and not self.global_blockers
        if self.recommendation_ready != expected_ready:
            raise ValueError("recommendation_ready does not match blockers")
        if self.abstain:
            if self.confidence != DecisionConfidence.LOW:
                raise ValueError("abstain decision must have low confidence")
            if preferred[0].kind != DecisionOptionKind.NO_ACTION:
                raise ValueError("abstain must prefer no action")
            if preferred[0].action != DecisionAction.WAIT_FOR_DATA:
                raise ValueError("abstain must wait for data")
            if any(
                option.kind != DecisionOptionKind.NO_ACTION
                and option.status != DecisionOptionStatus.BLOCKED
                for option in self.options
            ):
                raise ValueError("abstain must block change options")
        elif preferred[0].action == DecisionAction.WAIT_FOR_DATA:
            raise ValueError("ready decision cannot prefer wait-for-data")

        strategic = next(
            option
            for option in self.options
            if option.kind == DecisionOptionKind.STRATEGIC_REBALANCE
        )
        if strategic.status == DecisionOptionStatus.PREFERRED:
            raise ValueError("strategic rebalance cannot be preferred before PR-13")
        if self.market_coverage_count > self.required_market_count:
            raise ValueError("market coverage cannot exceed required count")
        return self
