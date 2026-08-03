from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from typing import Iterable

from omni_cio.contracts.v1.candidate_funnel import (
    CandidateBlockerCode,
    CandidateCostBasisV1,
    CandidateEvidenceV1,
    CandidateFactorGradesV1,
    CandidateFunnelResultV1,
    CandidateGlobalBlockerCode,
    CandidateKind,
    CandidatePriceBasis,
    CandidateRole,
    CandidateScoreV1,
    GapUrgency,
    PortfolioGapV1,
    PreliminaryLossStatus,
    RejectedCandidateV1,
)
from omni_cio.contracts.v1.common import Money
from omni_cio.contracts.v1.investment_policy import InvestmentPolicyStatementV1
from omni_cio.contracts.v1.market import SourceAuthority
from omni_cio.contracts.v1.portfolio import InstrumentType
from omni_cio.contracts.v1.universe import (
    MarketUniverseSnapshotV1,
    UniverseInstrumentV1,
)
from omni_cio.policy import assess_investment_policy, policy_reference


_TRUSTED_AUTHORITIES = {
    SourceAuthority.PRIMARY,
    SourceAuthority.OFFICIAL,
    SourceAuthority.REGULATED,
}
_MARKET_MAX_AGE_SECONDS = 300
_FUTURE_TOLERANCE_SECONDS = 60

_FACTOR_WEIGHTS = {
    "role_fit": 25,
    "diversification": 20,
    "liquidity": 20,
    "cost": 15,
    "permanent_loss": 10,
    "freshness": 10,
}


