from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel, Money
from omni_cio.contracts.v1.investment_policy import PolicyReferenceV1
from omni_cio.contracts.v1.market import MarketLiquidityV1, MarketQuoteV1
from omni_cio.contracts.v1.portfolio import InstrumentType


UnitInterval = Annotated[Decimal, Field(ge=0, le=1, allow_inf_nan=False)]
Grade = Annotated[int, Field(ge=0, le=4)]
RankPoints = Annotated[int, Field(ge=0, le=400)]
Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]

CANDIDATE_FACTOR_WEIGHTS: dict[str, int] = {
    "role_fit": 25,
    "diversification": 20,
    "liquidity": 20,
    "cost": 15,
    "permanent_loss": 10,
    "freshness": 10,
}


class CandidateRole(StrEnum):
    LIQUIDITY_RESERVE = "liquidity_reserve"
    DEFENSIVE_BOND = "defensive_bond"
    INCOME = "income"
    EQUITY_GROWTH = "equity_growth"
    DIVERSIFICATION = "diversification"


class GapUrgency(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class CandidateKind(StrEnum):
    SECURITY = "security"
    NO_ACTION_CASH = "no_action_cash"


class CandidatePriceBasis(StrEnum):
    CURRENCY = "currency"
    PERCENT_OF_NOMINAL = "percent_of_nominal"


class PreliminaryLossStatus(StrEnum):
    PASS = "pass"
    WATCH = "watch"
    UNKNOWN = "unknown"
    BLOCK = "block"


class CandidateGlobalBlockerCode(StrEnum):
    IPS_NOT_READY = "ips_not_ready"
    UNIVERSE_NOT_READY = "universe_not_ready"
    DUPLICATE_EVIDENCE = "duplicate_evidence"
    EVIDENCE_COVERAGE_INCOMPLETE = "evidence_coverage_incomplete"


class CandidateBlockerCode(StrEnum):
    ROLE_MISMATCH = "role_mismatch"
    POLICY_INSTRUMENT_NOT_ALLOWED = "policy_instrument_not_allowed"
    POLICY_INSTRUMENT_PROHIBITED = "policy_instrument_prohibited"
    POLICY_MARKET_NOT_ALLOWED = "policy_market_not_allowed"
    POLICY_MARKET_PROHIBITED = "policy_market_prohibited"
    TARGET_CURRENCY_MISMATCH = "target_currency_mismatch"
    LIQUIDITY_FLAG_INSUFFICIENT = "liquidity_flag_insufficient"
    MARKET_EVIDENCE_MISSING = "market_evidence_missing"
    EVALUATION_INCOMPLETE = "evaluation_incomplete"
    MARKET_IDENTITY_MISMATCH = "market_identity_mismatch"
    MARKET_SOURCE_UNTRUSTED = "market_source_untrusted"
    MARKET_STALE = "market_stale"
    MARKET_FUTURE_TIMESTAMP = "market_future_timestamp"
    COST_BASIS_INVALID = "cost_basis_invalid"
    BUDGET_CURRENCY_MISMATCH = "budget_currency_mismatch"
    UNAFFORDABLE_MIN_LOT = "unaffordable_min_lot"
    PORTFOLIO_VALUE_CURRENCY_MISMATCH = "portfolio_value_currency_mismatch"
    POSITION_LIMIT = "position_limit"
    GROUP_LIMIT = "group_limit"
    SECTOR_LIMIT = "sector_limit"
    CURRENCY_LIMIT = "currency_limit"
    PERMANENT_LOSS_BLOCKED = "permanent_loss_blocked"


class PortfolioGapV1(ContractModel):
    gap_id: Annotated[str, Field(pattern=r"^gap_[a-z0-9][a-z0-9_-]{2,63}$")]
    role: CandidateRole
    urgency: GapUrgency
    target_currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
    portfolio_snapshot_sha256: Sha256
    budget: Money | None = None
    max_research_candidates: Annotated[int, Field(ge=1, le=10)] = 5

    @field_validator("target_currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_budget(self) -> PortfolioGapV1:
        if self.budget is not None and self.budget.currency != self.target_currency:
            raise ValueError("gap budget currency must equal target currency")
        return self


class CandidateExposureContextV1(ContractModel):
    instrument_uid: Annotated[str, Field(min_length=1, max_length=128)]
    portfolio_value: Money
    current_position_weight: UnitInterval
    current_group_weight: UnitInterval
    current_sector_weight: UnitInterval
    current_currency_weight: UnitInterval

    @model_validator(mode="after")
    def validate_hierarchy(self) -> CandidateExposureContextV1:
        if self.portfolio_value.amount <= 0:
            raise ValueError("portfolio value must be positive")
        if self.current_group_weight < self.current_position_weight:
            raise ValueError("group weight cannot be below position weight")
        if self.current_sector_weight < self.current_position_weight:
            raise ValueError("sector weight cannot be below position weight")
        if self.current_currency_weight < self.current_position_weight:
            raise ValueError("currency weight cannot be below position weight")
        return self


class CandidateCostBasisV1(ContractModel):
    instrument_uid: Annotated[str, Field(min_length=1, max_length=128)]
    price_basis: CandidatePriceBasis
    nominal: Money | None = None
    accrued_interest_per_unit: Money | None = None

    @model_validator(mode="after")
    def validate_basis(self) -> CandidateCostBasisV1:
        if self.price_basis is CandidatePriceBasis.PERCENT_OF_NOMINAL:
            if self.nominal is None:
                raise ValueError("percent-of-nominal basis requires nominal")
            if self.nominal.amount <= 0:
                raise ValueError("bond nominal must be positive")
            if (
                self.accrued_interest_per_unit is not None
                and self.accrued_interest_per_unit.currency != self.nominal.currency
            ):
                raise ValueError("bond nominal and accrued interest currency mismatch")
        elif self.nominal is not None or self.accrued_interest_per_unit is not None:
            raise ValueError("currency price basis cannot carry bond nominal/ACI")
        return self


class CandidateRiskScreenV1(ContractModel):
    screen_model: Literal["preliminary_loss_v1"] = "preliminary_loss_v1"
    instrument_uid: Annotated[str, Field(min_length=1, max_length=128)]
    status: PreliminaryLossStatus
    evidence_codes: tuple[
        Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")], ...
    ] = ()

    @field_validator("evidence_codes", mode="before")
    @classmethod
    def normalize_codes(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("evidence_codes must be a collection")
        return tuple(sorted({str(item).strip().upper() for item in value}))


class CandidateEvidenceV1(ContractModel):
    instrument_uid: Annotated[str, Field(min_length=1, max_length=128)]
    quote: MarketQuoteV1
    liquidity: MarketLiquidityV1
    exposure: CandidateExposureContextV1
    cost_basis: CandidateCostBasisV1
    risk_screen: CandidateRiskScreenV1

    @model_validator(mode="after")
    def validate_identity(self) -> CandidateEvidenceV1:
        expected_key = f"uid:{self.instrument_uid}"
        if self.quote.instrument_key != expected_key:
            raise ValueError("quote identity does not match instrument_uid")
        if self.liquidity.instrument_key != expected_key:
            raise ValueError("liquidity identity does not match instrument_uid")
        for uid in (
            self.exposure.instrument_uid,
            self.cost_basis.instrument_uid,
            self.risk_screen.instrument_uid,
        ):
            if uid != self.instrument_uid:
                raise ValueError("candidate evidence identity mismatch")
        if self.quote.currency != self.liquidity.currency:
            raise ValueError("quote/liquidity currency mismatch")
        return self


class CandidateFactorGradesV1(ContractModel):
    role_fit: Grade
    diversification: Grade
    liquidity: Grade
    cost: Grade
    permanent_loss: Grade
    freshness: Grade

    def rank_points(self) -> int:
        return sum(
            int(getattr(self, name)) * weight
            for name, weight in CANDIDATE_FACTOR_WEIGHTS.items()
        )


class CandidateScoreV1(ContractModel):
    kind: CandidateKind
    candidate_id: Annotated[str, Field(min_length=3, max_length=256)]
    role: CandidateRole
    rank_points: RankPoints
    factors: CandidateFactorGradesV1
    instrument_uid: Annotated[str | None, Field(max_length=128)] = None
    ticker: Annotated[str | None, Field(max_length=32)] = None
    instrument_type: InstrumentType | None = None
    minimum_lot_cost: Money | None = None
    research_required: bool

    @model_validator(mode="after")
    def validate_score(self) -> CandidateScoreV1:
        if self.rank_points != self.factors.rank_points():
            raise ValueError("rank_points must reconcile to fixed ordinal factor weights")
        security_fields = (
            self.instrument_uid,
            self.instrument_type,
            self.minimum_lot_cost,
        )
        if self.kind is CandidateKind.SECURITY:
            if any(item is None for item in security_fields):
                raise ValueError(
                    "security score requires instrument identity and lot cost"
                )
            if not self.research_required:
                raise ValueError("security candidate must require deep research")
        else:
            if any(item is not None for item in (*security_fields, self.ticker)):
                raise ValueError("cash alternative cannot carry security fields")
            if self.research_required:
                raise ValueError("cash alternative cannot require security research")
        return self


class RejectedCandidateV1(ContractModel):
    instrument_uid: Annotated[str, Field(min_length=1, max_length=128)]
    ticker: Annotated[str | None, Field(max_length=32)] = None
    blockers: Annotated[tuple[CandidateBlockerCode, ...], Field(min_length=1)]
    rank_points: RankPoints | None = None

    @field_validator("blockers", mode="before")
    @classmethod
    def normalize_blockers(cls, value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("candidate blockers must be a collection")
        return tuple(sorted(set(value), key=str))


class CandidateFunnelResultV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    scoring_model: Literal["candidate_funnel_v1_ordinal_400"] = (
        "candidate_funnel_v1_ordinal_400"
    )
    assessed_at: datetime
    gap: PortfolioGapV1
    policy_reference: PolicyReferenceV1
    universe_sha256: Sha256
    ranked_alternatives: Annotated[tuple[CandidateScoreV1, ...], Field(min_length=1)]
    research_shortlist: tuple[CandidateScoreV1, ...] = ()
    rejected: tuple[RejectedCandidateV1, ...] = ()
    global_blockers: tuple[CandidateGlobalBlockerCode, ...] = ()
    funnel_sha256: Sha256
    decision_ready: bool
    trading_methods: Literal[False] = False

    @field_validator("assessed_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("assessed_at must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("global_blockers", mode="before")
    @classmethod
    def normalize_global_blockers(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("global blockers must be a collection")
        return tuple(sorted(set(value), key=str))

    @model_validator(mode="after")
    def validate_result(self) -> CandidateFunnelResultV1:
        cash_rows = [
            row
            for row in self.ranked_alternatives
            if row.kind is CandidateKind.NO_ACTION_CASH
        ]
        if len(cash_rows) != 1:
            raise ValueError("funnel requires exactly one NO_ACTION/CASH alternative")
        expected_ranked = tuple(
            sorted(
                self.ranked_alternatives,
                key=lambda row: (
                    -row.rank_points,
                    0 if row.kind is CandidateKind.NO_ACTION_CASH else 1,
                    row.candidate_id,
                ),
            )
        )
        if self.ranked_alternatives != expected_ranked:
            raise ValueError("ranked alternatives must use deterministic ordering")
        if len(self.research_shortlist) > self.gap.max_research_candidates:
            raise ValueError("research shortlist exceeds configured bound")
        if any(
            row.kind is not CandidateKind.SECURITY
            for row in self.research_shortlist
        ):
            raise ValueError("research shortlist may contain securities only")
        ranked_security_ids = {
            row.candidate_id
            for row in self.ranked_alternatives
            if row.kind is CandidateKind.SECURITY
        }
        if any(
            row.candidate_id not in ranked_security_ids
            for row in self.research_shortlist
        ):
            raise ValueError("research shortlist must come from ranked securities")
        if self.decision_ready != (not self.global_blockers):
            raise ValueError("decision_ready must match global blockers")
        if not self.decision_ready and self.research_shortlist:
            raise ValueError("blocked funnel cannot publish research shortlist")
        return self
