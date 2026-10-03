"""Read-only R4 adapter from durable portfolio evidence to balancing primitives."""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, InvalidOperation
from typing import Any, cast
from uuid import UUID

from .balancing import (
    AllocationCap,
    BalancingPolicy,
    BalancingPreview,
    BalancingScenario,
    Candidate,
    Holding,
    PlannedTrade,
    RatingBucket,
    RiskState,
    build_balancing_preview,
    screen_candidates,
)
from .broker import BrokerConnectionError, BrokerService
from .intelligence import (
    EVIDENCE_RETRIEVAL_MAX_AGE,
    assess_candidate_fundamental_risk,
)
from .portfolio_store import BalancingPolicyRecord, InvestmentProfileRecord
from .tbank import (
    TBankAssetFundamental,
    TBankBondCoupon,
    TBankHistoricCandle,
    TBankInstrumentMetadata,
    TBankLastPrice,
    TBankMoney,
    TBankRating,
    TBankUnavailable,
)

LIVE_CANDIDATE_LIMIT = 4
MARKET_QUOTE_MAX_AGE = timedelta(minutes=15)
TBANK_LIQUIDITY_WINDOW_DAYS = 45
TBANK_LIQUIDITY_MIN_COMPLETED_DAYS = 10
_YIELD_YEAR_SECONDS = Decimal("31557600")
_YIELD_RATE_FLOOR = Decimal("-0.95")
_YIELD_RATE_INITIAL_CEILING = Decimal("1")
_YIELD_RATE_MAX_CEILING = Decimal("100")

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
    holdings_override: tuple[Holding, ...] | None = None,
    candidates_override: tuple[Candidate, ...] | None = None,
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
    holdings = (
        holdings_override
        if holdings_override is not None
        else tuple(_holding(row) for row in holdings_rows)
    )
    policy = _policy(profile, policy_record, nav_rub)
    candidates = (
        candidates_override
        if candidates_override is not None
        else tuple(
            _candidate(
                row,
                context=context,
                policy=policy,
                observed_at=observed_at,
            )
            for row in candidate_rows
        )
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
            "notes": list(item.candidate.notes),
            "rating_bucket": item.candidate.rating_bucket,
            "risk_state": item.candidate.risk_state,
            "ytw_percent": (
                str(item.candidate.ytw_percent)
                if item.candidate.ytw_percent is not None
                else None
            ),
            "duration_years": (
                str(item.candidate.duration_years)
                if item.candidate.duration_years is not None
                else None
            ),
            "liquidity_days": item.candidate.liquidity_days,
            "max_liquid_lots": item.candidate.max_liquid_lots,
            "transaction_cost_rub_per_lot": str(
                item.candidate.market_lot_cost_rub
                + item.candidate.accrued_coupon_rub_per_lot
                + item.candidate.buy_fee_rub_per_lot
                + item.candidate.spread_cost_rub_per_lot
            ),
            "expected_net_gain_rub_per_lot": str(
                item.candidate.expected_horizon_gain_rub_per_lot
                - item.candidate.buy_fee_rub_per_lot
                - item.candidate.spread_cost_rub_per_lot
                - item.candidate.uncertainty_haircut_rub_per_lot
                - item.candidate.credit_loss_rub_per_lot
                - item.candidate.liquidity_penalty_rub_per_lot
            ),
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
        "account_id": str(context.get("account_id") or ""),
        "captured_at": captured_at,
        "snapshot_age_seconds": snapshot_age_seconds,
        "nav_rub": str(nav_rub),
        "free_cash_rub": str(cash_rub),
        "constraints": _serialize(
            _proposal_constraints(
                profile,
                policy_record,
                policy,
            )
        ),
        "candidate_count": len(screened),
        "eligible_candidate_count": eligible_count,
        "screening_blockers": blockers,
        "screening": screening,
        "scenarios": _scenario_payloads(
            preview,
            nav_rub=nav_rub,
            cash_rub=cash_rub,
            holdings=holdings,
            candidates=candidates,
        ),
    }


