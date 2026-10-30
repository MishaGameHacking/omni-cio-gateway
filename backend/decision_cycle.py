"""Persisted, deterministic decision receipts; no broker transport or model call.

A candidate preview is not an executable investment decision. This layer keeps
that distinction explicit and records why no real order was sent. Callers own
transactions and must revalidate the input lineage before persisting. Evaluation
and hashing happen outside a database write transaction.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import re

try:
    from . import margin_policy
    from .volume_contract import decimal as _amount, financial_context, instrument_currency
except ImportError:
    import margin_policy
    from volume_contract import decimal as _amount, financial_context, instrument_currency

VERSION = 1
MAX_CANDIDATES = 100
_CODE = re.compile(r"[a-z][a-z0-9_]{0,95}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_MESSAGES = {
    "real_order_execution_disabled": "Сервер рассчитывает решения, но отправка реальных торговых поручений не включена.",
    "strategy_required": "Нет сохранённой стратегии для расчёта.",
    "automation_paused": "Автоматический анализ приостановлен; прежний расчёт не применяется.",
    "account_outside_mandate": "Счёт отсутствует в подтверждённом снимке или не соответствует стратегии.",
    "candidate_account_unverified": "Расчёт кандидата не привязан к выбранному счёту.",
    "investment_profile_incomplete": "Не все параметры инвестиционного профиля подтверждены; причины перечислены отдельно.",
    "loss_capacity_not_confirmed": "Не сохранено подтверждение способности переносить инвестиционные потери.",
    "income_stability_unknown": "В стратегии не указана стабильность дохода.",
    "loss_capacity_invalid": "Допустимый размер потерь отсутствует или выходит за пределы 0–100%.",
    "zero_loss_capacity_blocks_new_risk": "В стратегии допустимые потери равны нулю; новые рискованные вложения заблокированы.",
    "fresh_snapshot_required": "Для решения нужен свежий снимок счёта.",
    "portfolio_coverage_incomplete": "Данные портфеля неполные; доступные средства не подтверждены.",
    "broker_connection_required": "Нет действующего подключения брокера.",
    "evidence_revision_required": "Не подтверждена версия проверенных источников.",
    "strategy_changed": "Сохранённое решение относится к прежней версии стратегии.",
    "snapshot_changed": "Портфель изменился после расчёта решения.",
    "evidence_changed": "Источники изменились после расчёта решения.",
    "decision_inputs_changed": "Данные изменились во время расчёта; результат сохранён только для аудита.",
    "candidate_expired": "Срок действия котировки или проверки кандидата истёк.",
    "decision_expired": "Срок действия сохранённого расчёта истёк.",
    "candidate_constraints_failed": "Кандидат не прошёл все проверки ограничений.",
    "investment_research_incomplete": "Инвестиционное обоснование кандидата ещё не завершено.",
    "tax_and_settlement_effects": "Не завершена проверка налогов и расчётов по сделке.",
    "loss_capacity_and_full_investment_profile": "Не завершена проверка способности переносить потери.",
    "investment_thesis_and_valuation": "Не завершена проверка инвестиционного обоснования и стоимости.",
    "no_whole_lot_within_target_and_reserve": "Целого лота в пределах целевой доли и защищённого резерва пока нет.",
    "candidate_quantity_unverified": "Количество бумаг не согласовано с размером лота.",
    "candidate_cost_unverified": "Полная стоимость с комиссией и НКД не подтверждена.",
    "sell_owned_units_unverified": "Не подтверждено достаточное количество собственных незаблокированных бумаг для продажи.",
    "protected_reserve_would_be_spent": "Расчётная покупка затронула бы защищённый резерв.",
    "own_cash_unverified": "Свободный рублёвый остаток собственных средств не подтверждён.",
    "borrowed_cash_not_permitted": "Отрицательный денежный остаток не используется как собственный бюджет.",
    "no_candidates_reviewed": "Проверенных кандидатов в этом цикле ещё нет.",
    "no_action_required": "В этом цикле нет обоснованного действия с целым лотом.",
    "candidate_input_invalid": "Данные кандидата неполные или имеют неверный формат.",
    "discovery_incomplete": "Поиск кандидатов ещё не завершён.",
    "market_price_polling_paused": "Проверка цены ожидает разрешённого торгового окна.",
    "limit_trading_unavailable": "Лимитная торговля сейчас недоступна.",
    "broker_purchase_unavailable": "Брокер не разрешает покупку этого инструмента.",
    "strategy_rebalance_cooldown": "Срок между перестановками в этом инструменте ещё не истёк.",
    "strategy_turnover_limit": "Достигнут лимит оборота стратегии.",
    "issuer_rating_required": "Не подтверждён кредитный рейтинг эмитента.",
    "issue_rating_required": "Не подтверждён кредитный рейтинг выпуска облигации.",
    "cash_floor_breached": "Свежий рублёвый остаток ниже установленного предела −4 999 ₽.",
}


class DecisionCycleError(ValueError):
    pass


def _json(value):
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as error:
        raise DecisionCycleError("decision_inputs_not_json") from error


def _hash(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _clock(now):
    if isinstance(now, datetime):
        if now.tzinfo is None or now.utcoffset() is None:
            raise DecisionCycleError("decision_aware_clock_required")
        now = int(now.timestamp())
    if type(now) is not int or now < 0:
        raise DecisionCycleError("decision_clock_invalid")
    return now


def _stamp(value):
    try:
        if not isinstance(value, str):
            return None
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return int(moment.timestamp()) if moment.tzinfo is not None and moment.utcoffset() is not None else None
    except (ValueError, OverflowError):
        return None


def _iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat() if value is not None else None


def _mapping(value):
    return value if isinstance(value, dict) else {}


def _rows(value):
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _number(value):
    return format(value, "f") if value is not None else None


def _name(value):
    return isinstance(value, str) and 0 < len(value) <= 160 and value.strip() == value


def _codes(values):
    if not isinstance(values, list) or len(values) > 100:
        return ["candidate_input_invalid"]
    return sorted({value if isinstance(value, str) and _CODE.fullmatch(value) else "candidate_input_invalid" for value in values})


def reason(code):
    code = code if isinstance(code, str) and _CODE.fullmatch(code) else "candidate_input_invalid"
    return {"code": code, "message": _MESSAGES.get(code, "Не завершена обязательная проверка данных инструмента.")}


def _lineage(active, snapshot, discovery, evidence_revision, broker_key):
    if not _name(broker_key):
        raise DecisionCycleError("decision_broker_binding_invalid")
    version = (active or {}).get("version")
    snapshot_id = (snapshot or {}).get("snapshot_id")
    return {"broker_key": broker_key, "strategy_version": version if type(version) is int and version > 0 else None,
            "snapshot_id": snapshot_id if _name(snapshot_id) else None,
            "evidence_revision": json.loads(_json(evidence_revision)),
            "strategy_digest": _hash(active), "snapshot_digest": _hash(snapshot), "discovery_digest": _hash(discovery)}


def _selected_account(config, snapshot):
    account = _mapping(config.get("mandate")).get("account_id")
    reasons = []
    accounts = _rows((snapshot or {}).get("accounts"))
    if not _name(account) or account not in [row.get("id") for row in accounts]:
        reasons.append("account_outside_mandate")
    account = account if _name(account) else None
    account_value = next((row.get("value") for row in accounts if row.get("id") == account), None)
    return account, account_value, reasons


def _protected_reserve(config, account_value):
    total = _amount(account_value)
    reserve = _amount(config.get("reserve"))
    reserve_currency = _mapping(config.get("reserve")).get("currency")
    reserve_percent = _amount(_mapping(config.get("construction")).get("reserve_percent", 0))
    if (reserve is None or reserve < 0 or reserve_currency != "RUB" or total is None or total < 0
            or _mapping(account_value).get("currency") != "RUB"
            or reserve_percent is None or not 0 <= reserve_percent <= 100):
        return None
    return max(reserve, total * reserve_percent / 100)


def _ruble_cash_rows(snapshot, account):
    return [row for row in _rows((snapshot or {}).get("positions"))
            if row.get("account_id") == account and row.get("instrument_type") == "cash"
            and instrument_currency({**row, "metadata": _mapping(row.get("metadata"))}) == "RUB"
            and _mapping(row.get("value")).get("currency") == "RUB"]


def _cash_row_amount(row):
    amount, blocked = _amount(row.get("value")), _amount(row.get("blocked_quantity"))
    if amount is None or blocked is None or blocked < 0 or type(row.get("blocked")) is not bool:
        return Decimal(0), "own_cash_unverified"
    if amount < 0:
        return Decimal(0), "borrowed_cash_not_permitted"
    if row.get("blocked") is False and blocked == 0:
        return amount, None
    return Decimal(0), None


def _unblocked_cash(rows):
    cash = Decimal(0)
    reasons = [] if rows else ["own_cash_unverified"]
    seen = set()
    for row in rows:
        identity = row.get("instrument_uid")
        if not _name(identity) or identity in seen:
            reasons.append("own_cash_unverified")
        else:
            seen.add(identity)
        amount, error = _cash_row_amount(row)
        cash += amount
        if error:
            reasons.append(error)
    return cash, reasons


def _funding(active, snapshot):
    config = _mapping((active or {}).get("config"))
    account, account_value, reasons = _selected_account(config, snapshot)
    reserve = _protected_reserve(config, account_value)
    if reserve is None:
        reasons.append("own_cash_unverified")
    cash, cash_reasons = _unblocked_cash(_ruble_cash_rows(snapshot, account))
    reasons.extend(cash_reasons)
    return account, {"observed_unblocked_rub": _number(cash) if not reasons else None,
                     "protected_reserve_rub": _number(reserve),
                     "available_above_reserve_rub": _number(max(Decimal(0), cash - reserve)) if not reasons else None,
                     "performance_calculated": False}, reasons


def _budget_diagnostics(value):
    if (not isinstance(value, dict) or value.get("basis") != "planning_bounds_before_exact_broker_cost"
            or value.get("currency") != "RUB"):
        return None
    fields = ("planning_budget", "minimum_lot_principal", "minimum_lot_planning_amount", "planning_budget_shortfall",
              "position_limit_percent", "position_cap_value", "planning_capital_for_position_limit",
              "capital_shortfall_for_position_limit", "cash_shortfall_at_current_reserve")
    return {**{key: _number(_amount(value.get(key))) for key in fields}, "currency": "RUB",
            "limited_by": _codes(value.get("limited_by", [])), "basis": "planning_bounds_before_exact_broker_cost",
            "quote_allowance_is_actual_fee": False, "automatic_order": False}


def _candidate_lineage_gates(row, lineage, account):
    gates = []
    if not _name(row.get("instrument_uid")):
        gates.append("candidate_input_invalid")
    if row.get("account_id") != account or not _name(account):
        gates.append("candidate_account_unverified")
    if row.get("snapshot_id") != lineage["snapshot_id"] or not lineage["snapshot_id"]:
        gates.append("snapshot_changed")
    if row.get("strategy_version") != lineage["strategy_version"] or lineage["strategy_version"] is None:
        gates.append("strategy_changed")
    if row.get("evidence_revision") != lineage["evidence_revision"] or lineage["evidence_revision"] is None:
        gates.append("evidence_changed")
    return gates


def _candidate_evidence_gates(row, now):
    gates = []
    observed, expiry = _stamp(row.get("as_of")), _stamp(row.get("expires_at"))
    if observed is None or expiry is None or not observed <= now < expiry or not 0 < expiry - observed <= 300:
        gates.append("candidate_expired")
    if row.get("constraints_passed") is not True:
        gates.append("candidate_constraints_failed")
    if row.get("recommendation_complete") is not True:
        gates.append("investment_research_incomplete")
    return gates, expiry


def _candidate_quantity_gates(row):
    gates = []
    action, lots, lot = row.get("action"), row.get("suggested_lots"), row.get("lot")
    if action not in ("buy", "sell"):
        gates.append("no_action_required")
    if type(lots) is not int or not 1 <= lots <= 1_000_000:
        gates.append("no_whole_lot_within_target_and_reserve")
    quantity_valid = type(lot) is int and 1 <= lot <= 1_000_000 and type(lots) is int and _amount(row.get("quantity")) == lots * lot
    if not quantity_valid:
        gates.append("candidate_quantity_unverified")
    return gates, quantity_valid


def _candidate_owned_sale_gates(row, snapshot, account, quantity_valid):
    if row.get("action") != "sell":
        return []
    held = [position for position in _rows((snapshot or {}).get("positions"))
            if position.get("account_id") == account and position.get("instrument_uid") == row.get("instrument_uid")]
    units = _amount(held[0].get("quantity")) if len(held) == 1 else None
    blocked = _amount(held[0].get("blocked_quantity")) if len(held) == 1 else None
    if (not quantity_valid or len(held) != 1 or held[0].get("blocked") is not False
            or units is None or blocked is None or not 0 <= blocked <= units or units - blocked < row["suggested_lots"] * row["lot"]):
        return ["sell_owned_units_unverified"]
    return []


def _candidate_cost_gates(row, cash):
    gates = []
    cost = _amount(row.get("total_cost"))
    currency = _mapping(row.get("total_cost")).get("currency")
    currency = currency if isinstance(currency, str) and re.fullmatch(r"[A-Z]{3}", currency) else None
    if cost is None or cost <= 0 or currency != "RUB":
        gates.append("candidate_cost_unverified")
    elif row.get("action") == "buy":
        available = _amount(cash["available_above_reserve_rub"])
        if available is None:
            gates.append("own_cash_unverified")
        elif cost > available:
            gates.append("protected_reserve_would_be_spent")
    return gates, cost, currency


def _candidate(row, lineage, account, cash, snapshot, now):
    row = _mapping(row)
    missing = _codes(row.get("missing_evidence", []))
    limitations = _codes(row.get("limitations", []))
    gates = _candidate_lineage_gates(row, lineage, account)
    evidence_gates, expiry = _candidate_evidence_gates(row, now)
    quantity_gates, quantity_valid = _candidate_quantity_gates(row)
    owned_sale_gates = _candidate_owned_sale_gates(row, snapshot, account, quantity_valid)
    cost_gates, cost, currency = _candidate_cost_gates(row, cash)
    gates.extend(evidence_gates + quantity_gates + owned_sale_gates + cost_gates)
    action, lots, lot = row.get("action"), row.get("suggested_lots"), row.get("lot")
    codes = sorted(set(missing + limitations + gates))
    return {"instrument_uid": row.get("instrument_uid") if _name(row.get("instrument_uid")) else None,
            "account_id": account, "action": action if action in ("buy", "sell") else "wait",
            "suggested_lots": lots if type(lots) is int and 0 <= lots <= 1_000_000 else 0,
            "lot": lot if type(lot) is int and lot > 0 else None,
            "total_cost": {"amount": _number(cost), "currency": currency} if cost is not None else None,
            "expires_at": _iso(expiry), "constraints_passed": row.get("constraints_passed") is True,
            "recommendation_complete": row.get("recommendation_complete") is True,
            "missing_evidence": missing, "limitations": limitations, "decision_blockers": codes,
            "preview_eligible": not codes, "budget_diagnostics": _budget_diagnostics(row.get("budget_diagnostics"))}


def _identity(value):
    core = {key: value[key] for key in ("schema_version", "input_digest", "expires_at", "state", "no_op",
                  "execution", "blockers", "candidates", "proposed_action", "cash")}
    # Re-reading identical evidence does not create a new decision every second.
    core["margin"] = {key: item for key, item in value["margin"].items() if key != "evaluated_at"}
    return _hash(core)


def _lineage_blockers(lineage, discovery, evidence_revision, broker_key):
    blockers = []
    if lineage["strategy_version"] is None:
        blockers.append("strategy_required")
    if broker_key == "disconnected":
        blockers.append("broker_connection_required")
    if not isinstance(evidence_revision, dict) or not evidence_revision:
        blockers.append("evidence_revision_required")
    if discovery.get("snapshot_id") not in (None, lineage["snapshot_id"]):
        blockers.append("snapshot_changed")
    if discovery.get("strategy_version") not in (None, lineage["strategy_version"]):
        blockers.append("strategy_changed")
    return blockers


def _snapshot_blockers(snapshot, now):
    blockers = []
    observed = _stamp((snapshot or {}).get("as_of"))
    if observed is None or not observed <= now < observed + 300:
        blockers.append("fresh_snapshot_required")
    if _mapping((snapshot or {}).get("position_coverage")).get("complete") is not True:
        blockers.append("portfolio_coverage_incomplete")
    for field in ("accounts", "positions"):
        records = (snapshot or {}).get(field)
        if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
            blockers.append("candidate_input_invalid")
    return blockers, observed


def _profile_blockers(active):
    config = _mapping((active or {}).get("config"))
    construction = _mapping(config.get("construction"))
    capacity = _amount(_mapping(config.get("mandate")).get("loss_capacity_percent"))
    reasons = []
    if construction.get("loss_capacity_confirmed") is not True:
        reasons.append("loss_capacity_not_confirmed")
    if construction.get("income_stability") not in ("stable", "variable"):
        reasons.append("income_stability_unknown")
    if capacity is None or not 0 <= capacity <= 100:
        reasons.append("loss_capacity_invalid")
    if reasons:
        reasons.insert(0, "investment_profile_incomplete")
    if capacity == 0:
        reasons.append("zero_loss_capacity_blocks_new_risk")
    return reasons


def _select_proposed(candidates, discovery, blockers):
    if not candidates:
        blockers.append("no_candidates_reviewed")
        blockers.extend(_codes([row.get("code") for row in _rows(discovery.get("reasons"))]))
    eligible = sorted([row for row in candidates if row["preview_eligible"]],
                      key=lambda row: (row["action"] != "sell", row["instrument_uid"]))
    if not eligible and candidates:
        blockers.extend(code for row in candidates for code in row["decision_blockers"])
    return eligible[0] if eligible and not blockers else None


def _decision_expiry(observed, proposed, candidates, now):
    deadlines = [observed + 300] if observed is not None else []
    if proposed is not None:
        deadlines.append(_stamp(proposed["expires_at"]))
    else:
        deadlines.extend(_stamp(row["expires_at"]) for row in candidates
                         if _stamp(row["expires_at"]) is not None and _stamp(row["expires_at"]) > now)
    return _iso(min(deadlines)) if deadlines else None


@financial_context
def evaluate(active, snapshot, discovery, evidence_revision, now, broker_key):
    """Evaluate already collected facts without fetching, trading or spending."""
    observation_clock = now if isinstance(now, datetime) else datetime.fromtimestamp(_clock(now), timezone.utc)
    now = _clock(now)
    for value in (active, snapshot, discovery):
        if value is not None and not isinstance(value, dict):
            raise DecisionCycleError("decision_object_required")
    discovery = discovery or {}
    lineage = _lineage(active, snapshot, discovery, evidence_revision, broker_key)
    blockers = _lineage_blockers(lineage, discovery, evidence_revision, broker_key)
    snapshot_blockers, observed = _snapshot_blockers(snapshot, now)
    blockers.extend(snapshot_blockers + _profile_blockers(active))
    account, cash, funding_reasons = _funding(active, snapshot)
    blockers.extend(funding_reasons)
    margin = margin_policy.observe_portfolio(snapshot, account, now=observation_clock)
    if margin["fresh"] and margin["observed_floor_breached"] is True:
        blockers.append("cash_floor_breached")
    rows = discovery.get("candidates", [])
    if not isinstance(rows, list) or len(rows) > MAX_CANDIDATES:
        raise DecisionCycleError("decision_candidate_count_invalid")
    candidates = [_candidate(row, lineage, account, cash, snapshot, now) for row in rows]
    proposed = _select_proposed(candidates, discovery, blockers)
    state = "blocked" if blockers else "waiting"
    if proposed:
        state = "preview_available"
    result = {"schema_version": VERSION, "input_digest": _hash(lineage), "evaluated_at": _iso(now),
              "expires_at": _decision_expiry(observed, proposed, candidates, now),
              "lineage": lineage, "state": state, "no_op": True,
              "execution": {"mode": "read_only", "real_orders_enabled": False, "reason": "real_order_execution_disabled"},
              "blockers": [reason(code) for code in sorted(set(blockers + ["real_order_execution_disabled"]))],
              "candidates": candidates, "proposed_action": proposed, "cash": cash, "margin": margin}
    result["cycle_id"] = _identity(result)
    return result


def initialize_in(db):
    """Caller owns the short schema transaction; never commits an outer one."""
    db.execute("""CREATE TABLE IF NOT EXISTS portfolio_decision_cycles (
        user_id INTEGER NOT NULL,broker_key TEXT NOT NULL,cycle_id TEXT NOT NULL,
        input_digest TEXT NOT NULL,evaluated_at INTEGER NOT NULL,payload_json TEXT NOT NULL,
        PRIMARY KEY(user_id,broker_key,cycle_id))""")
    db.execute("CREATE INDEX IF NOT EXISTS portfolio_decision_cycles_latest ON portfolio_decision_cycles(user_id,broker_key,evaluated_at DESC)")


def invalidate(result, codes):
    """Preserve evaluated input lineage and append an immutable blocked outcome."""
    invalid = json.loads(_json(result))
    reasons = {row["code"] for row in invalid["blockers"]} | set(_codes(codes))
    invalid.update(state="blocked", proposed_action=None, no_op=True,
                   blockers=[reason(code) for code in sorted(reasons)])
    for candidate in invalid["candidates"]:
        candidate["preview_eligible"] = False
    _invalidate_margin(invalid, codes)
    invalid["cycle_id"] = _identity(invalid)
    return invalid


def _invalidate_margin(result, codes):
    margin = result["margin"]
    margin.update(state="stale", fresh=False, observed_floor_breached=None,
                  minimum_observed_shortfall_rub=None,
                  reasons=sorted(set(margin["reasons"]) | set(codes)))


def persist_in(db, user_id, result):
    """Append once; the caller must compare current DB lineage in this transaction."""
    if type(user_id) is not int or user_id <= 0 or not isinstance(result, dict):
        raise DecisionCycleError("decision_receipt_invalid")
    try:
        valid = (result["schema_version"] == VERSION and _HASH.fullmatch(result["input_digest"])
                 and result["input_digest"] == _hash(result["lineage"])
                 and result["cycle_id"] == _identity(result)
                 and result["execution"] == {"mode": "read_only", "real_orders_enabled": False, "reason": "real_order_execution_disabled"}
                 and result["no_op"] is True and _name(result["lineage"]["broker_key"]))
        at = _stamp(result["evaluated_at"])
    except (KeyError, TypeError):
        valid, at = False, None
    if not valid or at is None:
        raise DecisionCycleError("decision_receipt_invalid")
    cursor = db.execute("INSERT OR IGNORE INTO portfolio_decision_cycles VALUES(?,?,?,?,?,?)",
                        (user_id, result["lineage"]["broker_key"], result["cycle_id"], result["input_digest"], at, _json(result)))
    return cursor.rowcount == 1


def latest(db, user_id, broker_key, active, snapshot, evidence_revision, now, *, enabled=True):
    """Read and invalidate stale display state without changing the audit record."""
    now = _clock(now)
    row = db.execute("""SELECT payload_json FROM portfolio_decision_cycles WHERE user_id=? AND broker_key=?
        ORDER BY evaluated_at DESC,rowid DESC LIMIT 1""", (user_id, broker_key)).fetchone()
    if row is None:
        return None
    result = json.loads(row[0])
    lineage = result["lineage"]
    invalid = []
    if enabled is not True:
        invalid.append("automation_paused")
    if lineage["strategy_version"] != (active or {}).get("version") or lineage["strategy_digest"] != _hash(active):
        invalid.append("strategy_changed")
    if lineage["snapshot_id"] != (snapshot or {}).get("snapshot_id") or lineage["snapshot_digest"] != _hash(snapshot):
        invalid.append("snapshot_changed")
    if lineage["evidence_revision"] != evidence_revision:
        invalid.append("evidence_changed")
    expiry, evaluated = _stamp(result.get("expires_at")), _stamp(result.get("evaluated_at"))
    if expiry is None or expiry <= now or evaluated is None or evaluated > now:
        invalid.append("decision_expired")
    result["current"] = not invalid
    result["historical_state"] = result["state"]
    if invalid:
        codes = {row["code"] for row in result["blockers"]} | set(invalid)
        result.update(state="blocked", proposed_action=None, no_op=True,
                      blockers=[reason(code) for code in sorted(codes)])
        for candidate in result["candidates"]:
            candidate["preview_eligible"] = False
        _invalidate_margin(result, invalid)
    return result

