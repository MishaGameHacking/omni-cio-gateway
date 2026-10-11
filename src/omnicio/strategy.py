"""Versioned strategy mandates, durable drafts and exact tail-risk mathematics.

Templates are explicit engineering policies, not calibrated return forecasts.
This module has no network, account authority, or broker execution capability.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any, cast

CATALOG_VERSION = "1.1.0"
# Catalog editions are not schema versions. Retain every released edition whose
# exact document schema remains readable; changing that schema requires migration.
_RELEASED_DOCUMENT_EDITIONS = ("2026-10-06.1", "1.0.0", "1.1.0")
_LEGACY_PRESETS = {
    "near_goal": {"title": "Ближайшая цель", "current_id": "conservative"},
    "floating": {"title": "Переменная ставка", "current_id": "income"},
}


def compatible_document_versions() -> tuple[str, ...]:
    return tuple(dict.fromkeys((*_RELEASED_DOCUMENT_EDITIONS, CATALOG_VERSION)))


ALLOCATION_KEYS = ("shares", "bonds", "funds", "cash")
RATING_LEVELS = (
    "AAA",
    "AA+",
    "AA",
    "AA-",
    "A+",
    "A",
    "A-",
    "BBB+",
    "BBB",
    "BBB-",
    "BB+",
    "BB",
    "BB-",
    "B+",
    "B",
    "B-",
    "CCC+",
    "CCC",
    "CCC-",
    "CC",
    "C",
    "SD",
    "RD",
    "D",
    "NR",
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
    "max_instrument_percent",
    "max_sector_percent",
    "max_issuer_percent",
    "max_group_percent",
    "max_share_percent",
    "max_bond_percent",
    "max_etf_percent",
    "max_below_grade_percent",
    "max_unknown_percent",
    "max_term_months",
    "turnover_budget_percent",
    "max_daily_turnover_participation_percent",
    "securities_tax_rate_percent",
    "uncertainty_haircut_percent",
    "credit_loss_haircut_percent",
    "no_trade_band_percent",
    "min_replace_benefit_rub",
)
PERSONAL_FIELDS = {"reserve_rub", "planned_withdrawal_rub", "securities_tax_rate_percent"}
SOURCES = (
    {
        "id": "buffett1989",
        "title": "Berkshire Hathaway: письмо 1989 года",
        "url": "https://www.berkshirehathaway.com/letters/1989.html",
    },
    {
        "id": "buffett2013",
        "title": "Berkshire Hathaway: письмо 2013 года",
        "url": "https://www.berkshirehathaway.com/letters/2013ltr.pdf",
    },
    {
        "id": "vanguard",
        "title": "Vanguard: цели, распределение, расходы, дисциплина",
        "url": "https://ownyourfuture.vanguard.com/content/en/learn/financial-planning/vanguards-4-principles-for-investing-success.html",
    },
    {
        "id": "allweather",
        "title": "Bridgewater: The All Weather Story",
        "url": "https://www.bridgewater.com/research-and-insights/the-all-weather-story",
    },
    {
        "id": "cvar",
        "title": "Rockafellar–Uryasev: условный риск потерь (CVaR)",
        "url": "https://sites.math.washington.edu/~rtr/papers/rtr179-CVaR1.pdf",
    },
    {
        "id": "overfit",
        "title": "Bailey и соавторы: переобучение при проверке стратегий",
        "url": "https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf",
    },
    {
        "id": "acra",
        "title": "АКРА: определения рейтинговых шкал",
        "url": "https://www.acra-ratings.ru/about-ratings/scales/",
    },
)
# Values below describe different mandates. They have NOT been optimized against
# market history. Precision is constrained by the existing financial contracts.
_CATEGORY_BASE = "Базовые"
_CATEGORY_GOAL = "По задачам"
_CATEGORY_INVESTOR = "Именные"
_SPECS = (
    (
        "balanced",
        "Сбалансированная",
        _CATEGORY_BASE,
        (30, 50, 10, 10),
        84,
        25,
        84,
        5,
        "balanced",
        "Распределение между классами с предпочтением меньшей исторической волатильности.",
        "Акции и облигации могут дешеветь одновременно. Целевые доли не защищают капитал.",
        "vanguard",
    ),
    (
        "conservative",
        "Консервативная",
        _CATEGORY_BASE,
        (0, 75, 5, 20),
        36,
        15,
        36,
        5,
        "capital_preservation",
        "Короткие сроки, высокий подтверждённый рейтинг и денежный резерв.",
        "Низкая историческая волатильность не исключает дефолт и будущие потери.",
        "cvar",
    ),
    (
        "aggressive",
        "Агрессивная",
        _CATEGORY_BASE,
        (80, 10, 5, 5),
        120,
        50,
        36,
        10,
        "momentum",
        "Положительная динамика на обучающем периоде с ограничением концентрации.",
        "Динамика может развернуться. Плечо и торговые полномочия не включаются.",
        "overfit",
    ),
    (
        "income",
        "Доходная",
        _CATEGORY_GOAL,
        (10, 70, 10, 10),
        60,
        20,
        60,
        5,
        "cashflow",
        "Планирование поступлений с контролем сроков и источников выплат.",
        "Высокий купон сам по себе не делает выпуск подходящим. Погашение не считается доходом.",
        "vanguard",
    ),
    (
        "growth",
        "Накопление",
        _CATEGORY_BASE,
        (55, 25, 10, 10),
        120,
        35,
        120,
        5,
        "growth",
        "Длинный срок, пополнения и ограничение лишних перестроек.",
        "Большая доля акций может привести к сильному и длительному снижению стоимости.",
        "vanguard",
    ),
    (
        "buffett",
        "Стратегия Баффета",
        _CATEGORY_INVESTOR,
        (70, 10, 10, 10),
        120,
        40,
        36,
        5,
        "quality_value",
        "Адаптация принципов: качество бизнеса, понятность и дисциплина цены.",
        "Это не портфель Berkshire и не оригинальная рекомендация Баффетта "
        "для рынка РФ. Нужна оценка бизнеса.",
        "buffett1989",
    ),
    (
        "bogle",
        "Стратегия Богла",
        _CATEGORY_INVESTOR,
        (0, 20, 70, 10),
        120,
        35,
        60,
        5,
        "index_cost",
        "Адаптация принципов широкого покрытия рынка и контроля расходов фондов.",
        "Фонд может быть концентрированным. Лимиты компаний проверяются по "
        "его составу, не названию.",
        "vanguard",
    ),
    (
        "dalio",
        "Стратегия Далио",
        _CATEGORY_INVESTOR,
        (20, 50, 20, 10),
        120,
        25,
        120,
        5,
        "regime_risk",
        "Адаптация идеи проверки разных сочетаний роста экономики и инфляции.",
        "Не копия All Weather. Без чувствительности инструментов к факторам "
        "баланс риска не подтверждён.",
        "allweather",
    ),
    (
        "ladder",
        "Лестница облигаций",
        _CATEGORY_GOAL,
        (0, 85, 0, 15),
        60,
        15,
        60,
        4,
        "ladder",
        "Распределяет проверенные погашения по годовым ступеням внутри горизонта.",
        "Недоступные ступени остаются незаполненными. Нужны договорные сроки и стоимость лота.",
        "cvar",
    ),
    (
        "dividends",
        "Дивидендная",
        _CATEGORY_GOAL,
        (60, 20, 10, 10),
        120,
        35,
        60,
        5,
        "dividends",
        "Объявленные выплаты, покрытие свободным денежным потоком и долговая нагрузка.",
        "Дивиденды могут отменить. Даты публикации и источники отчётности проверяются отдельно.",
        "buffett1989",
    ),
)

# These are disclosed engineering criteria, not parameters optimized on a test set.
# Both current screening and historical research consume this same rule set.
_SELECTION_RULES: dict[str, dict[str, Any]] = {
    "balanced": {"ranking": "inverse_volatility", "rebalance_sessions": 21},
    "conservative": {
        "ranking": "short_quality",
        "rebalance_sessions": 63,
        "minimum_rating": "AA-",
        "maximum_volatility_percent": "20",
    },
    "aggressive": {
        "ranking": "positive_momentum",
        "rebalance_sessions": 21,
        "minimum_momentum_percent": "0",
    },
    "income": {"ranking": "documented_cashflow", "rebalance_sessions": 63},
    "growth": {"ranking": "risk_adjusted_momentum", "rebalance_sessions": 63},
    "buffett": {
        "ranking": "quality_value",
        "rebalance_sessions": 126,
        "minimum_roe_percent": "15",
        "maximum_debt_to_ebitda": "3",
        "minimum_fcf_yield_percent": "3",
    },
    "bogle": {
        "ranking": "index_cost",
        "rebalance_sessions": 126,
        "maximum_expense_percent": "1",
        "minimum_constituents": 30,
        "maximum_constituent_percent": "10",
    },
    "dalio": {
        "ranking": "regime_risk",
        "rebalance_sessions": 63,
        "minimum_factor_observations": 60,
        "regime_allocation": "equal_regime_budgets_within_asset_class_then_inverse_volatility",
    },
    "ladder": {"ranking": "maturity_ladder", "rebalance_sessions": 126, "rung_months": 12},
    "dividends": {
        "ranking": "covered_dividends",
        "rebalance_sessions": 63,
        "maximum_debt_to_ebitda": "3",
        "maximum_payout_percent": "80",
    },
    # Read saved policies with their original mandate; never convert a floating-rate
    # bond draft into the new aggressive equity mandate just to fill the catalog.
    "near_goal": {
        "ranking": "short_quality",
        "rebalance_sessions": 63,
        "minimum_rating": "AA-",
        "maximum_volatility_percent": "20",
    },
    "floating": {"ranking": "floating_cashflow", "rebalance_sessions": 63},
}


def strategy_rule_set(preset_id: str) -> dict[str, Any]:
    try:
        return copy.deepcopy(_SELECTION_RULES[preset_id])
    except (KeyError, TypeError) as exc:
        raise ValueError("strategy_preset_unknown") from exc


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
    (
        ident,
        title,
        category,
        allocation,
        horizon,
        drawdown,
        term,
        issuer,
        method,
        text,
        risk,
        source,
    ) = spec
    caps = dict.fromkeys(RATING_LEVELS, "0")
    for grade in RATING_LEVELS[:7]:
        caps[grade] = "100"  # Ceilings, not required weights and not probabilities.
    for grade in RATING_LEVELS[7:10]:
        caps[grade] = "10" if ident != "conservative" else "0"
    values = (
        "70" if ident == "bogle" else str(issuer),
        "25",
        str(issuer),
        str(issuer * 2),
        str(allocation[0]),
        str(allocation[1]),
        str(allocation[2]),
        "0",
        "0",
        str(term),
        "10",
        "5",
        None,
        "3",
        "2",
        "1",
        "500",
    )
    document = {
        "base_preset_id": ident,
        "catalog_version": CATALOG_VERSION,
        "customized": False,
        "allocation": dict(zip(ALLOCATION_KEYS, allocation, strict=True)),
        "locked": [],
        "excluded": [],
        "profile": {
            "reserve_rub": None,
            "planned_withdrawal_rub": None,
            "horizon_months": str(horizon),
            "max_drawdown_percent": str(drawdown),
            "liquidity_horizon_days": "5",
            "allow_below_investment_grade": False,
        },
        "policy": dict(zip(POLICY_KEYS, values, strict=True)),
        "rules": {
            "rating_caps": caps,
            "yield_floor": "key_rate" if ident == "income" else "none",
            "yield_margin_pp": "0",
            "fund_wrapper_cap_percent": "70" if ident == "bogle" else "20",
        },
    }
    return {
        "id": ident,
        "title": title,
        "category": category,
        "method": method,
        "description": text,
        "risk": risk,
        "source_ids": [source],
        "document": document,
        "calibration": "not_calibrated",
        "probability_of_profit": None,
        "probability_reason": "Правила шаблона не являются калиброванной вероятностью прибыли.",
        "selection_rules": strategy_rule_set(ident),
        "parameter_basis": "Явные исходные условия модели; не оптимум, найденный на истории рынка.",
    }


def strategy_catalog() -> dict[str, Any]:
    # Retired mandates remain readable for saved drafts/research, but are not
    # offered as additional product strategies.
    presets = [_template(spec) for spec in _SPECS if spec[0] in {"balanced", "income", "growth"}]
    titles = {"income": "Купоны и дивиденды", "growth": "Долгосрочное накопление"}
    for preset in presets:
        preset["title"] = titles.get(preset["id"], preset["title"])
    return {
        "version": CATALOG_VERSION,
        "default_id": "balanced",
        "compatible_document_versions": list(compatible_document_versions()),
        "sources": copy.deepcopy(list(SOURCES)),
        "presets": presets,
        "custom": {"id": "custom", "title": "Своя стратегия", "base_id": "balanced"},
        "rating_levels": list(RATING_LEVELS),
        "legacy_presets": copy.deepcopy(_LEGACY_PRESETS),
        "note": "Три подхода и своя стратегия. Доходность и вероятность успеха не гарантируются. "
        "Сохранение черновика не меняет подтверждённые условия и не создаёт сделок.",
    }


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
        if (
            not isinstance(items, list)
            or len(items) > 4
            or any(not isinstance(k, str) or k not in ALLOCATION_KEYS for k in items)
            or len(set(items)) != len(items)
        ):
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
    rules = _exact_keys(
        value, ("rating_caps", "yield_floor", "yield_margin_pp", "fund_wrapper_cap_percent")
    )
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
    data = _exact_keys(
        value,
        (
            "base_preset_id",
            "catalog_version",
            "customized",
            "allocation",
            "locked",
            "excluded",
            "profile",
            "policy",
            "rules",
        ),
    )
    if data["catalog_version"] not in compatible_document_versions():
        raise ValueError("strategy_catalog_changed")
    ident = data["base_preset_id"]
    strategy_rule_set(ident)
    if ident in _LEGACY_PRESETS and data["catalog_version"] != "2026-10-06.1":
        raise ValueError("strategy_preset_unknown")
    if type(data["customized"]) is not bool:
        raise ValueError("strategy_mode_invalid")
    return {
        "base_preset_id": data["base_preset_id"],
        "catalog_version": data["catalog_version"],
        "customized": data["customized"],
        **_allocation_flags(data),
        "profile": _profile_values(data["profile"]),
        "policy": _policy_values(data["policy"]),
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


def expected_shortfall(
    losses: Sequence[Decimal],
    probabilities: Sequence[Decimal],
    confidence: Decimal = Decimal("0.95"),
) -> Decimal:
    """Discrete upper-tail CVaR, with fractional mass at the quantile boundary."""
    if (
        not losses
        or len(losses) != len(probabilities)
        or any(not value.is_finite() for value in (*losses, *probabilities, confidence))
        or not 0 < confidence < 1
        or any(p < 0 for p in probabilities)
        or sum(probabilities) != 1
    ):
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
