"""Next portfolio action, priced by the broker and bound to strategy/snapshot.

Only one funded action per observation is exposed, so independently checked
rows cannot spend the same cash or concentration budget. Sales never finance
buys before the next confirmed broker snapshot. No order API is called.
"""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING

from fastapi import HTTPException

try:
    from . import volume_state as state, volume_purchases as purchases, volume_market as market
    from . import portfolio_details as details
    from .strategy_construction import allocation_policy, target_value, instrument_policy_reasons
    from .strategy_yield import key_rate, yield_filter
    from .investment_links import instrument_link
    from .strategy_activity import activity_budget
    from .volume_contract import decimal, text_number, financial_context, error_code, instrument_currency
except ImportError:
    import volume_state as state
    import volume_purchases as purchases
    import volume_market as market
    import portfolio_details as details
    from strategy_construction import allocation_policy, target_value, instrument_policy_reasons
    from strategy_yield import key_rate, yield_filter
    from investment_links import instrument_link
    from strategy_activity import activity_budget
    from volume_contract import decimal, text_number, financial_context, error_code, instrument_currency

ZERO = Decimal(0)
QUOTE_ALLOWANCE = Decimal("0.01")
ACTIVITY_REASONS = {"strategy_operation_window_incomplete", "strategy_operation_window_stale",
    "strategy_operations_conflicting", "strategy_rebalance_cooldown", "strategy_turnover_amount_unknown"}


def held_values(snapshot, account, uid, kind):
    rows = [row for row in snapshot.get("positions", []) if row.get("account_id") == account]
    current = sum((decimal(row.get("value")) or ZERO for row in rows if row.get("instrument_uid") == uid), ZERO)
    held_class = sum((decimal(row.get("value")) or ZERO for row in rows if row.get("instrument_type") == kind), ZERO)
    # A RUB display valuation of foreign cash is not spendable RUB. Unknown
    # denomination, valuation currency or blocked quantity cannot fund a plan.
    cash = sum((decimal(row.get("value")) or ZERO for row in rows if row.get("instrument_type") == "cash"
                and instrument_currency(row) == "RUB" and isinstance(row.get("value"), dict)
                and row["value"].get("currency") == "RUB"
                and row.get("blocked") is False and decimal(row.get("blocked_quantity")) == ZERO), ZERO)
    return current, held_class, cash


@financial_context
def affordable_target_lots(*, total, current, held_class, cash, unit_cost, lot, visible, config, kind):
    if any(value is None or value < 0 for value in (total, current, held_class, cash, unit_cost)) or unit_cost == 0:
        return 0
    if type(lot) is not int or lot <= 0 or type(visible) is not int or visible < 0:
        return 0
    policy = allocation_policy(config)
    if policy["missing"]:
        return 0
    reserve = max(decimal(config.get("reserve")) or ZERO,
                  total * decimal(policy["weights_percent"]["cash"]) / 100)
    desired = target_value(config, total, kind, held_class, current) - current
    budget = max(ZERO, min(cash - reserve, desired))
    # Leave one percent for the exact fee/NKD quote. A later check can only
    # reduce this amount; no remote-quote monotonicity is assumed.
    return min(1_000_000, visible, int((budget / (unit_cost * lot * (1 + QUOTE_ALLOWANCE))).to_integral_value(rounding=ROUND_FLOOR)))


def _planning_lot_amounts(unit_cost, lot):
    if unit_cost is None or unit_cost <= 0 or type(lot) is not int or lot <= 0:
        return None, None, None
    principal = unit_cost * lot
    allowance = principal * QUOTE_ALLOWANCE
    return principal, allowance, principal + allowance


def _planning_capital(held, minimum, percent):
    if minimum is None or percent is None or percent <= 0:
        return None
    return ((held + minimum) * 100 / percent).quantize(Decimal("0.01"), rounding=ROUND_CEILING)


def _shortfall(required, available):
    return max(ZERO, required - available) if required is not None else None


def _binding_constraints(policy, minimum, visible, rooms):
    limited_by = ["allocation_policy"] if policy["missing"] else []
    if minimum is not None:
        limited_by.extend(code for code, room in rooms if room is not None and room < minimum)
        if visible is not None and visible < 1:
            limited_by.append("visible_liquidity")
    return limited_by


