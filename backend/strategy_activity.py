"""Bound repeated reallocations using executed broker operations only."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

try:
    from .volume_contract import decimal, timestamp, financial_context
except ImportError:
    from volume_contract import decimal, timestamp, financial_context


def _trades(snapshot, account, begin, now):
    operations = snapshot.get("operations") or {}
    if operations.get("complete") is not True or timestamp(operations.get("start")) > begin:
        raise ValueError("strategy_operation_window_incomplete")
    if timestamp(operations.get("end")) < now - timedelta(minutes=5):
        raise ValueError("strategy_operation_window_stale")
    result, seen = [], {}
    for row in operations.get("items", []):
        if row.get("account_id") != account or row.get("category") != "trades" or row.get("state") != "OPERATION_STATE_EXECUTED":
            continue
        key = row.get("id")
        if not key or (key in seen and seen[key] != row):
            raise ValueError("strategy_operations_conflicting")
        if key not in seen and begin <= timestamp(row.get("date")) <= now:
            result.append(row)
        seen[key] = row
    return result


@financial_context
def activity_budget(config, snapshot, account, uid, total, now=None):
    now = now or datetime.now(timezone.utc)
    mandate = config["mandate"]
    days = mandate["turnover_window_days"]
    cooldown = mandate["rebalance_cooldown_days"]
    # Use the longer window to inspect the cooldown even when turnover resets earlier.
    begin = now - timedelta(days=max(days, cooldown))
    rows = _trades(snapshot, account, begin, now)
    spent = Decimal(0)
    for row in rows:
        date = timestamp(row["date"])
        if row.get("instrumentUid") == uid and date > now - timedelta(days=cooldown):
            raise ValueError("strategy_rebalance_cooldown")
        if date < now - timedelta(days=days):
            continue
        payment = row.get("payment") or {}
        amount = decimal(payment)
        if amount is None or payment.get("currency") != "RUB":
            raise ValueError("strategy_turnover_amount_unknown")
        spent += abs(amount)
    return max(Decimal(0), total * decimal(mandate["max_discretionary_turnover_percent"]) / 100 - spent)
