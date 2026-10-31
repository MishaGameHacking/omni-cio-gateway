"""Exact RUB cash-floor arithmetic, not broker credit approval or order dispatch.

Inputs must be account-bound observations supplied by a separate trusted reader.
Signed cash is already net of existing borrowing; never add that debt a second
time. Each pending debit says explicitly whether cash already includes it.
Neither a tariff nor this requested floor proves collateral sufficiency. All
results require a separate fresh broker margin check and remain non-executable.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING

try:
    from .volume_contract import decimal, financial_context, instrument_currency, timestamp
except ImportError:
    from volume_contract import decimal, financial_context, instrument_currency, timestamp

CASH_FLOOR_RUB = Decimal("-4999.00")
MAX_AGE_SECONDS = 60
PORTFOLIO_MAX_AGE_SECONDS = 300
MAX_PENDING_DEBITS = 1000
ZERO = Decimal(0)


def _mapping(value):
    return value if isinstance(value, dict) else {}


def _identifier(value):
    return isinstance(value, str) and 0 < len(value) <= 160 and value.strip() == value and all(ord(c) >= 32 for c in value)


def _amount(value, *, signed=False):
    # Canonical inputs are scalar RUB values. A nested MoneyValue in another
    # currency must not silently pass through decimal() under a RUB field name.
    if not isinstance(value, (str, int, Decimal)):
        return None
    parsed = decimal(value)
    if parsed is None or parsed.as_tuple().exponent < -9 or not signed and parsed < 0:
        return None
    return parsed


def _stamp(value):
    try:
        return timestamp(value)
    except ValueError:
        return None


def _clock(now):
    if now is None:
        return datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("margin_aware_clock_required")
    return now.astimezone(timezone.utc)


def _fresh(value, now):
    observed = _stamp(value)
    return observed is not None and 0 <= (now - observed).total_seconds() < MAX_AGE_SECONDS


def _valid_window(observed_at, expires_at, now):
    observed, expiry = _stamp(observed_at), _stamp(expires_at)
    return observed is not None and expiry is not None and observed <= now < expiry


def _text(value):
    return format(value, "f") if value is not None else None


def _pending(snapshot):
    rows = snapshot.get("pending_debits")
    if snapshot.get("pending_complete") is not True or not isinstance(rows, list) or len(rows) > MAX_PENDING_DEBITS:
        return None, {}, ["margin_pending_debits_incomplete"]
    seen, reasons = {}, []
    for raw in rows:
        row = _mapping(raw)
        identity, amount, included = row.get("id"), _amount(row.get("amount_rub")), row.get("included_in_cash")
        if not _identifier(identity) or amount is None or type(included) is not bool or row.get("currency") != "RUB":
            reasons.append("margin_pending_debit_invalid")
            continue
        signature = (amount, included)
        if identity in seen and seen[identity] != signature:
            reasons.append("margin_pending_debit_conflict")
        seen[identity] = signature
    unreflected = sum((amount for amount, included in seen.values() if not included), ZERO)
    return (None if reasons else unreflected), seen, reasons


def _observation(snapshot, now):
    snapshot = _mapping(snapshot)
    account, cash = snapshot.get("account_id"), _amount(snapshot.get("cash_rub"), signed=True)
    reasons = []
    if not _identifier(account):
        reasons.append("margin_account_required")
    if snapshot.get("currency") != "RUB" or cash is None:
        reasons.append("margin_signed_ruble_cash_unknown")
    if snapshot.get("cash_basis") != "signed_cash_with_explicit_pending_inclusion":
        reasons.append("margin_cash_basis_unverified")
    if not _fresh(snapshot.get("observed_at"), now):
        reasons.append("margin_cash_observation_stale_or_future")
    pending, identities, pending_reasons = _pending(snapshot)
    reasons.extend(pending_reasons)
    effective = cash - pending if cash is not None and pending is not None else None
    return account, cash, pending, effective, identities, reasons


def _repayment(cash):
    if cash is None:
        return None, None
    breach = max(ZERO, CASH_FLOOR_RUB - cash)
    return breach, breach.quantize(Decimal("0.01"), rounding=ROUND_CEILING)


def _base(account, now):
    return {"schema_version": 1, "account_id": account if _identifier(account) else None,
        "currency": "RUB", "evaluated_at": now.isoformat(), "cash_floor_rub": _text(CASH_FLOOR_RUB),
        "arithmetic_policy_passed": False, "ready_for_order": False, "real_orders_enabled": False,
        "broker_margin_check_required": True, "margin_call_risk_assessed": False,
        "safety_guaranteed": False, "policy_floor_is_not_broker_margin_call_threshold": True}


def _native_currency(row):
    metadata = row.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        return None
    return instrument_currency(row)


def _portfolio_cash(snapshot, account):
    accounts, positions = snapshot.get("accounts"), snapshot.get("positions")
    if (not _identifier(account) or not isinstance(accounts, list)
            or sum(_mapping(row).get("id") == account for row in accounts) != 1):
        return None, ["margin_selected_account_unverified"]
    if not isinstance(positions, list):
        return None, ["margin_native_ruble_cash_unverified"]
    rows = [row for row in positions if isinstance(row, dict) and row.get("account_id") == account
        and row.get("instrument_type") == "cash"
        and (_native_currency(row) == "RUB" or row.get("instrument_uid") == "cash:RUB")]
    if len(rows) != 1:
        return None, ["margin_native_ruble_cash_not_unique"]
    row = rows[0]
    uid, value = row.get("instrument_uid"), _mapping(row.get("value"))
    conflicting_uid = isinstance(uid, str) and uid.startswith("cash:") and uid != "cash:RUB"
    cash = _amount(value.get("amount"), signed=True)
    if _native_currency(row) != "RUB" or conflicting_uid or value.get("currency") != "RUB" or cash is None:
        return None, ["margin_native_ruble_cash_unverified"]
    return cash, []


@financial_context
def observe_portfolio(snapshot: dict, account_id: str, *, now: datetime | None = None) -> dict:
    """Monitor persisted native RUB cash only, without inferring full liabilities.

    normalize_snapshot assigns one broker observation time to the snapshot.
    Pending charges, reservations and collateral are not complete here. A fresh
    cash breach remains visible as a minimum observed shortfall even when those
    additional obligations are unknown. Never derive buying power from this.
    """
    now, snapshot = _clock(now), _mapping(snapshot)
    cash, reasons = _portfolio_cash(snapshot, account_id)
    observed = _stamp(snapshot.get("as_of"))
    timely = observed is not None and 0 <= (now - observed).total_seconds() < PORTFOLIO_MAX_AGE_SECONDS
    if not timely:
        reasons.append("margin_portfolio_observation_stale_or_future")
    fresh = cash is not None and not reasons
    _, shortfall = _repayment(cash if fresh else None)
    observation_state = "unknown"
    if cash is not None:
        observation_state = "observed" if fresh else "stale"
    return {"schema_version": 1, "account_id": account_id if _identifier(account_id) else None,
        "basis": "persisted_native_ruble_cash_only", "currency": "RUB",
        "cash_floor_rub": _text(CASH_FLOOR_RUB), "evaluated_at": now.isoformat(),
        "state": observation_state,
        "observed_cash_rub": _text(cash), "as_of": observed.isoformat() if observed else None,
        "fresh": fresh, "max_age_seconds": PORTFOLIO_MAX_AGE_SECONDS,
        "observed_floor_breached": cash < CASH_FLOOR_RUB if fresh else None,
        "minimum_observed_shortfall_rub": _text(shortfall),
        "commitments_verified": False, "full_repayment_unknown": True, "full_repayment_rub": None,
        "ready_for_order": False, "real_orders_enabled": False,
        "policy_floor_is_not_broker_margin_call_threshold": True,
        "reasons": sorted(set(reasons))}


@financial_context
def evaluate_current(snapshot: dict, *, now: datetime | None = None) -> dict:
    """Observe the floor and cash repayment only; never choose assets to sell.

    pending_debits includes known charges and remaining purchase commitments.
    Amounts already reflected in signed cash must have included_in_cash=True.
    Unknown or conflicting obligations make the result unknown, never zero.
    """
    now = _clock(now)
    account, cash, pending, effective, _, reasons = _observation(snapshot, now)
    trusted = not reasons
    breach, repayment = _repayment(effective if trusted else None)
    result = _base(account, now)
    current_state = "unknown"
    if trusted:
        current_state = "breached" if breach > 0 else "within_requested_floor"
    result.update(state=current_state,
        observed_cash_rub=_text(cash), unreflected_pending_debits_rub=_text(pending),
        cash_after_commitments_rub=_text(effective if trusted else None),
        observed_cash_breaches_floor=cash < CASH_FLOOR_RUB if trusted else None,
        commitments_breach_floor=breach > 0 if trusted else None,
        breach_amount_rub=_text(breach), required_repayment_rub=_text(repayment),
        repayment_rounding="up_to_ruble_minor_unit", reasons=sorted(set(reasons)),
        arithmetic_policy_passed=trusted and breach == 0,
        maximum_all_in_buy_rub=_text(max(ZERO, effective - CASH_FLOOR_RUB)) if trusted else None)
    return result


def _quote(quote, account, identities, now):
    quote = _mapping(quote)
    reasons = []
    if quote.get("account_id") != account or not _identifier(quote.get("proposal_id")):
        reasons.append("margin_quote_account_or_identity_invalid")
    elif quote["proposal_id"] in identities:
        reasons.append("margin_proposal_already_committed")
    if quote.get("currency") != "RUB" or quote.get("costs_complete") is not True:
        reasons.append("margin_all_in_cost_unknown")
    if not _fresh(quote.get("observed_at"), now) or not _valid_window(quote.get("observed_at"), quote.get("expires_at"), now):
        reasons.append("margin_quote_stale_or_future")
    fields = ("principal_rub", "commission_rub", "accrued_interest_rub", "other_charges_rub")
    parts = [_amount(quote.get(key)) for key in fields]
    total = _amount(quote.get("total_rub"))
    if total is None or total <= 0 or any(value is None for value in parts):
        reasons.append("margin_all_in_cost_unknown")
    elif parts[0] <= 0 or sum(parts, ZERO) != total:
        reasons.append("margin_all_in_cost_conflict")
    return total, reasons


def _tariff(tariff, account, now):
    tariff = _mapping(tariff)
    valid = (tariff.get("account_id") == account and tariff.get("verified") is True
        and tariff.get("all_charges_known") is True and _identifier(tariff.get("source_id"))
        and _valid_window(tariff.get("observed_at"), tariff.get("expires_at"), now))
    return [] if valid else ["margin_tariff_or_charges_unknown"]


@financial_context
def evaluate_buy(snapshot: dict, quote: dict, tariff: dict | None, *, now: datetime | None = None) -> dict:
    """Calculate the proposed all-in cash bound; never authorize borrowing.

    Quote components must add exactly to total, including commission, accrued
    interest and any known other debit. Tariff provenance is supplied evidence,
    not a claim that a loan is free. Broker limits/collateral remain unchecked.
    """
    now = _clock(now)
    account, cash, pending, effective, identities, reasons = _observation(snapshot, now)
    observation_valid = not reasons
    total, quote_reasons = _quote(quote, account, identities, now)
    reasons.extend(quote_reasons)
    reasons.extend(_tariff(tariff, account, now))
    if not reasons and effective < CASH_FLOOR_RUB:
        reasons.append("margin_existing_commitments_breach_floor")
    projected = effective - total if not reasons else None
    if projected is not None and projected < CASH_FLOOR_RUB:
        reasons.append("margin_proposed_buy_breaches_floor")
    breach, repayment = _repayment(projected)
    result = _base(account, now)
    result.update(state="calculated" if projected is not None else "blocked",
        observed_cash_rub=_text(cash), unreflected_pending_debits_rub=_text(pending),
        cash_after_commitments_rub=_text(effective if observation_valid else None), all_in_buy_rub=_text(total),
        projected_cash_rub=_text(projected), projected_breach_amount_rub=_text(breach),
        required_repayment_if_executed_rub=_text(repayment),
        arithmetic_policy_passed=projected is not None and not reasons,
        reasons=sorted(set(reasons + ["broker_margin_check_required"])))
    return result