@financial_context
def budget_diagnostics(*, total, current, held_class, cash, config, kind,
                       unit_cost=None, lot=None, visible=None, turnover=None):
    """Explain a planning bound without certifying a broker quote or weakening it.

    Values are decimal text in the strategy currency. Required capital holds the
    existing position/class values fixed and checks only the named constraint;
    it is neither a deposit recommendation nor permission for a purchase.
    """
    policy = allocation_policy(config)
    position_percent = decimal(config.get("limits", {}).get("position_percent"))
    class_percent = decimal(policy["weights_percent"].get(kind)) or ZERO
    reserve = max(decimal(config.get("reserve")) or ZERO,
                  total * decimal(policy["weights_percent"]["cash"]) / 100)
    cash_room = max(ZERO, cash - reserve)
    position_cap = total * position_percent / 100 if position_percent is not None else None
    position_room = max(ZERO, position_cap - current) if position_cap is not None else None
    class_room = max(ZERO, total * class_percent / 100 - held_class)
    desired = target_value(config, total, kind, held_class, current)
    target_gap = max(ZERO, desired - current)
    planning_budget = min(cash_room, target_gap)
    if turnover is not None:
        planning_budget = min(planning_budget, max(ZERO, turnover))
    principal, allowance, minimum = _planning_lot_amounts(unit_cost, lot)
    limited_by = _binding_constraints(policy, minimum, visible,
        (("cash_after_reserve", cash_room), ("position_limit", position_room),
         ("asset_class_target", class_room), ("turnover_budget", turnover)))
    capital = _planning_capital(current, minimum, position_percent)
    class_capital = _planning_capital(held_class, minimum, class_percent)
    amounts = {"account_total": total, "observed_cash": cash, "protected_reserve": reserve,
        "cash_after_reserve": cash_room, "current_position_value": current,
        "position_limit_percent": position_percent, "position_cap_value": position_cap,
        "position_room": position_room, "class_target_percent": class_percent,
        "class_room": class_room, "target_value": desired, "target_gap": target_gap,
        "turnover_budget": turnover, "planning_budget": planning_budget,
        "minimum_lot_principal": principal, "quote_allowance_percent": QUOTE_ALLOWANCE * 100,
        "quote_allowance_amount": allowance, "minimum_lot_planning_amount": minimum,
        "planning_budget_shortfall": _shortfall(minimum, planning_budget),
        "cash_shortfall_at_current_reserve": _shortfall(minimum, cash_room),
        "planning_capital_for_position_limit": capital,
        "capital_shortfall_for_position_limit": _shortfall(capital, total),
        "planning_capital_for_class_target": class_capital}
    return {"schema_version": 1, "currency": config.get("reserve", {}).get("currency", "RUB"),
        **{key: text_number(value) for key, value in amounts.items()},
        "visible_lots": visible, "limited_by": limited_by, "policy_missing": policy["missing"],
        "basis": "planning_bounds_before_exact_broker_cost",
        "quote_allowance_is_actual_fee": False, "broker_all_in_quote": None,
        "broker_quote_lots": None, "automatic_order": False,
        "capital_calculation_scope": "named_constraint_only_existing_holdings_fixed"}


def _book_offer(user, uid):
    with details.BrokerReader(user) as reader:
        book = market.broker_read(reader, "order_book", {"instrumentId": uid, "depth": 1})
    if book.get("instrumentUid") != uid or not purchases.policy.fresh(book.get("orderbookTs"), datetime.now(timezone.utc), 60):
        raise HTTPException(409, "order_book_stale_or_undated")
    if book.get("isConsistent", True) is not True:
        raise HTTPException(409, "order_book_not_consistent")
    rows = book.get("asks")
    if not isinstance(rows, list) or not rows:
        raise HTTPException(409, "order_book_invalid")
    price, quantity = decimal(rows[0].get("price")), decimal(rows[0].get("quantity"))
    if price is None or price <= 0 or quantity is None or quantity < 1 or quantity % 1:
        raise HTTPException(409, "order_book_invalid")
    return price, int(quantity)


