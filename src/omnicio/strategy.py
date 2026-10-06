"""Versioned strategy templates and exact, bounded scenario calculations.

Templates are explicit engineering policies, not calibrated return forecasts.
This module has no network, account authority, or broker execution capability.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from decimal import ROUND_FLOOR, Decimal, InvalidOperation
from typing import Any, cast

CATALOG_VERSION = "2026-10-06.1"
ALLOCATION_KEYS = ("shares", "bonds", "funds", "cash")
RATING_LEVELS = (
    "AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-",
    "BB+", "BB", "BB-", "B+", "B", "B-", "CCC+", "CCC", "CCC-", "CC", "C",
    "SD", "RD", "D", "NR",
)
# Display buckets are not a cross-agency equivalence or default-probability model.
PROFILE_LIMITS = {
    "reserve_rub": ("1000000000000", 8),
    "planned_withdrawal_rub": ("1000000000000", 8),
    "horizon_months": ("1200", 0),
    "max_drawdown_percent": ("100", 4),
    "liquidity_horizon_days": ("36500", 0),
}
POLICY_KEYS = (
    "max_instrument_percent", "max_sector_percent", "max_issuer_percent",
    "max_group_percent", "max_share_percent", "max_bond_percent", "max_etf_percent",
    "max_below_grade_percent", "max_unknown_percent", "max_term_months",
    "turnover_budget_percent", "max_daily_turnover_participation_percent",
    "securities_tax_rate_percent", "uncertainty_haircut_percent",
    "credit_loss_haircut_percent", "no_trade_band_percent", "min_replace_benefit_rub",
)
PERSONAL_FIELDS = {"reserve_rub", "planned_withdrawal_rub", "securities_tax_rate_percent"}
SOURCES = (
    {"id": "buffett1989", "title": "Berkshire Hathaway: письмо 1989 года",
     "url": "https://www.berkshirehathaway.com/letters/1989.html"},
    {"id": "buffett2013", "title": "Berkshire Hathaway: письмо 2013 года",
     "url": "https://www.berkshirehathaway.com/letters/2013ltr.pdf"},
    {"id": "vanguard", "title": "Vanguard: цели, распределение, расходы, дисциплина",
     "url": "https://ownyourfuture.vanguard.com/content/en/learn/financial-planning/vanguards-4-principles-for-investing-success.html"},
    {"id": "allweather", "title": "Bridgewater: The All Weather Story",
     "url": "https://www.bridgewater.com/research-and-insights/the-all-weather-story"},
    {"id": "cvar", "title": "Rockafellar–Uryasev: условный риск потерь (CVaR)",
     "url": "https://sites.math.washington.edu/~rtr/papers/rtr179-CVaR1.pdf"},
    {"id": "overfit", "title": "Bailey и соавторы: переобучение при проверке стратегий",
     "url": "https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf"},
    {"id": "acra", "title": "АКРА: определения рейтинговых шкал",
     "url": "https://www.acra-ratings.ru/about-ratings/scales/"},
)
# Values below describe different mandates. They have NOT been optimized against
# market history. Precision is constrained by the existing financial contracts.
_CATEGORY_BASE = "Базовые"
_CATEGORY_GOAL = "По задачам"
_CATEGORY_INVESTOR = "Именные"
_SPECS = (
    ("income", "Доход", _CATEGORY_BASE, (10, 70, 10, 10), 60, 20, 60, 5,
     "cashflow", "Планирование поступлений с контролем сроков и источников выплат.",
     "Высокий купон сам по себе не делает выпуск подходящим. Погашение не "
         "считается доходом.", "vanguard"),
    ("growth", "Накопление", _CATEGORY_BASE, (55, 25, 10, 10), 120, 35, 120, 5,
     "growth", "Длинный срок, пополнения и ограничение лишних перестроек.",
     "Большая доля акций может привести к сильному и длительному снижению стоимости.", "vanguard"),
    ("balanced", "Сочетание", _CATEGORY_BASE, (30, 50, 10, 10), 84, 25, 84, 5,
     "balanced", "Соединяет рост капитала и облигационную часть без выбора одной цели за вас.",
     "Акции и облигации могут дешеветь одновременно; название не означает "
         "защиту капитала.", "vanguard"),
    ("near_goal", "Ближайшая цель", _CATEGORY_GOAL, (0, 60, 0, 40), 12, 10, 12, 3,
     "liability", "Условия для цели с известным сроком: короткий горизонт и больше "
         "свободных денег.",
     "Даже короткая облигация может не погаситься. Резерв и предстоящие "
         "снятия уточняются отдельно.", "cvar"),
    ("ladder", "Лестница погашений", _CATEGORY_GOAL, (0, 85, 0, 15), 60, 15, 60, 4,
     "ladder", "Подход к распределению погашений по срокам. Подбор самих выпусков "
         "ещё требует календаря.",
     "При малой сумме не каждая ступень достижима. Неизвестные будущие "
         "ставки не угадываются.", "cvar"),
    ("floating", "Переменная ставка", _CATEGORY_GOAL, (0, 80, 10, 10), 36, 15, 36, 4,
     "floating", "Отдельный подход к бумагам с пересматриваемым купоном.",
     "Нужны формула купона, лаг, надбавка и ограничения. Старый купон не "
         "обещает будущую доходность.", "cvar"),
    ("dividends", "Дивиденды и качество", _CATEGORY_GOAL, (60, 20, 10, 10), 120, 35, 60, 5,
     "dividends", "Для изучения бизнеса с выплатами, источников денег и долговой нагрузки.",
     "Дивиденды могут отменить. Без отчётности и решения о выплате "
         "персональный подбор не готов.", "buffett1989"),
    ("buffett", "Уоррен Баффетт · качество", _CATEGORY_INVESTOR, (70, 10, 10, 10), 120, 40, 36, 5,
     "quality_value", "Адаптация принципов: качество бизнеса, понятность и дисциплина цены.",
     "Это не портфель Berkshire и не оригинальная рекомендация Баффетта "
         "для рынка РФ. Нужна оценка бизнеса.", "buffett1989"),
    ("bogle", "Джон Богл · широкий рынок", _CATEGORY_INVESTOR, (0, 20, 70, 10), 120, 35, 60, 5,
     "index_cost", "Адаптация принципов широкого покрытия рынка и контроля расходов фондов.",
     "Фонд может быть концентрированным. Лимиты компаний проверяются по "
         "его составу, не названию.", "vanguard"),
    ("dalio", "Рэй Далио · баланс рисков", _CATEGORY_INVESTOR, (20, 50, 20, 10), 120, 25, 120, 5,
     "regime_risk", "Адаптация идеи проверки разных сочетаний роста экономики и инфляции.",
     "Не копия All Weather. Без чувствительности инструментов к факторам "
         "баланс риска не подтверждён.", "allweather"),
)


def _number(value: object, maximum: str = "100", places: int = 4) -> str | None:
    """Keep unknown distinct from zero; accept only finite exact decimal text."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("strategy_decimal_format")
    text = str(value)
    if len(text) > 40 or not text or any(c not in "0123456789." for c in text):
        raise ValueError("strategy_decimal_format")
    try:
        parsed = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("strategy_decimal_format") from exc
    if not parsed.is_finite() or not 0 <= parsed <= Decimal(maximum):
        raise ValueError("strategy_decimal_bounds")
    parts = parsed.as_tuple()
    significant = list(parts.digits)
    trailing = 0
    while significant and significant[-1] == 0:
        significant.pop()
        trailing += 1
    if parsed and -int(parts.exponent) - trailing > places:
        raise ValueError("strategy_decimal_precision")
    result = format(parsed, "f")
    return result.rstrip("0").rstrip(".") if "." in result else result