def build_live_balancing_payload(
    *,
    user_id: UUID,
    profile: InvestmentProfileRecord | None,
    policy_record: BalancingPolicyRecord | None,
    context: dict[str, object] | None,
    broker: BrokerService,
    now: datetime | None = None,
) -> dict[str, object]:
    """Enrich a bounded bond shortlist with read-only T-Invest evidence."""
    observed_at = (now or datetime.now(UTC)).astimezone(UTC)
    durable = build_balancing_payload(
        profile=profile,
        policy_record=policy_record,
        context=context,
        now=observed_at,
    )
    if (
        durable.get("status") != "observed"
        or profile is None
        or policy_record is None
        or context is None
    ):
        return {**durable, "live_status": "not_applicable"}

    rows = _dict_rows(context.get("candidates"))
    prefiltered = tuple(
        row
        for row in rows
        if _eligible_for_live_enrichment(row, context, observed_at)
    )
    if not prefiltered:
        return {
            **durable,
            "live_status": "no_prefilter_candidates",
            "live_candidate_count": 0,
        }

    try:
        shortlist_yields = broker.candidate_market_yields(
            user_id,
            tuple(
                str(row["instrument_uid"])
                for row in prefiltered[:100]
            ),
        )
    except (BrokerConnectionError, TBankUnavailable, ValueError):
        return {
            **durable,
            "live_status": "degraded",
            "live_reason": "tbank_shortlist_signal_unavailable",
            "live_candidate_count": 0,
        }

    yield_by_uid = {
        item.instrument_uid: item
        for item in shortlist_yields
        if _fresh_market_time(item.time, observed_at)
        and (_decimal(item.yield_percent) or Decimal("0")) > 0
    }
    ranked = sorted(
        (
            (
                _decimal(yield_by_uid[str(row["instrument_uid"])].yield_percent)
                or Decimal("0"),
                str(row["instrument_uid"]),
                row,
            )
            for row in prefiltered[:100]
            if str(row["instrument_uid"]) in yield_by_uid
        ),
        key=lambda item: (-item[0], item[1]),
    )
    selected = tuple(item[2] for item in ranked[:LIVE_CANDIDATE_LIMIT])
    if not selected:
        return {
            **durable,
            "live_status": "no_shortlist_signal",
            "live_candidate_count": 0,
        }

    try:
        fundamentals = broker.candidate_fundamentals(
            user_id,
            tuple(
                str(row.get("asset_uid") or "")
                for row in selected
                if row.get("asset_uid")
            ),
        )
        prices = broker.candidate_last_prices(
            user_id,
            tuple(str(row["instrument_uid"]) for row in selected),
        )
    except (BrokerConnectionError, TBankUnavailable, ValueError):
        return {
            **durable,
            "live_status": "degraded",
            "live_reason": "tbank_live_evidence_unavailable",
            "live_candidate_count": len(selected),
        }

    fundamental_by_asset = {
        item.asset_uid: item
        for item in fundamentals
    }
    price_by_uid = {
        item.instrument_uid: item
        for item in prices
    }
    selected_uids = {
        str(item.get("instrument_uid") or "")
        for item in selected
    }
    enriched: list[Candidate] = []
    live_sources: list[dict[str, object]] = []
    policy = _policy(
        profile,
        policy_record,
        _decimal(context.get("nav_rub")) or Decimal("0"),
    )

    for row in rows:
        uid = str(row.get("instrument_uid") or "")
        if uid not in selected_uids:
            enriched.append(
                _with_candidate_blocker(
                    _candidate(
                        row,
                        context=context,
                        policy=policy,
                        observed_at=observed_at,
                    ),
                    "live_enrichment_not_selected",
                )
            )
            continue
        try:
            candidate, sources = _enrich_bond_candidate(
                user_id=user_id,
                row=row,
                context=context,
                profile=profile,
                policy_record=policy_record,
                broker=broker,
                fundamental=fundamental_by_asset.get(
                    str(row.get("asset_uid") or "")
                ),
                last_price=price_by_uid.get(uid),
                observed_at=observed_at,
            )
        except (BrokerConnectionError, TBankUnavailable, ValueError):
            candidate = _with_candidate_blocker(
                _candidate(
                    row,
                    context=context,
                    policy=policy,
                    observed_at=observed_at,
                ),
                "live_candidate_evidence_unavailable",
            )
            sources = ()
        enriched.append(candidate)
        live_sources.extend(sources)

    payload = build_balancing_payload(
        profile=profile,
        policy_record=policy_record,
        context=context,
        now=observed_at,
        candidates_override=tuple(enriched),
    )
    payload["live_status"] = "received"
    payload["live_candidate_count"] = len(selected)
    payload["live_sources"] = _dedupe_sources(live_sources)
    payload["methodology"] = {
        "candidate_limit": LIVE_CANDIDATE_LIMIT,
        "shortlist_universe_limit": 100,
        "shortlist_signal": "tbank_market_yield_not_decision_metric",
        "decision_yield": "cashflow_ytm_equals_ytw_only_without_future_options",
        "market_quote_max_age_seconds": int(
            MARKET_QUOTE_MAX_AGE.total_seconds()
        ),
        "liquidity_window_days": TBANK_LIQUIDITY_WINDOW_DAYS,
        "liquidity_min_completed_days": TBANK_LIQUIDITY_MIN_COMPLETED_DAYS,
        "liquidity_source": "tbank_exchange_daily_candles",
        "tax_rate_percent": str(policy_record.securities_tax_rate_percent),
        "max_daily_turnover_participation_percent": str(
            policy_record.max_daily_turnover_participation_percent
        ),
        "execution_enabled": False,
    }
    return payload


