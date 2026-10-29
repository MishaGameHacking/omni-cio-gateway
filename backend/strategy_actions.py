"""Next portfolio action, priced by the broker and bound to strategy/snapshot.

Only one funded action per observation is exposed, so independently checked
rows cannot spend the same cash or concentration budget. Sales never finance
buys before the next confirmed broker snapshot. No order API is called.
"""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_FLOOR

from fastapi import HTTPException

try:
    from . import volume_state as state, volume_purchases as purchases, volume_market as market
    from . import portfolio_details as details
    from .strategy_construction import allocation_policy, target_value
    from .strategy_yield import key_rate, yield_filter
    from .investment_links import instrument_link
    from .volume_contract import decimal, text_number, financial_context, error_code, timestamp
except ImportError:
    import volume_state as state
    import volume_purchases as purchases
    import volume_market as market
    import portfolio_details as details
    from strategy_construction import allocation_policy, target_value
    from strategy_yield import key_rate, yield_filter
    from investment_links import instrument_link
    from volume_contract import decimal, text_number, financial_context, error_code, timestamp

ZERO = Decimal(0)


def held_values(snapshot, account, uid, kind):
    rows = [row for row in snapshot.get("positions", []) if row.get("account_id") == account]
    current = sum((decimal(row.get("value")) or ZERO for row in rows if row.get("instrument_uid") == uid), ZERO)
    held_class = sum((decimal(row.get("value")) or ZERO for row in rows if row.get("instrument_type") == kind), ZERO)
    cash = sum((decimal(row.get("value")) or ZERO for row in rows if row.get("instrument_type") == "cash"
                and not row.get("blocked") and (decimal(row.get("blocked_quantity")) or ZERO) == 0), ZERO)
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
    return min(1_000_000, visible, int((budget / (unit_cost * lot * Decimal("1.01"))).to_integral_value(rounding=ROUND_FLOOR)))


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


@financial_context
def assess_candidate(user, item, account, active, snapshot):
    uid, kind, config = item["uid"], item["instrument_type"], active["config"]
    lot = int(decimal(item["lot"]))
    base = {"instrument_uid": uid, "ticker": item.get("ticker") or "", "name": item.get("name") or uid,
            "instrument_type": kind, "currency": "RUB", "lot": lot, "lots_checked": 0,
            "suggested_lots": 0, "action": "wait", "constraints_passed": False,
            "recommendation_complete": False, "as_of": None, "expires_at": None,
            "total_cost": None, "check_id": None, "snapshot_id": snapshot["snapshot_id"],
            "strategy_version": active["version"], "evidence_revision": None,
            "checks": [], "missing_evidence": [], "broker_url": instrument_link(kind, item.get("ticker"), item.get("isin"))}
    try:
        total = decimal(next((row.get("value") for row in snapshot.get("accounts", []) if row.get("id") == account), None))
        current, held_class, cash = held_values(snapshot, account, uid, kind)
        desired = target_value(config, total, kind, held_class, current) if total is not None else None
        if desired is not None and current > desired and not allocation_policy(config)["missing"]:
            try:
                from .strategy_sales import assess_reduction
            except ImportError:
                from strategy_sales import assess_reduction
            return assess_reduction(user, item, account, active, snapshot, desired, base)
        price, visible = _book_offer(user, uid)
        with details.BrokerReader(user) as reader:
            meta = market.broker_read(reader, kind + "_by", {"idType": "INSTRUMENT_ID_TYPE_UID", "id": uid}).get("instrument")
        if not isinstance(meta, dict) or meta.get("uid") != uid:
            raise HTTPException(502, "instrument_identity_mismatch")
        meta = {**meta, "instrumentType": kind}
        total = decimal(next((row.get("value") for row in snapshot.get("accounts", []) if row.get("id") == account), None))
        current, held_class, cash = held_values(snapshot, account, uid, kind)
        settlement = decimal(purchases.settlement_price(meta, purchases.price_quotation(text_number(price))))
        lots = affordable_target_lots(total=total, current=current, held_class=held_class, cash=cash,
            unit_cost=settlement, lot=lot, visible=visible, config=config, kind=kind)
        base["target_value"] = text_number(target_value(config, total, kind, held_class, current)) if total is not None else None
        base["current_value"] = text_number(current)
        if lots == 0:
            base["missing_evidence"] = allocation_policy(config)["missing"] or ["no_whole_lot_within_target_and_reserve"]
            return base
        result = purchases._check_purchase(purchases.PurchaseCheck(account_id=account, instrument_uid=uid,
            lots=lots, limit_price=text_number(price), strategy_version=active["version"]), user, archive=False)
        base.update(lots_checked=lots, as_of=result["as_of"], expires_at=result["expires_at"],
            total_cost=result.get("total_cost"), evidence_revision=result.get("evidence_revision"),
            limit_price=text_number(price), quantity=str(lots * lot), constraints_passed=result["constraints_passed"],
            investor_qualified=result.get("investor_qualified"), investor_tests=result.get("investor_tests", []))
        base["missing_evidence"] = list(result["reasons"])
        if result["constraints_passed"]:
            paid = decimal(result["total_cost"])
            principal = decimal(result.get("clean_principal"))
            reserve = max(decimal(config.get("reserve")) or ZERO,
                total * decimal(allocation_policy(config)["weights_percent"]["cash"]) / 100)
            max_cost = decimal(config["mandate"]["max_trade_cost_percent"])
            if paid > min(cash - reserve, max(ZERO, desired - current)) or principal is None or principal <= 0 or (paid - principal) / principal * 100 > max_cost:
                base["missing_evidence"] = ["exact_quote_exceeds_target_reserve_or_cost_limit"]
                return base
            rate = _rate_check(user, config, meta, decimal(result["total_cost"]), Decimal(lots * lot))
            base["yield_comparison"] = rate
            if not rate["passed"]:
                base["missing_evidence"].append(rate["reason"])
            else:
                base.update(action="buy", suggested_lots=lots,
                    explanation="Докупка до целевой доли с сохранением резерва и лимитов. Перепроверьте итоговую цену и налоговые последствия у брокера.")
        # This is a constrained allocation instruction, not a claim that a
        # valuation thesis, personal tax calculation, or prediction is complete.
        base["limitations"] = result.get("remaining_checks", [])
    except HTTPException as error:
        if error_code(error) in {"automation_paused", "monitoring_connection_changed"}:
            raise
        base["missing_evidence"] = [error_code(error)]
    except (ValueError, KeyError, TypeError):
        base["missing_evidence"] = ["strategy_calculation_evidence_incomplete"]
    return base


def next_action_plan(discovery: dict) -> dict:
    current = [row for row in discovery.get("candidates", []) if row.get("evidence_current")]
    proposed = [row for row in current if row.get("suggested_lots", 0) > 0 and not row.get("missing_evidence")]
    return {"state": "available" if proposed else "waiting", "as_of": discovery.get("as_of"),
            "actions": proposed[:1], "pending": [row for row in discovery.get("candidates", []) if row not in proposed[:1]],
            "one_action_at_a_time": True, "automatic_order": False,
            "source": "T-Invest API + confirmed strategy", "coverage": discovery.get("coverage", {}),
            "explanation": "После операции следующий шаг рассчитывается по обновлённому портфелю. Неподтверждённые продажи не пополняют бюджет покупок."}
