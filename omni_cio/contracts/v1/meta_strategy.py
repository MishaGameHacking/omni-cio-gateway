from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
import hashlib
import json
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.investment_policy import PolicyReferenceV1


Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
UnitWeight = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("1"), allow_inf_nan=False),
]
ComparisonGrade = Annotated[int, Field(ge=0, le=4)]
FrictionWeight = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("2"), allow_inf_nan=False),
]


class StrategyRegime(StrEnum):
    NO_ACTION = "no_action"
    CAPITAL_PRESERVATION = "capital_preservation"
    DEFENSIVE_BALANCED = "defensive_balanced"
    BALANCED_CORE = "balanced_core"
    GROWTH_CORE = "growth_core"


class StrategyComponentKind(StrEnum):
    LIQUIDITY_RESERVE = "liquidity_reserve"
    QUALITY_DEBT = "quality_debt"
    DIVERSIFIED_CORE = "diversified_core"
    BOUNDED_ACTIVE = "bounded_active"


class StrategyComponentDirective(StrEnum):
    REQUIRED = "required"
    ALLOWED = "allowed"
    FORBIDDEN = "forbidden"


class StrategySelectionBlockerCode(StrEnum):
    IPS_NOT_READY = "ips_not_ready"
    POLICY_BINDING_MISMATCH = "policy_binding_mismatch"
    RISK_BINDING_MISMATCH = "risk_binding_mismatch"
    RISK_NOT_READY = "risk_not_ready"
    HYPOTHETICAL_RISK_ASSESSMENT = "hypothetical_risk_assessment"
    TAX_CONTEXT_UNKNOWN = "tax_context_unknown"
    FRICTION_EVIDENCE_INCOMPLETE = "friction_evidence_incomplete"
    FRICTION_EVIDENCE_STALE = "friction_evidence_stale"
    FRICTION_EVIDENCE_FUTURE = "friction_evidence_future"
    NO_FEASIBLE_STRATEGY = "no_feasible_strategy"


class StrategyCandidateBlockerCode(StrEnum):
    CURRENT_HARD_BREACH = "current_hard_breach"
    RISK_BUDGET_EXCEEDED = "risk_budget_exceeded"
    HORIZON_TOO_SHORT = "horizon_too_short"
    DIVERSIFIED_CORE_UNAVAILABLE = "diversified_core_unavailable"
    QUALITY_DEBT_UNAVAILABLE = "quality_debt_unavailable"
    LIQUIDITY_TOO_WEAK = "liquidity_too_weak"


class StrategyReviewAction(StrEnum):
    REVIEW = "review"
    CANCEL = "cancel"


class StrategyReviewCode(StrEnum):
    POLICY_CHANGED = "policy_changed"
    PORTFOLIO_CHANGED = "portfolio_changed"
    RISK_STATE_CHANGED = "risk_state_changed"
    HARD_BREACH_APPEARED = "hard_breach_appeared"
    FRICTION_EVIDENCE_STALE = "friction_evidence_stale"
    TAX_CONTEXT_CHANGED = "tax_context_changed"