class CandidateFunnelEvaluationError(ValueError):
    """The funnel cannot be evaluated safely from the supplied snapshots."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise CandidateFunnelEvaluationError(
            "CANDIDATE_FUNNEL_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _append_unique[T](target: list[T], value: T) -> None:
    if value not in target:
        target.append(value)


def _market_code(row: UniverseInstrumentV1) -> str | None:
    raw = row.real_exchange or row.exchange
    if not raw:
        return None
    value = raw.strip().upper()
    prefix = "REAL_EXCHANGE_"
    return value[len(prefix) :] if value.startswith(prefix) else value


def _role_fit_grade(role: CandidateRole, instrument_type: InstrumentType) -> int | None:
    mapping: dict[CandidateRole, dict[InstrumentType, int]] = {
        CandidateRole.LIQUIDITY_RESERVE: {
            InstrumentType.ETF: 3,
            InstrumentType.BOND: 2,
        },
        CandidateRole.DEFENSIVE_BOND: {
            InstrumentType.BOND: 4,
        },
        CandidateRole.INCOME: {
            InstrumentType.BOND: 4,
            InstrumentType.ETF: 3,
            InstrumentType.SHARE: 2,
        },
        CandidateRole.EQUITY_GROWTH: {
            InstrumentType.SHARE: 4,
            InstrumentType.ETF: 3,
        },
        CandidateRole.DIVERSIFICATION: {
            InstrumentType.ETF: 4,
            InstrumentType.SHARE: 3,
            InstrumentType.BOND: 3,
        },
    }
    return mapping[role].get(instrument_type)


def _static_blockers(
    *,
    row: UniverseInstrumentV1,
    gap: PortfolioGapV1,
    policy: InvestmentPolicyStatementV1,
) -> tuple[CandidateBlockerCode, ...]:
    blockers: list[CandidateBlockerCode] = []
    instrument_type = row.identity.instrument_type
    market = _market_code(row)

    if _role_fit_grade(gap.role, instrument_type) is None:
        blockers.append(CandidateBlockerCode.ROLE_MISMATCH)
    if (
        policy.allowed_instrument_types
        and instrument_type not in policy.allowed_instrument_types
    ):
        blockers.append(CandidateBlockerCode.POLICY_INSTRUMENT_NOT_ALLOWED)
    if instrument_type in policy.prohibited_instrument_types:
        blockers.append(CandidateBlockerCode.POLICY_INSTRUMENT_PROHIBITED)
    if policy.allowed_markets and (market is None or market not in policy.allowed_markets):
        blockers.append(CandidateBlockerCode.POLICY_MARKET_NOT_ALLOWED)
    if market is not None and market in policy.prohibited_markets:
        blockers.append(CandidateBlockerCode.POLICY_MARKET_PROHIBITED)
    if row.identity.currency != gap.target_currency:
        blockers.append(CandidateBlockerCode.TARGET_CURRENCY_MISMATCH)
    if row.liquidity_sufficient is False:
        blockers.append(CandidateBlockerCode.LIQUIDITY_FLAG_INSUFFICIENT)
    return tuple(sorted(set(blockers), key=str))


def _cash_score(gap: PortfolioGapV1) -> CandidateScoreV1:
    role_grade = {
        GapUrgency.LOW: 4,
        GapUrgency.NORMAL: 3,
        GapUrgency.HIGH: 1,
    }[gap.urgency]
    factors = CandidateFactorGradesV1(
        role_fit=role_grade,
        diversification=3,
        liquidity=4,
        cost=4,
        permanent_loss=4,
        freshness=4,
    )
    return CandidateScoreV1(
        kind=CandidateKind.NO_ACTION_CASH,
        candidate_id="cash:no_action",
        role=gap.role,
        rank_points=_rank_points(factors),
        factors=factors,
        research_required=False,
    )


def _rank_points(factors: CandidateFactorGradesV1) -> int:
    return sum(
        int(getattr(factors, name)) * weight
        for name, weight in _FACTOR_WEIGHTS.items()
    )


def _freshness_grade(
    evidence: CandidateEvidenceV1,
    *,
    assessed_at: datetime,
) -> tuple[int | None, tuple[CandidateBlockerCode, ...]]:
    ages = [
        (assessed_at - evidence.quote.as_of).total_seconds(),
        (assessed_at - evidence.liquidity.as_of).total_seconds(),
    ]
    blockers: list[CandidateBlockerCode] = []
    if any(age < -_FUTURE_TOLERANCE_SECONDS for age in ages):
        blockers.append(CandidateBlockerCode.MARKET_FUTURE_TIMESTAMP)
    if any(age > _MARKET_MAX_AGE_SECONDS for age in ages):
        blockers.append(CandidateBlockerCode.MARKET_STALE)
    if blockers:
        return None, tuple(sorted(set(blockers), key=str))

    age = max(max(ages), Decimal("0"))
    if age <= 30:
        return 4, ()
    if age <= 60:
        return 3, ()
    if age <= 180:
        return 2, ()
    return 1, ()


def _minimum_lot_cost(
    *,
    row: UniverseInstrumentV1,
    evidence: CandidateEvidenceV1,
) -> tuple[Money | None, CandidateBlockerCode | None]:
    ask = evidence.liquidity.best_ask
    lot = Decimal(row.identity.lot)
    currency = evidence.liquidity.currency
    basis = evidence.cost_basis

    if row.identity.instrument_type is InstrumentType.BOND:
        if basis.price_basis is not CandidatePriceBasis.PERCENT_OF_NOMINAL:
            return None, CandidateBlockerCode.COST_BASIS_INVALID
        if basis.nominal is None or basis.nominal.currency != currency:
            return None, CandidateBlockerCode.COST_BASIS_INVALID
        accrued = basis.accrued_interest_per_unit
        if accrued is not None and accrued.currency != currency:
            return None, CandidateBlockerCode.COST_BASIS_INVALID
        accrued_amount = accrued.amount if accrued is not None else Decimal("0")
        per_unit = ask / Decimal("100") * basis.nominal.amount + accrued_amount
        return Money(amount=per_unit * lot, currency=currency), None

    if basis.price_basis is not CandidatePriceBasis.CURRENCY:
        return None, CandidateBlockerCode.COST_BASIS_INVALID
    return Money(amount=ask * lot, currency=currency), None


def _liquidity_grade(spread_bps: Decimal) -> int:
    if spread_bps <= Decimal("10"):
        return 4
    if spread_bps <= Decimal("25"):
        return 3
    if spread_bps <= Decimal("50"):
        return 2
    if spread_bps <= Decimal("100"):
        return 1
    return 0


def _cost_grade(minimum_lot_cost: Money, gap: PortfolioGapV1) -> int:
    if gap.budget is None:
        return 2
    ratio = minimum_lot_cost.amount / gap.budget.amount
    if ratio <= Decimal("0.05"):
        return 4
    if ratio <= Decimal("0.10"):
        return 3
    if ratio <= Decimal("0.25"):
        return 2
    if ratio <= Decimal("0.50"):
        return 1
    return 0


def _permanent_loss_grade(status: PreliminaryLossStatus) -> int:
    return {
        PreliminaryLossStatus.PASS: 4,
        PreliminaryLossStatus.WATCH: 2,
        PreliminaryLossStatus.UNKNOWN: 1,
        PreliminaryLossStatus.BLOCK: 0,
    }[status]


def _headroom_grade(
    *,
    minimum_lot_cost: Money,
    evidence: CandidateEvidenceV1,
    policy: InvestmentPolicyStatementV1,
) -> tuple[int | None, tuple[CandidateBlockerCode, ...]]:
    exposure = evidence.exposure
    if exposure.portfolio_value.currency != minimum_lot_cost.currency:
        return None, (CandidateBlockerCode.PORTFOLIO_VALUE_CURRENCY_MISMATCH,)

    delta = minimum_lot_cost.amount / exposure.portfolio_value.amount
    checks = (
        (
            exposure.current_position_weight,
            policy.max_position_weight,
            CandidateBlockerCode.POSITION_LIMIT,
        ),
        (
            exposure.current_group_weight,
            policy.max_group_weight,
            CandidateBlockerCode.GROUP_LIMIT,
        ),
        (
            exposure.current_sector_weight,
            policy.max_sector_weight,
            CandidateBlockerCode.SECTOR_LIMIT,
        ),
        (
            exposure.current_currency_weight,
            policy.max_currency_weight,
            CandidateBlockerCode.CURRENCY_LIMIT,
        ),
    )
    blockers: list[CandidateBlockerCode] = []
    ratios: list[Decimal] = []
    for current, limit, blocker in checks:
        if limit is None or limit <= 0:
            blockers.append(blocker)
            continue
        projected = current + delta
        if projected > limit:
            blockers.append(blocker)
            continue
        ratios.append((limit - projected) / limit)

    if blockers:
        return None, tuple(sorted(set(blockers), key=str))
    worst = min(ratios)
    if worst >= Decimal("0.50"):
        return 4, ()
    if worst >= Decimal("0.25"):
        return 3, ()
    if worst >= Decimal("0.10"):
        return 2, ()
    if worst > 0:
        return 1, ()
    return 0, ()


def _market_trusted(evidence: CandidateEvidenceV1) -> bool:
    return (
        evidence.quote.source.authority in _TRUSTED_AUTHORITIES
        and evidence.liquidity.source.authority in _TRUSTED_AUTHORITIES
    )


def _evaluate_security(
    *,
    row: UniverseInstrumentV1,
    evidence: CandidateEvidenceV1,
    gap: PortfolioGapV1,
    policy: InvestmentPolicyStatementV1,
    assessed_at: datetime,
) -> tuple[CandidateScoreV1 | None, tuple[CandidateBlockerCode, ...]]:
    blockers: list[CandidateBlockerCode] = []
    role_grade = _role_fit_grade(gap.role, row.identity.instrument_type)
    if role_grade is None:
        blockers.append(CandidateBlockerCode.ROLE_MISMATCH)

    if evidence.instrument_uid != row.identity.uid:
        blockers.append(CandidateBlockerCode.MARKET_IDENTITY_MISMATCH)
    if evidence.quote.currency != row.identity.currency:
        blockers.append(CandidateBlockerCode.TARGET_CURRENCY_MISMATCH)
    if not _market_trusted(evidence):
        blockers.append(CandidateBlockerCode.MARKET_SOURCE_UNTRUSTED)

    freshness_grade, freshness_blockers = _freshness_grade(
        evidence,
        assessed_at=assessed_at,
    )
    blockers.extend(freshness_blockers)

    minimum_lot_cost, cost_blocker = _minimum_lot_cost(row=row, evidence=evidence)
    if cost_blocker is not None:
        blockers.append(cost_blocker)
    if minimum_lot_cost is not None:
        if minimum_lot_cost.currency != gap.target_currency:
            blockers.append(CandidateBlockerCode.TARGET_CURRENCY_MISMATCH)
        if gap.budget is not None:
            if gap.budget.currency != minimum_lot_cost.currency:
                blockers.append(CandidateBlockerCode.BUDGET_CURRENCY_MISMATCH)
            elif minimum_lot_cost.amount > gap.budget.amount:
                blockers.append(CandidateBlockerCode.UNAFFORDABLE_MIN_LOT)

    if evidence.risk_screen.status is PreliminaryLossStatus.BLOCK:
        blockers.append(CandidateBlockerCode.PERMANENT_LOSS_BLOCKED)

    diversification_grade: int | None = None
    if minimum_lot_cost is not None:
        diversification_grade, exposure_blockers = _headroom_grade(
            minimum_lot_cost=minimum_lot_cost,
            evidence=evidence,
            policy=policy,
        )
        blockers.extend(exposure_blockers)

    if blockers:
        return None, tuple(sorted(set(blockers), key=str))
    if (
        role_grade is None
        or freshness_grade is None
        or minimum_lot_cost is None
        or diversification_grade is None
    ):
        return None, (CandidateBlockerCode.EVALUATION_INCOMPLETE,)

    factors = CandidateFactorGradesV1(
        role_fit=role_grade,
        diversification=diversification_grade,
        liquidity=_liquidity_grade(evidence.liquidity.spread_bps),
        cost=_cost_grade(minimum_lot_cost, gap),
        permanent_loss=_permanent_loss_grade(evidence.risk_screen.status),
        freshness=freshness_grade,
    )
    return (
        CandidateScoreV1(
            kind=CandidateKind.SECURITY,
            candidate_id=f"uid:{row.identity.uid}",
            role=gap.role,
            rank_points=_rank_points(factors),
            factors=factors,
            instrument_uid=row.identity.uid,
            ticker=row.identity.ticker,
            instrument_type=row.identity.instrument_type,
            minimum_lot_cost=minimum_lot_cost,
            research_required=True,
        ),
        (),
    )


def _rank_key(row: CandidateScoreV1) -> tuple[int, int, str]:
    cash_tie_priority = 0 if row.kind is CandidateKind.NO_ACTION_CASH else 1
    return (-row.rank_points, cash_tie_priority, row.candidate_id)


def _result_fingerprint(
    *,
    assessed_at: datetime,
    gap: PortfolioGapV1,
    policy_reference_payload: object,
    universe_sha256: str,
    ranked: tuple[CandidateScoreV1, ...],
    shortlist: tuple[CandidateScoreV1, ...],
    rejected: tuple[RejectedCandidateV1, ...],
    global_blockers: tuple[CandidateGlobalBlockerCode, ...],
) -> str:
    payload = {
        "assessed_at": assessed_at.isoformat(),
        "gap": gap.model_dump(mode="json"),
        "policy_reference": policy_reference_payload,
        "universe_sha256": universe_sha256,
        "ranked_alternatives": [row.model_dump(mode="json") for row in ranked],
        "research_shortlist": [row.model_dump(mode="json") for row in shortlist],
        "rejected": [row.model_dump(mode="json") for row in rejected],
        "global_blockers": [row.value for row in global_blockers],
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _blocked_result(
    *,
    assessed_at: datetime,
    gap: PortfolioGapV1,
    policy: InvestmentPolicyStatementV1,
    universe: MarketUniverseSnapshotV1,
    blockers: Iterable[CandidateGlobalBlockerCode],
    rejected: tuple[RejectedCandidateV1, ...],
) -> CandidateFunnelResultV1:
    reference = policy_reference(policy)
    global_blockers = tuple(sorted(set(blockers), key=str))
    ranked = (_cash_score(gap),)
    fingerprint = _result_fingerprint(
        assessed_at=assessed_at,
        gap=gap,
        policy_reference_payload=reference.model_dump(mode="json"),
        universe_sha256=universe.content_sha256,
        ranked=ranked,
        shortlist=(),
        rejected=rejected,
        global_blockers=global_blockers,
    )
    return CandidateFunnelResultV1(
        assessed_at=assessed_at,
        gap=gap,
        policy_reference=reference,
        universe_sha256=universe.content_sha256,
        ranked_alternatives=ranked,
        research_shortlist=(),
        rejected=rejected,
        global_blockers=global_blockers,
        funnel_sha256=fingerprint,
        decision_ready=False,
    )


def build_candidate_funnel(
    *,
    gap: PortfolioGapV1,
    policy: InvestmentPolicyStatementV1,
    universe: MarketUniverseSnapshotV1,
    evidence: tuple[CandidateEvidenceV1, ...],
    assessed_at: datetime | None = None,
) -> CandidateFunnelResultV1:
    """Create a reproducible shortlist with blockers before ordinal scoring."""

    now = _aware_utc(assessed_at)
    policy_assessment = assess_investment_policy(policy, assessed_at=now)
    global_blockers: list[CandidateGlobalBlockerCode] = []
    if not policy_assessment.ready_for_personal_sizing:
        global_blockers.append(CandidateGlobalBlockerCode.IPS_NOT_READY)
    if not universe.decision_ready:
        global_blockers.append(CandidateGlobalBlockerCode.UNIVERSE_NOT_READY)

    if global_blockers:
        rejected = tuple(
            RejectedCandidateV1(
                instrument_uid=row.identity.uid or "missing-uid",
                ticker=row.identity.ticker,
                blockers=(CandidateBlockerCode.EVALUATION_INCOMPLETE,),
            )
            for row in sorted(
                universe.instruments,
                key=lambda item: (item.identity.uid or "", item.identity.ticker or ""),
            )
        )
        return _blocked_result(
            assessed_at=now,
            gap=gap,
            policy=policy,
            universe=universe,
            blockers=global_blockers,
            rejected=rejected,
        )

    rejected: list[RejectedCandidateV1] = []
    eligible: list[UniverseInstrumentV1] = []
    for row in universe.instruments:
        blockers = _static_blockers(row=row, gap=gap, policy=policy)
        if blockers:
            rejected.append(
                RejectedCandidateV1(
                    instrument_uid=row.identity.uid or "missing-uid",
                    ticker=row.identity.ticker,
                    blockers=blockers,
                )
            )
        else:
            eligible.append(row)

    evidence_by_uid: dict[str, list[CandidateEvidenceV1]] = defaultdict(list)
    for item in evidence:
        evidence_by_uid[item.instrument_uid].append(item)
    if any(len(items) > 1 for items in evidence_by_uid.values()):
        global_blockers.append(CandidateGlobalBlockerCode.DUPLICATE_EVIDENCE)

    missing_evidence_uids = {
        row.identity.uid
        for row in eligible
        if row.identity.uid and len(evidence_by_uid.get(row.identity.uid, ())) != 1
    }
    if missing_evidence_uids:
        global_blockers.append(
            CandidateGlobalBlockerCode.EVIDENCE_COVERAGE_INCOMPLETE
        )
        rejected.extend(
            RejectedCandidateV1(
                instrument_uid=row.identity.uid or "missing-uid",
                ticker=row.identity.ticker,
                blockers=(CandidateBlockerCode.MARKET_EVIDENCE_MISSING,),
            )
            for row in eligible
            if row.identity.uid in missing_evidence_uids
        )

    if global_blockers:
        return _blocked_result(
            assessed_at=now,
            gap=gap,
            policy=policy,
            universe=universe,
            blockers=global_blockers,
            rejected=tuple(
                sorted(rejected, key=lambda item: (item.instrument_uid, item.ticker or ""))
            ),
        )

    scored: list[CandidateScoreV1] = []
    for row in eligible:
        uid = row.identity.uid
        if uid is None:
            continue
        score, blockers = _evaluate_security(
            row=row,
            evidence=evidence_by_uid[uid][0],
            gap=gap,
            policy=policy,
            assessed_at=now,
        )
        if blockers:
            rejected.append(
                RejectedCandidateV1(
                    instrument_uid=uid,
                    ticker=row.identity.ticker,
                    blockers=blockers,
                )
            )
        elif score is not None:
            scored.append(score)

    ranked = tuple(sorted((*scored, _cash_score(gap)), key=_rank_key))
    security_ranked = tuple(
        row for row in ranked if row.kind is CandidateKind.SECURITY
    )
    shortlist = security_ranked[: gap.max_research_candidates]
    rejected_tuple = tuple(
        sorted(rejected, key=lambda item: (item.instrument_uid, item.ticker or ""))
    )
    reference = policy_assessment.reference
    fingerprint = _result_fingerprint(
        assessed_at=now,
        gap=gap,
        policy_reference_payload=reference.model_dump(mode="json"),
        universe_sha256=universe.content_sha256,
        ranked=ranked,
        shortlist=shortlist,
        rejected=rejected_tuple,
        global_blockers=(),
    )
    return CandidateFunnelResultV1(
        assessed_at=now,
        gap=gap,
        policy_reference=reference,
        universe_sha256=universe.content_sha256,
        ranked_alternatives=ranked,
        research_shortlist=shortlist,
        rejected=rejected_tuple,
        global_blockers=(),
        funnel_sha256=fingerprint,
        decision_ready=True,
    )