def _rate_check(user, config, meta, total_cost, quantity):
    if (config.get("construction") or {}).get("key_rate_mode") != "at_least_key_rate" or meta.get("instrumentType") != "bond":
        return {"passed": True, "applicable": False}
    now = datetime.now(timezone.utc)
    benchmark = key_rate()
    with details.BrokerReader(user) as reader:
        raw = reader.read("coupons", {"instrumentId": meta["uid"], "from": now.isoformat(), "to": meta["maturityDate"]})
    events = raw.get("events")
    if not isinstance(events, list):
        raise ValueError("bond_coupon_schedule_incomplete")
    return yield_filter(config, meta, events, total_cost / quantity, benchmark, now)


def _base_candidate(item, active, snapshot):
    observed = datetime.now(timezone.utc).isoformat()
    return {"instrument_uid": item["uid"], "ticker": item.get("ticker") or "", "name": item.get("name") or item["uid"],
            "instrument_type": item["instrument_type"], "currency": "RUB", "lot": int(decimal(item["lot"])), "lots_checked": 0,
            "suggested_lots": 0, "action": "wait", "constraints_passed": False,
            "recommendation_complete": False, "as_of": observed, "observed_at": observed, "expires_at": None,
            "quote_as_of": None, "budget_diagnostics": None,
            "total_cost": None, "check_id": None, "snapshot_id": snapshot["snapshot_id"],
            "strategy_version": active["version"], "evidence_revision": None,
            "checks": [], "missing_evidence": [],
            "broker_url": instrument_link(item["instrument_type"], item.get("ticker"), item.get("isin"))}


def _exact_budget_reasons(result, config, total, cash, desired, current):
    paid, principal = decimal(result["total_cost"]), decimal(result.get("clean_principal"))
    commission = result.get("estimated_commission") or {}
    fee = decimal(commission)
    reserve = max(decimal(config.get("reserve")) or ZERO,
                  total * decimal(allocation_policy(config)["weights_percent"]["cash"]) / 100)
    if paid is None or paid > min(cash - reserve, max(ZERO, desired - current)):
        return ["exact_quote_exceeds_target_or_reserve"]
    if principal is None or principal <= 0 or fee is None or fee < 0 or str(commission.get("currency")).upper() != "RUB":
        return ["commission_not_verified"]
    if fee / principal * 100 > decimal(config["mandate"]["max_trade_cost_percent"]):
        return ["commission_above_strategy_limit"]
    return []


def _assess_addition(user, item, account, active, snapshot, budget, base):
    uid, kind, config = item["uid"], item["instrument_type"], active["config"]
    total, current, held_class, cash, desired = budget
    price, visible = _book_offer(user, uid)
    with details.BrokerReader(user) as reader:
        meta = market.broker_read(reader, kind + "_by", {"idType": "INSTRUMENT_ID_TYPE_UID", "id": uid}).get("instrument")
    if not isinstance(meta, dict) or meta.get("uid") != uid:
        raise HTTPException(502, "instrument_identity_mismatch")
    meta = {**meta, "instrumentType": kind}
    instrument_reasons = instrument_policy_reasons(meta, base["lot"], config)
    if instrument_reasons:
        base["missing_evidence"] = instrument_reasons
        return base
    settlement = decimal(purchases.settlement_price(meta, purchases.price_quotation(text_number(price))))
    base["budget_diagnostics"] = budget_diagnostics(total=total, current=current, held_class=held_class, cash=cash,
        config=config, kind=kind, unit_cost=settlement, lot=base["lot"], visible=visible)
    lots = affordable_target_lots(total=total, current=current, held_class=held_class, cash=cash,
        unit_cost=settlement, lot=base["lot"], visible=visible, config=config, kind=kind)
    available = activity_budget(config, snapshot, account, uid, total)
    base["budget_diagnostics"] = budget_diagnostics(total=total, current=current, held_class=held_class, cash=cash,
        config=config, kind=kind, unit_cost=settlement, lot=base["lot"], visible=visible, turnover=available)
    lots = min(lots, int((available / (settlement * base["lot"] * (1 + QUOTE_ALLOWANCE))).to_integral_value(rounding=ROUND_FLOOR)))
    base.update(target_value=text_number(desired), current_value=text_number(current))
    if lots == 0:
        base["missing_evidence"] = allocation_policy(config)["missing"] or ["no_whole_lot_within_target_and_reserve"]
        return base
    result = purchases._check_purchase(purchases.PurchaseCheck(account_id=account, instrument_uid=uid,
        lots=lots, limit_price=text_number(price), strategy_version=active["version"]), user, archive=False)
    base.update(lots_checked=lots, as_of=result["as_of"], quote_as_of=result["as_of"], expires_at=result["expires_at"],
        total_cost=result.get("total_cost"), evidence_revision=result.get("evidence_revision"),
        limit_price=text_number(price), quantity=str(lots * base["lot"]), constraints_passed=result["constraints_passed"],
        investor_qualified=result.get("investor_qualified"), investor_tests=result.get("investor_tests", []),
        limitations=result.get("remaining_checks", []), missing_evidence=list(result["reasons"]))
    if not result["constraints_passed"]:
        return base
    base["budget_diagnostics"].update(broker_all_in_quote=result.get("total_cost"), broker_quote_lots=lots)
    base["missing_evidence"] = _exact_budget_reasons(result, config, total, cash, desired, current)
    if (decimal(result["total_cost"]) or ZERO) > available:
        base["missing_evidence"].append("strategy_turnover_limit")
    if base["missing_evidence"]:
        return base
    rate = _rate_check(user, config, meta, decimal(result["total_cost"]), Decimal(lots * base["lot"]))
    base["yield_comparison"] = rate
    if not rate["passed"]:
        base["missing_evidence"].append(rate["reason"])
        return base
    base.update(action="buy", suggested_lots=lots,
        explanation="Докупка до целевой доли с сохранением резерва и лимитов. Это расчёт распределения, а не прогноз доходности.")
    return base