def _eligible_for_live_enrichment(
    row: dict[str, object],
    context: dict[str, object],
    observed_at: datetime,
) -> bool:
    if str(row.get("instrument_type") or "") != "bond":
        return False
    if str(row.get("currency") or "").upper() != "RUB":
        return False
    if (
        row.get("api_trade_available") is not True
        or row.get("buy_available") is not True
    ):
        return False
    if _integer(row.get("lot")) <= 0:
        return False
    if not str(row.get("instrument_uid") or ""):
        return False
    if (
        not str(row.get("issuer_id") or "")
        or str(row.get("issuer_country_code") or "").upper() != "RU"
        or not str(row.get("group_id") or "")
    ):
        return False
    nominal = _decimal(row.get("nominal_value"))
    if nominal is None or nominal <= 0:
        return False
    if str(row.get("nominal_currency") or "").upper() != "RUB":
        return False
    required_tests = row.get("required_tests")
    if isinstance(required_tests, list) and required_tests:
        return False
    broker_user = context.get("broker_user")
    qualified = (
        broker_user.get("qualified")
        if isinstance(broker_user, dict)
        else None
    )
    if row.get("for_qual_investor") is True and qualified is not True:
        return False
    account = context.get("account")
    account_type = (
        str(account.get("type") or "").upper()
        if isinstance(account, dict)
        else ""
    )
    if "IIS" in account_type and row.get("for_iis") is not True:
        return False
    if not _fresh(_datetime(row.get("provider_retrieved_at")), observed_at):
        return False
    if not _fresh(_datetime(row.get("access_observed_at")), observed_at):
        return False
    structure = (
        row.get("floating_coupon"),
        row.get("perpetual"),
        row.get("amortization"),
        row.get("subordinated"),
    )
    return all(value is False for value in structure)


def _with_candidate_blocker(candidate: Candidate, reason: str) -> Candidate:
    return replace(
        candidate,
        access_reasons=tuple(
            dict.fromkeys((*candidate.access_reasons, reason))
        ),
    )


