"""Read-only comparison of an exact saved strategy with sourced account evidence.

This is an assessment of constraints, not a trade allocator or a return forecast.
Unknown coverage is propagated; receiving a fresh HTTP response never manufactures
issuer identities, issue ratings, fund constituents, or future cash flows.
"""

from __future__ import annotations

import calendar
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any, Literal
from urllib.parse import urlsplit

from .freshness import PORTFOLIO_MAX_AGE
from .portfolio import PortfolioAnalysis, SecurityExposure
from .strategy import (
    ALLOCATION_KEYS,
    RATING_LEVELS,
    document_hash,
    normalize_document,
    strategy_rule_set,
)
from .tbank import TBankInstrumentMetadata, TBankRating

_ZERO = Decimal("0")
_HUNDRED = Decimal("100")
_CLASS = {"share": "shares", "bond": "bonds", "etf": "funds"}
_CLASS_CAP = {
    "shares": "max_share_percent",
    "bonds": "max_bond_percent",
    "funds": "max_etf_percent",
}
_RATING_MAX_AGE = timedelta(days=366)
_IDENTITY_MAX_AGE = timedelta(days=30)
_MISSING_PREFIX = "missing:"
_DIVIDEND_COVERAGE_INVALID = "research_dividend_coverage_invalid"
_DIVIDEND_COVERAGE_MISSING = "missing:dividend_cashflow_coverage"
_DIVIDEND_COVERAGE_KEYS = frozenset({
    "issuer_id", "scope", "currency", "period_start", "period_end",
    "operating_cashflow", "capital_expenditure", "gross_dividends_paid", "cashflows_complete",
})
_State = Literal["evaluated", "blocked", "unknown", "inapplicable"]


@dataclass(frozen=True, slots=True)
class IssuerEvidence:
    """A verified mapping, not an asset UID or an inferred company name."""

    instrument_uid: str
    issuer_id: str
    group_id: str
    source_url: str
    verified_at: datetime
    mapping_source_url: str
    group_source_url: str


_METHOD_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "income": ("Объявленные купоны и дивиденды с датами, отдельно от возврата номинала.",),
    "growth": ("Сопоставимая история полной доходности и подтверждённые расходы.",),
    "balanced": ("Оценка совместных потерь акций и облигаций на сопоставимых данных.",),
    "conservative": ("Подтверждённый высокий рейтинг, срок погашения и история риска.",),
    "aggressive": ("Положительная динамика на прошлом периоде и достаточный объём торгов.",),
    "near_goal": ("Дата потребности в деньгах и договорные сроки возврата капитала.",),
    "ladder": ("Договорные даты погашений и стоимость каждого доступного лота.",),
    "floating": ("Формула купона, лаг пересмотра, ограничения и сценарий будущей ставки.",),
    "dividends": ("Решения о выплатах, денежный поток и сопоставимая отчётность компаний.",),
    "buffett": ("Сопоставимая отчётность, долг и проверяемая оценка стоимости бизнеса.",),
    "bogle": ("Раскрытый состав фондов, расходы, индекс и пересечения с прямыми позициями.",),
    "dalio": ("Состав фондов и оценённая чувствительность инструментов к ставкам и инфляции.",),
}


def _amount(value: object) -> Decimal | None:
    if not isinstance(value, (str, Decimal, int)) or isinstance(value, bool):
        return None
    try:
        number = Decimal(value)
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() and number >= 0 else None


def _text(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def _fresh(when: datetime | None, now: datetime, maximum: timedelta) -> bool:
    return when is not None and when.tzinfo is not None and timedelta(0) <= now - when < maximum


def _check(
    key: str,
    title: str,
    state: _State,
    detail: str,
    *,
    value: object = None,
    limit: object = None,
    sources: Sequence[str] = (),
) -> dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "state": state,
        "detail": detail,
        "value": value,
        "limit": limit,
        "source_ids": list(sources),
    }


def _ceiling(
    key: str,
    title: str,
    value: Decimal | None,
    limit: object,
    *,
    nav: Decimal,
    complete: bool,
    sources: Sequence[str],
) -> dict[str, Any]:
    cap = _amount(limit)
    percent = value * _HUNDRED / nav if value is not None and nav > 0 else None
    state: _State = "unknown"
    detail = "Не хватает значения лимита, стоимости или полного покрытия позиций."
    if percent is not None and cap is not None:
        if percent > cap:
            state = "blocked"
            detail = "Уже известная доля выше лимита. Это не команда продать позицию."
        elif complete:
            state = "evaluated"
            detail = (
                "Текущая доля не превышает выбранный предел. После покупки нужна новая проверка."
            )
    return _check(
        key,
        title,
        state,
        detail,
        value={"rub": _text(value), "percent": _text(percent), "complete": complete},
        limit=_text(cap),
        sources=sources,
    )


def _position_totals(
    analysis: PortfolioAnalysis,
) -> tuple[dict[str, Decimal], list[SecurityExposure], bool]:
    totals = dict.fromkeys(ALLOCATION_KEYS, _ZERO)
    known: list[SecurityExposure] = []
    complete = True
    seen: set[str] = set()
    for item in analysis.securities:
        if not item.uid or item.uid in seen:
            raise ValueError("strategy_duplicate_position")
        seen.add(item.uid)
        value = _amount(item.value_rub)
        kind = _CLASS.get(item.instrument_type)
        if value is None or kind is None:
            complete = False
            continue
        totals[kind] += value
        known.append(item)
    cash = _amount(analysis.rub_cash_total)
    if cash is None:
        complete = False
    else:
        totals["cash"] = cash
    return totals, known, complete


