"""Deterministic purchase constraints. No model scores, returns or trading rights."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

try:
    from .credit_evidence import Source, MAXIMUM_CREDIT_LEVEL
    from .volume_contract import decimal, financial_context, instrument_currency, money, text_number, timestamp, ZERO
except ImportError:
    from credit_evidence import Source, MAXIMUM_CREDIT_LEVEL
    from volume_contract import decimal, financial_context, instrument_currency, money, text_number, timestamp, ZERO

try:
    from .portfolio_mandate import mandate_purchase_reasons
except ImportError:
    from portfolio_mandate import mandate_purchase_reasons

POLICY_VERSION = "purchase-constraints-share-aaa-v3"
AXES = ("position", "issuer", "group", "sector", "currency")


def fresh(value, now: datetime, seconds: int) -> bool:
    try:
        return 0 <= (now - timestamp(value)).total_seconds() < seconds
    except (TypeError, ValueError):
        return False


def verified_identity(value, now: datetime) -> bool:
    try:
        return bool(value.get("issuer_id") and value.get("group_id") and Source(**value["source"]).valid(now))
    except (AttributeError, KeyError, TypeError, ValueError):
        return False


def asset_risk_reasons(meta):
    if meta.get("instrumentType") != "etf":
        return []
    try:
        from .fund_policy import fund_reasons
    except ImportError:
        from fund_policy import fund_reasons
    return fund_reasons(meta)


def instrument_reasons(meta: dict, info: dict, config: dict) -> list[str]:
    reasons = asset_risk_reasons(meta)
    kind = meta.get("instrumentType")
    if kind not in {"share", "bond", "etf"}:
        reasons.append("instrument_requires_separate_risk_model")
    exchange = {"REAL_EXCHANGE_MOEX": "MOEX", "REAL_EXCHANGE_RTS": "SPB"}.get(meta.get("realExchange"))
    if exchange is None or not ({exchange, "RU"} & set(config.get("allowed_markets", []))):
        reasons.append("market_not_allowed_or_unknown")
    if meta.get("buyAvailableFlag") is not True or meta.get("apiTradeAvailableFlag") is not True or meta.get("blockedTcaFlag") is True:
        reasons.append("broker_purchase_unavailable")
    if meta.get("forQualInvestorFlag") is True and info.get("qualStatus") is not True:
        reasons.append("broker_qualification_required")
    # The typed instrument already accounts for completed broker tests and
    # returns ONLY missing ones. An older GetInfo observation cannot override it.
    tests = meta.get("requiredTests", [])
    if not isinstance(tests, list) or tests:
        reasons.append("broker_tests_not_confirmed")
    if kind == "bond" and (meta.get("subordinatedFlag") is not False or meta.get("perpetualFlag") is not False):
        reasons.append("complex_bond_not_excluded")
    elif meta.get("subordinatedFlag") is True or meta.get("perpetualFlag") is True:
        reasons.append("complex_bond_not_allowed")
    return reasons


def credit_reasons(assessment: dict, kind: str) -> list[str]:
    if kind == "etf":
        return []  # Fund terms and conservative overlap replace issuer credit scoring.
    rows = assessment.get("ratings", [])
    reasons = []
    if assessment.get("warnings"):
        reasons.append("rating_evidence_incomplete_or_conflicting")
    issuer_rows = [row for row in rows if row.get("subject_kind") == "issuer"]
    if not issuer_rows:
        reasons.append("issuer_rating_required")
    # The owner's new-share rule concerns the issuer's verified national
    # credit rating. An issue rating, a weaker agency's opinion, or an old AAA
    # cannot substitute for the current issuer assessment. Freshness, source
    # authenticity and issuer binding are established by reviewed_credit;
    # warnings from that assessment remain independent hard blockers above.
    if kind == "share" and (not issuer_rows or any(
            type(row.get("level_within_agency")) is not int
            or row["level_within_agency"] != 0 for row in issuer_rows)):
        reasons.append("share_issuer_aaa_required")
    if kind == "bond" and not any(row.get("subject_kind") == "issue" for row in rows):
        reasons.append("issue_rating_required")
    if any(type(row.get("level_within_agency")) is not int
           or not 0 <= row["level_within_agency"] <= MAXIMUM_CREDIT_LEVEL for row in rows):
        reasons.append("rating_below_bbb_or_unknown")
    return reasons


def _row_keys(row: dict) -> dict:
    identity, meta = row.get("verified_identity") or {}, row.get("metadata") or {}
    return {"position": row.get("instrument_uid"), "issuer": identity.get("issuer_id"),
            "group": identity.get("group_id"), "sector": meta.get("sector"),
            "currency": instrument_currency(row)}


def exposure_amounts(snapshot: dict, now: datetime) -> tuple[dict, list[str]]:
    groups = {axis: {} for axis in AXES}
    reasons, seen, total = [], set(), ZERO
    currency = snapshot.get("currency")
    for row in snapshot.get("positions", []):
        key = (row.get("account_id"), row.get("instrument_uid"))
        value = decimal(row.get("value"))
        if key in seen or value is None or value < 0 or (row.get("value") or {}).get("currency") != currency:
            reasons.append("portfolio_values_incomplete_or_conflicting")
            continue
        seen.add(key)
        total += value
        if row.get("instrument_type") == "cash":
            reasons.extend(_add_cash_exposure(row, value, groups))
            continue
        reasons.extend(_add_position_exposures(row, value, groups, now))
    capital = decimal(snapshot.get("capital", {}).get("total"))
    if capital is None or abs(total - capital) > Decimal("0.01"):
        reasons.append("portfolio_total_not_reconciled")
    return groups, reasons


def _add_cash_exposure(row, value, groups):
    denomination = instrument_currency(row)
    if denomination is None:
        return ["portfolio_currency_unknown"]
    groups["currency"][denomination] = groups["currency"].get(denomination, ZERO) + value
    return []


def _add_position_exposures(row, value, groups, now):
    reasons = []
    if not verified_identity(row.get("verified_identity"), now):
        reasons.append("portfolio_identity_unverified")
    for axis, identifier in _row_keys(row).items():
        if not identifier:
            reasons.append("portfolio_" + axis + "_unknown")
        else:
            groups[axis][identifier] = groups[axis].get(identifier, ZERO) + value
    return reasons


def _quote_amount(value: dict, field: str, currency: str):
    item = value.get(field)
    if not isinstance(item, dict) or str(item.get("currency", "")).upper() != currency:
        return None
    return decimal(item)


def cost_basis(quote: dict, capacity: dict, currency: str, lots: int) -> tuple[dict, list[str]]:
    total = _quote_amount(quote, "totalOrderAmount", currency)
    initial = _quote_amount(quote, "initialOrderAmount", currency)
    own = capacity.get("buyLimits") or {}
    available, max_lots = decimal(own.get("buyMoneyAmount")), decimal(own.get("buyMaxLots"))
    reasons = []
    if decimal(quote.get("lotsRequested")) != lots or total is None or initial is None or not ZERO < initial <= total:
        reasons.append("broker_cost_not_verified")
    if str(capacity.get("currency", "")).upper() != currency or available is None or available < 0 or max_lots is None or max_lots < 0 or max_lots % 1:
        reasons.append("own_money_capacity_not_verified")
    elif lots > max_lots or total is not None and total > available:
        reasons.append("insufficient_own_money")
    return {"total": total, "initial": initial, "available": available}, reasons


def _limits(groups: dict, candidate: dict, config: dict, total: Decimal, cost: Decimal) -> tuple[list, list]:
    observations, reasons = [], []
    for axis, key in candidate.items():
        cap = decimal(config.get("limits", {}).get(axis + "_percent"))
        if not key or cap is None or not 0 < cap <= 100:
            reasons.append("candidate_" + axis + "_unverified")
            continue
        before = groups[axis].get(key, ZERO)
        # A same-currency purchase transfers cash into a security. Counting the
        # purchase again would double count that currency. Keeping its pre-trade
        # amount (capped at remaining capital) is conservative after costs.
        after = min(before, total) if axis == "currency" else before + cost
        share = after / total * 100
        observations.append({"axis": axis, "id": key, "amount_before": text_number(before),
                             "share_upper_bound_percent": text_number(share), "limit_percent": text_number(cap)})
        if share > cap:
            reasons.append(axis + "_limit_exceeded")
    return observations, reasons


def _observation_reasons(snapshot, config, meta, identity, observed_at, now):
    currency = str(meta.get("currency", "")).upper()
    reasons = []
    lot = decimal(meta.get("lot"))
    if lot is None or lot <= 0 or lot % 1:
        reasons.append("instrument_lot_invalid")
    if not fresh(observed_at, now, 60) or not fresh(snapshot.get("as_of"), now, 300):
        reasons.append("fresh_observations_required")
    if snapshot.get("position_coverage", {}).get("complete") is not True:
        reasons.append("portfolio_coverage_incomplete")
    if not verified_identity(identity, now):
        reasons.append("candidate_identity_unverified")
    if currency != snapshot.get("currency") or currency != config.get("reserve", {}).get("currency"):
        reasons.append("currency_conversion_not_verified")
    return reasons


def _snapshot_cash(snapshot, account_id, currency):
    return sum((decimal(row.get("value")) or ZERO for row in snapshot.get("positions", [])
        if row.get("instrument_type") == "cash" and row.get("account_id") == account_id
        and instrument_currency(row) == currency), ZERO)


def _funding_and_concentrations(snapshot, config, meta, identity, groups, costs, cost_errors, account_id):
    reasons, observations = [], []
    reserve = decimal(config.get("reserve"))
    if reserve is None or reserve < 0:
        return observations, ["reserve_not_verified"]
    if cost_errors:
        return observations, reasons
    paid, initial, available = costs["total"], costs["initial"], costs["available"]
    currency = str(meta.get("currency", "")).upper()
    observed_cash = _snapshot_cash(snapshot, account_id, currency)
    if observed_cash < paid:
        reasons.append("snapshot_cash_requires_refresh")
    if available - paid < reserve:
        reasons.append("protected_reserve_would_be_spent")
    # Upper bound: all excess above clean principal is treated as lost capital,
    # and all-in cost as added exposure, including accrued interest.
    total = decimal(snapshot.get("capital", {}).get("total"))
    denominator = total - (paid - initial) if total is not None else ZERO
    if denominator <= 0:
        return observations, reasons + ["capital_after_costs_invalid"]
    candidate = {"position": meta.get("uid"), "issuer": (identity or {}).get("issuer_id"),
                 "group": (identity or {}).get("group_id"), "sector": meta.get("sector"),
                 "currency": str(meta.get("currency", "")).upper()}
    groups = {axis: dict(values) for axis, values in groups.items()}
    fund_total = sum((decimal(row.get("value")) or ZERO for row in snapshot.get("positions", [])
                      if row.get("instrument_type") == "etf"), ZERO)
    for axis in ("issuer", "group", "sector"):
        key = candidate[axis]
        if meta.get("instrumentType") == "etf":
            groups[axis][key] = max(groups[axis].values(), default=ZERO) + fund_total
        elif fund_total:
            groups[axis][key] = groups[axis].get(key, ZERO) + fund_total
    observations, breaches = _limits(groups, candidate, config, denominator, paid)
    return observations, reasons + breaches


@financial_context
def assess_purchase(*, snapshot: dict, config: dict, meta: dict, identity: dict,
                    credit: dict, info: dict, quote: dict, capacity: dict,
                    lots: int, account_id: str, observed_at: str, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    if type(lots) is not int or not 1 <= lots <= 1_000_000:
        raise ValueError("whole_positive_lots_required")
    currency = str(meta.get("currency", "")).upper()
    reasons = instrument_reasons(meta, info, config) + credit_reasons(credit, meta.get("instrumentType"))
    reasons.extend(mandate_purchase_reasons(config, meta.get("instrumentType"), account_id, credit))
    reasons.extend(_observation_reasons(snapshot, config, meta, identity, observed_at, now))
    costs, cost_errors = cost_basis(quote, capacity, currency, lots)
    reasons.extend(cost_errors)
    groups, group_errors = exposure_amounts(snapshot, now)
    reasons.extend(group_errors)
    observations, financing_errors = _funding_and_concentrations(snapshot, config, meta, identity, groups, costs, cost_errors, account_id)
    reasons.extend(financing_errors)
    lot = decimal(meta.get("lot"))
    paid, initial, available = costs["total"], costs["initial"], costs["available"]
    return {"policy_version": POLICY_VERSION, "constraints_passed": not reasons, "reasons": sorted(set(reasons)),
            "rating_rule": {"share_issuer_minimum_grade": "AAA", "bond_minimum_grade": "BBB",
                "stricter_owner_mandate_preserved": True,
                "scope": "national_creditworthiness_not_share_price_or_return_guarantee"},
            "lots": lots, "quantity": text_number(lot * lots) if lot is not None else None,
            "total_cost": money(paid, currency), "clean_principal": money(initial, currency),
            "cash_after": money(available - paid, currency) if available is not None and paid is not None else None,
            "concentrations": observations, "concentration_basis": "conservative_all_in_cost_upper_bound",
            "reserve_basis": "full_strategy_reserve_protected_on_selected_account",
            "automatic_order": False, "expected_return": None, "optimality_claimed": False}


@financial_context
def margin_of_safety(price, conservative_value) -> str | None:
    """Graham principle, not a fair-value estimator or an automatic buy signal."""
    current, value = decimal(price), decimal(conservative_value)
    if current is None or value is None or current <= 0 or value <= 0:
        return None
    return text_number((value - current) / value * 100)