def _enrich_bond_candidate(
    *,
    user_id: UUID,
    row: dict[str, object],
    context: dict[str, object],
    profile: InvestmentProfileRecord,
    policy_record: BalancingPolicyRecord,
    broker: BrokerService,
    fundamental: TBankAssetFundamental | None,
    last_price: TBankLastPrice | None,
    observed_at: datetime,
) -> tuple[Candidate, tuple[dict[str, object], ...]]:
    nav_rub = _decimal(context.get("nav_rub"))
    if nav_rub is None or nav_rub <= 0:
        raise ValueError("candidate NAV is unavailable")
    base = _candidate(
        row,
        context=context,
        policy=_policy(profile, policy_record, nav_rub),
        observed_at=observed_at,
    )
    if base.asset_class != "bond":
        return _with_candidate_blocker(
            base,
            "live_asset_class_not_supported",
        ), ()

    info = _metadata_from_row(row)
    if (
        not str(row.get("issuer_id") or "")
        or str(row.get("issuer_country_code") or "").upper() != "RU"
    ):
        return _with_candidate_blocker(
            base,
            "issuer_identity_not_verified",
        ), ()
    if not str(row.get("group_id") or ""):
        return _with_candidate_blocker(
            base,
            "issuer_group_not_verified",
        ), ()

    maturity = info.maturity_date
    nominal = info.nominal
    if (
        maturity is None
        or maturity <= observed_at
        or nominal is None
        or nominal.currency.upper() != "RUB"
        or base.lot_size <= 0
    ):
        return _with_candidate_blocker(base, "bond_term_missing"), ()
    nominal_per_bond = _money_rub(nominal)
    if nominal_per_bond <= 0:
        raise ValueError("bond nominal must be positive")

    assessment = assess_candidate_fundamental_risk(
        info,
        fundamental,
        assessed_at=observed_at,
    )
    ratings = broker.candidate_bond_ratings(
        user_id,
        base.instrument_uid,
    )
    rating_bucket, rating_notes, rating_under_watch = (
        _rating_bucket_from_tbank(
            ratings,
            observed_at=observed_at,
        )
    )
    if last_price is None or not _fresh_market_time(
        last_price.time,
        observed_at,
    ):
        return _with_candidate_blocker(base, "quote_missing"), ()

    order_book = broker.candidate_order_book(
        user_id,
        base.instrument_uid,
        depth=10,
    )
    if (
        not order_book.is_consistent
        or not order_book.asks
        or not order_book.bids
        or not _fresh_market_time(order_book.time, observed_at)
    ):
        return _with_candidate_blocker(base, "order_book_unusable"), ()
    best_ask = min(Decimal(level.price) for level in order_book.asks)
    best_bid = max(Decimal(level.price) for level in order_book.bids)
    if best_bid <= 0 or best_ask <= best_bid:
        return _with_candidate_blocker(base, "order_book_unusable"), ()

    ask_currency_per_bond = _bond_points_to_currency(
        best_ask,
        nominal_per_bond,
    )
    order_price = broker.candidate_order_price(
        user_id,
        base.instrument_uid,
        price=str(ask_currency_per_bond),
        direction="buy",
        quantity_lots=1,
    )
    initial = _money_rub(order_price.initial_order_amount)
    total = _money_rub(order_price.total_order_amount)
    fee = _money_rub(order_price.executed_commission_rub)
    aci = (
        _money_rub(order_price.bond_aci_value)
        if order_price.bond_aci_value
        else Decimal("0")
    )
    expected_total = initial + aci + fee
    tolerance = max(Decimal("0.05"), total * Decimal("0.0001"))
    if (
        initial <= 0
        or total <= 0
        or fee < 0
        or aci < 0
        or abs(total - expected_total) > tolerance
    ):
        raise ValueError("invalid T-Invest order price evidence")

    cashflow_to = maturity + timedelta(days=1)
    coupons = broker.candidate_bond_coupons(
        user_id,
        base.instrument_uid,
        from_at=observed_at,
        to_at=cashflow_to,
    )
    events = broker.candidate_bond_events(
        user_id,
        base.instrument_uid,
        from_at=observed_at,
        to_at=cashflow_to,
    )
    defaulted = any(
        event.default_date is not None
        and event.default_date <= observed_at
        for event in events
    )
    if defaulted:
        return _with_candidate_blocker(
            base,
            "candidate_confirmed_default",
        ), ()
    if any(
        event.event_type in {"EVENT_TYPE_CALL", "EVENT_TYPE_CONV"}
        and (event.event_date is None or event.event_date > observed_at)
        for event in events
    ):
        return _with_candidate_blocker(
            base,
            "bond_option_events_unsupported",
        ), ()

    cashflows = _fixed_bond_cashflows(
        coupons=coupons,
        maturity=maturity,
        nominal_per_bond=nominal_per_bond,
        lot_size=base.lot_size,
        observed_at=observed_at,
    )
    dirty_purchase = initial + aci
    ytw_percent = _yield_to_maturity_percent(
        dirty_purchase,
        cashflows,
        observed_at,
    )
    if ytw_percent is None or ytw_percent <= 0:
        return _with_candidate_blocker(base, "bond_ytw_missing"), ()
    duration_years = _macaulay_duration_years(
        dirty_purchase,
        cashflows,
        observed_at,
        ytw_percent,
    )
    if duration_years is None or duration_years <= 0:
        return _with_candidate_blocker(base, "bond_duration_missing"), ()

    candles_from = observed_at - timedelta(
        days=TBANK_LIQUIDITY_WINDOW_DAYS
    )
    candles = broker.candidate_daily_exchange_candles(
        user_id,
        base.instrument_uid,
        from_at=candles_from,
        to_at=observed_at,
    )
    average_daily_turnover = _average_bond_daily_turnover_rub(
        candles=candles,
        nominal_per_bond=nominal_per_bond,
        lot_size=base.lot_size,
        observed_at=observed_at,
    )
    if average_daily_turnover is None:
        return _with_candidate_blocker(
            base,
            "liquidity_evidence_missing",
        ), ()

    daily_capacity = (
        average_daily_turnover
        * policy_record.max_daily_turnover_participation_percent
        / Decimal("100")
    )
    if daily_capacity <= 0:
        return _with_candidate_blocker(base, "liquidity_limit"), ()
    liquidity_days = max(
        1,
        int(
            (total / daily_capacity).to_integral_value(
                rounding=ROUND_CEILING
            )
        ),
    )
    max_liquid_lots = int(
        (
            daily_capacity
            * Decimal(profile.liquidity_horizon_days)
            / total
        ).to_integral_value(rounding=ROUND_FLOOR)
    )

    term_months = _months_until(observed_at, maturity)
    if term_months is None or term_months <= 0:
        return _with_candidate_blocker(base, "bond_term_missing"), ()

    future_cash = sum((amount for _, amount in cashflows), Decimal("0"))
    gross_gain = future_cash - dirty_purchase
    uncertainty = (
        total * policy_record.uncertainty_haircut_percent / Decimal("100")
    )
    credit_loss = (
        total * policy_record.credit_loss_haircut_percent / Decimal("100")
    )

    removable = {
        "candidate_risk_assessment_missing",
        "quote_missing",
        "bond_ytw_missing",
        "bond_duration_missing",
        "provider_liquidity_flag_missing",
    }
    access_reasons = tuple(
        reason for reason in base.access_reasons if reason not in removable
    )
    notes = (
        "shortlisted_by_tbank_market_yield_signal",
        "issuer_identity_from_verified_mapping",
        *rating_notes,
        "issuer_group_from_verified_mapping",
        "buy_cost_from_tinvest_get_order_price",
        "ytw_from_tinvest_fixed_cashflows",
        "liquidity_from_tinvest_exchange_candles",
        "no_future_call_or_conversion_events",
        "expected_gain_from_contractual_cashflows",
        "tax_not_applied_to_new_buy",
    )
    risk_state: RiskState = assessment.state
    if rating_under_watch and risk_state == "normal":
        risk_state = "watch"
    evidence_complete = (
        assessment.fundamental_status == "received"
        and risk_state in {"normal", "watch", "elevated"}
        and not access_reasons
    )
    candidate = replace(
        base,
        rating_bucket=rating_bucket,
        risk_state=risk_state,
        market_lot_cost_rub=initial,
        accrued_coupon_rub_per_lot=aci,
        buy_fee_rub_per_lot=fee,
        spread_cost_rub_per_lot=Decimal("0"),
        expected_horizon_gain_rub_per_lot=gross_gain,
        uncertainty_haircut_rub_per_lot=uncertainty,
        credit_loss_rub_per_lot=credit_loss,
        liquidity_penalty_rub_per_lot=Decimal("0"),
        liquidity_days=liquidity_days,
        max_liquid_lots=max_liquid_lots,
        term_months=term_months,
        ytw_percent=ytw_percent,
        duration_years=duration_years,
        evidence_complete=evidence_complete,
        limit_price=best_ask,
        limit_price_type="point",
        access_reasons=access_reasons,
        notes=notes,
    )
    sources: tuple[dict[str, object], ...] = (
        {
            "id": f"tbank-last-price:{base.instrument_uid}",
            "provider": "tbank",
            "kind": "last_price",
            "retrieved_at": last_price.time,
        },
        {
            "id": f"tbank-order-book:{base.instrument_uid}",
            "provider": "tbank",
            "kind": "order_book",
            "retrieved_at": order_book.time,
        },
        {
            "id": f"tbank-order-price:{base.instrument_uid}",
            "provider": "tbank",
            "kind": "order_price",
            "retrieved_at": observed_at,
        },
        {
            "id": f"tbank-bond-ratings:{base.instrument_uid}",
            "provider": "tbank",
            "kind": "issuer_ratings",
            "retrieved_at": observed_at,
        },
        {
            "id": f"tbank-bond-cashflows:{base.instrument_uid}",
            "provider": "tbank",
            "kind": "bond_coupons_and_events",
            "retrieved_at": observed_at,
        },
        {
            "id": f"tbank-daily-candles:{base.instrument_uid}",
            "provider": "tbank",
            "kind": "exchange_daily_candles",
            "retrieved_at": observed_at,
        },
    )
    return candidate, sources