class StrategyFrictionEvidenceV1(ContractModel):
    regime: StrategyRegime
    transition_cost_weight: UnitWeight
    tax_cost_weight: UnitWeight
    as_of: datetime
    source_sha256s: Annotated[tuple[Sha256, ...], Field(min_length=1)]

    @field_validator("as_of")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("strategy friction timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("source_sha256s", mode="before")
    @classmethod
    def normalize_sources(cls, value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("strategy friction sources must be a collection")
        result = tuple(sorted(set(value)))
        if not result:
            raise ValueError("strategy friction sources cannot be empty")
        return result

    @model_validator(mode="after")
    def validate_regime(self) -> StrategyFrictionEvidenceV1:
        if self.regime is StrategyRegime.NO_ACTION:
            raise ValueError("NO_ACTION cannot carry transition friction evidence")
        return self

    @property
    def total_friction_weight(self) -> Decimal:
        return self.transition_cost_weight + self.tax_cost_weight


class MetaStrategySettingsV1(ContractModel):
    friction_max_age_seconds: Annotated[int, Field(ge=60)] = 86400
    future_tolerance_seconds: Annotated[int, Field(ge=0)] = 60


class StrategyComponentV1(ContractModel):
    kind: StrategyComponentKind
    directive: StrategyComponentDirective
    rationale_code: Annotated[
        str,
        Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$"),
    ]


class StrategyComparisonV1(ContractModel):
    regime: StrategyRegime
    feasible: bool
    objective_fit: ComparisonGrade
    risk_fit: ComparisonGrade
    liquidity_fit: ComparisonGrade
    friction_weight: FrictionWeight | None = None
    blockers: tuple[StrategyCandidateBlockerCode, ...] = ()
    rationale_codes: tuple[
        Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")], ...
    ] = ()

    @field_validator("blockers", mode="before")
    @classmethod
    def normalize_blockers(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("strategy candidate blockers must be a collection")
        return tuple(sorted(set(value), key=str))

    @field_validator("rationale_codes", mode="before")
    @classmethod
    def normalize_rationale_codes(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("strategy rationale codes must be a collection")
        return tuple(sorted({str(item).strip().upper() for item in value}))

    @model_validator(mode="after")
    def validate_feasibility(self) -> StrategyComparisonV1:
        if self.feasible and self.blockers:
            raise ValueError("feasible strategy cannot carry candidate blockers")
        if not self.feasible and not self.blockers:
            raise ValueError("infeasible strategy requires at least one blocker")
        if self.regime is StrategyRegime.NO_ACTION and self.friction_weight not in (
            None,
            Decimal("0"),
        ):
            raise ValueError("NO_ACTION friction must be zero or absent")
        return self


class StrategyReviewConditionV1(ContractModel):
    code: StrategyReviewCode
    action: StrategyReviewAction


class MetaStrategySelectionV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    selected_at: datetime
    portfolio_snapshot_sha256: Sha256
    policy_reference: PolicyReferenceV1
    risk_assessment_sha256: Sha256
    selected_regime: StrategyRegime
    components: Annotated[tuple[StrategyComponentV1, ...], Field(min_length=4, max_length=4)]
    comparisons: Annotated[tuple[StrategyComparisonV1, ...], Field(min_length=5, max_length=5)]
    blockers: tuple[StrategySelectionBlockerCode, ...] = ()
    review_conditions: Annotated[
        tuple[StrategyReviewConditionV1, ...],
        Field(min_length=6, max_length=6),
    ]
    remediation_required: bool
    decision_ready: bool
    optimizer_eligible: bool
    selection_sha256: Sha256
    trading_methods: Literal[False] = False

    @field_validator("selected_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("strategy selection timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("components", mode="before")
    @classmethod
    def normalize_components(cls, value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("strategy components must be a collection")
        return tuple(sorted(value, key=lambda row: _item_key(row, "kind")))

    @field_validator("comparisons", mode="before")
    @classmethod
    def normalize_comparisons(cls, value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("strategy comparisons must be a collection")
        return tuple(sorted(value, key=_comparison_sort_key))

    @field_validator("blockers", mode="before")
    @classmethod
    def normalize_blockers(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("strategy selection blockers must be a collection")
        return tuple(sorted(set(value), key=str))

    @field_validator("review_conditions", mode="before")
    @classmethod
    def normalize_review_conditions(cls, value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("strategy review conditions must be a collection")
        return tuple(sorted(value, key=lambda row: _item_key(row, "code")))

    @model_validator(mode="after")
    def validate_selection(self) -> MetaStrategySelectionV1:
        component_kinds = [row.kind for row in self.components]
        if set(component_kinds) != set(StrategyComponentKind):
            raise ValueError("selection must contain every strategy component exactly once")
        if len(component_kinds) != len(set(component_kinds)):
            raise ValueError("strategy component kinds must be unique")

        regimes = [row.regime for row in self.comparisons]
        if set(regimes) != set(StrategyRegime):
            raise ValueError("selection must compare every strategy regime exactly once")
        if len(regimes) != len(set(regimes)):
            raise ValueError("strategy comparison regimes must be unique")
        if self.comparisons != tuple(sorted(self.comparisons, key=_comparison_sort_key)):
            raise ValueError("strategy comparisons must use deterministic ordering")

        review_codes = [row.code for row in self.review_conditions]
        if set(review_codes) != set(StrategyReviewCode):
            raise ValueError("selection must contain every review condition exactly once")
        if len(review_codes) != len(set(review_codes)):
            raise ValueError("strategy review conditions must be unique")

        expected_ready = not self.blockers
        if self.decision_ready != expected_ready:
            raise ValueError("strategy readiness must match global blockers")
        if not self.decision_ready and self.selected_regime is not StrategyRegime.NO_ACTION:
            raise ValueError("blocked selection must fail closed to NO_ACTION")

        feasible = tuple(row for row in self.comparisons if row.feasible)
        if self.decision_ready:
            if not feasible:
                raise ValueError("ready selection requires a feasible strategy")
            if self.selected_regime is not feasible[0].regime:
                raise ValueError("selected regime must equal best deterministic comparison")
            if any(
                row.regime is not StrategyRegime.NO_ACTION
                and row.feasible
                and row.friction_weight is None
                for row in self.comparisons
            ):
                raise ValueError("ready non-NO_ACTION comparisons require friction evidence")

        expected_optimizer = self.decision_ready and (
            self.selected_regime is not StrategyRegime.NO_ACTION
        )
        if self.optimizer_eligible != expected_optimizer:
            raise ValueError("optimizer eligibility must match selected actionable regime")
        if self.selection_sha256 != meta_strategy_sha256(self):
            raise ValueError("strategy selection SHA-256 does not match canonical payload")
        return self


def _item_key(row: object, attribute: str) -> str:
    if isinstance(row, dict):
        value = row.get(attribute)
    else:
        value = getattr(row, attribute, None)
    if isinstance(value, StrEnum):
        return value.value
    return str(value)


def _comparison_sort_key(row: object) -> tuple[object, ...]:
    if isinstance(row, dict):
        regime = row.get("regime")
        feasible = bool(row.get("feasible", False))
        risk_fit = int(row.get("risk_fit", 0))
        objective_fit = int(row.get("objective_fit", 0))
        liquidity_fit = int(row.get("liquidity_fit", 0))
        friction = row.get("friction_weight")
    else:
        regime = getattr(row, "regime", StrategyRegime.NO_ACTION)
        feasible = bool(getattr(row, "feasible", False))
        risk_fit = int(getattr(row, "risk_fit", 0))
        objective_fit = int(getattr(row, "objective_fit", 0))
        liquidity_fit = int(getattr(row, "liquidity_fit", 0))
        friction = getattr(row, "friction_weight", None)
    regime_value = regime.value if isinstance(regime, StrategyRegime) else str(regime)
    friction_value = Decimal("99") if friction is None else Decimal(str(friction))
    return (
        0 if feasible else 1,
        -risk_fit,
        -objective_fit,
        -liquidity_fit,
        friction_value,
        0 if regime_value == StrategyRegime.NO_ACTION.value else 1,
        regime_value,
    )


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def meta_strategy_sha256(selection: MetaStrategySelectionV1) -> str:
    payload = selection.model_dump(mode="json", exclude={"selection_sha256"})
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