def _template(spec: tuple[Any, ...]) -> dict[str, Any]:
    (ident, title, category, allocation, horizon, drawdown, term, issuer,
     method, text, risk, source) = spec
    caps = dict.fromkeys(RATING_LEVELS, "0")
    for grade in RATING_LEVELS[:7]:
        caps[grade] = "100"  # Ceilings, not required weights and not probabilities.
    for grade in RATING_LEVELS[7:10]:
        caps[grade] = "10" if ident not in {"near_goal", "floating"} else "0"
    values = (str(issuer), "25", str(issuer), str(issuer * 2), str(allocation[0]),
              str(allocation[1]), str(allocation[2]), "0", "0", str(term), "10", "5",
              None, "3", "2", "1", "500")
    document = {
        "base_preset_id": ident, "catalog_version": CATALOG_VERSION, "customized": False,
        "allocation": dict(zip(ALLOCATION_KEYS, allocation, strict=True)),
        "locked": [], "excluded": [],
        "profile": {"reserve_rub": None, "planned_withdrawal_rub": None,
                    "horizon_months": str(horizon), "max_drawdown_percent": str(drawdown),
                    "liquidity_horizon_days": "5", "allow_below_investment_grade": False},
        "policy": dict(zip(POLICY_KEYS, values, strict=True)),
        "rules": {"rating_caps": caps, "yield_floor": "key_rate" if ident == "income" else "none",
                  "yield_margin_pp": "0",
                      "fund_wrapper_cap_percent": "70" if ident == "bogle" else "20"},
    }
    return {"id": ident, "title": title, "category": category, "method": method,
            "description": text, "risk": risk, "source_ids": [source], "document": document,
            "calibration": "not_calibrated", "probability_of_profit": None,
            "parameter_basis": "Явные исходные условия модели; не оптимум, найденный на истории "
                "рынка."}


