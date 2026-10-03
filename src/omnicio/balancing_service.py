"""Read-only R4 adapter from durable portfolio evidence to balancing primitives."""

from __future__ import annotations

import math
import re
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, InvalidOperation
from typing import Any, cast
from uuid import UUID

from .balancing import (
    AllocationCap,
    BalancingPolicy,
    Candidate,
    Holding,
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
    TBankBondEvent,
    TBankHistoricCandle,
    TBankInstrumentMetadata,
    TBankLastPrice,
    TBankMoney,
    TBankRating,
    TBankUnavailable,
)

LIVE_CANDIDATE_LIMIT = 4
LIVE_REPLACEMENT_LIMIT = 4
MARKET_QUOTE_MAX_AGE = timedelta(minutes=15)
TBANK_LIQUIDITY_WINDOW_DAYS = 45
TBANK_LIQUIDITY_MIN_OBSERVED_DAYS = 10

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


def build_live_balancing_payload(
    *,
    user_id: UUID,
    profile: InvestmentProfileRecord | None,
    policy_record: BalancingPolicyRecord | None,
    context: dict[str, object] | None,
    broker: BrokerService,
    now: datetime | None = None,
) -> dict[str, object]:
    """Enrich a bounded candidate set with read-only T-Invest evidence."""
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
    enriched: list[Candidate] = []
    live_sources: list[dict[str, object]] = []

    for row in rows:
        uid = str(row.get("instrument_uid") or "")
        if not any(str(item.get("instrument_uid") or "") == uid for item in selected):
            candidate = _candidate(
                row,
                context=context,
                policy=_policy(
                    profile,
                    policy_record,
                    _decimal(context.get("nav_rub")) or Decimal("0"),
                ),
                observed_at=observed_at,
            )
            enriched.append(
                _with_candidate_blocker(
                    candidate,
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
            candidate = _candidate(
                row,
                context=context,
                policy=_policy(
                    profile,
                    policy_record,
                    _decimal(context.get("nav_rub")) or Decimal("0"),
                ),
                observed_at=observed_at,
            )
            candidate = _with_candidate_blocker(
                candidate,
                "live_candidate_evidence_unavailable",
            )
            sources = ()
        enriched.append(candidate)
        live_sources.extend(sources)

    holding_rows = _dict_rows(context.get("holdings"))
    replacement_rows = tuple(
        row
        for row in holding_rows
        if str(row.get("risk_state") or "") in {
            "elevated",
            "critical",
            "confirmed_default",
        }
    )[:LIVE_REPLACEMENT_LIMIT]
    replacement_uids = {
        str(row.get("instrument_uid") or "")
        for row in replacement_rows
    }
    enriched_holdings: list[Holding] = []
    for row in holding_rows:
        uid = str(row.get("instrument_uid") or "")
        if uid not in replacement_uids:
            enriched_holdings.append(_holding(row))
            continue
        try:
            holding, sources = _enrich_replacement_holding(
                user_id=user_id,
                row=row,
                policy_record=policy_record,
                broker=broker,
                observed_at=observed_at,
            )
        except (BrokerConnectionError, MoexError, TBankUnavailable, ValueError):
            holding = _holding(row)
            sources = ()
        enriched_holdings.append(holding)
        live_sources.extend(sources)

    payload = build_balancing_payload(
        profile=profile,
        policy_record=policy_record,
        context=context,
        now=observed_at,
        holdings_override=tuple(enriched_holdings),
        candidates_override=tuple(enriched),
    )
    payload["live_status"] = "received"
    payload["live_candidate_count"] = len(selected)
    payload["live_sources"] = _dedupe_sources(live_sources)
    payload["methodology"] = {
        "candidate_limit": LIVE_CANDIDATE_LIMIT,
        "shortlist_universe_limit": 100,
        "shortlist_signal": "tbank_market_yield_not_decision_metric",
        "replacement_limit": LIVE_REPLACEMENT_LIMIT,
        "market_quote_max_age_seconds": int(
            MARKET_QUOTE_MAX_AGE.total_seconds()
        ),
        "liquidity_window_days": TBANK_LIQUIDITY_WINDOW_DAYS,
        "liquidity_min_observed_days": TBANK_LIQUIDITY_MIN_OBSERVED_DAYS,
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
    if not str(row.get("isin") or "") or not str(row.get("class_code") or ""):
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
    qualified = broker_user.get("qualified") if isinstance(broker_user, dict) else None
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
    policy = _policy(profile, policy_record, nav_rub)
    base = _candidate(
        row,
        context=context,
        policy=policy,
        observed_at=observed_at,
    )
    if base.asset_class != "bond":
        return _with_candidate_blocker(
            base,
            "live_asset_class_not_supported",
        ), ()

    info = broker.candidate_bond_metadata(user_id, base.instrument_uid)
    structure_blocker = _bond_structure_blocker(info, observed_at)
    if structure_blocker is not None:
        return _with_candidate_blocker(base, structure_blocker), ()

    assessment = assess_candidate_fundamental_risk(
        info,
        fundamental,
        assessed_at=observed_at,
    )
    rating_bucket, rating_under_watch = _rating_bucket(info.ratings)

    if (
        info.maturity_date is None
        or info.maturity_date <= observed_at
        or info.nominal is None
    ):
        return _with_candidate_blocker(base, "bond_term_missing"), ()
    evidence_to = info.maturity_date + timedelta(days=2)
    coupons = broker.candidate_bond_coupons(
        user_id,
        base.instrument_uid,
        from_at=observed_at,
        to_at=evidence_to,
    )
    events = broker.candidate_bond_events(
        user_id,
        base.instrument_uid,
        from_at=observed_at - timedelta(days=1),
        to_at=evidence_to,
    )
    if _confirmed_default(events, observed_at):
        return replace(
            _with_candidate_blocker(base, "confirmed_default"),
            risk_state="confirmed_default",
        ), ()
    if _future_call_exists(info, events, observed_at):
        return _with_candidate_blocker(
            base,
            "bond_call_structure_not_supported",
        ), ()

    cashflows = _bond_cashflows(info, coupons, observed_at)
    if not cashflows:
        return _with_candidate_blocker(base, "bond_cashflows_missing"), ()

    if last_price is None or not _fresh_market_time(last_price.time, observed_at):
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

    order_price = broker.candidate_order_price(
        user_id,
        base.instrument_uid,
        price=str(best_ask),
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
    dirty_price = initial + aci
    if dirty_price <= 0 or total <= 0 or fee < 0 or aci < 0:
        raise ValueError("invalid T-Invest order price evidence")

    yield_duration = _bond_yield_and_duration(
        dirty_price,
        cashflows,
        observed_at,
    )
    if yield_duration is None:
        return _with_candidate_blocker(base, "bond_ytw_missing"), ()
    ytw_percent, duration_years = yield_duration

    candle_from = observed_at - timedelta(days=TBANK_LIQUIDITY_WINDOW_DAYS)
    candles = broker.candidate_daily_candles(
        user_id,
        base.instrument_uid,
        from_at=candle_from,
        to_at=observed_at,
        limit=90,
    )
    liquidity = _bond_liquidity(
        info=info,
        candles=candles,
        dirty_price=dirty_price,
        order_book_ask_lots=sum(level.quantity_lots for level in order_book.asks),
        participation_percent=(
            policy_record.max_daily_turnover_participation_percent
        ),
        horizon_days=profile.liquidity_horizon_days,
        observed_at=observed_at,
    )
    if liquidity is None:
        return _with_candidate_blocker(base, "liquidity_evidence_missing"), ()
    liquidity_days, max_liquid_lots, average_daily_turnover = liquidity
    if max_liquid_lots <= 0:
        return _with_candidate_blocker(base, "liquidity_limit"), ()

    term_months = _months_until(observed_at, info.maturity_date)
    if term_months is None or term_months <= 0:
        return _with_candidate_blocker(base, "bond_term_missing"), ()

    gross_gain = sum(
        amount
        for _payment_at, amount in cashflows
    ) - dirty_price
    uncertainty = (
        dirty_price
        * policy_record.uncertainty_haircut_percent
        / Decimal("100")
    )
    credit_loss = (
        dirty_price
        * policy_record.credit_loss_haircut_percent
        / Decimal("100")
    )

    removable = {
        "issuer_identity_not_verified",
        "issuer_group_not_verified",
        "candidate_risk_assessment_missing",
        "quote_missing",
        "bond_ytw_missing",
        "bond_duration_missing",
        "provider_liquidity_flag_missing",
    }
    access_reasons = tuple(
        reason for reason in base.access_reasons if reason not in removable
    )
    risk_state: RiskState = assessment.state
    if rating_under_watch and risk_state == "normal":
        risk_state = "watch"

    verified_issuer_id = str(row.get("issuer_id") or "")
    verified_group_id = str(row.get("group_id") or "")
    if verified_issuer_id and verified_group_id:
        issuer_id = verified_issuer_id
        group_id = verified_group_id
        identity_note = "issuer_group_from_verified_mapping"
    else:
        # Unknown legal issuer/group identity must never split concentration.
        issuer_id = "unverified_issuer_group"
        group_id = "unverified_issuer_group"
        identity_note = "issuer_identity_conservative_shared_bucket"

    notes = (
        "shortlisted_by_tbank_market_yield_signal",
        identity_note,
        "rating_from_tinvest_bond_metadata",
        "buy_cost_from_tinvest_get_order_price",
        "ytw_from_tinvest_coupon_cashflows",
        "duration_from_tinvest_coupon_cashflows",
        "liquidity_from_tinvest_exchange_daily_candles",
        "expected_gain_to_maturity_from_provider_cashflows",
        "tax_not_applied_to_new_buy",
        f"average_daily_turnover_rub:{average_daily_turnover}",
    )
    evidence_complete = (
        assessment.fundamental_status == "received"
        and risk_state in {"normal", "watch", "elevated"}
        and not access_reasons
    )
    candidate = replace(
        base,
        issuer_id=issuer_id,
        group_id=group_id,
        rating_bucket=cast(Any, rating_bucket),
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
        access_reasons=access_reasons,
        notes=notes,
    )
    source_root = "https://developer.tbank.ru/invest/api/"
    sources: tuple[dict[str, object], ...] = (
        {
            "id": f"tbank-bond-by:{base.instrument_uid}",
            "provider": "tbank",
            "kind": "bond_metadata_ratings",
            "url": source_root + "instruments-service-bond-by",
            "retrieved_at": observed_at,
        },
        {
            "id": f"tbank-bond-coupons:{base.instrument_uid}",
            "provider": "tbank",
            "kind": "bond_cashflows",
            "url": source_root + "instruments-service-get-bond-coupons",
            "retrieved_at": observed_at,
        },
        {
            "id": f"tbank-bond-events:{base.instrument_uid}",
            "provider": "tbank",
            "kind": "bond_events",
            "url": source_root + "instruments-service-get-bond-events",
            "retrieved_at": observed_at,
        },
        {
            "id": f"tbank-last-price:{base.instrument_uid}",
            "provider": "tbank",
            "kind": "last_price",
            "url": source_root + "market-data-service-get-last-prices",
            "retrieved_at": last_price.time,
        },
        {
            "id": f"tbank-order-book:{base.instrument_uid}",
            "provider": "tbank",
            "kind": "order_book",
            "url": source_root + "market-data-service-get-order-book",
            "retrieved_at": order_book.time,
        },
        {
            "id": f"tbank-order-price:{base.instrument_uid}",
            "provider": "tbank",
            "kind": "order_price",
            "url": source_root + "orders-service-get-order-price",
            "retrieved_at": observed_at,
        },
        {
            "id": f"tbank-candles:{base.instrument_uid}",
            "provider": "tbank",
            "kind": "historical_liquidity",
            "url": source_root + "market-data-service-get-candles",
            "retrieved_at": observed_at,
        },
    )
    return candidate, sources


def _enrich_replacement_holding(
    *,
    user_id: UUID,
    row: dict[str, object],
    policy_record: BalancingPolicyRecord,
    broker: BrokerService,
    observed_at: datetime,
) -> tuple[Holding, tuple[dict[str, object], ...]]:
    base = _holding(row)
    if (
        base.asset_class != "bond"
        or base.blocked
        or base.lots <= 0
        or base.risk_state not in {"elevated", "critical", "confirmed_default"}
    ):
        return base, ()

    info = broker.candidate_bond_metadata(user_id, base.instrument_uid)
    if _bond_structure_blocker(info, observed_at) is not None:
        return base, ()
    if info.maturity_date is None or info.maturity_date <= observed_at:
        return base, ()

    evidence_to = info.maturity_date + timedelta(days=2)
    coupons = broker.candidate_bond_coupons(
        user_id,
        base.instrument_uid,
        from_at=observed_at,
        to_at=evidence_to,
    )
    events = broker.candidate_bond_events(
        user_id,
        base.instrument_uid,
        from_at=observed_at - timedelta(days=1),
        to_at=evidence_to,
    )
    if _confirmed_default(events, observed_at):
        return base, ()
    if _future_call_exists(info, events, observed_at):
        return base, ()
    cashflows = _bond_cashflows(info, coupons, observed_at)
    if not cashflows:
        return base, ()

    order_book = broker.candidate_order_book(
        user_id,
        base.instrument_uid,
        depth=10,
    )
    if (
        not order_book.is_consistent
        or not order_book.bids
        or not order_book.asks
        or not _fresh_market_time(order_book.time, observed_at)
    ):
        return base, ()
    best_bid = max(Decimal(level.price) for level in order_book.bids)
    best_ask = min(Decimal(level.price) for level in order_book.asks)
    if best_bid <= 0 or best_ask <= best_bid:
        return base, ()

    sale = broker.candidate_order_price(
        user_id,
        base.instrument_uid,
        price=str(best_bid),
        direction="sell",
        quantity_lots=base.lots,
    )
    initial = _money_rub(sale.initial_order_amount)
    fee = _money_rub(sale.executed_commission_rub)
    aci = (
        _money_rub(sale.bond_aci_value)
        if sale.bond_aci_value is not None
        else Decimal("0")
    )
    gross_sale = initial + aci
    fifo = _decimal(row.get("average_price_fifo_value"))
    fifo_currency = str(row.get("average_price_fifo_currency") or "").upper()
    quantity = _decimal(row.get("quantity"))
    if (
        gross_sale <= 0
        or fee < 0
        or fifo is None
        or fifo <= 0
        or fifo_currency != "RUB"
        or quantity is None
        or quantity <= 0
    ):
        return base, ()

    per_lot_dirty = gross_sale / Decimal(base.lots)
    yield_duration = _bond_yield_and_duration(
        per_lot_dirty,
        cashflows,
        observed_at,
    )
    if yield_duration is None:
        return base, ()

    cost_basis = fifo * quantity
    taxable_gain = max(Decimal("0"), gross_sale - fee - cost_basis)
    tax = (
        taxable_gain
        * policy_record.securities_tax_rate_percent
        / Decimal("100")
    )
    future_cash = sum(
        amount for _payment_at, amount in cashflows
    ) * Decimal(base.lots)
    stress = gross_sale * (
        policy_record.uncertainty_haircut_percent
        + policy_record.credit_loss_haircut_percent
    ) / Decimal("100")
    expected_hold_gain = future_cash - gross_sale - stress

    enriched = replace(
        base,
        value_rub=gross_sale,
        expected_horizon_gain_rub=expected_hold_gain,
        sell_fee_rub=fee,
        exit_spread_cost_rub=Decimal("0"),
        tax_if_sold_rub=tax,
        replacement_costs_complete=True,
    )
    source_root = "https://developer.tbank.ru/invest/api/"
    sources: tuple[dict[str, object], ...] = (
        {
            "id": f"tbank-held-bond:{base.instrument_uid}",
            "provider": "tbank",
            "kind": "held_bond_metadata_cashflows",
            "url": source_root + "instruments-service-bond-by",
            "retrieved_at": observed_at,
        },
        {
            "id": f"tbank-sell-order-book:{base.instrument_uid}",
            "provider": "tbank",
            "kind": "sell_order_book",
            "url": source_root + "market-data-service-get-order-book",
            "retrieved_at": order_book.time,
        },
        {
            "id": f"tbank-sell-order-price:{base.instrument_uid}",
            "provider": "tbank",
            "kind": "sell_order_price",
            "url": source_root + "orders-service-get-order-price",
            "retrieved_at": observed_at,
        },
    )
    return enriched, sources


def _bond_structure_blocker(
    info: TBankInstrumentMetadata,
    observed_at: datetime,
) -> str | None:
    if info.currency.upper() != "RUB":
        return "currency_not_allowed"
    if info.nominal is None or info.nominal.currency.upper() != "RUB":
        return "bond_nominal_missing"
    if info.lot <= 0:
        return "invalid_lot_size"
    if info.perpetual is not False:
        return "bond_perpetual_not_supported"
    if info.amortization is not False:
        return "bond_amortization_not_supported"
    if info.floating_coupon is not False:
        return "bond_floating_coupon_not_supported"
    if info.subordinated is not False:
        return "bond_subordinated_not_supported"
    if info.call_date is not None and info.call_date > observed_at:
        return "bond_call_structure_not_supported"
    return None


def _future_call_exists(
    info: TBankInstrumentMetadata,
    events: tuple[TBankBondEvent, ...],
    observed_at: datetime,
) -> bool:
    if info.call_date is not None and info.call_date > observed_at:
        return True
    return any(
        event.event_type.endswith("CALL")
        and event.event_date is not None
        and event.event_date > observed_at
        for event in events
    )


def _confirmed_default(
    events: tuple[TBankBondEvent, ...],
    observed_at: datetime,
) -> bool:
    return any(
        event.default_date is not None
        and event.default_date <= observed_at
        for event in events
    )


def _bond_cashflows(
    info: TBankInstrumentMetadata,
    coupons: tuple[TBankBondCoupon, ...],
    observed_at: datetime,
) -> tuple[tuple[datetime, Decimal], ...]:
    if (
        info.nominal is None
        or info.nominal.currency.upper() != "RUB"
        or info.maturity_date is None
        or info.maturity_date <= observed_at
        or info.lot <= 0
    ):
        return ()
    nominal = Decimal(info.nominal.value)
    if not nominal.is_finite() or nominal <= 0:
        return ()

    values: dict[datetime, Decimal] = {}
    for coupon in coupons:
        if (
            coupon.coupon_date <= observed_at
            or coupon.coupon_date > info.maturity_date
            or coupon.pay_one_bond.currency.upper() != "RUB"
        ):
            continue
        amount = Decimal(coupon.pay_one_bond.value) * Decimal(info.lot)
        if not amount.is_finite() or amount < 0:
            return ()
        values[coupon.coupon_date] = (
            values.get(coupon.coupon_date, Decimal("0")) + amount
        )
    principal = nominal * Decimal(info.lot)
    values[info.maturity_date] = (
        values.get(info.maturity_date, Decimal("0")) + principal
    )
    return tuple(sorted(values.items(), key=lambda item: item[0]))


def _bond_yield_and_duration(
    dirty_price: Decimal,
    cashflows: tuple[tuple[datetime, Decimal], ...],
    observed_at: datetime,
) -> tuple[Decimal, Decimal] | None:
    if dirty_price <= 0 or not cashflows:
        return None
    price = float(dirty_price)

    def present_value(rate: float) -> float:
        if rate <= -1:
            return math.inf
        result = 0.0
        for payment_at, amount in cashflows:
            years = max(
                1.0 / 365.25,
                (payment_at - observed_at).total_seconds()
                / (365.25 * 24 * 60 * 60),
            )
            result += float(amount) / math.pow(1.0 + rate, years)
        return result

    lower = -0.95
    upper = 1.0
    if present_value(lower) < price:
        return None
    while present_value(upper) > price and upper < 128:
        upper = upper * 2 + 1
    if present_value(upper) > price:
        return None

    for _ in range(120):
        middle = (lower + upper) / 2
        if present_value(middle) > price:
            lower = middle
        else:
            upper = middle
    rate = (lower + upper) / 2
    denominator = present_value(rate)
    if not math.isfinite(rate) or denominator <= 0:
        return None

    weighted = 0.0
    for payment_at, amount in cashflows:
        years = max(
            1.0 / 365.25,
            (payment_at - observed_at).total_seconds()
            / (365.25 * 24 * 60 * 60),
        )
        discounted = float(amount) / math.pow(1.0 + rate, years)
        weighted += years * discounted
    duration = weighted / denominator
    if not math.isfinite(duration) or duration <= 0:
        return None
    return (
        Decimal(str(rate * 100)).quantize(Decimal("0.000001")),
        Decimal(str(duration)).quantize(Decimal("0.000001")),
    )


def _bond_liquidity(
    *,
    info: TBankInstrumentMetadata,
    candles: tuple[TBankHistoricCandle, ...],
    dirty_price: Decimal,
    order_book_ask_lots: int,
    participation_percent: Decimal,
    horizon_days: int,
    observed_at: datetime,
) -> tuple[int, int, Decimal] | None:
    if (
        info.nominal is None
        or info.nominal.currency.upper() != "RUB"
        or info.lot <= 0
        or dirty_price <= 0
        or participation_percent <= 0
        or horizon_days <= 0
        or order_book_ask_lots <= 0
    ):
        return None
    nominal = Decimal(info.nominal.value)
    if nominal <= 0 or not nominal.is_finite():
        return None

    turnovers: list[Decimal] = []
    for candle in candles:
        if (
            not candle.is_complete
            or candle.time >= observed_at
            or candle.volume_lots < 0
        ):
            continue
        close_points = Decimal(candle.close)
        if not close_points.is_finite() or close_points <= 0:
            return None
        turnover = (
            close_points
            / Decimal("100")
            * nominal
            * Decimal(info.lot)
            * Decimal(candle.volume_lots)
        )
        if not turnover.is_finite() or turnover < 0:
            return None
        turnovers.append(turnover)
    if len(turnovers) < TBANK_LIQUIDITY_MIN_OBSERVED_DAYS:
        return None

    average_daily_turnover = (
        sum(turnovers, Decimal("0")) / Decimal(len(turnovers))
    )
    daily_capacity = (
        average_daily_turnover
        * participation_percent
        / Decimal("100")
    )
    if daily_capacity <= 0:
        return None
    liquidity_days = max(
        1,
        int(
            (dirty_price / daily_capacity).to_integral_value(
                rounding=ROUND_CEILING
            )
        ),
    )
    history_capacity_lots = int(
        (
            daily_capacity * Decimal(horizon_days) / dirty_price
        ).to_integral_value(rounding=ROUND_FLOOR)
    )
    return (
        liquidity_days,
        max(0, min(history_capacity_lots, order_book_ask_lots)),
        average_daily_turnover.quantize(Decimal("0.01")),
    )


def _rating_bucket(
    ratings: tuple[TBankRating, ...],
) -> tuple[str, bool]:
    if not ratings:
        return "unknown", False
    buckets: list[str] = []
    under_watch = False
    for rating in ratings:
        under_watch = under_watch or rating.is_under_watch
        level = re.sub(r"\s+", "", rating.rating_level.upper())
        match = re.search(
            r"(AAA|AA|BBB|BB|CCC|CC|A|B|C|D)",
            level,
            flags=re.ASCII,
        )
        if match is None:
            buckets.append("unknown")
            continue
        grade = match.group(1)
        if grade == "AAA":
            buckets.append("aaa")
        elif grade == "AA":
            buckets.append("aa")
        elif grade == "A":
            buckets.append("a")
        elif grade == "BBB":
            buckets.append("bbb")
        else:
            buckets.append("below_grade")
    rank = {
        "aaa": 0,
        "aa": 1,
        "a": 2,
        "bbb": 3,
        "below_grade": 4,
        "unknown": 5,
    }
    return max(buckets, key=rank.__getitem__), under_watch


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