@financial_context
def assess_candidate(user, item, account, active, snapshot):
    uid, kind, config = item["uid"], item["instrument_type"], active["config"]
    base = _base_candidate(item, active, snapshot)
    base["account_id"] = account
    try:
        total = decimal(next((row.get("value") for row in snapshot.get("accounts", []) if row.get("id") == account), None))
        if total is None or total <= 0:
            raise ValueError("account_value_unknown")
        current, held_class, cash = held_values(snapshot, account, uid, kind)
        desired = target_value(config, total, kind, held_class, current)
        base["budget_diagnostics"] = budget_diagnostics(total=total, current=current, held_class=held_class, cash=cash,
            config=config, kind=kind)
        if current > desired and not allocation_policy(config)["missing"]:
            try:
                from .strategy_sales import assess_reduction
            except ImportError:
                from strategy_sales import assess_reduction
            reduction = assess_reduction(user, item, account, active, snapshot, desired, base)
            if reduction.get("expires_at"):
                reduction["quote_as_of"] = reduction.get("as_of")
            return reduction
        if not (config.get("construction") or {}).get("reinvest", True):
            # Cash has no provenance after settlement. Without a verified
            # withdrawal/reserve ledger it must not be silently reinvested.
            base["missing_evidence"] = ["reinvestment_disabled_new_buys_paused"]
            return base
        return _assess_addition(user, item, account, active, snapshot, (total, current, held_class, cash, desired), base)
    except HTTPException as error:
        if error_code(error) in {"automation_paused", "monitoring_connection_changed"}:
            raise
        base["missing_evidence"] = [error_code(error)]
    except ValueError as error:
        code = str(error)
        base["missing_evidence"] = [code if code in ACTIVITY_REASONS else "strategy_calculation_evidence_incomplete"]
    except (KeyError, TypeError):
        base["missing_evidence"] = ["strategy_calculation_evidence_incomplete"]
    return base


def next_action_plan(discovery: dict) -> dict:
    current = [row for row in discovery.get("candidates", []) if row.get("evidence_current")]
    proposed = sorted([row for row in current if row.get("suggested_lots", 0) > 0 and not row.get("missing_evidence")],
                      key=lambda row: row.get("action") != "sell")
    return {"state": "available" if proposed else "waiting", "as_of": discovery.get("as_of"),
            "actions": proposed[:1], "pending": [row for row in discovery.get("candidates", []) if row not in proposed[:1]],
            "one_action_at_a_time": True, "automatic_order": False,
            "source": "T-Invest API + confirmed strategy", "coverage": discovery.get("coverage", {}),
            "explanation": "После операции следующий шаг рассчитывается по обновлённому портфелю. Неподтверждённые продажи не пополняют бюджет покупок."}
