"""Read-only R4 adapter from durable portfolio evidence to balancing primitives."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, cast

from .balancing import (
    AllocationCap,
    BalancingPolicy,
    Candidate,
    Holding,
    RiskState,
    build_balancing_preview,
    screen_candidates,
)
from .intelligence import EVIDENCE_RETRIEVAL_MAX_AGE
from .portfolio_store import BalancingPolicyRecord, InvestmentProfileRecord

_RISK_STATES: set[str] = {
    "data_missing",
    "normal",
    "watch",
    "elevated",
    "critical",
    "confirmed_default",
}


def build_balancing_payload(
    *,
    profile: InvestmentProfileRecord | None,
    policy_record: BalancingPolicyRecord | None,
    context: dict[str, object] | None,
    now: datetime | None = None,
) -> dict[str, object]:
    """Build a fail-closed, non-executable preview from persisted evidence."""
    observed_at = (now or datetime.now(UTC)).astimezone(UTC)
    base: dict[str, object] = {
        "execution_enabled": False,
        "proposal_enabled": False,
        "stage": "r4_preview",
    }
    if profile is None:
        return {**base, "status": "profile_required"}
    if policy_record is None:
        return {
            **base,
            "status": "balancing_policy_required",
            "profile_version": profile.version,
        }
    if context is None:
        return {
            **base,
            "status": "snapshot_required",
            "profile_version": profile.version,
            "policy_version": policy_record.version,
        }

    captured_at = _datetime(context.get("captured_at"))
    if captured_at is None:
        return _blocked(base, profile, policy_record, "snapshot_time_missing")
    snapshot_age_seconds = int((observed_at - captured_at).total_seconds())
    if snapshot_age_seconds < 0:
        return _blocked(base, profile, policy_record, "snapshot_time_in_future")
    if snapshot_age_seconds > int(EVIDENCE_RETRIEVAL_MAX_AGE.total_seconds()):
        return {
            **_blocked(base, profile, policy_record, "snapshot_stale"),
            "snapshot_age_seconds": snapshot_age_seconds,
        }
    if context.get("analysis_status") != "observed":
        return _blocked(base, profile, policy_record, "snapshot_not_observed")
    if context.get("limits_loading_in_progress") is True:
        return _blocked(base, profile, policy_record, "broker_limits_loading")

    nav_rub = _decimal(context.get("nav_rub"))
    cash_rub = _decimal(context.get("rub_cash_unblocked"))
    if nav_rub is None or nav_rub <= 0:
        return _blocked(base, profile, policy_record, "nav_unavailable")
    if cash_rub is None or cash_rub < 0:
        return _blocked(base, profile, policy_record, "free_cash_unavailable")

    holdings_rows = _dict_rows(context.get("holdings"))
    candidate_rows = _dict_rows(context.get("candidates"))
    holdings = tuple(_holding(row) for row in holdings_rows)
    policy = _policy(profile, policy_record, nav_rub)
    candidates = tuple(
        _candidate(
            row,
            context=context,
            policy=policy,
            observed_at=observed_at,
        )
        for row in candidate_rows
    )

    screened = screen_candidates(candidates, policy)
    preview = build_balancing_preview(
        nav_rub=nav_rub,
        cash_rub=cash_rub,
        holdings=holdings,
        candidates=candidates,
        policy=policy,
    )
    screening = [
        {
            "instrument_uid": item.candidate.instrument_uid,
            "ticker": item.candidate.ticker,
            "asset_class": item.candidate.asset_class,
            "eligible": item.eligible,
            "reasons": list(item.reasons),
            "rating_bucket": item.candidate.rating_bucket,
            "risk_state": item.candidate.risk_state,
        }
        for item in screened
    ]
    eligible_count = sum(1 for item in screened if item.eligible)
    blockers = sorted(
        {
            reason
            for item in screened
            if not item.eligible
            for reason in item.reasons
        }
    )
    return {
        **base,
        "status": "observed",
        "profile_version": profile.version,
        "policy_version": policy_record.version,
        "snapshot_id": str(context.get("snapshot_id") or ""),
        "captured_at": captured_at,
        "snapshot_age_seconds": snapshot_age_seconds,
        "nav_rub": str(nav_rub),
        "free_cash_rub": str(cash_rub),
        "candidate_count": len(screened),
        "eligible_candidate_count": eligible_count,
        "screening_blockers": blockers,
        "screening": screening,
        "scenarios": _serialize(asdict(preview)),
    }


def _blocked(
    base: dict[str, object],
    profile: InvestmentProfileRecord,
    policy: BalancingPolicyRecord,
    reason: str,
) -> dict[str, object]:
    return {
        **base,
        "status": "blocked",
        "reason": reason,
        "profile_version": profile.version,
        "policy_version": policy.version,
    }


def _policy(
    profile: InvestmentProfileRecord,
    record: BalancingPolicyRecord,
    nav_rub: Decimal,
) -> BalancingPolicy:
    below_grade = (
        record.max_below_grade_percent
        if profile.allow_below_investment_grade
        else Decimal("0")
    )
    return BalancingPolicy(
        reserve_rub=profile.reserve_rub,
        planned_withdrawal_rub=profile.planned_withdrawal_rub,
        max_instrument_percent=record.max_instrument_percent,
        max_sector_percent=record.max_sector_percent,
        max_issuer_percent=record.max_issuer_percent,
        max_group_percent=record.max_group_percent,
        max_below_grade_percent=below_grade,
        max_unknown_percent=record.max_unknown_percent,
        max_liquidity_days=profile.liquidity_horizon_days,
        max_term_months=min(record.max_term_months, profile.horizon_months),
        turnover_budget_rub=(
            nav_rub * record.turnover_budget_percent / Decimal("100")
        ),
        no_trade_band_percent=record.no_trade_band_percent,
        min_replace_benefit_rub=record.min_replace_benefit_rub,
        allowed_asset_classes=("share", "bond", "etf"),
        allowed_currencies=("RUB",),
        allowed_risk_states=("normal",),
        asset_class_caps=(
            AllocationCap("share", record.max_share_percent),
            AllocationCap("bond", record.max_bond_percent),
            AllocationCap("etf", record.max_etf_percent),
        ),
        currency_caps=(AllocationCap("RUB", Decimal("100")),),
    )


def _holding(row: dict[str, object]) -> Holding:
    value = _decimal(row.get("value_rub")) or Decimal("0")
    quantity = _decimal(row.get("quantity")) or Decimal("0")
    lot = _integer(row.get("lot"))
    lots = 0
    quantity_misaligned = True
    if lot > 0 and quantity >= 0:
        raw_lots = quantity / Decimal(lot)
        integral = raw_lots.to_integral_value()
        if raw_lots == integral:
            lots = int(integral)
            quantity_misaligned = False

    risk = str(row.get("risk_state") or "data_missing")
    if risk not in _RISK_STATES:
        risk = "data_missing"
    rating_status = str(row.get("rating_status") or "data_missing")
    rating_bucket = "not_applicable" if rating_status == "not_applicable" else "unknown"
    issuer_id = str(row.get("issuer_id") or "") or "unknown_issuer"
    group_id = str(row.get("group_id") or "") or "unknown_group"
    blocked_lots = _decimal(row.get("blocked_lots")) or Decimal("0")
    return Holding(
        instrument_uid=str(row.get("instrument_uid") or ""),
        ticker=str(row.get("ticker") or ""),
        asset_class=str(row.get("instrument_type") or ""),
        sector=str(row.get("sector") or "") or "unknown_sector",
        issuer_id=issuer_id,
        group_id=group_id,
        rating_bucket=cast(Any, rating_bucket),
        currency=str(row.get("currency") or "").upper(),
        risk_state=cast(RiskState, risk),
        lots=lots,
        value_rub=value,
        expected_horizon_gain_rub=Decimal("0"),
        blocked=(
            row.get("blocked") is True
            or blocked_lots > 0
            or quantity_misaligned
        ),
        replacement_costs_complete=False,
    )


def _candidate(
    row: dict[str, object],
    *,
    context: dict[str, object],
    policy: BalancingPolicy,
    observed_at: datetime,
) -> Candidate:
    asset_class = str(row.get("instrument_type") or "")
    issuer_id = str(row.get("issuer_id") or "")
    group_id = str(row.get("group_id") or "")
    issuer_country = str(row.get("issuer_country_code") or "").upper()
    access_reasons: list[str] = []

    required_tests = row.get("required_tests")
    pending_tests = (
        tuple(str(item) for item in required_tests)
        if isinstance(required_tests, list)
        else ()
    )
    broker_user = context.get("broker_user")
    qualified = (
        broker_user.get("qualified")
        if isinstance(broker_user, dict)
        else None
    )
    account = context.get("account")
    account_type = (
        str(account.get("type") or "").upper()
        if isinstance(account, dict)
        else ""
    )

    if row.get("for_qual_investor") is True and qualified is not True:
        access_reasons.append("qualification_required")
    if "IIS" in account_type and row.get("for_iis") is not True:
        access_reasons.append("iis_not_allowed")
    if not issuer_id or issuer_country != "RU":
        access_reasons.append("issuer_identity_not_verified")
    if not group_id:
        access_reasons.append("issuer_group_not_verified")
    if asset_class == "etf":
        access_reasons.append("fund_look_through_missing")

    catalog_time = _datetime(row.get("provider_retrieved_at"))
    access_time = _datetime(row.get("access_observed_at"))
    if not _fresh(catalog_time, observed_at):
        access_reasons.append("catalog_stale")
    if not _fresh(access_time, observed_at):
        access_reasons.append("account_access_stale")
    access_reasons.append("candidate_risk_assessment_missing")
    access_reasons.append("quote_missing")
    if asset_class in {"share", "etf"}:
        access_reasons.append("expected_return_model_missing")
    if asset_class == "bond":
        access_reasons.append("bond_ytw_missing")
        access_reasons.append("bond_duration_missing")

    maturity = _datetime(row.get("maturity_date"))
    term_months = _months_until(observed_at, maturity)
    structure_values = (
        row.get("floating_coupon"),
        row.get("perpetual"),
        row.get("amortization"),
        row.get("subordinated"),
    )
    structure_known = all(value is not None for value in structure_values)
    structure_supported = (
        structure_known
        and not any(value is True for value in structure_values)
    )
    if asset_class == "bond" and not structure_known:
        access_reasons.append("bond_structure_missing")

    liquidity_days: int | None = None
    if row.get("liquidity") is False:
        access_reasons.append("provider_liquidity_flag_false")
    elif row.get("liquidity") is None:
        access_reasons.append("provider_liquidity_flag_missing")

    rating_bucket = "unknown" if asset_class == "bond" else "not_applicable"
    risk_state: RiskState = "data_missing"
    evidence_complete = not any(
        reason in {
            "issuer_identity_not_verified",
            "issuer_group_not_verified",
            "fund_look_through_missing",
            "catalog_stale",
            "account_access_stale",
            "bond_structure_missing",
        }
        for reason in access_reasons
    )

    return Candidate(
        instrument_uid=str(row.get("instrument_uid") or ""),
        ticker=str(row.get("ticker") or ""),
        asset_class=asset_class,
        sector=str(row.get("sector") or "") or "unknown_sector",
        issuer_id=issuer_id or "unknown_issuer",
        group_id=group_id or "unknown_group",
        rating_bucket=cast(Any, rating_bucket),
        currency=str(row.get("currency") or "").upper(),
        risk_state=risk_state,
        lot_size=_integer(row.get("lot")),
        market_lot_cost_rub=Decimal("0"),
        accrued_coupon_rub_per_lot=Decimal("0"),
        buy_fee_rub_per_lot=Decimal("0"),
        spread_cost_rub_per_lot=Decimal("0"),
        expected_horizon_gain_rub_per_lot=Decimal("0"),
        uncertainty_haircut_rub_per_lot=Decimal("0"),
        credit_loss_rub_per_lot=Decimal("0"),
        liquidity_penalty_rub_per_lot=Decimal("0"),
        liquidity_days=liquidity_days,
        term_months=term_months,
        ytw_percent=None,
        duration_years=None,
        api_trade_available=row.get("api_trade_available") is True,
        buy_available=row.get("buy_available") is True,
        required_tests_passed=not pending_tests,
        evidence_complete=evidence_complete,
        structure_supported=(structure_supported if asset_class == "bond" else True),
        access_reasons=tuple(dict.fromkeys(access_reasons)),
    )


def _fresh(value: datetime | None, now: datetime) -> bool:
    if value is None or value > now:
        return False
    return now - value <= EVIDENCE_RETRIEVAL_MAX_AGE


def _months_until(now: datetime, maturity: datetime | None) -> int | None:
    if maturity is None:
        return None
    if maturity <= now:
        return 0
    months = (maturity.year - now.year) * 12 + maturity.month - now.month
    if maturity.day > now.day:
        months += 1
    return max(0, months)


def _datetime(value: object) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    return value.astimezone(UTC)


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def _integer(value: object) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _dict_rows(value: object) -> tuple[dict[str, object], ...]:
    if not isinstance(value, list):
        return ()
    result: list[dict[str, object]] = []
    for item in value:
        if isinstance(item, dict):
            result.append(dict(cast(dict[str, object], item)))
    return tuple(result)


def _serialize(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize(item) for item in value]
    return value