def _rating_bucket_from_tbank(
    ratings: tuple[TBankRating, ...],
    *,
    observed_at: datetime,
) -> tuple[RatingBucket, tuple[str, ...], bool]:
    if not ratings:
        return "unknown", ("issuer_rating_missing",), False

    buckets: list[RatingBucket] = []
    notes: list[str] = ["issuer_ratings_from_tinvest_bond_by"]
    under_watch = False
    for rating in ratings:
        rating_date = rating.rating_date.astimezone(UTC)
        if rating_date > observed_at:
            return (
                "unknown",
                tuple((*notes, "issuer_rating_time_invalid")),
                False,
            )
        bucket = _rating_level_bucket(rating.rating_level)
        if bucket is None:
            return (
                "unknown",
                tuple((*notes, "issuer_rating_level_unrecognized")),
                under_watch,
            )
        buckets.append(bucket)
        notes.append(
            "issuer_rating:"
            + rating.agency_name
            + ":"
            + rating.rating_level
            + ":"
            + rating_date.date().isoformat()
        )
        under_watch = under_watch or rating.is_under_watch

    order: dict[RatingBucket, int] = {
        "below_grade": 0,
        "bbb": 1,
        "a": 2,
        "aa": 3,
        "aaa": 4,
        "unknown": -1,
        "not_applicable": 5,
    }
    worst = min(buckets, key=lambda item: order[item])
    if under_watch:
        notes.append("issuer_rating_under_watch")
    return worst, tuple(notes), under_watch


def _rating_level_bucket(value: str) -> RatingBucket | None:
    letters = "".join(char for char in value.upper() if char.isalpha())
    if letters.startswith("RU"):
        letters = letters[2:]
    if letters.endswith("RU"):
        letters = letters[:-2]
    mapping: dict[str, RatingBucket] = {
        "AAA": "aaa",
        "AA": "aa",
        "A": "a",
        "BBB": "bbb",
        "BB": "below_grade",
        "B": "below_grade",
        "CCC": "below_grade",
        "CC": "below_grade",
        "C": "below_grade",
        "D": "below_grade",
    }
    return mapping.get(letters)


def _fixed_bond_cashflows(
    *,
    coupons: tuple[TBankBondCoupon, ...],
    maturity: datetime,
    nominal_per_bond: Decimal,
    lot_size: int,
    observed_at: datetime,
) -> tuple[tuple[datetime, Decimal], ...]:
    by_date: dict[datetime, Decimal] = {}
    for coupon in coupons:
        when = coupon.coupon_date.astimezone(UTC)
        if when <= observed_at or when > maturity:
            continue
        amount = _money_rub(coupon.pay_one_bond) * Decimal(lot_size)
        if amount < 0:
            raise ValueError("bond coupon must not be negative")
        by_date[when] = by_date.get(when, Decimal("0")) + amount
    maturity_utc = maturity.astimezone(UTC)
    redemption = nominal_per_bond * Decimal(lot_size)
    by_date[maturity_utc] = (
        by_date.get(maturity_utc, Decimal("0")) + redemption
    )
    result = tuple(
        (when, amount)
        for when, amount in sorted(by_date.items())
        if amount > 0
    )
    if not result:
        raise ValueError("bond cashflows are empty")
    return result


