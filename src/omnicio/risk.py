"""Deterministic evidence model for portfolio watch risk and payout observations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Literal
from uuid import UUID

RiskState = Literal[
    "data_missing",
    "normal",
    "watch",
    "elevated",
    "critical",
    "confirmed_default",
]
SourceStatus = Literal["received", "partial", "unavailable", "not_configured"]

FUNDAMENTALS_MAX_AGE = timedelta(days=550)
REPORT_MAX_AGE = timedelta(days=550)


@dataclass(frozen=True, slots=True)
class FundamentalEvidence:
    instrument_uid: str
    asset_uid: str
    currency: str
    retrieved_at: datetime
    fiscal_period_start: datetime | None
    fiscal_period_end: datetime | None
    metrics: dict[str, str | None]


@dataclass(frozen=True, slots=True)
class ReportEvidence:
    instrument_uid: str
    report_date: datetime
    period_year: int
    period_num: int
    period_type: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class PayoutEvidence:
    instrument_uid: str
    kind: Literal["dividend", "coupon", "bond_event"]
    event_key: str
    event_date: datetime
    record_date: datetime | None
    declared_at: datetime | None
    provider_payment_at: datetime | None
    amount_value: str | None
    amount_currency: str | None
    status: str
    source_id: str
    source_url: str
    details: dict[str, object]


@dataclass(frozen=True, slots=True)
class SourceEvidenceStatus:
    source_id: str
    scope_key: str
    status: SourceStatus
    retrieved_at: datetime
    source_url: str


@dataclass(frozen=True, slots=True)
class InstrumentRiskEvidence:
    instrument_uid: str
    ticker: str
    instrument_type: str
    sector: str
    fundamental: FundamentalEvidence | None
    reports: tuple[ReportEvidence, ...]
    payouts: tuple[PayoutEvidence, ...]
    confirmed_default_at: datetime | None
    sources: tuple[SourceEvidenceStatus, ...]


@dataclass(frozen=True, slots=True)
class RiskReason:
    code: str
    severity: Literal["info", "watch", "elevated", "critical"]
    title: str
    detail: str
    source_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    instrument_uid: str
    ticker: str
    state: RiskState
    sector_model: str
    coverage: Literal["complete", "partial", "missing"]
    reasons: tuple[RiskReason, ...]
    evaluated_at: datetime
    latest_fundamental_period_end: datetime | None
    latest_report_date: datetime | None


@dataclass(frozen=True, slots=True)
class RiskSnapshotSummary:
    snapshot_id: UUID
    captured_at: datetime
    assessments: tuple[RiskAssessment, ...]
    payouts: tuple[PayoutEvidence, ...]
    sources: tuple[SourceEvidenceStatus, ...]


def _number(metrics: dict[str, str | None], key: str) -> Decimal | None:
    value = metrics.get(key)
    if value is None or value == "":
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() else None


def _sector_model(sector: str) -> str:
    normalized = sector.strip().lower()
    if any(
        token in normalized
        for token in (
            "bank",
            "банк",
            "credit institution",
            "кредитн",
        )
    ):
        return "bank"
    if any(token in normalized for token in ("insurance", "insurer", "страх")):
        return "insurer"
    if any(
        token in normalized
        for token in (
            "developer",
            "real estate",
            "construction",
            "девел",
            "недвиж",
            "строит",
        )
    ):
        return "developer"
    return "ordinary_company"


def _latest_report(reports: tuple[ReportEvidence, ...]) -> datetime | None:
    if not reports:
        return None
    return max(item.report_date for item in reports)


def _source_coverage(
    evidence: InstrumentRiskEvidence,
    *,
    now: datetime,
) -> tuple[Literal["complete", "partial", "missing"], list[RiskReason]]:
    reasons: list[RiskReason] = []
    unavailable = {
        item.source_id
        for item in evidence.sources
        if item.status in {"unavailable", "not_configured"}
    }
    if unavailable:
        reasons.append(
            RiskReason(
                code="source_unavailable",
                severity="info",
                title="Часть источников недоступна",
                detail=(
                    "Недоступные или не подключённые источники: "
                    + ", ".join(sorted(unavailable))
                    + ". Отсутствие данных не трактуется как отсутствие риска."
                ),
                source_ids=tuple(sorted(unavailable)),
            )
        )

    fundamental = evidence.fundamental
    latest_report = _latest_report(evidence.reports)
    if fundamental is None:
        reasons.append(
            RiskReason(
                code="fundamentals_missing",
                severity="info",
                title="Нет проверенных фундаментальных показателей",
                detail="Для инструмента не получен набор фундаментальных показателей T-Invest.",
                source_ids=("tbank_fundamentals",),
            )
        )
    elif (
        fundamental.fiscal_period_end is None
        or now - fundamental.fiscal_period_end > FUNDAMENTALS_MAX_AGE
    ):
        reasons.append(
            RiskReason(
                code="fundamentals_stale",
                severity="info",
                title="Фундаментальные данные устарели",
                detail=(
                    "Период фундаментальных данных слишком старый для статуса normal; "
                    "система сохраняет неопределённость."
                ),
                source_ids=("tbank_fundamentals",),
            )
        )

    if latest_report is None:
        reasons.append(
            RiskReason(
                code="report_schedule_missing",
                severity="info",
                title="Нет подтверждённой даты отчётности",
                detail="T-Invest не вернул событие публикации отчётности для проверяемого окна.",
                source_ids=("tbank_reports",),
            )
        )
    elif now - latest_report > REPORT_MAX_AGE:
        reasons.append(
            RiskReason(
                code="report_stale",
                severity="info",
                title="Последняя подтверждённая отчётность устарела",
                detail="Дата последнего события отчётности старше допустимого окна свежести.",
                source_ids=("tbank_reports",),
            )
        )

    # Credit-rating facts are intentionally not fabricated. Automated agency
    # ingestion remains disabled until a permitted/licensed feed is configured.
    reasons.append(
        RiskReason(
            code="rating_feed_missing",
            severity="info",
            title="Кредитный рейтинг не подтверждён",
            detail=(
                "Автоматический лицензированный feed кредитных рейтингов не подключён. "
                "OmniCIO не присваивает и не переносит рейтинг по умолчанию."
            ),
            source_ids=("cbr_cra_registry",),
        )
    )

    if fundamental is None:
        return "missing", reasons
    if unavailable or any(
        item.code in {"fundamentals_stale", "report_schedule_missing", "report_stale"}
        for item in reasons
    ):
        return "partial", reasons
    # Rating coverage is still intentionally incomplete until the feed gate is resolved.
    return "partial", reasons


def _ordinary_company_reasons(
    fundamental: FundamentalEvidence,
) -> list[RiskReason]:
    reasons: list[RiskReason] = []
    leverage = _number(fundamental.metrics, "net_debt_to_ebitda")
    total_leverage = _number(fundamental.metrics, "total_debt_to_ebitda_mrq")
    coverage = _number(fundamental.metrics, "fixed_charge_coverage_ratio_fy")
    current_ratio = _number(fundamental.metrics, "current_ratio_mrq")
    fcf = _number(fundamental.metrics, "free_cash_flow_ttm")
    debt_change = _number(fundamental.metrics, "total_debt_change_five_years")

    effective_leverage = leverage if leverage is not None else total_leverage
    if effective_leverage is not None:
        if effective_leverage >= Decimal("6"):
            reasons.append(
                RiskReason(
                    code="high_leverage",
                    severity="elevated",
                    title="Высокая долговая нагрузка",
                    detail=(
                        f"Наблюдаемый Net debt/EBITDA или Debt/EBITDA: "
                        f"{effective_leverage}. Это watch-индикатор, а не вероятность дефолта."
                    ),
                    source_ids=("tbank_fundamentals",),
                )
            )
        elif effective_leverage >= Decimal("4"):
            reasons.append(
                RiskReason(
                    code="leverage_watch",
                    severity="watch",
                    title="Долговая нагрузка требует наблюдения",
                    detail=f"Наблюдаемый показатель долговой нагрузки: {effective_leverage}.",
                    source_ids=("tbank_fundamentals",),
                )
            )

    if coverage is not None:
        if coverage < Decimal("1"):
            reasons.append(
                RiskReason(
                    code="coverage_below_one",
                    severity="elevated",
                    title="Покрытие фиксированных платежей ниже единицы",
                    detail=f"FCCR: {coverage}. Требуется проверка отчётности и структуры долга.",
                    source_ids=("tbank_fundamentals",),
                )
            )
        elif coverage < Decimal("2"):
            reasons.append(
                RiskReason(
                    code="coverage_watch",
                    severity="watch",
                    title="Покрытие фиксированных платежей снижено",
                    detail=f"FCCR: {coverage}.",
                    source_ids=("tbank_fundamentals",),
                )
            )

    if current_ratio is not None and current_ratio < Decimal("1"):
        reasons.append(
            RiskReason(
                code="current_ratio_watch",
                severity="watch",
                title="Текущая ликвидность ниже единицы",
                detail=f"Current ratio: {current_ratio}.",
                source_ids=("tbank_fundamentals",),
            )
        )

    if fcf is not None and fcf < 0 and debt_change is not None and debt_change > 0:
        reasons.append(
            RiskReason(
                code="fcf_debt_watch",
                severity="watch",
                title="Отрицательный FCF при росте долга",
                detail=(
                    "Свободный денежный поток отрицательный, а пятилетнее изменение долга "
                    "положительное. Это требует проверки первичной отчётности."
                ),
                source_ids=("tbank_fundamentals",),
            )
        )
    return reasons


def _bank_reasons(fundamental: FundamentalEvidence) -> list[RiskReason]:
    reasons: list[RiskReason] = [
        RiskReason(
            code="bank_model_limited",
            severity="info",
            title="Для банка нужна отдельная модель",
            detail=(
                "Debt/EBITDA для банков не используется. Без данных о капитале, качестве "
                "кредитов и ликвидности банк не получает статус normal."
            ),
            source_ids=("tbank_fundamentals",),
        )
    ]
    roa = _number(fundamental.metrics, "roa")
    net_margin = _number(fundamental.metrics, "net_interest_margin_mrq")
    if roa is not None and roa < 0:
        reasons.append(
            RiskReason(
                code="bank_negative_roa",
                severity="watch",
                title="Отрицательная рентабельность активов",
                detail=f"ROA: {roa}. Нужна проверка банковской отчётности и качества активов.",
                source_ids=("tbank_fundamentals",),
            )
        )
    if net_margin is not None and net_margin < 0:
        reasons.append(
            RiskReason(
                code="bank_negative_nim",
                severity="watch",
                title="Отрицательная процентная маржа",
                detail=f"Net interest margin: {net_margin}.",
                source_ids=("tbank_fundamentals",),
            )
        )
    return reasons


def assess_instrument(
    evidence: InstrumentRiskEvidence,
    *,
    now: datetime,
) -> RiskAssessment:
    """Create an explainable watch state without estimating a default probability."""
    if now.tzinfo is None:
        raise ValueError("risk assessment time must be timezone-aware")
    now = now.astimezone(UTC)

    coverage, reasons = _source_coverage(evidence, now=now)
    sector_model = _sector_model(evidence.sector)

    if evidence.confirmed_default_at is not None:
        reasons.insert(
            0,
            RiskReason(
                code="confirmed_default",
                severity="critical",
                title="Источник сообщает дату дефолта",
                detail=(
                    "T-Invest bond event содержит explicit default_date "
                    f"{evidence.confirmed_default_at.date().isoformat()}."
                ),
                source_ids=("tbank_bond_events",),
            ),
        )
        state: RiskState = "confirmed_default"
    else:
        if evidence.fundamental is not None:
            if sector_model == "bank":
                reasons.extend(_bank_reasons(evidence.fundamental))
                coverage = "partial"
            elif sector_model in {"insurer", "developer"}:
                reasons.append(
                    RiskReason(
                        code=f"{sector_model}_model_limited",
                        severity="info",
                        title="Нужна специализированная секторная модель",
                        detail=(
                            "OmniCIO не применяет корпоративные Debt/EBITDA-пороги к этому "
                            "сектору без подтверждённых профильных метрик. Риск остаётся "
                            "неполностью покрытым."
                        ),
                        source_ids=("tbank_fundamentals",),
                    )
                )
                coverage = "partial"
            else:
                reasons.extend(_ordinary_company_reasons(evidence.fundamental))

        severities = {reason.severity for reason in reasons}
        if "critical" in severities:
            state = "critical"
        elif "elevated" in severities:
            state = "elevated"
        elif "watch" in severities:
            state = "watch"
        elif coverage != "complete":
            state = "data_missing"
        else:
            state = "normal"

    severity_order = {"critical": 0, "elevated": 1, "watch": 2, "info": 3}
    reasons.sort(key=lambda reason: (severity_order[reason.severity], reason.code))
    return RiskAssessment(
        instrument_uid=evidence.instrument_uid,
        ticker=evidence.ticker,
        state=state,
        sector_model=sector_model,
        coverage=coverage,
        reasons=tuple(reasons),
        evaluated_at=now,
        latest_fundamental_period_end=(
            evidence.fundamental.fiscal_period_end
            if evidence.fundamental is not None
            else None
        ),
        latest_report_date=_latest_report(evidence.reports),
    )
