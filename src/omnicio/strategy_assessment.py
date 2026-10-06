"""Read-only comparison of an exact saved strategy with sourced account evidence.

This is an assessment of constraints, not a trade allocator or a return forecast.
Unknown coverage is propagated; receiving a fresh HTTP response never manufactures
issuer identities, issue ratings, fund constituents, or future cash flows.
"""

from __future__ import annotations

import calendar
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Literal
from urllib.parse import urlsplit

from .freshness import PORTFOLIO_MAX_AGE
from .portfolio import PortfolioAnalysis, SecurityExposure
from .strategy import ALLOCATION_KEYS, RATING_LEVELS, document_hash, normalize_document
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
    rows = []
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


def _calendar_days(months: Decimal, now: datetime) -> Decimal | None:
    limit_month = now.year * 12 + now.month - 1 + int(months)
    year, month0 = divmod(limit_month, 12)
    if year > 9999:
        return None
    end = now.replace(
        year=year, month=month0 + 1, day=min(now.day, calendar.monthrange(year, month0 + 1)[1])
    )
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
    max_days = _calendar_days(months, now) if months is not None else None
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
        ("no_trade_band_percent", "Порог выгоды замены, % позиции"),
        ("min_replace_benefit_rub", "Минимальная выгода замены, ₽"),
    ):
        checks.append(
            _check(
                key,
                title,
                "inapplicable",
                "Проверка текущего состава не предлагает замену. При замене выгода после расходов "
                "должна быть строго выше большего из процентного и рублёвого порогов.",
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
    return {
        "status": "assessed",
        "stage": "account_constraints",
        "execution_enabled": False,
        "candidate_selection_ready": False,
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
        "scope": "Проверка выбранной рабочей стратегии на фактическом составе счёта. "
        "Это не полный подбор покупок: неизвестные условия показаны отдельно. "
        "Подтверждённые ограничения и брокерские поручения не изменены.",
    }
