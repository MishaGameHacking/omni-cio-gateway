"""Deterministic, read-only portfolio observations; never a trading authority."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation

from .financial import PERCENT_SCALE, RUB_QUANTUM
from .tbank import (
    TBankInstrumentMetadata,
    TBankMoney,
    TBankPortfolio,
    TBankPortfolioPosition,
    TBankPositions,
)

_SUPPORTED = {"share", "bond", "etf"}
_CLASS_LABELS = {
    "shares": "Акции",
    "bonds": "Облигации",
    "funds": "Фонды",
    "currencies": "Валюта и деньги",
    "futures": "Фьючерсы",
    "options": "Опционы",
    "structured_products": "Структурные продукты",
    "dfa": "ЦФА",
}
# This is only a review threshold. It is not a target allocation or an investment recommendation.
_CONCENTRATION_NOTICE = Decimal("25")


class PortfolioAnalysisError(ValueError):
    """Portfolio evidence is internally inconsistent or unsafe to interpret."""


@dataclass(frozen=True, slots=True)
class Allocation:
    key: str
    label: str
    value_rub: str
    nav_percent: str | None


@dataclass(frozen=True, slots=True)
class SecurityExposure:
    uid: str
    ticker: str
    name: str
    instrument_type: str
    sector: str
    country_of_risk: str
    for_qual_investor: bool | None
    blocked: bool
    value_rub: str | None
    nav_percent: str | None


@dataclass(frozen=True, slots=True)
class Observation:
    code: str
    priority: int
    title: str
    detail: str
    source_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PortfolioAnalysis:
    status: str
    nav_rub: str
    rub_cash_total: str
    rub_cash_blocked: str
    rub_cash_unblocked: str | None
    security_count: int
    valued_security_count: int
    sector_coverage_percent: str | None
    classes: tuple[Allocation, ...]
    sectors: tuple[Allocation, ...]
    securities: tuple[SecurityExposure, ...]
    observations: tuple[Observation, ...]
    execution_enabled: bool = False
    valuation_status: str = "unknown"
    positions_valuation_status: str = "unknown"
    sector_status: str = "unknown"


def _number(value: str) -> Decimal:
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise PortfolioAnalysisError("invalid portfolio amount") from exc
    if not number.is_finite():
        raise PortfolioAnalysisError("non-finite portfolio amount")
    return number


def _text(value: Decimal) -> str:
    return format(value, "f")


def _percent(value: Decimal, total: Decimal) -> str | None:
    return _text(value / total * PERCENT_SCALE) if total > 0 else None


def _rub_money(items: tuple[TBankMoney, ...]) -> tuple[Decimal, bool]:
    rub_items = [item for item in items if item.currency.upper() == "RUB"]
    values = [_number(item.value) for item in rub_items]
    return sum(values, Decimal(0)), len(values) <= 1 and all(value >= 0 for value in values)


def _value(position: TBankPortfolioPosition) -> Decimal | None:
    # Futures/options need different exposure math and are intentionally not approximated here.
    if position.instrument_type not in _SUPPORTED:
        return None
    quantity = _number(position.quantity)
    price = position.current_price
    if quantity < 0 or price is None or price.currency.upper() != "RUB":
        return None
    amount = _number(price.value)
    if amount < 0:
        return None
    if position.instrument_type == "bond":
        # T-Invest OperationsService returns current_price in settlement currency and current_nkd
        # separately. Gross bond value therefore includes accrued interest.
        nkd = position.current_nkd
        if nkd is None or nkd.currency.upper() != "RUB":
            return None
        accrued = _number(nkd.value)
        if accrued < 0:
            return None
        amount += accrued
    return amount * quantity


def _cash_state(
    portfolio: TBankPortfolio,
    positions: TBankPositions,
    nav: Decimal,
) -> tuple[Decimal, Decimal, bool]:
    cash, cash_valid = _rub_money(positions.money)
    blocked, blocked_valid = _rub_money(positions.blocked_money)
    compatible = nav >= 0 and cash_valid and blocked_valid and blocked <= cash
    compatible = compatible and all(
        _number(item.value) >= 0 for item in (*positions.money, *positions.blocked_money)
    )
    compatible = compatible and all(
        _number(position.quantity) >= 0 and _number(position.blocked_lots) >= 0
        for position in portfolio.positions
    )
    compatible = compatible and all(
        _number(item.money.value) >= 0
        for item in portfolio.asset_totals
        if item.money.currency.upper() == "RUB"
    )
    compatible = compatible and not any(
        position.instrument_type in {"futures", "future", "option", "options"}
        for position in portfolio.positions
        if _number(position.quantity) != 0
    )
    return cash, blocked, compatible


def _exposure(
    position: TBankPortfolioPosition,
    info: TBankInstrumentMetadata | None,
    nav: Decimal,
) -> SecurityExposure:
    if info is not None and info.instrument_type != position.instrument_type:
        raise PortfolioAnalysisError("portfolio metadata instrument type mismatch")
    uid = position.instrument_uid or position.figi
    value = _value(position)
    sector = info.sector if info is not None else ""
    # A fund's own category is not look-through exposure to its underlying issuers/sectors.
    if position.instrument_type == "etf":
        sector = ""
    return SecurityExposure(
        uid=uid,
        ticker=(info.ticker if info else "") or position.ticker,
        name=(info.name if info else "") or position.ticker or uid,
        instrument_type=position.instrument_type,
        sector=sector,
        country_of_risk=info.country_of_risk if info else "",
        for_qual_investor=info.for_qual_investor if info else None,
        blocked=position.blocked or _number(position.blocked_lots) > 0,
        value_rub=_text(value) if value is not None else None,
        nav_percent=_percent(value, nav) if value is not None else None,
    )


def _securities(
    portfolio: TBankPortfolio,
    metadata: tuple[TBankInstrumentMetadata, ...],
    nav: Decimal,
) -> tuple[SecurityExposure, ...]:
    by_uid = {item.uid: item for item in metadata}
    if len(by_uid) != len(metadata):
        raise PortfolioAnalysisError("duplicate metadata uid")

    securities: list[SecurityExposure] = []
    seen: set[str] = set()
    for position in portfolio.positions:
        if position.instrument_type == "currency" or _number(position.quantity) == 0:
            continue
        uid = position.instrument_uid or position.figi
        if not uid or uid in seen:
            raise PortfolioAnalysisError("missing or duplicate portfolio instrument identity")
        seen.add(uid)
        securities.append(_exposure(position, by_uid.get(position.instrument_uid), nav))

    return tuple(
        sorted(
            securities,
            key=lambda item: (
                item.value_rub is None,
                -_number(item.value_rub or "0"),
                item.uid,
            ),
        )
    )


def _sector_values(securities: tuple[SecurityExposure, ...]) -> dict[str, Decimal]:
    values: dict[str, Decimal] = {}
    for security in securities:
        if security.value_rub is None:
            continue
        values[security.sector] = values.get(security.sector, Decimal(0)) + _number(
            security.value_rub
        )
    return values


def _class_allocations(portfolio: TBankPortfolio, nav: Decimal) -> tuple[Allocation, ...]:
    return tuple(
        sorted(
            (
                Allocation(
                    item.kind,
                    _CLASS_LABELS.get(item.kind, item.kind),
                    item.money.value,
                    _percent(_number(item.money.value), nav),
                )
                for item in portfolio.asset_totals
                if item.money.currency.upper() == "RUB"
            ),
            key=lambda item: (-_number(item.value_rub), item.key),
        )
    )


def _sector_allocations(
    sector_values: dict[str, Decimal],
    nav: Decimal,
) -> tuple[Allocation, ...]:
    return tuple(
        sorted(
            (
                Allocation(
                    key or "unknown",
                    key or "Не определён / состав фонда",
                    _text(value),
                    _percent(value, nav),
                )
                for key, value in sector_values.items()
            ),
            key=lambda item: (-_number(item.value_rub), item.key),
        )
    )


def _observations(
    securities: tuple[SecurityExposure, ...],
    positions: TBankPositions,
    *,
    incomplete: bool,
    compatible: bool,
    unblocked: Decimal | None,
) -> tuple[Observation, ...]:
    observations: list[Observation] = []
    source_ids = ("portfolio", "positions")

    if not compatible:
        observations.append(
            Observation(
                "reconcile",
                0,
                "Нужна сверка счёта",
                "Обнаружены отрицательные суммы, производные инструменты или несогласованные "
                "оценки. Остаток для новых покупок не определён. Повторите сверку с брокером.",
                source_ids,
            )
        )

    if positions.limits_loading_in_progress:
        observations.append(
            Observation(
                "limits_loading",
                0,
                "Брокер ещё рассчитывает лимиты",
                "Свободные деньги не подтверждены. Дождитесь завершения расчёта лимитов.",
                ("positions",),
            )
        )

    blocked_count = sum(item.blocked for item in securities)
    if blocked_count:
        observations.append(
            Observation(
                "blocked",
                1,
                "Есть заблокированные позиции",
                f"Позиций с блокировкой: {blocked_count}. Их нельзя считать полностью свободными "
                "для продажи. Блокировка сама по себе не доказывает дефолт эмитента.",
                ("portfolio",),
            )
        )

    concentrated = [
        item
        for item in securities
        if item.nav_percent is not None and _number(item.nav_percent) > _CONCENTRATION_NOTICE
    ]
    if concentrated:
        largest = concentrated[0]
        observations.append(
            Observation(
                "concentration",
                1,
                "Проверьте концентрацию",
                f"{largest.name}: {_number(largest.nav_percent or '0'):.1f}% стоимости портфеля. "
                "25% — только порог наблюдения для проверки концентрации, а не целевая доля "
                "и не команда продавать.",
                ("portfolio",),
            )
        )

    if incomplete:
        observations.append(
            Observation(
                "coverage",
                1,
                "Часть структуры не определена",
                "Для некоторых позиций нет рублёвой оценки с НКД или проверенного сектора. "
                "Иностранные суммы не пересчитываются без подтверждённого курса; состав фондов "
                "не угадывается.",
                ("portfolio", "catalog"),
            )
        )

    observations.append(
        Observation(
            "evidence_required",
            2,
            "Проверка эмитентов ещё не завершена",
            "Полнота рейтингов, юридических эмитентов, групп, отчётности и состава фондов "
            "проверяется отдельно для каждого источника. Страна риска и сектор брокера "
            "не доказывают регистрацию эмитента и не заменяют эти проверки.",
            ("catalog",),
        )
    )

    if unblocked is not None and unblocked > 0:
        observations.append(
            Observation(
                "cash",
                2,
                "Есть незаблокированные рубли",
                f"{unblocked:,.2f} ₽ = денежный остаток минус денежные блокировки. Это "
                "предварительный остаток до резерва, налогов, комиссий, активных заявок и "
                "проверки ограничений; он не является разрешённым бюджетом покупки.",
                ("positions",),
            )
        )

    observations.append(
        Observation(
            "execution_disabled",
            2,
            "Торговое исполнение выключено",
            "Текущий этап — только доказательное наблюдение. Подбор замен, подтверждение "
            "пакета, выставление заявок и автоматическое реинвестирование не включены.",
            source_ids,
        )
    )

    observations.sort(key=lambda item: (item.priority, item.code))
    return tuple(observations)


def analyze_portfolio(
    portfolio: TBankPortfolio,
    positions: TBankPositions,
    metadata: tuple[TBankInstrumentMetadata, ...],
) -> PortfolioAnalysis:
    """Describe verified holdings while exposing uncertainty instead of guessing."""
    if portfolio.total.currency.upper() != "RUB":
        raise PortfolioAnalysisError("RUB portfolio valuation required")

    nav = _number(portfolio.total.value)
    cash, blocked, compatible = _cash_state(portfolio, positions, nav)
    securities = _securities(portfolio, metadata, nav)
    sector_values = _sector_values(securities)
    valued = sum(sector_values.values(), Decimal(0))
    classified = sum(
        (value for sector, value in sector_values.items() if sector),
        Decimal(0),
    )
    incomplete = any(item.value_rub is None or not item.sector for item in securities)

    # GetPortfolio and GetPositions are separate provider reads, not an atomic valuation.
    # A large impossible overlap is surfaced as reconciliation instead of normalized away.
    class_subtotal = sum(
        (_number(item.money.value) for item in portfolio.asset_totals
         if item.money.currency.upper() == "RUB"),
        Decimal(0),
    )
    valuation_consistent = (
        nav >= 0 and nav >= max(valued + cash, class_subtotal) - RUB_QUANTUM
    )
    if not valuation_consistent:
        compatible = False
        # Retain raw observations for reconciliation, but do not turn a
        # contradictory denominator into apparently valid allocation percentages.
        securities = tuple(replace(item, nav_percent=None) for item in securities)
    allocation_nav = nav if valuation_consistent else Decimal(0)

    unblocked = (
        cash - blocked
        if compatible and not positions.limits_loading_in_progress
        else None
    )
    status = "observed"
    if not compatible:
        status = "needs_reconciliation"
    elif incomplete or positions.limits_loading_in_progress:
        status = "partial"

    return PortfolioAnalysis(
        status=status,
        nav_rub=_text(nav),
        rub_cash_total=_text(cash),
        rub_cash_blocked=_text(blocked),
        rub_cash_unblocked=_text(unblocked) if unblocked is not None else None,
        security_count=len(securities),
        valued_security_count=sum(item.value_rub is not None for item in securities),
        sector_coverage_percent=_percent(classified, valued),
        classes=_class_allocations(portfolio, allocation_nav),
        sectors=_sector_allocations(sector_values, allocation_nav),
        securities=securities,
        observations=_observations(
            securities,
            positions,
            incomplete=incomplete,
            compatible=compatible,
            unblocked=unblocked,
        ),
        # RUB NAV is supplied by the broker independently of fund look-through
        # and spendable-cash checks. An impossible observed overlap invalidates it.
        valuation_status="complete" if valuation_consistent else "unavailable",
        positions_valuation_status=(
            "complete" if all(item.value_rub is not None for item in securities) else "partial"
        ),
        sector_status="complete" if all(item.sector for item in securities) else "partial",
    )