def strategy_catalog() -> dict[str, Any]:
    return {"version": CATALOG_VERSION, "default_id": "balanced",
        "sources": copy.deepcopy(list(SOURCES)),
            "presets": [_template(spec) for spec in _SPECS], "rating_levels": list(RATING_LEVELS),
            "sample_illustration": {"successes": 100, "trials": 100,
                                    "wilson_lower_95": wilson_interval(100, 100)[0],
                                    "scope": "Условные независимые испытания, не рыночная "
                                        "история и не прогноз"},
            "note": "10 редактируемых подходов. Доходность и вероятность успеха не гарантируются. "
                    "Сохранение черновика не меняет подтверждённые условия и не создаёт сделок."}


def preset_document(preset_id: str) -> dict[str, Any]:
    for spec in _SPECS:
        if spec[0] == preset_id:
            return cast(dict[str, Any], _template(spec)["document"])
    raise ValueError("strategy_preset_unknown")


def _exact_keys(value: object, keys: Sequence[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError("strategy_fields_invalid")
    return value


def _allocation_flags(data: dict[str, Any]) -> dict[str, Any]:
    allocation = _exact_keys(data["allocation"], ALLOCATION_KEYS)
    if any(type(v) is not int or not 0 <= v <= 100 for v in allocation.values()):
        raise ValueError("strategy_allocation_invalid")
    if sum(allocation.values()) != 100:
        raise ValueError("strategy_allocation_total")
    result: dict[str, Any] = {"allocation": dict(allocation)}
    for name in ("locked", "excluded"):
        items = data[name]
        if (not isinstance(items, list) or len(items) > 4
                or any(not isinstance(k, str) or k not in ALLOCATION_KEYS for k in items)
                or len(set(items)) != len(items)):
            raise ValueError("strategy_allocation_flags")
        result[name] = sorted(items)
    if any(allocation[key] != 0 for key in result["excluded"]):
        raise ValueError("strategy_excluded_weight")
    if set(result["excluded"]) & set(result["locked"]):
        raise ValueError("strategy_excluded_lock")
    return result


def _profile_values(value: object) -> dict[str, Any]:
    profile = _exact_keys(value, (*PROFILE_LIMITS, "allow_below_investment_grade"))
    if type(profile["allow_below_investment_grade"]) is not bool:
        raise ValueError("strategy_permission_invalid")
    result = dict(profile)
    for key, (maximum, places) in PROFILE_LIMITS.items():
        result[key] = _number(profile[key], maximum, places)
    if result["horizon_months"] == "0":
        raise ValueError("strategy_horizon_invalid")
    return result


def _policy_values(value: object) -> dict[str, Any]:
    policy = _exact_keys(value, POLICY_KEYS)
    result = {}
    limits = {"max_term_months": ("1200", 0), "min_replace_benefit_rub": ("1000000000000", 8)}
    for key in POLICY_KEYS:
        maximum, places = limits.get(key, ("100", 4))
        result[key] = _number(policy[key], maximum, places)
    return result


def _rule_values(value: object) -> dict[str, Any]:
    rules = _exact_keys(value, ("rating_caps", "yield_floor", "yield_margin_pp",
                                "fund_wrapper_cap_percent"))
    caps = _exact_keys(rules["rating_caps"], RATING_LEVELS)
    result = dict(rules)
    result["rating_caps"] = {key: _number(val) for key, val in caps.items()}
    if any(v is None for v in result["rating_caps"].values()):
        raise ValueError("strategy_rating_cap_missing")
    if rules["yield_floor"] not in ("none", "key_rate"):
        raise ValueError("strategy_yield_mode")
    for key in ("yield_margin_pp", "fund_wrapper_cap_percent"):
        result[key] = _number(rules[key])
        if result[key] is None:
            raise ValueError("strategy_rule_missing")
    return result


def normalize_document(value: object) -> dict[str, Any]:
    """Validate untrusted draft without inferring consent or filling missing facts."""
    data = _exact_keys(value, ("base_preset_id", "catalog_version", "customized", "allocation",
                               "locked", "excluded", "profile", "policy", "rules"))
    if data["catalog_version"] != CATALOG_VERSION:
        raise ValueError("strategy_catalog_changed")
    preset_document(data["base_preset_id"])
    if type(data["customized"]) is not bool:
        raise ValueError("strategy_mode_invalid")
    return {
        "base_preset_id": data["base_preset_id"], "catalog_version": CATALOG_VERSION,
        "customized": data["customized"], **_allocation_flags(data),
        "profile": _profile_values(data["profile"]), "policy": _policy_values(data["policy"]),
        "rules": _rule_values(data["rules"]),
    }


def validate_selection(document: object, *, intent: str) -> dict[str, Any]:
    result = normalize_document(document)
    if intent == "edit":
        result["customized"] = True
    elif intent == "select":
        template = preset_document(result["base_preset_id"])
        # User-specific money/tax facts survive switching templates. No default overwrites them.
        for section in ("profile", "policy"):
            for key in PERSONAL_FIELDS & template[section].keys():
                template[section][key] = result[section][key]
        result["customized"] = False
        if result != normalize_document(template):
            raise ValueError("strategy_preset_mismatch")
    else:
        raise ValueError("strategy_intent_invalid")
    return result


def document_hash(document: Mapping[str, Any]) -> str:
    encoded = json.dumps(document, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def expected_shortfall(losses: Sequence[Decimal], probabilities: Sequence[Decimal],
                       confidence: Decimal = Decimal("0.95")) -> Decimal:
    """Discrete upper-tail CVaR, with fractional mass at the quantile boundary."""
    if (not losses or len(losses) != len(probabilities)
            or any(not value.is_finite() for value in (*losses, *probabilities, confidence))
            or not 0 < confidence < 1 or any(p < 0 for p in probabilities)
            or sum(probabilities) != 1):
        raise ValueError("invalid_loss_distribution")
    tail = 1 - confidence
    remaining, weighted = tail, Decimal(0)
    for loss, probability in sorted(zip(losses, probabilities, strict=True), reverse=True):
        mass = min(remaining, probability)
        weighted += mass * loss
        remaining -= mass
        if remaining == 0:
            break
    return weighted / tail


def wilson_interval(
    successes: int, trials: int, z: float = 1.959963984540054,
) -> tuple[float, float]:
    """Conditional sample interval; independence is an assumption, not market evidence."""
    if (type(successes) is not int or type(trials) is not int or trials <= 0
            or not 0 <= successes <= trials or not math.isfinite(z) or z <= 0):
        raise ValueError("invalid_trial_counts")
    p = successes / trials
    divisor = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / divisor
    half = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / divisor
    return (0.0 if successes == 0 else max(0.0, center - half),
            1.0 if successes == trials else min(1.0, center + half))


STRESS_ASSUMPTIONS = (
    ("Условное снижение", ("-30", "-10", "-25", "0")),
    ("Условный тяжёлый шок", ("-50", "-20", "-45", "0")),
    ("Разнонаправленные цены", ("10", "-15", "5", "0")),
    ("Снижение акций, рост облигаций", ("-20", "10", "-15", "0")),
    ("Условный рост", ("30", "10", "25", "0")),
)


def stress_diagnostics(document: object, *, nav_rub: Decimal) -> dict[str, Any]:
    """Static price shocks with explicit test weights, not event probabilities."""
    data = normalize_document(document)
    if not nav_rub.is_finite() or not 0 < nav_rub <= Decimal("1000000000000"):
        raise ValueError("strategy_capital_invalid")
    rows = []
    losses = []
    for title, changes in STRESS_ASSUMPTIONS:
        change = sum(
            (Decimal(data["allocation"][key]) * Decimal(shock) / Decimal("100")
             for key, shock in zip(ALLOCATION_KEYS, changes, strict=True)),
            Decimal(0),
        )
        loss = -nav_rub * change / Decimal("100")
        losses.append(loss)
        rows.append({"title": title, "class_changes_percent": dict(zip(ALLOCATION_KEYS,
            changes, strict=True)),
                     "portfolio_change_percent": str(change), "change_rub": str(-loss)})
    # Five equal stress-test weights are exactly representable. They are not
    # estimates of market frequencies; no probability of profit is inferred.
    weights = (Decimal("0.20"),) * 5
    return {"scenarios": rows, "test_weights": [str(weight) for weight in weights],
            "tail_level": "0.95", "test_tail_loss_rub": str(expected_shortfall(losses, weights)),
            "worst_test_loss_rub": str(max(losses)), "probability_of_profit": None,
            "scope": "Условные изменения цен, не история рынка. Веса относятся только к "
                "набору тестов. "
                     "Не учтены будущие выплаты, налоги, инфляция, дефолты и сделки. "
                     "Фонды здесь — отдельная условная корзина без раскрытия состава."}


def capital_feasibility(
    document: object, *, nav_rub: Decimal, lot_cost_rub: Decimal,
) -> dict[str, Any]:
    """An exact toy-lot diagnostic, not a security selection or a forecast."""
    data = normalize_document(document)
    if (not nav_rub.is_finite() or not lot_cost_rub.is_finite()
            or nav_rub <= 0 or lot_cost_rub <= 0):
        raise ValueError("strategy_capital_invalid")
    raw_cap = data["policy"]["max_issuer_percent"]
    if raw_cap is None:
        return {"status": "unknown", "reason": "issuer_cap_unknown"}
    cap = Decimal(raw_cap)
    budget = nav_rub * cap / 100
    lots = int((budget / lot_cost_rub).to_integral_value(rounding=ROUND_FLOOR))
    bond_share = Decimal(data["allocation"]["bonds"])
    count = math.ceil(bond_share / cap) if cap else None
    return {"status": "feasible" if lots else "lot_blocked", "issuer_budget_rub": str(budget),
            "lots_per_issuer": lots, "minimum_issuers_if_all_bonds_corporate": count,
            "minimum_nav_for_one_lot": str(lot_cost_rub * 100 / cap) if cap else None,
            "note": "Условная стоимость лота с расходами. Проверка не подтверждает наличие бумаг, "
                    "их доходность, независимость компаний или выполнимость всего портфеля."}