def _yield_to_maturity_percent(
    dirty_price: Decimal,
    cashflows: tuple[tuple[datetime, Decimal], ...],
    observed_at: datetime,
) -> Decimal | None:
    if dirty_price <= 0 or not cashflows:
        return None

    low = _YIELD_RATE_FLOOR
    high = _YIELD_RATE_INITIAL_CEILING
    low_value = _cashflow_npv(
        dirty_price,
        cashflows,
        observed_at,
        low,
    )
    high_value = _cashflow_npv(
        dirty_price,
        cashflows,
        observed_at,
        high,
    )
    while high_value > 0 and high < _YIELD_RATE_MAX_CEILING:
        high *= Decimal("2")
        high_value = _cashflow_npv(
            dirty_price,
            cashflows,
            observed_at,
            high,
        )
    if low_value < 0 or high_value > 0:
        return None

    for _ in range(96):
        middle = (low + high) / Decimal("2")
        value = _cashflow_npv(
            dirty_price,
            cashflows,
            observed_at,
            middle,
        )
        if abs(value) <= Decimal("0.0000001"):
            low = middle
            high = middle
            break
        if value > 0:
            low = middle
        else:
            high = middle
    rate = (low + high) / Decimal("2")
    return (rate * Decimal("100")).quantize(Decimal("0.0001"))


def _cashflow_npv(
    dirty_price: Decimal,
    cashflows: tuple[tuple[datetime, Decimal], ...],
    observed_at: datetime,
    annual_rate: Decimal,
) -> Decimal:
    base = Decimal("1") + annual_rate
    if base <= 0:
        raise ValueError("annual yield must be greater than -100%")
    total = -dirty_price
    for when, amount in cashflows:
        seconds = Decimal(str((when - observed_at).total_seconds()))
        if seconds <= 0:
            continue
        years = seconds / _YIELD_YEAR_SECONDS
        discount = (base.ln() * years).exp()
        total += amount / discount
    return total


def _macaulay_duration_years(
    dirty_price: Decimal,
    cashflows: tuple[tuple[datetime, Decimal], ...],
    observed_at: datetime,
    ytm_percent: Decimal,
) -> Decimal | None:
    rate = ytm_percent / Decimal("100")
    base = Decimal("1") + rate
    if dirty_price <= 0 or base <= 0:
        return None
    weighted = Decimal("0")
    present = Decimal("0")
    for when, amount in cashflows:
        seconds = Decimal(str((when - observed_at).total_seconds()))
        if seconds <= 0:
            continue
        years = seconds / _YIELD_YEAR_SECONDS
        value = amount / ((base.ln() * years).exp())
        present += value
        weighted += years * value
    if present <= 0:
        return None
    return (weighted / present).quantize(Decimal("0.0001"))


def _average_bond_daily_turnover_rub(
    *,
    candles: tuple[TBankHistoricCandle, ...],
    nominal_per_bond: Decimal,
    lot_size: int,
    observed_at: datetime,
) -> Decimal | None:
    completed = tuple(
        candle
        for candle in candles
        if candle.is_complete
        and candle.source == "CANDLE_SOURCE_EXCHANGE"
        and candle.time <= observed_at
    )
    if len(completed) < TBANK_LIQUIDITY_MIN_COMPLETED_DAYS:
        return None
    values = [
        (
            Decimal(candle.close)
            / Decimal("100")
            * nominal_per_bond
            * Decimal(lot_size)
            * Decimal(candle.volume_lots)
        )
        for candle in completed
    ]
    total = sum(values, Decimal("0"))
    if total <= 0:
        return None
    return total / Decimal(len(values))


def _metadata_from_row(row: dict[str, object]) -> TBankInstrumentMetadata:
    nominal_value = _decimal(row.get("nominal_value"))
    nominal_currency = str(row.get("nominal_currency") or "").upper()
    nominal = (
        TBankMoney(nominal_currency, str(nominal_value))
        if nominal_value is not None and nominal_currency
        else None
    )
    required_raw = row.get("required_tests")
    required_tests = (
        tuple(str(item) for item in required_raw)
        if isinstance(required_raw, list)
        else ()
    )
    return TBankInstrumentMetadata(
        uid=str(row.get("instrument_uid") or ""),
        figi=str(row.get("figi") or ""),
        asset_uid=str(row.get("asset_uid") or ""),
        position_uid="",
        name=str(row.get("name") or ""),
        ticker=str(row.get("ticker") or ""),
        isin=str(row.get("isin") or ""),
        instrument_type=str(row.get("instrument_type") or ""),
        currency=str(row.get("currency") or "").upper(),
        class_code=str(row.get("class_code") or ""),
        lot=_integer(row.get("lot")),
        sector=str(row.get("sector") or ""),
        country_of_risk=str(row.get("country_of_risk") or ""),
        for_qual_investor=cast(bool | None, row.get("for_qual_investor")),
        for_iis=cast(bool | None, row.get("for_iis")),
        api_trade_available=cast(bool | None, row.get("api_trade_available")),
        buy_available=cast(bool | None, row.get("buy_available")),
        sell_available=cast(bool | None, row.get("sell_available")),
        required_tests=required_tests,
        nominal=nominal,
        maturity_date=_datetime(row.get("maturity_date")),
        floating_coupon=cast(bool | None, row.get("floating_coupon")),
        perpetual=cast(bool | None, row.get("perpetual")),
        amortization=cast(bool | None, row.get("amortization")),
        subordinated=cast(bool | None, row.get("subordinated")),
        liquidity=cast(bool | None, row.get("liquidity")),
    )