def _allocation_rows(
    data: Mapping[str, Any],
    totals: Mapping[str, Decimal],
    nav: Decimal,
    complete: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in ALLOCATION_KEYS:
        target = nav * Decimal(data["allocation"][key]) / _HUNDRED
        actual = totals[key]
        rows.append(
            {
                "key": key,
                "target_percent": data["allocation"][key],
                "target_rub": _text(target),
                "current_rub": _text(actual),
                "current_percent": _text(actual * _HUNDRED / nav) if nav else None,
                "difference_rub": _text(target - actual),
                "complete": complete,
            }
        )
    return rows


def _cash_checks(
    data: Mapping[str, Any],
    analysis: PortfolioAnalysis,
    nav: Decimal,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    total = _amount(analysis.rub_cash_total)
    blocked = _amount(analysis.rub_cash_blocked)
    free = _amount(analysis.rub_cash_unblocked)
    coherent = (
        total is not None and blocked is not None and free is not None and total == blocked + free
    )
    reserve = _amount(data["profile"]["reserve_rub"])
    withdrawals = _amount(data["profile"]["planned_withdrawal_rub"])
    target = nav * Decimal(data["allocation"]["cash"]) / _HUNDRED
    available = None
    shortfall = None
    if (
        coherent
        and free is not None
        and total is not None
        and reserve is not None
        and withdrawals is not None
    ):
        # The target describes total cash, not a second independent reserve.
        # Broker blocks already reduce `free`; do not subtract them again.
        capacity = min(free - reserve - withdrawals, total - target - withdrawals)
        available = max(_ZERO, capacity)
        shortfall = max(_ZERO, -capacity)
    state: _State = "evaluated" if available is not None else "unknown"
    cash = {
        "total_rub": _text(total),
        "blocked_rub": _text(blocked),
        "unblocked_rub": _text(free),
        "reserve_rub": _text(reserve),
        "withdrawals_rub": _text(withdrawals),
        "target_rub": _text(target),
        "allocation_capacity_rub": _text(available),
        "shortfall_rub": _text(shortfall),
        "executable_budget": False,
    }
    checks = [
        _check(
            "cash_budget",
            "Деньги для расчёта распределения",
            state,
            "Из свободных рублей исключены резерв и снятия; также сохранена целевая денежная доля. "
            "Целевая доля и резерв не складываются дважды. Комиссии будущих покупок ещё не учтены.",
            value=cash,
            sources=("portfolio", "positions"),
        )
    ]
    for key, title, value in (
        ("reserve_rub", "Резерв", reserve),
        ("planned_withdrawal_rub", "Планируемые снятия", withdrawals),
    ):
        checks.append(
            _check(
                key,
                title,
                "evaluated" if value is not None else "unknown",
                "Учтено при расчёте свободного остатка."
                if value is not None
                else "Сумма не указана. Отсутствующее значение не заменяется нулём.",
                value=_text(value),
                sources=("saved_strategy",),
            )
        )
    return cash, checks


def _source_url(value: str) -> bool:
    """Check stored provenance syntax, not assert that an arbitrary site is official."""
    try:
        url = urlsplit(value)
        return (
            url.scheme == "https"
            and bool(url.hostname)
            and url.port in {None, 443}
            and url.username is None
            and url.password is None
        )
    except ValueError:
        return False


def _verified_mappings(
    mappings: Sequence[IssuerEvidence],
    now: datetime,
) -> dict[str, IssuerEvidence]:
    seen: set[str] = set()
    result = {}
    for mapping in mappings:
        if mapping.instrument_uid in seen:
            raise ValueError("strategy_ambiguous_issuer")
        seen.add(mapping.instrument_uid)
        if (
            mapping.issuer_id
            and _source_url(mapping.source_url)
            and _source_url(mapping.mapping_source_url)
            and _fresh(mapping.verified_at, now, _IDENTITY_MAX_AGE)
        ):
            result[mapping.instrument_uid] = mapping
    return result


def _identity_totals(
    positions: Sequence[SecurityExposure],
    mappings: Sequence[IssuerEvidence],
    now: datetime,
) -> tuple[dict[str, Decimal], dict[str, Decimal], bool, bool]:
    by_uid = _verified_mappings(mappings, now)
    issuers: dict[str, Decimal] = defaultdict(Decimal)
    groups: dict[str, Decimal] = defaultdict(Decimal)
    issuer_complete = group_complete = True
    for item in positions:
        value = _amount(item.value_rub)
        if value == 0:
            continue
        row = by_uid.get(item.uid)
        if row is None or value is None or item.instrument_type == "etf":
            issuer_complete = group_complete = False
            continue
        issuers[row.issuer_id] += value
        if row.group_id and _source_url(row.group_source_url):
            groups[row.group_id] += value
        else:
            group_complete = False
    return dict(issuers), dict(groups), issuer_complete, group_complete


def _concentration_checks(
    data: Mapping[str, Any],
    positions: Sequence[SecurityExposure],
    mappings: Sequence[IssuerEvidence],
    *,
    nav: Decimal,
    complete: bool,
    now: datetime,
) -> list[dict[str, Any]]:
    policy = data["policy"]
    sectors: dict[str, Decimal] = defaultdict(Decimal)
    sector_complete = complete
    for item in positions:
        value = _amount(item.value_rub)
        if not item.sector or item.instrument_type == "etf":
            sector_complete = sector_complete and value == 0
        elif value is not None:
            sectors[item.sector] += value
    issuers, groups, issuer_complete, group_complete = _identity_totals(positions, mappings, now)
    instruments = [_amount(item.value_rub) or _ZERO for item in positions]
    dimensions = (
        ("instrument", "Один инструмент", max(instruments, default=_ZERO), complete),
        ("sector", "Один сектор", max(sectors.values(), default=_ZERO), sector_complete),
        (
            "issuer",
            "Одна компания",
            max(issuers.values(), default=_ZERO),
            complete and issuer_complete,
        ),
        (
            "group",
            "Одна группа компаний",
            max(groups.values(), default=_ZERO),
            complete and group_complete,
        ),
    )
    return [
        _ceiling(
            "max_" + key + "_percent",
            title,
            value,
            policy["max_" + key + "_percent"],
            nav=nav,
            complete=covered,
            sources=("portfolio", "catalog", "issuer_mapping"),
        )
        for key, title, value, covered in dimensions
    ]


def rating_notch(rating: TBankRating, now: datetime) -> str | None:
    """Only explicitly named ordinary RU national scales; no guessed equivalence.

    The stricter supported notch is used when agencies disagree. This is a
    screening convention, not a cross-agency default-probability calibration.
    Expected/structured/international/withdrawn and stale symbols stay unknown.
    """
    if not _fresh(rating.rating_date, now, _RATING_MAX_AGE):
        return None
    agency = rating.agency_name.strip().casefold()
    level = rating.rating_level.strip()
    if agency in {"эксперт ра", "expert ra", "raexpert"} and level.startswith("ru"):
        level = level[2:]
    elif agency in {"акра", "acra"} and level.endswith("(RU)"):
        level = level[:-4]
    else:
        return None
    return level if level in RATING_LEVELS[:21] or level == "D" else None


def _rating_totals(
    positions: Sequence[SecurityExposure],
    ratings: Mapping[str, Sequence[TBankRating]],
    now: datetime,
) -> tuple[dict[str, Decimal], list[dict[str, Any]]]:
    amounts = dict.fromkeys(RATING_LEVELS, _ZERO)
    rows: list[dict[str, Any]] = []
    for item in positions:
        if item.instrument_type != "bond":
            continue
        evidence = ratings.get(item.uid, ())
        notches = [rating_notch(rating, now) for rating in evidence]
        notch = "NR"
        if notches and all(value is not None for value in notches):
            notch = max((value for value in notches if value is not None), key=RATING_LEVELS.index)
        amounts[notch] += _amount(item.value_rub) or _ZERO
        rows.append(
            {
                "instrument_uid": item.uid,
                "notch": notch,
                "rating_object": "issuer",
                "source_id": "tbank_bond_ratings",
                "evidence": [
                    {
                        "agency": r.agency_name,
                        "level": r.rating_level,
                        "date": r.rating_date.isoformat(),
                        "under_watch": r.is_under_watch,
                    }
                    for r in evidence
                ],
            }
        )
    return amounts, rows


def _rating_checks(
    data: Mapping[str, Any],
    positions: Sequence[SecurityExposure],
    ratings: Mapping[str, Sequence[TBankRating]],
    *,
    nav: Decimal,
    complete: bool,
    now: datetime,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    amounts, rows = _rating_totals(positions, ratings, now)
    below = sum((amounts[key] for key in RATING_LEVELS[10:24]), _ZERO)
    policy = data["policy"]
    checks = [
        _ceiling(
            "max_unknown_percent",
            "Облигации с непроверенным рейтингом",
            amounts["NR"],
            policy["max_unknown_percent"],
            nav=nav,
            complete=complete,
            sources=("portfolio", "tbank_bond_ratings"),
        ),
        _ceiling(
            "max_below_grade_percent",
            "Облигации ниже инвестиционного уровня",
            below,
            policy["max_below_grade_percent"],
            nav=nav,
            complete=complete and amounts["NR"] == 0,
            sources=("tbank_bond_ratings",),
        ),
    ]
    allowed = data["profile"]["allow_below_investment_grade"]
    permission_state: _State = "unknown"
    if below > 0 and not allowed:
        permission_state = "blocked"
    elif complete and amounts["NR"] == 0:
        permission_state = "evaluated"
    checks.append(
        _check(
            "allow_below_investment_grade",
            "Разрешение повышенного кредитного риска",
            permission_state,
            "Разрешение учитывается независимо от процентного лимита. Не включает торговые права.",
            value=allowed,
            limit=policy["max_below_grade_percent"],
            sources=("saved_strategy", "tbank_bond_ratings"),
        )
    )
    for notch in RATING_LEVELS:
        checks.append(
            _ceiling(
                "rating_caps." + notch,
                "Предел рейтинга " + notch,
                amounts[notch],
                data["rules"]["rating_caps"][notch],
                nav=nav,
                complete=complete and (notch == "NR" or amounts["NR"] == 0),
                sources=("tbank_bond_ratings",),
            )
        )
    return checks, rows


def _maturity_terms(
    bonds: Sequence[SecurityExposure],
    metadata: Mapping[str, TBankInstrumentMetadata],
    now: datetime,
) -> tuple[list[Decimal], bool]:
    terms = []
    covered = all(_amount(position.value_rub) is not None for position in bonds)
    for position in bonds:
        info = metadata.get(position.uid)
        if info is None or info.maturity_date is None or info.maturity_date.tzinfo is None:
            covered = False
            continue
        days = Decimal(str((info.maturity_date - now).total_seconds())) / Decimal("86400")
        covered = covered and days > 0 and info.perpetual is False
        terms.append(days)
    return terms, covered


def _calendar_horizon_end(months: Decimal, now: datetime) -> datetime | None:
    limit_month = now.year * 12 + now.month - 1 + int(months)
    year, month0 = divmod(limit_month, 12)
    if not 1 <= year <= 9999:
        return None
    return now.replace(
        year=year, month=month0 + 1, day=min(now.day, calendar.monthrange(year, month0 + 1)[1])
    )


def calendar_horizon_days(months: Decimal, now: datetime) -> Decimal | None:
    end = _calendar_horizon_end(months, now)
    if end is None:
        return None
    return Decimal(str((end - now).total_seconds())) / Decimal("86400")


def _term_check(
    key: str,
    title: str,
    months: Decimal | None,
    terms: Sequence[Decimal],
    *,
    has_bonds: bool,
    covered: bool,
    now: datetime,
) -> dict[str, Any]:
    state: _State = "unknown"
    detail = "Неизвестны срок или условия погашения. Дата погашения не обещает возврат денег."
    max_days = calendar_horizon_days(months, now) if months is not None else None
    if not has_bonds:
        state, detail = "inapplicable", "Сейчас нет оценённых облигаций для сравнения срока."
    elif max_days is not None:
        if any(days > max_days for days in terms):
            state, detail = (
                "blocked",
                "Есть погашения позже выбранного срока. Продажа не выполняется.",
            )
        elif covered:
            state, detail = "evaluated", "Известные даты погашения укладываются в выбранный срок."
    return _check(key, title, state, detail, limit=_text(months), sources=("catalog",))


def _term_checks(
    data: Mapping[str, Any],
    positions: Sequence[SecurityExposure],
    metadata: Mapping[str, TBankInstrumentMetadata],
    now: datetime,
) -> list[dict[str, Any]]:
    bonds = [p for p in positions if p.instrument_type == "bond" and _amount(p.value_rub) != 0]
    terms, covered = _maturity_terms(bonds, metadata, now)
    return [
        _term_check(
            key,
            title,
            _amount(data[section][key]),
            terms,
            has_bonds=bool(bonds),
            covered=covered,
            now=now,
        )
        for key, title, section in (
            ("horizon_months", "Горизонт", "profile"),
            ("max_term_months", "Срок облигаций", "policy"),
        )
    ]


def _dependent_checks(data: Mapping[str, Any], nav: Decimal) -> list[dict[str, Any]]:
    """Keep unevaluated purchase/return controls visible, never silently ignored."""
    meanings = (
        (
            "max_drawdown_percent",
            "Допустимая просадка",
            "Нужны сценарии потерь конкретных активов.",
        ),
        ("liquidity_horizon_days", "Срок выхода", "Нужны свежие объёмы торгов и глубина стакана."),
        (
            "max_daily_turnover_participation_percent",
            "Доля дневного оборота",
            "Нужны завершённые биржевые свечи и объём планируемой операции.",
        ),
        ("securities_tax_rate_percent", "Налог", "Нужны вид выплаты, налоговая база и льготы."),
        (
            "uncertainty_haircut_percent",
            "Запас на неопределённость",
            "Применяется к оценке конкретной операции, которой в этой проверке ещё нет.",
        ),
        (
            "credit_loss_haircut_percent",
            "Кредитный стресс",
            "Это выбранное допущение убытка, не вероятность дефолта; нужна конкретная операция.",
        ),
    )
    checks = []
    for key, title, detail in meanings:
        section = "profile" if key in data["profile"] else "policy"
        checks.append(
            _check(
                key, title, "unknown", detail, limit=data[section][key], sources=("saved_strategy",)
            )
        )
    turnover = _amount(data["policy"]["turnover_budget_percent"])
    checks.append(
        _check(
            "turnover_budget_percent",
            "Бюджет перестройки",
            "evaluated" if turnover is not None else "unknown",
            "Рублёвый предел рассчитан от стоимости счёта. "
            "Это предел будущего сценария, не расход денег.",
            value=_text(nav * turnover / _HUNDRED) if turnover is not None else None,
            limit=_text(turnover),
            sources=("portfolio", "saved_strategy"),
        )
    )
    for key, title in (
        ("no_trade_band_percent", "Порог отклонения доли, п.п."),
        ("min_replace_benefit_rub", "Минимальное сокращение отклонения, ₽"),
    ):
        checks.append(
            _check(
                key,
                title,
                "inapplicable",
                "В исторической модели ребалансировка требует превышения порога отклонения "
                "доли и сокращения денежного отклонения после издержек не ниже рублёвого порога. "
                "Это соответствие целевым долям, не прогноз денежной прибыли.",
                limit=data["policy"][key],
                sources=("saved_strategy",),
            )
        )
    floor = data["rules"]["yield_floor"]
    for key, title, value in (
        ("yield_floor", "Порог ключевой ставки", floor),
        ("yield_margin_pp", "Запас к ставке", data["rules"]["yield_margin_pp"]),
    ):
        checks.append(
            _check(
                key,
                title,
                "inapplicable" if floor == "none" else "unknown",
                "Фильтр выключен."
                if floor == "none"
                else "Для проверки нужны действующая ставка ЦБ "
                "и сопоставимая доходность по потокам "
                "после известных расходов. Купон вместо доходности не используется.",
                limit=value,
            )
        )
    return checks


def _class_checks(
    data: Mapping[str, Any],
    totals: Mapping[str, Decimal],
    nav: Decimal,
    complete: bool,
) -> list[dict[str, Any]]:
    checks = []
    for kind, key in _CLASS_CAP.items():
        checks.append(
            _ceiling(
                key,
                {"shares": "Акции", "bonds": "Облигации", "funds": "Фонды"}[kind],
                totals[kind],
                data["policy"][key],
                nav=nav,
                complete=complete,
                sources=("portfolio",),
            )
        )
        cap = _amount(data["policy"][key])
        if cap is not None and Decimal(data["allocation"][kind]) > cap:
            checks.append(
                _check(
                    "target_conflict." + kind,
                    "Цель и верхний предел",
                    "blocked",
                    "Целевая доля выше максимальной. Система не изменяет ограничения за вас.",
                    value=data["allocation"][kind],
                    limit=data["policy"][key],
                )
            )
    return checks


def _flag_checks(
    data: Mapping[str, Any],
    totals: Mapping[str, Decimal],
    complete: bool,
) -> list[dict[str, Any]]:
    checks = []
    for key in ("locked", "excluded"):
        state: _State = "evaluated" if complete else "unknown"
        if key == "locked":
            state = "inapplicable"
        if key == "excluded" and any(totals[k] > 0 for k in data[key]):
            state = "blocked"
        checks.append(
            _check(
                key,
                "Закреплённые доли" if key == "locked" else "Запрещённые классы",
                state,
                "Замки управляют редактированием долей, а не блокировкой бумаг у брокера."
                if key == "locked"
                else "Запрет относится к новым покупкам. Имеющиеся позиции не продаются.",
                value=data[key],
                sources=("saved_strategy", "portfolio"),
            )
        )
    return checks


def assess_strategy_account(
    document: object,
    *,
    analysis: PortfolioAnalysis,
    captured_at: datetime,
    metadata: Sequence[TBankInstrumentMetadata] = (),
    mappings: Sequence[IssuerEvidence] = (),
    ratings: Mapping[str, Sequence[TBankRating]] | None = None,
    now: datetime | None = None,
    candidates: Sequence[StrategyCandidateFacts] = (),
) -> dict[str, Any]:
    """Assess current exposures; never turn an unknown into a feasible purchase."""
    observed = now or datetime.now(UTC)
    if observed.tzinfo is None or not _fresh(captured_at, observed, PORTFOLIO_MAX_AGE):
        raise ValueError("strategy_snapshot_not_fresh")
    data = normalize_document(document)
    nav = _amount(analysis.nav_rub)
    if nav is None or analysis.status == "needs_reconciliation":
        raise ValueError("strategy_snapshot_not_reconciled")
    totals, known, complete = _position_totals(analysis)
    residual = nav - sum(totals.values(), _ZERO)
    if residual < Decimal("-0.01"):
        raise ValueError("strategy_snapshot_not_reconciled")
    complete = complete and abs(residual) <= Decimal("0.01")
    complete = complete and analysis.status == "observed"
    checks = [
        _check(
            "allocation",
            "Целевое распределение",
            "evaluated" if complete and nav > 0 else "unknown",
            "Сравнение с фактическими позициями и рублями. Другие валюты и неполные позиции "
            "не выдаются за свободные рубли.",
            value={"unclassified_rub": _text(max(_ZERO, residual)), "complete": complete},
            sources=("portfolio", "positions"),
        )
    ]
    cash, cash_checks = _cash_checks(data, analysis, nav)
    checks.extend(cash_checks)
    checks.extend(_class_checks(data, totals, nav, complete))
    checks.extend(
        _concentration_checks(data, known, mappings, nav=nav, complete=complete, now=observed)
    )
    checks.append(
        _ceiling(
            "fund_wrapper_cap_percent",
            "Один фонд как инструмент",
            max(
                (_amount(p.value_rub) or _ZERO for p in known if p.instrument_type == "etf"),
                default=_ZERO,
            ),
            data["rules"]["fund_wrapper_cap_percent"],
            nav=nav,
            complete=complete,
            sources=("portfolio",),
        )
    )
    checks.extend(_flag_checks(data, totals, complete))
    rating_checks, rating_rows = _rating_checks(
        data,
        known,
        ratings or {},
        nav=nav,
        complete=complete and totals["funds"] == 0,
        now=observed,
    )
    checks.extend(rating_checks)
    by_uid = {item.uid: item for item in metadata}
    if len(by_uid) != len(metadata):
        raise ValueError("strategy_ambiguous_metadata")
    checks.extend(_term_checks(data, analysis.securities, by_uid, observed))
    checks.extend(_dependent_checks(data, nav))
    requirements = _METHOD_REQUIREMENTS[data["base_preset_id"]]
    selection = select_strategy_candidates(data, candidates, as_of=observed)
    return {
        "status": "assessed",
        "stage": "account_constraints",
        "execution_enabled": False,
        "candidate_selection_ready": selection["candidate_selection_ready"],
        "selection": selection,
        "proposed_trades": [],
        "strategy_hash": document_hash(data),
        "base_preset_id": data["base_preset_id"],
        "nav_rub": _text(nav),
        "captured_at": captured_at.isoformat(),
        "valid_until": (captured_at + PORTFOLIO_MAX_AGE).isoformat(),
        "allocation": _allocation_rows(data, totals, nav, complete),
        "cash": cash,
        "checks": checks,
        "ratings": rating_rows,
        "method_requirements": list(requirements),
        "probability_of_profit": None,
        "probability_reason": "Лимиты и подбор по фактам не оценивают вероятность будущей прибыли.",
        "scope": "Проверка выбранной рабочей стратегии на фактическом составе счёта. "
        "Это не полный подбор покупок: неизвестные условия показаны отдельно. "
        "Подтверждённые ограничения и брокерские поручения не изменены.",
    }


@dataclass(frozen=True, slots=True)
class StrategyFact:
    """An observation with its availability time, not merely period end."""

    value: Decimal | int | str | bool | datetime | Mapping[str, Any]
    available_at: datetime
    source_url: str


def _dividend_coverage_date(value: object) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(_DIVIDEND_COVERAGE_INVALID) from exc
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(_DIVIDEND_COVERAGE_INVALID)
    try:
        return value.astimezone(UTC)
    except (ValueError, OverflowError) as exc:
        raise ValueError(_DIVIDEND_COVERAGE_INVALID) from exc


def _dividend_coverage_amount(value: object, *, nonnegative: bool) -> str:
    if (isinstance(value, bool) or not isinstance(value, (str, int, Decimal))
            or len(str(value)) > 80):
        raise ValueError(_DIVIDEND_COVERAGE_INVALID)
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(_DIVIDEND_COVERAGE_INVALID) from exc
    exponent = number.as_tuple().exponent
    if (
        not number.is_finite() or not isinstance(exponent, int)
        or exponent < -28 or exponent > 15 or number.copy_abs() > Decimal("1e15")
        or (nonnegative and number < 0)
    ):
        raise ValueError(_DIVIDEND_COVERAGE_INVALID)
    return format(number, "f")


def normalize_dividend_cashflow_coverage(
    value: object, *, available_at: datetime
) -> dict[str, Any]:
    """Validate same-issuer annual cash flows in one disclosed original currency."""
    if not isinstance(value, Mapping) or set(value) != _DIVIDEND_COVERAGE_KEYS:
        raise ValueError(_DIVIDEND_COVERAGE_INVALID)
    issuer, currency = value["issuer_id"], value["currency"]
    if not isinstance(issuer, str) or not 1 <= len(issuer.strip()) <= 200:
        raise ValueError(_DIVIDEND_COVERAGE_INVALID)
    issuer = issuer.strip()
    if value["scope"] != "consolidated_issuer_all_equity":
        raise ValueError(_DIVIDEND_COVERAGE_INVALID)
    if (
        not isinstance(currency, str) or len(currency) != 3
        or not currency.isascii() or not currency.isalpha() or currency != currency.upper()
    ):
        raise ValueError(_DIVIDEND_COVERAGE_INVALID)
    if type(value["cashflows_complete"]) is not bool:
        raise ValueError(_DIVIDEND_COVERAGE_INVALID)
    start = _dividend_coverage_date(value["period_start"])
    end = _dividend_coverage_date(value["period_end"])
    available = _dividend_coverage_date(available_at)
    if (start >= end or end > available
            or not timedelta(days=330) <= end - start <= timedelta(days=400)):
        raise ValueError(_DIVIDEND_COVERAGE_INVALID)
    amounts = {
        key: _dividend_coverage_amount(value[key], nonnegative=key != "operating_cashflow")
        for key in ("operating_cashflow", "capital_expenditure", "gross_dividends_paid")
    }
    return {
        "issuer_id": issuer, "scope": value["scope"], "currency": currency,
        "period_start": start.isoformat(), "period_end": end.isoformat(),
        **amounts, "cashflows_complete": value["cashflows_complete"],
    }


@dataclass(frozen=True, slots=True)
class FundConstituent:
    issuer_id: str
    sector: str
    group_id: str
    weight_percent: Decimal
    available_at: datetime
    source_url: str


@dataclass(frozen=True, slots=True)
class StrategyCandidateFacts:
    """Read-only research evidence; never an executable broker order."""

    instrument_uid: str
    ticker: str
    asset_class: str
    lot_size: int
    currency: str
    facts: Mapping[str, StrategyFact] = field(default_factory=dict)
    constituents: tuple[FundConstituent, ...] = ()
    fact_history: Mapping[str, tuple[StrategyFact, ...]] = field(default_factory=dict)


def _known_observation(
    candidate: StrategyCandidateFacts,
    key: str,
    as_of: datetime,
) -> StrategyFact | None:
    observations = list(candidate.fact_history.get(key, ()))
    latest = candidate.facts.get(key)
    if latest is not None:
        observations.append(latest)
    known = [
        fact
        for fact in observations
        if fact.available_at.tzinfo is not None
        and fact.available_at <= as_of
        and _source_url(fact.source_url)
    ]
    if not known:
        return None
    return max(known, key=lambda fact: fact.available_at)


def _known_fact(candidate: StrategyCandidateFacts, key: str, as_of: datetime) -> object:
    fact = _known_observation(candidate, key, as_of)
    return fact.value if fact is not None else None


def _numeric_fact(
    candidate: StrategyCandidateFacts,
    key: str,
    as_of: datetime,
) -> Decimal | None:
    raw = _known_fact(candidate, key, as_of)
    if isinstance(raw, bool) or not isinstance(raw, (Decimal, int, str)):
        return None
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return None
    return value if value.is_finite() and value.copy_abs() <= Decimal("1e15") else None


def _constituents_known(candidate: StrategyCandidateFacts, as_of: datetime) -> bool:
    rows = candidate.constituents
    return (
        bool(rows)
        and all(
            row.issuer_id
            and row.sector
            and row.group_id
            and row.weight_percent.is_finite()
            and 0 < row.weight_percent <= 100
            and row.available_at.tzinfo is not None
            and row.available_at <= as_of
            and _source_url(row.source_url)
            for row in rows
        )
        and sum((row.weight_percent for row in rows), _ZERO) == 100
    )


def _bond_maturity(
    candidate: StrategyCandidateFacts,
    data: Mapping[str, Any],
    as_of: datetime,
) -> tuple[list[str], int | None]:
    reasons: list[str] = []
    maturity = _known_fact(candidate, "maturity_date", as_of)
    months: int | None = None
    if not isinstance(maturity, datetime) or maturity.tzinfo is None:
        reasons.append("missing:maturity_date")
    else:
        months = (maturity.year - as_of.year) * 12 + maturity.month - as_of.month
        limits = [
            _amount(data[section][key])
            for section, key in (
                ("profile", "horizon_months"),
                ("policy", "max_term_months"),
            )
        ]
        if any(limit is None for limit in limits):
            reasons.append("missing:maturity_limit")
        elif maturity <= as_of or any(
            Decimal(str((maturity - as_of).total_seconds())) / 86400
            > (calendar_horizon_days(limit, as_of) or _ZERO)
            for limit in limits
            if limit is not None
        ):
            reasons.append("maturity_limit")
    return reasons, months


def _ladder_rung_ends(data: Mapping[str, Any], as_of: datetime) -> tuple[datetime, ...]:
    limits = [
        _amount(data[section][key])
        for section, key in (("profile", "horizon_months"), ("policy", "max_term_months"))
    ]
    if any(limit is None or limit <= 0 for limit in limits):
        return ()
    horizon = int(min(limit for limit in limits if limit is not None))
    step = int(strategy_rule_set(data["base_preset_id"])["rung_months"])
    ends = []
    for months in range(step, horizon + step, step):
        end = _calendar_horizon_end(Decimal(min(months, horizon)), as_of)
        if end is None:
            return ()
        ends.append(end)
    return tuple(ends)


def _bond_maturity_bucket(
    candidate: StrategyCandidateFacts,
    data: Mapping[str, Any],
    as_of: datetime,
    rules: Mapping[str, Any],
    months: int,
    engine_version: str,
) -> str:
    if rules["ranking"] != "maturity_ladder" or engine_version not in {"1.3.2", "1.3.3"}:
        return str(max(0, months) // int(rules.get("rung_months", 12)))
    maturity = _known_fact(candidate, "maturity_date", as_of)
    if isinstance(maturity, datetime):
        for index, end in enumerate(_ladder_rung_ends(data, as_of)):
            if maturity <= end:
                return str(index)
    return ""


def _credit_category_reasons(notch: str, data: Mapping[str, Any]) -> list[str]:
    if notch != "NR" and notch not in RATING_LEVELS[10:24]:
        return []
    key = "max_unknown_percent" if notch == "NR" else "max_below_grade_percent"
    cap = _amount(data["policy"][key])
    if cap is None:
        return [_MISSING_PREFIX + key]
    if cap == 0:
        return [key + "_excluded"]
    return []


def _bond_criteria(
    candidate: StrategyCandidateFacts,
    data: Mapping[str, Any],
    as_of: datetime,
    rules: Mapping[str, Any],
) -> tuple[list[str], int | None]:
    reasons, months = _bond_maturity(candidate, data, as_of)
    notch = _known_fact(candidate, "rating", as_of)
    if not isinstance(notch, str) or notch not in RATING_LEVELS:
        notch = "NR"
    if Decimal(data["rules"]["rating_caps"][notch]) == 0:
        reasons.append("missing:rating" if notch == "NR" else "rating_excluded")
    reasons.extend(_credit_category_reasons(notch, data))
    if notch in RATING_LEVELS[10:24] and not data["profile"]["allow_below_investment_grade"]:
        reasons.append("below_grade_not_allowed")
    minimum = rules.get("minimum_rating")
    if minimum and RATING_LEVELS.index(notch) > RATING_LEVELS.index(minimum):
        reasons.append("minimum_rating")
    if _known_fact(candidate, "perpetual", as_of) is not False:
        reasons.append("missing:finite_bond_term")
    return reasons, months


def _required_numbers(
    candidate: StrategyCandidateFacts,
    as_of: datetime,
    keys: tuple[str, ...],
) -> tuple[dict[str, Decimal], list[str]]:
    values, missing = {}, []
    for key in keys:
        value = _numeric_fact(candidate, key, as_of)
        if value is None:
            missing.append(_MISSING_PREFIX + key)
        values[key] = _ZERO if value is None else value
    return values, missing


def _training_values(
    candidate: StrategyCandidateFacts,
    data: Mapping[str, Any],
    as_of: datetime,
) -> tuple[dict[str, Decimal], list[str]]:
    values, reasons = _required_numbers(
        candidate,
        as_of,
        (
            "history_observations",
            "volatility_percent",
            "max_drawdown_percent",
            "momentum_percent",
            "price_rub",
            "daily_volume_lots",
        ),
    )
    if values["history_observations"] < 60:
        reasons.append("insufficient_training_history")
    if values["price_rub"] <= 0 or values["daily_volume_lots"] <= 0:
        reasons.append("price_or_liquidity_missing")
    if values["volatility_percent"] < 0 or values["max_drawdown_percent"] < 0:
        reasons.append("invalid_risk_metric")
    drawdown_cap = _amount(data["profile"]["max_drawdown_percent"])
    if drawdown_cap is not None and values["max_drawdown_percent"] > drawdown_cap:
        reasons.append("historical_drawdown_limit")
    return values, reasons


def _cashflow_score(
    candidate: StrategyCandidateFacts,
    as_of: datetime,
    rules: Mapping[str, Any],
) -> tuple[Decimal, list[str], str]:
    values, reasons = _required_numbers(candidate, as_of, ("cashflow_yield_percent",))
    score = values["cashflow_yield_percent"]
    if score <= 0:
        reasons.append("positive_documented_cashflow_required")
    if rules["ranking"] == "floating_cashflow" and candidate.asset_class == "bonds":
        if _known_fact(candidate, "floating_coupon", as_of) is not True:
            reasons.append("floating_coupon_required")
        if _known_fact(candidate, "coupon_formula_verified", as_of) is not True:
            reasons.append("missing:coupon_formula")
    return score, reasons, ""


def _quality_value_score(
    candidate: StrategyCandidateFacts,
    as_of: datetime,
    rules: Mapping[str, Any],
) -> tuple[Decimal, list[str], str] | None:
    if candidate.asset_class != "shares":
        return None
    values, reasons = _required_numbers(
        candidate,
        as_of,
        ("roe_percent", "debt_to_ebitda", "free_cashflow_yield_percent"),
    )
    roe, debt, cashflow = (
        values[key]
        for key in (
            "roe_percent",
            "debt_to_ebitda",
            "free_cashflow_yield_percent",
        )
    )
    if roe < Decimal(rules["minimum_roe_percent"]):
        reasons.append("return_on_equity_limit")
    if debt < 0 or debt > Decimal(rules["maximum_debt_to_ebitda"]):
        reasons.append("debt_limit")
    if cashflow < Decimal(rules["minimum_fcf_yield_percent"]):
        reasons.append("cashflow_value_limit")
    score = max(_ZERO, cashflow) * max(_ZERO, roe) / (1 + max(_ZERO, debt))
    return score, reasons, ""


def _index_cost_score(
    candidate: StrategyCandidateFacts,
    as_of: datetime,
    rules: Mapping[str, Any],
) -> tuple[Decimal, list[str], str] | None:
    if candidate.asset_class != "funds":
        return None
    values, reasons = _required_numbers(candidate, as_of, ("expense_ratio_percent",))
    expense = values["expense_ratio_percent"]
    if _known_fact(candidate, "index_tracking", as_of) is not True:
        reasons.append("missing:index_tracking")
    if not _constituents_known(candidate, as_of):
        reasons.append("missing:fund_constituents")
    else:
        if len({row.issuer_id for row in candidate.constituents}) < rules["minimum_constituents"]:
            reasons.append("fund_too_concentrated")
        dimensions, _ = _candidate_dimensions(candidate, as_of)
        if max(dimensions["issuer"].values()) * 100 > Decimal(rules["maximum_constituent_percent"]):
            reasons.append("fund_constituent_limit")
    if expense < 0 or expense > Decimal(rules["maximum_expense_percent"]):
        reasons.append("fund_expense_limit")
    return 1 / (Decimal("0.01") + max(_ZERO, expense)), reasons, ""


def _regime_risk_score(
    candidate: StrategyCandidateFacts,
    as_of: datetime,
    rules: Mapping[str, Any],
) -> tuple[Decimal, list[str], str]:
    values, reasons = _required_numbers(
        candidate,
        as_of,
        (
            "growth_beta",
            "inflation_beta",
            "factor_observations",
            "volatility_percent",
        ),
    )
    growth, inflation = values["growth_beta"], values["inflation_beta"]
    if values["factor_observations"] < rules["minimum_factor_observations"]:
        reasons.append("insufficient_factor_history")
    if growth == 0 or inflation == 0:
        reasons.append("factor_exposure_not_identified")
    bucket = ("growth+" if growth > 0 else "growth-") + (
        "/inflation+" if inflation > 0 else "/inflation-"
    )
    return 1 / (1 + max(_ZERO, values["volatility_percent"])), reasons, bucket


def _covered_dividends_score(
    candidate: StrategyCandidateFacts,
    as_of: datetime,
    rules: Mapping[str, Any],
    *,
    engine_version: str = "1.3.1",
) -> tuple[Decimal, list[str], str] | None:
    if candidate.asset_class != "shares":
        return None
    keys: tuple[str, ...] = ("dividend_yield_percent", "payout_ratio_percent", "debt_to_ebitda")
    if engine_version not in {"1.3.2", "1.3.3"}:
        keys += ("free_cashflow_yield_percent",)
    values, reasons = _required_numbers(
        candidate, as_of, keys,
    )
    score, payout, debt = (
        values[key]
        for key in (
            "dividend_yield_percent",
            "payout_ratio_percent",
            "debt_to_ebitda",
        )
    )
    if _known_fact(candidate, "dividend_declared", as_of) is not True:
        reasons.append("missing:dividend_decision")
    if engine_version in {"1.3.2", "1.3.3"}:
        _, coverage_reasons = _dividend_cashflow_evidence(candidate, as_of)
        reasons.extend(coverage_reasons)
    elif values["free_cashflow_yield_percent"] <= 0:
        reasons.append("dividends_not_cashflow_covered")
    if not 0 <= payout <= Decimal(rules["maximum_payout_percent"]):
        reasons.append("payout_limit")
    if not 0 <= debt <= Decimal(rules["maximum_debt_to_ebitda"]):
        reasons.append("debt_limit")
    if score <= 0:
        reasons.append("positive_dividend_required")
    return score, reasons, ""


def _dividend_cashflow_evidence(
    candidate: StrategyCandidateFacts, as_of: datetime,
) -> tuple[dict[str, Any] | None, list[str]]:
    observation = _known_observation(candidate, "dividend_cashflow_coverage", as_of)
    if observation is None:
        return None, [_DIVIDEND_COVERAGE_MISSING]
    try:
        value = normalize_dividend_cashflow_coverage(
            observation.value, available_at=observation.available_at,
        )
    except ValueError:
        return None, [_DIVIDEND_COVERAGE_MISSING]
    reasons = []
    if value["issuer_id"] != _known_fact(candidate, "issuer_id", as_of):
        reasons.append("dividend_coverage_issuer_mismatch")
    if not value["cashflows_complete"]:
        reasons.append(_DIVIDEND_COVERAGE_MISSING)
    earliest = _calendar_horizon_end(Decimal(-18), as_of)
    if earliest is not None and datetime.fromisoformat(value["period_end"]) < earliest:
        reasons.append("dividend_coverage_stale")
    # Input bounds allow 16 integer and 28 fractional digits. Preserve the exact
    # subtraction/comparison even at the smallest permitted unit near 1e15.
    with localcontext() as context:
        context.prec = 64
        cashflow = Decimal(value["operating_cashflow"]) - Decimal(value["capital_expenditure"])
        dividends = Decimal(value["gross_dividends_paid"])
        ratio = None
        if dividends <= 0:
            reasons.append("positive_dividend_required")
        else:
            ratio = format(cashflow / dividends, "f")
            if cashflow < dividends:
                reasons.append("dividends_not_cashflow_covered")
    return {
        key: value[key] for key in (
            "issuer_id", "currency", "period_start", "period_end", "operating_cashflow",
            "capital_expenditure", "gross_dividends_paid",
        )
    } | {
        "free_cashflow": format(cashflow, "f"), "coverage_ratio": ratio,
        "available_at": observation.available_at.astimezone(UTC).isoformat(),
        "source_url": observation.source_url,
    }, reasons


_FACT_SCORERS = {
    "documented_cashflow": _cashflow_score,
    "floating_cashflow": _cashflow_score,
    "quality_value": _quality_value_score,
    "index_cost": _index_cost_score,
    "regime_risk": _regime_risk_score,
}


def _fact_method_score(
    candidate: StrategyCandidateFacts, as_of: datetime,
    rules: Mapping[str, Any], engine_version: str,
) -> tuple[Decimal, list[str], str] | None:
    if rules["ranking"] == "covered_dividends":
        return _covered_dividends_score(candidate, as_of, rules, engine_version=engine_version)
    scorer = _FACT_SCORERS.get(rules["ranking"])
    if scorer is None:
        return None
    return scorer(candidate, as_of, rules)


def _yield_floor_reasons(
    candidate: StrategyCandidateFacts,
    data: Mapping[str, Any],
    as_of: datetime,
) -> list[str]:
    if data["rules"]["yield_floor"] != "key_rate":
        return []
    values, reasons = _required_numbers(candidate, as_of, ("net_yield_percent", "key_rate_percent"))
    if values["net_yield_percent"] < (
        values["key_rate_percent"] + Decimal(data["rules"]["yield_margin_pp"])
    ):
        reasons.append("net_yield_floor")
    return reasons


def _price_mandate_score(
    mode: str,
    values: Mapping[str, Decimal],
    rules: Mapping[str, Any],
) -> tuple[Decimal, list[str]]:
    volatility, momentum = values["volatility_percent"], values["momentum_percent"]
    score = 1 / (1 + max(_ZERO, volatility))
    reasons = []
    if mode == "short_quality" and volatility > Decimal(rules["maximum_volatility_percent"]):
        reasons.append("historical_volatility_limit")
    elif mode == "positive_momentum":
        if momentum <= Decimal(rules["minimum_momentum_percent"]):
            reasons.append("momentum_not_positive")
        score = max(_ZERO, momentum)
    elif mode == "risk_adjusted_momentum":
        score = (100 + max(Decimal("-99"), momentum)) / (1 + max(_ZERO, volatility))
    return score, reasons


def _method_score(
    candidate: StrategyCandidateFacts,
    data: Mapping[str, Any],
    as_of: datetime,
    engine_version: str,
) -> tuple[Decimal | None, list[str], str]:
    rules = strategy_rule_set(data["base_preset_id"])
    mode = rules["ranking"]
    values, reasons = _training_values(candidate, data, as_of)
    if engine_version == "1.3.3" and data["profile"]["max_drawdown_percent"] is None:
        reasons.append("missing:drawdown_limit")
    score, price_reasons = _price_mandate_score(mode, values, rules)
    reasons.extend(price_reasons)
    bucket = ""
    if candidate.asset_class == "bonds":
        bond_reasons, months = _bond_criteria(candidate, data, as_of, rules)
        reasons.extend(bond_reasons)
        if mode in {"maturity_ladder", "short_quality"} and months is not None:
            bucket = _bond_maturity_bucket(candidate, data, as_of, rules, months, engine_version)
            score /= 1 + max(0, months)
    details = _fact_method_score(candidate, as_of, rules, engine_version)
    if details is not None:
        score, method_reasons, bucket = details
        reasons.extend(method_reasons)
    reasons.extend(_yield_floor_reasons(candidate, data, as_of))
    return (None if reasons else score), sorted(set(reasons)), bucket


def _candidate_dimensions(
    candidate: StrategyCandidateFacts,
    as_of: datetime,
) -> tuple[dict[str, dict[str, Decimal]], list[str]]:
    dimensions: dict[str, dict[str, Decimal]] = {name: {} for name in ("issuer", "sector", "group")}
    if candidate.asset_class == "funds":
        if not _constituents_known(candidate, as_of):
            return dimensions, ["fund_lookthrough"]
        for row in candidate.constituents:
            for name, key in (
                ("issuer", row.issuer_id),
                ("sector", row.sector),
                ("group", row.group_id),
            ):
                dimensions[name][key] = dimensions[name].get(key, _ZERO) + row.weight_percent / 100
        return dimensions, []
    missing = []
    for name, key in (("issuer", "issuer_id"), ("sector", "sector"), ("group", "group_id")):
        raw = _known_fact(candidate, key, as_of)
        if isinstance(raw, str) and raw:
            dimensions[name][raw] = Decimal(1)
        else:
            missing.append(name)
    return dimensions, missing


_RankedCandidate = tuple[StrategyCandidateFacts, Decimal, str]
_ExposureLedger = dict[str, dict[str, Decimal]]


def _candidate_fact_value(key: str, fact: StrategyFact, engine_version: str) -> object:
    if key == "dividend_cashflow_coverage" and engine_version in {"1.3.2", "1.3.3"}:
        try:
            return normalize_dividend_cashflow_coverage(fact.value, available_at=fact.available_at)
        except ValueError:
            return None
    return str(fact.value)


def _rank_candidates(
    data: Mapping[str, Any],
    candidates: Sequence[StrategyCandidateFacts],
    as_of: datetime,
    engine_version: str,
) -> tuple[list[dict[str, Any]], list[_RankedCandidate]]:
    rows, eligible = [], []
    for candidate in candidates:
        reasons = []
        if candidate.asset_class not in ALLOCATION_KEYS[:3]:
            reasons.append("unsupported_asset_class")
        elif (
            candidate.asset_class in data["excluded"]
            or data["allocation"][candidate.asset_class] == 0
        ):
            reasons.append("asset_class_excluded")
        if candidate.currency.upper() != "RUB":
            reasons.append("non_ruble_series")
        if type(candidate.lot_size) is not int or candidate.lot_size <= 0:
            reasons.append("lot_size_missing")
        score, evidence_reasons, bucket = _method_score(candidate, data, as_of, engine_version)
        reasons = sorted(set(reasons + evidence_reasons))
        rows.append(
            {
                "instrument_uid": candidate.instrument_uid,
                "ticker": candidate.ticker,
                "asset_class": candidate.asset_class,
                "eligible": not reasons,
                "reasons": reasons,
                "score": _text(score) if not reasons else None,
                "bucket": bucket,
                "facts": {
                    key: {
                        "value": _candidate_fact_value(key, fact, engine_version),
                        "available_at": fact.available_at.isoformat(),
                        "source_url": fact.source_url,
                    }
                    for key in sorted(set(candidate.facts) | set(candidate.fact_history))
                    if (fact := _known_observation(candidate, key, as_of)) is not None
                },
            }
        )
        if not reasons and score is not None:
            eligible.append((candidate, score, bucket))
    return rows, eligible


def _bond_exposure_limits(
    candidate: StrategyCandidateFacts,
    data: Mapping[str, Any],
    as_of: datetime,
    *,
    enforce_credit_permission: bool,
) -> list[tuple[str, str, Decimal, Decimal]]:
    """Keep rating, credit-category and explicit permission ceilings independent."""
    fact = _known_fact(candidate, "rating", as_of)
    notch = fact if isinstance(fact, str) and fact in RATING_LEVELS else "NR"
    limits = [("rating", notch, Decimal(1), Decimal(data["rules"]["rating_caps"][notch]))]
    if notch == "NR" or notch in RATING_LEVELS[10:24]:
        credit_key = "max_unknown_percent" if notch == "NR" else "max_below_grade_percent"
        cap = _amount(data["policy"][credit_key]) or _ZERO
        limits.append(("credit", credit_key, Decimal(1), cap))
    if (enforce_credit_permission and notch in RATING_LEVELS[10:24]
            and not data["profile"]["allow_below_investment_grade"]):
        limits.append(("credit", "below_grade_not_allowed", Decimal(1), _ZERO))
    return limits


def _candidate_exposure_limits(
    candidate: StrategyCandidateFacts,
    data: Mapping[str, Any],
    as_of: datetime,
    missing: set[str],
    *,
    enforce_credit_permission: bool = True,
) -> list[tuple[str, str, Decimal, Decimal]]:
    dimensions, unknown = _candidate_dimensions(candidate, as_of)
    missing.update("unverified:" + key for key in unknown)
    limits: list[tuple[str, str, Decimal, Decimal]] = []
    for name, entries in dimensions.items():
        cap = _amount(data["policy"]["max_" + name + "_percent"])
        if cap is None:
            missing.add("policy.max_" + name + "_percent")
        else:
            limits.extend((name, key, exposure, cap) for key, exposure in entries.items())
    if candidate.asset_class == "bonds":
        limits.extend(_bond_exposure_limits(
            candidate, data, as_of, enforce_credit_permission=enforce_credit_permission,
        ))
    return limits


def _bounded_candidate_weight(
    candidate: StrategyCandidateFacts,
    weight: Decimal,
    data: Mapping[str, Any],
    as_of: datetime,
    used: _ExposureLedger,
    missing: set[str],
    allocated: Decimal = _ZERO,
) -> Decimal:
    cap = _amount(data["policy"]["max_instrument_percent"])
    if cap is None:
        missing.add("policy.max_instrument_percent")
        return _ZERO
    cap = max(_ZERO, cap - allocated)
    weight = min(weight, cap)
    if candidate.asset_class == "funds":
        weight = min(
            weight, max(_ZERO, Decimal(data["rules"]["fund_wrapper_cap_percent"]) - allocated)
        )
    limits = _candidate_exposure_limits(candidate, data, as_of, missing)
    for name, key, exposure, cap in limits:
        weight = min(weight, max(_ZERO, cap - used[name][key]) / exposure)
    for name, key, exposure, _ in limits:
        used[name][key] += weight * exposure
    return weight


def _ranked_weight(
    ranked: _RankedCandidate,
    matching: Sequence[_RankedCandidate],
    budget: Decimal,
    mode: str,
) -> Decimal:
    _, score, bucket = ranked
    if mode in {"maturity_ladder", "regime_risk"}:
        buckets = {item[2] for item in matching}
        peers = [item for item in matching if item[2] == bucket]
        if mode == "maturity_ladder":
            return budget / len(buckets) / len(peers)
        regime_score = sum((item[1] for item in peers), _ZERO)
        return budget / len(buckets) * score / regime_score
    score_sum = sum((item[1] for item in matching), _ZERO)
    return budget * (score / score_sum if score_sum else Decimal(1) / len(matching))


def _allocate_ranked_group(
    matching: Sequence[_RankedCandidate],
    budget: Decimal,
    mode: str,
    data: Mapping[str, Any],
    as_of: datetime,
    used: _ExposureLedger,
    missing: set[str],
    *,
    redistribute: bool,
) -> dict[str, Decimal]:
    """Redistribute clipped weights while preserving every aggregate risk ceiling."""
    weights = {item[0].instrument_uid: _ZERO for item in matching}
    active = list(matching)
    tolerance = Decimal("0.000000000001")
    # Every additional round removes a saturated candidate. The final round
    # distributes all remaining capital when the remaining capacities permit it.
    for _ in range(len(matching) + 1 if redistribute else 1):
        remaining = budget - sum(weights.values(), _ZERO)
        if remaining <= tolerance or not active:
            break
        next_active = []
        for ranked in active:
            candidate = ranked[0]
            uid = candidate.instrument_uid
            proposed = _ranked_weight(ranked, active, remaining, mode)
            increment = _bounded_candidate_weight(
                candidate, proposed, data, as_of, used, missing, weights[uid]
            )
            weights[uid] += increment
            if increment + tolerance >= proposed:
                next_active.append(ranked)
        if len(next_active) == len(active):
            break
        active = next_active
    return weights


def _class_weights(
    data: Mapping[str, Any],
    matching: Sequence[_RankedCandidate],
    as_of: datetime,
    used: _ExposureLedger,
    missing: set[str],
    budget: Decimal,
    *,
    redistribute: bool,
) -> dict[str, Decimal]:
    mode = strategy_rule_set(data["base_preset_id"])["ranking"]
    # Ladder rungs and economic regimes have separate deliberate budgets.
    # A constrained rung must not silently transfer its mandate to another rung.
    groups: list[Sequence[_RankedCandidate]]
    if redistribute and mode in {"maturity_ladder", "regime_risk"}:
        buckets = sorted({item[2] for item in matching})
        groups = [[item for item in matching if item[2] == bucket] for bucket in buckets]
    else:
        groups = [matching]
    weights: dict[str, Decimal] = {}
    for group in groups:
        weights.update(
            _allocate_ranked_group(
                group,
                budget / len(groups),
                mode,
                data,
                as_of,
                used,
                missing,
                redistribute=redistribute,
            )
        )
    return weights


def _ladder_weights(
    data: Mapping[str, Any],
    matching: Sequence[_RankedCandidate],
    as_of: datetime,
    used: _ExposureLedger,
    missing: set[str],
    budget: Decimal,
) -> dict[str, Decimal]:
    ends = _ladder_rung_ends(data, as_of)
    if not ends:
        missing.add("ladder_horizon_unavailable")
        return {}
    rung_budget = budget / len(ends)
    weights: dict[str, Decimal] = {}
    for index in range(len(ends)):
        group = [item for item in matching if item[2] == str(index)]
        allocations = _allocate_ranked_group(
            group, rung_budget, "maturity_ladder", data, as_of, used, missing, redistribute=True,
        )
        weights.update(allocations)
    return weights


def _selected_class_rows(
    matching: Sequence[_RankedCandidate],
    weights: Mapping[str, Decimal],
    mode: str,
    kind: str,
    target: Decimal,
    missing: set[str],
) -> list[dict[str, Any]]:
    selected, allocated = [], _ZERO
    for ranked in matching:
        candidate, _, bucket = ranked
        weight = weights.get(candidate.instrument_uid, _ZERO)
        if weight <= 0:
            continue
        allocated += weight
        selected.append(
            {
                "instrument_uid": candidate.instrument_uid,
                "ticker": candidate.ticker,
                "asset_class": kind,
                "target_weight_percent": _text(weight),
                "reason": mode,
                "bucket": bucket,
            }
        )
    if allocated + Decimal("0.000001") < target:
        missing.add("unfilled_target:" + kind)
    return selected


def _select_asset_class(
    data: Mapping[str, Any],
    eligible: Sequence[_RankedCandidate],
    kind: str,
    as_of: datetime,
    used: _ExposureLedger,
    missing: set[str],
    *,
    engine_version: str,
) -> list[dict[str, Any]]:
    target = Decimal(data["allocation"][kind])
    if not target:
        return []
    class_cap = _amount(data["policy"][_CLASS_CAP[kind]])
    if class_cap is None:
        missing.add("policy." + _CLASS_CAP[kind])
        return []
    matching = sorted(
        (item for item in eligible if item[0].asset_class == kind),
        key=lambda item: (-item[1], item[0].instrument_uid),
    )
    mode = strategy_rule_set(data["base_preset_id"])["ranking"]
    calendar_ladder = (
        mode == "maturity_ladder" and kind == "bonds" and engine_version in {"1.3.2", "1.3.3"}
    )
    if not matching:
        missing.add("eligible_" + kind)
        if not calendar_ladder:
            return []
    if target > class_cap:
        missing.add("target_above_class_cap:" + kind)
    budget = min(target, class_cap)
    if calendar_ladder:
        weights = _ladder_weights(data, matching, as_of, used, missing, budget)
    else:
        weights = _class_weights(
            data, matching, as_of, used, missing, budget,
            redistribute=engine_version != "1.1.0",
        )
    return _selected_class_rows(matching, weights, mode, kind, target, missing)


def _ladder_coverage(
    data: Mapping[str, Any],
    selected: Sequence[Mapping[str, Any]],
    as_of: datetime,
    missing: set[str],
) -> list[dict[str, Any]]:
    ends = _ladder_rung_ends(data, as_of)
    if not ends:
        missing.update(("ladder_horizon_unavailable", "unfilled_target:bonds"))
        return []
    target = Decimal(data["allocation"]["bonds"]) / len(ends)
    rows = []
    start = as_of
    for index, end in enumerate(ends):
        allocated = sum(
            (Decimal(row["target_weight_percent"]) for row in selected
             if row["asset_class"] == "bonds" and row["bucket"] == str(index)), _ZERO,
        )
        if allocated + Decimal("0.000001") < target:
            missing.add("ladder_rung_unfilled:" + str(index + 1))
        rows.append({
            "rung": index + 1, "from": start.isoformat(), "to": end.isoformat(),
            "target_weight_percent": _text(target), "allocated_weight_percent": _text(allocated),
        })
        start = end
    return rows


def _selection_status(
    selected: Sequence[Mapping[str, Any]],
    missing: set[str],
    *,
    cash_only: bool,
    engine_version: str,
) -> str:
    ready = (
        bool(selected) or (cash_only and engine_version in {"1.3.1", "1.3.2", "1.3.3"})
    ) and not missing
    if ready:
        return "ready"
    if selected:
        return "partial"
    return "insufficient_data"


def _current_selection_evidence(
    data: Mapping[str, Any],
    candidates: Sequence[StrategyCandidateFacts],
    selected: list[dict[str, Any]],
    as_of: datetime,
    missing: set[str],
) -> dict[str, Any]:
    mode = strategy_rule_set(data["base_preset_id"])["ranking"]
    if mode == "maturity_ladder" and data["allocation"]["bonds"]:
        return {"ladder_rungs": _ladder_coverage(data, selected, as_of, missing)}
    if mode == "covered_dividends":
        by_uid = {candidate.instrument_uid: candidate for candidate in candidates}
        for row in selected:
            if row["asset_class"] != "shares":
                continue
            evidence, reasons = _dividend_cashflow_evidence(by_uid[row["instrument_uid"]], as_of)
            if evidence is not None and not reasons:
                row["dividend_cashflow_coverage"] = evidence
    return {}


def select_strategy_candidates(
    document: object,
    candidates: Sequence[StrategyCandidateFacts],
    *,
    as_of: datetime,
    engine_version: str = "1.3.3",
) -> dict[str, Any]:
    """Screen dated facts, rank by the mandate and allocate bounded research weights.

    Missing look-through or identities are exposed: a conditional research basket
    is useful, but it does not certify a complete personal investment selection.
    """
    data = normalize_document(document)
    if (as_of.tzinfo is None or len(candidates) > 100
            or engine_version not in {"1.1.0", "1.2.0", "1.3.0", "1.3.1", "1.3.2", "1.3.3"}):
        raise ValueError("strategy_candidate_input_invalid")
    ids = [row.instrument_uid for row in candidates]
    if any(not uid for uid in ids) or len(ids) != len(set(ids)):
        raise ValueError("strategy_duplicate_candidate")
    rows, eligible = _rank_candidates(data, candidates, as_of, engine_version)
    missing: set[str] = set()
    mode = strategy_rule_set(data["base_preset_id"])["ranking"]
    cash_only = data["allocation"]["cash"] == 100
    if mode == "regime_risk" and len({bucket for _, _, bucket in eligible}) < 4 and not (
        cash_only and engine_version in {"1.3.1", "1.3.2", "1.3.3"}
    ):
        missing.add("four_economic_regimes")
    used: _ExposureLedger = {
        name: defaultdict(Decimal) for name in ("issuer", "sector", "group", "rating", "credit")
    }
    selected = []
    for kind in ALLOCATION_KEYS[:3]:
        selected.extend(
            _select_asset_class(
                data, eligible, kind, as_of, used, missing,
                engine_version=engine_version,
            )
        )
    missing.update(
        reason
        for row in rows
        if "eligible_" + row["asset_class"] in missing
        for reason in row["reasons"]
        if reason.startswith(_MISSING_PREFIX)
    )
    details = {}
    if engine_version in {"1.3.2", "1.3.3"}:
        details = _current_selection_evidence(data, candidates, selected, as_of, missing)
    total = sum((Decimal(item["target_weight_percent"]) for item in selected), _ZERO)
    status = _selection_status(
        selected, missing, cash_only=cash_only, engine_version=engine_version,
    )
    return {
        "status": status,
        "candidate_selection_ready": status == "ready",
        "execution_enabled": False,
        "method": mode,
        "base_preset_id": data["base_preset_id"],
        "as_of": as_of.isoformat(),
        "candidates": rows,
        "selected": selected,
        "cash_weight_percent": _text(100 - total),
        "missing_requirements": sorted(missing),
        "probability_of_profit": None,
        "probability_reason": "Лимиты и подбор по фактам не оценивают вероятность будущей прибыли.",
        "scope": "Условный подбор по доступным на указанную дату фактам. Незаполненные доли "
        "остаются деньгами. Это исследовательская корзина, не торговое поручение.",
        **details,
    }


def candidate_weight_constraints(
    document: object,
    candidates: Sequence[StrategyCandidateFacts],
    weights: Mapping[str, Decimal],
    *,
    as_of: datetime,
    engine_version: str = "1.3.3",
) -> list[str]:
    """Recheck rounded, cost-adjusted holdings with the same look-through caps as selection."""
    data = normalize_document(document)
    missing: set[str] = set()
    used: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    classes: dict[str, Decimal] = defaultdict(Decimal)
    by_uid = {row.instrument_uid: row for row in candidates}
    for uid, weight in weights.items():
        if weight <= 0:
            continue
        candidate = by_uid.get(uid)
        if candidate is None:
            missing.add("held_instrument_evidence_missing:" + uid)
            continue
        classes[candidate.asset_class] += weight
        _holding_weight_limits(candidate, weight, data, missing)
        for name, key, exposure, limit in _candidate_exposure_limits(
            candidate, data, as_of, missing, enforce_credit_permission=engine_version == "1.3.3",
        ):
            used[name, key] += weight * exposure
            if used[name, key] > limit:
                missing.add("exposure_cap:" + name + ":" + key)
    _class_weight_limits(classes, data, missing)
    return sorted(missing)


def _holding_weight_limits(
    candidate: StrategyCandidateFacts, weight: Decimal, data: Mapping[str, Any], missing: set[str]
) -> None:
    uid = candidate.instrument_uid
    cap = _amount(data["policy"]["max_instrument_percent"])
    if cap is None or weight > cap:
        missing.add("instrument_cap:" + uid)
    if candidate.asset_class in data["excluded"]:
        missing.add("excluded_class:" + candidate.asset_class)
    if candidate.asset_class == "funds" and weight > Decimal(
        data["rules"]["fund_wrapper_cap_percent"]
    ):
        missing.add("fund_wrapper_cap:" + uid)


def _class_weight_limits(
    classes: Mapping[str, Decimal], data: Mapping[str, Any], missing: set[str]
) -> None:
    for kind, total in classes.items():
        key = {
            "shares": "max_share_percent",
            "bonds": "max_bond_percent",
            "funds": "max_etf_percent",
        }[kind]
        class_limit = _amount(data["policy"][key])
        if class_limit is None or total > class_limit:
            missing.add("class_cap:" + kind)