def _fresh_market_time(value: datetime | None, now: datetime) -> bool:
    if value is None or value.tzinfo is None:
        return False
    normalized = value.astimezone(UTC)
    return normalized <= now and now - normalized <= MARKET_QUOTE_MAX_AGE


def _bond_points_to_currency(
    price_points: Decimal,
    nominal_per_bond: Decimal,
) -> Decimal:
    if (
        not price_points.is_finite()
        or price_points <= 0
        or not nominal_per_bond.is_finite()
        or nominal_per_bond <= 0
    ):
        raise ValueError("bond price conversion requires positive finite values")
    return price_points / Decimal("100") * nominal_per_bond


def _money_rub(value: TBankMoney) -> Decimal:
    if value.currency.upper() != "RUB":
        raise ValueError("R4 money evidence must be RUB")
    parsed = Decimal(value.value)
    if not parsed.is_finite():
        raise ValueError("R4 money evidence must be finite")
    return parsed


def _dedupe_sources(
    sources: list[dict[str, object]],
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    seen: set[str] = set()
    for source in sources:
        key = str(source.get("id") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(source)
    return result


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


def _proposal_constraints(
    profile: InvestmentProfileRecord,
    record: BalancingPolicyRecord,
    policy: BalancingPolicy,
) -> dict[str, object]:
    return {
        "reserve_rub": profile.reserve_rub,
        "planned_withdrawal_rub": profile.planned_withdrawal_rub,
        "horizon_months": profile.horizon_months,
        "max_drawdown_percent": profile.max_drawdown_percent,
        "liquidity_horizon_days": profile.liquidity_horizon_days,
        "allow_below_investment_grade": profile.allow_below_investment_grade,
        "max_instrument_percent": record.max_instrument_percent,
        "max_sector_percent": record.max_sector_percent,
        "max_issuer_percent": record.max_issuer_percent,
        "max_group_percent": record.max_group_percent,
        "max_share_percent": record.max_share_percent,
        "max_bond_percent": record.max_bond_percent,
        "max_etf_percent": record.max_etf_percent,
        "max_below_grade_percent": policy.max_below_grade_percent,
        "max_unknown_percent": record.max_unknown_percent,
        "max_term_months": policy.max_term_months,
        "turnover_budget_rub": policy.turnover_budget_rub,
        "turnover_budget_percent": record.turnover_budget_percent,
        "max_daily_turnover_participation_percent": (
            record.max_daily_turnover_participation_percent
        ),
        "securities_tax_rate_percent": record.securities_tax_rate_percent,
        "uncertainty_haircut_percent": record.uncertainty_haircut_percent,
        "credit_loss_haircut_percent": record.credit_loss_haircut_percent,
        "no_trade_band_percent": record.no_trade_band_percent,
        "min_replace_benefit_rub": record.min_replace_benefit_rub,
        "allowed_asset_classes": list(policy.allowed_asset_classes),
        "allowed_currencies": list(policy.allowed_currencies),
        "allowed_risk_states": list(policy.allowed_risk_states),
    }


def _scenario_payloads(
    preview: BalancingPreview,
    *,
    nav_rub: Decimal,
    cash_rub: Decimal,
    holdings: tuple[Holding, ...],
    candidates: tuple[Candidate, ...],
) -> dict[str, object]:
    return cast(
        dict[str, object],
        _serialize(
            {
                "hold": _scenario_payload(
                    preview.hold,
                    nav_rub=nav_rub,
                    cash_rub=cash_rub,
                    holdings=holdings,
                    candidates=candidates,
                ),
                "deploy_cash": _scenario_payload(
                    preview.deploy_cash,
                    nav_rub=nav_rub,
                    cash_rub=cash_rub,
                    holdings=holdings,
                    candidates=candidates,
                ),
                "replacements": [
                    _scenario_payload(
                        scenario,
                        nav_rub=nav_rub,
                        cash_rub=cash_rub,
                        holdings=holdings,
                        candidates=candidates,
                    )
                    for scenario in preview.replacements
                ],
            }
        ),
    )


def _scenario_payload(
    scenario: BalancingScenario,
    *,
    nav_rub: Decimal,
    cash_rub: Decimal,
    holdings: tuple[Holding, ...],
    candidates: tuple[Candidate, ...],
) -> dict[str, object]:
    payload = cast(dict[str, object], asdict(scenario))
    payload["before_after"] = _scenario_before_after(
        scenario,
        nav_rub=nav_rub,
        cash_rub=cash_rub,
        holdings=holdings,
        candidates=candidates,
    )
    return payload


def _scenario_before_after(
    scenario: BalancingScenario,
    *,
    nav_rub: Decimal,
    cash_rub: Decimal,
    holdings: tuple[Holding, ...],
    candidates: tuple[Candidate, ...],
) -> dict[str, object]:
    before = _position_state(holdings)
    after = {
        uid: dict(position)
        for uid, position in before.items()
    }
    holding_by_uid = {
        item.instrument_uid: item
        for item in holdings
    }
    candidate_by_uid = {
        item.instrument_uid: item
        for item in candidates
    }

    for trade in scenario.trades:
        _apply_trade_to_position_state(
            after,
            trade,
            holding=holding_by_uid.get(trade.instrument_uid),
            candidate=candidate_by_uid.get(trade.instrument_uid),
        )

    total_cost = sum(
        (
            trade.estimated_cost_rub + trade.tax_rub
            for trade in scenario.trades
        ),
        Decimal("0"),
    )
    after_nav = max(Decimal("0"), nav_rub - total_cost)
    after_cash = (
        cash_rub + scenario.residual_cash_rub
        if scenario.kind == "replace"
        else scenario.residual_cash_rub
    )
    return {
        "before": _portfolio_state_payload(
            before,
            nav_rub=nav_rub,
            cash_rub=cash_rub,
        ),
        "after": _portfolio_state_payload(
            after,
            nav_rub=after_nav,
            cash_rub=after_cash,
        ),
    }


def _position_state(
    holdings: tuple[Holding, ...],
) -> dict[str, dict[str, object]]:
    return {
        item.instrument_uid: {
            "instrument_uid": item.instrument_uid,
            "ticker": item.ticker,
            "asset_class": item.asset_class,
            "sector": item.sector,
            "issuer_id": item.issuer_id,
            "group_id": item.group_id,
            "risk_state": item.risk_state,
            "lots": item.lots,
            "value_rub": item.value_rub,
        }
        for item in holdings
        if item.instrument_uid and item.lots > 0 and item.value_rub > 0
    }


def _apply_trade_to_position_state(
    positions: dict[str, dict[str, object]],
    trade: PlannedTrade,
    *,
    holding: Holding | None,
    candidate: Candidate | None,
) -> None:
    existing = positions.get(trade.instrument_uid)
    if trade.action == "sell":
        if existing is None:
            return
        lots = max(0, _integer(existing["lots"]) - trade.lots)
        value = max(
            Decimal("0"),
            cast(Decimal, existing["value_rub"]) - trade.notional_rub,
        )
        if lots == 0 or value == 0:
            positions.pop(trade.instrument_uid, None)
            return
        existing["lots"] = lots
        existing["value_rub"] = value
        return

    source = candidate
    if source is None:
        return
    if existing is None:
        positions[trade.instrument_uid] = {
            "instrument_uid": source.instrument_uid,
            "ticker": source.ticker,
            "asset_class": source.asset_class,
            "sector": source.sector,
            "issuer_id": source.issuer_id,
            "group_id": source.group_id,
            "risk_state": source.risk_state,
            "lots": trade.lots,
            "value_rub": trade.notional_rub,
        }
        return
    existing["lots"] = _integer(existing["lots"]) + trade.lots
    existing["value_rub"] = (
        cast(Decimal, existing["value_rub"]) + trade.notional_rub
    )


def _portfolio_state_payload(
    positions: dict[str, dict[str, object]],
    *,
    nav_rub: Decimal,
    cash_rub: Decimal,
) -> dict[str, object]:
    ordered = sorted(
        positions.values(),
        key=lambda item: (
            -cast(Decimal, item["value_rub"]),
            str(item["instrument_uid"]),
        ),
    )
    return {
        "nav_rub": nav_rub,
        "cash_rub": cash_rub,
        "positions": ordered,
        "exposures": {
            dimension: _exposure_dimension(
                ordered,
                dimension=dimension,
                nav_rub=nav_rub,
            )
            for dimension in (
                "asset_class",
                "sector",
                "issuer_id",
                "group_id",
            )
        },
    }


def _exposure_dimension(
    positions: list[dict[str, object]],
    *,
    dimension: str,
    nav_rub: Decimal,
) -> list[dict[str, object]]:
    totals: dict[str, Decimal] = {}
    for position in positions:
        key = str(position.get(dimension) or "unknown")
        value = cast(Decimal, position["value_rub"])
        totals[key] = totals.get(key, Decimal("0")) + value
    return [
        {
            "key": key,
            "value_rub": value,
            "nav_percent": (
                value / nav_rub * Decimal("100")
                if nav_rub > 0
                else Decimal("0")
            ),
        }
        for key, value in sorted(
            totals.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]


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
    quantity_lots = _decimal(row.get("quantity_lots"))
    lot = _integer(row.get("lot"))
    lots = 0
    quantity_misaligned = True
    if quantity_lots is not None and quantity_lots >= 0:
        integral_lots = quantity_lots.to_integral_value()
        if quantity_lots == integral_lots:
            lots = int(integral_lots)
            quantity_misaligned = False
    elif lot > 0 and quantity >= 0:
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
    group_id = str(row.get("group_id") or "") or "unverified_group"
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
        group_id=group_id or "unverified_group",
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
        max_liquid_lots=None,
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
