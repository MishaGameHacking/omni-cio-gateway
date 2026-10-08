"""Deterministic R3 evidence normalization and explainable risk-state derivation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal

from .broker import BrokerEvidenceSnapshot, BrokerObservationBundle
from .strategy_assessment import rating_notch
from .tbank import (
    TBankAssetFundamental,
    TBankAssetReport,
    TBankBondCoupon,
    TBankBondEvent,
    TBankDividend,
    TBankInstrumentMetadata,
    TBankPortfolioPosition,
    TBankRating,
)

RiskState = Literal[
    "data_missing",
    "normal",
    "watch",
    "elevated",
    "critical",
    "confirmed_default",
]
EvidenceStatus = Literal["received", "partial", "unavailable"]
DataStatus = Literal["data_missing", "received", "stale", "not_applicable"]

EVIDENCE_RETRIEVAL_MAX_AGE = timedelta(hours=36)
FUNDAMENTAL_MAX_AGE = timedelta(days=550)
RISK_RULESET_VERSION = "r3-evidence-v2"
MONETARY_FUNDAMENTAL_FIELDS = (
    "revenue_ttm",
    "ebitda_ttm",
    "net_income_ttm",
    "free_cash_flow_ttm",
    "total_debt_mrq",
)
RATIO_FUNDAMENTAL_FIELDS = (
    "total_debt_to_equity_mrq",
    "total_debt_to_ebitda_mrq",
    "net_debt_to_ebitda",
    "current_ratio_mrq",
    "fixed_charge_coverage_ratio_fy",
)
SOURCE_SCALE_FUNDAMENTAL_FIELDS = ("net_interest_margin_mrq", "roe", "roa")
FUNDAMENTAL_FIELDS = (
    MONETARY_FUNDAMENTAL_FIELDS + RATIO_FUNDAMENTAL_FIELDS + SOURCE_SCALE_FUNDAMENTAL_FIELDS
)
TBANK_DIVIDENDS_SOURCE = (
    "https://developer.tbank.ru/invest/api/instruments-service-get-dividends"
)
TBANK_BOND_COUPONS_SOURCE = (
    "https://developer.tbank.ru/invest/api/instruments-service-get-bond-coupons"
)
TBANK_BOND_EVENTS_SOURCE = (
    "https://developer.tbank.ru/invest/api/instruments-service-get-bond-events"
)
TBANK_ASSET_REPORTS_SOURCE = (
    "https://developer.tbank.ru/invest/api/instruments-service-get-asset-reports"
)
TBANK_FUNDAMENTALS_SOURCE = (
    "https://developer.tbank.ru/invest/api/instruments-service-get-asset-fundamentals"
)
TBANK_RATINGS_SOURCE = "https://developer.tbank.ru/invest/api/instruments-service-bond-by"


@dataclass(frozen=True, slots=True)
class EvidenceFact:
    subject_uid: str
    fact_type: str
    fact_key: str
    value_numeric: Decimal | None = None
    value_text: str | None = None
    currency: str | None = None
    unit: str | None = None
    effective_at: datetime | None = None
    published_at: datetime | None = None
    payload: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class PayoutEvidence:
    instrument_uid: str
    event_type: Literal["dividend", "coupon", "bond_event"]
    provider_key: str
    announced_at: datetime | None
    record_at: datetime | None
    expected_at: datetime | None
    actual_at: datetime | None
    amount: Decimal | None
    currency: str | None
    status: Literal["announced", "scheduled", "cancelled", "paid", "defaulted", "observed"]
    payload: dict[str, object]


@dataclass(frozen=True, slots=True)
class EvidenceDocument:
    provider: str
    document_type: str
    subject_uid: str
    provider_key: str
    source_url: str
    published_at: datetime | None
    effective_at: datetime | None
    payload: dict[str, object]
    facts: tuple[EvidenceFact, ...] = ()
    payout: PayoutEvidence | None = None


@dataclass(frozen=True, slots=True)
class InstrumentRiskAssessment:
    instrument_uid: str
    state: RiskState
    rating_status: DataStatus
    fundamental_status: DataStatus
    source_status: EvidenceStatus
    reasons: tuple[str, ...]
    evidence: dict[str, object]


def rating_source_references() -> tuple[dict[str, str], ...]:
    """Describe official rating sources without pretending unconfigured feeds were ingested."""
    return (
        {
            "id": "tbank_bond_ratings", "name": "T-Invest — рейтинги эмитентов облигаций",
            "url": TBANK_RATINGS_SOURCE, "access": "connected_broker",
            "ingestion": "provider_observed",
        },
        {
            "id": "cbr_rating_repository",
            "name": "Банк России — рейтинговый репозитарий",
            "url": "https://ratings.cbr.ru/",
            "access": "public_reference",
            "ingestion": "reference_only",
        },
        {
            "id": "expert_ra_rating_export",
            "name": "Эксперт РА — REST/SOAP выгрузка рейтингов",
            "url": "https://raexpert.ru/all-services/rating-export/",
            "access": "subscription",
            "ingestion": "not_configured",
        },
        {
            "id": "acra_rating_feed",
            "name": "АКРА — CSV data feed рейтингов",
            "url": "https://www.acra-ratings.ru/services/predostavlenie-dannykh/",
            "access": "subscription",
            "ingestion": "not_configured",
        },
    )


def _dividend_document(dividend: TBankDividend) -> EvidenceDocument:
    payload = asdict(dividend)
    key = "|".join(
        [
            dividend.instrument_uid,
            _time_key(dividend.record_date),
            _time_key(dividend.payment_date),
            dividend.dividend_net.currency,
            dividend.dividend_net.value,
        ]
    )
    return EvidenceDocument(
        provider="tbank",
        document_type="dividend",
        subject_uid=dividend.instrument_uid,
        provider_key=key,
        source_url=TBANK_DIVIDENDS_SOURCE,
        published_at=dividend.created_at or dividend.declared_date,
        effective_at=dividend.record_date or dividend.payment_date,
        payload=payload,
        payout=PayoutEvidence(
            instrument_uid=dividend.instrument_uid,
            event_type="dividend",
            provider_key=key,
            announced_at=dividend.declared_date or dividend.created_at,
            record_at=dividend.record_date,
            expected_at=dividend.payment_date,
            actual_at=None,
            amount=Decimal(dividend.dividend_net.value),
            currency=dividend.dividend_net.currency,
            status=(
                "cancelled"
                if dividend.dividend_type.strip().lower() == "cancelled"
                else "scheduled"
            ),
            payload=payload,
        ),
    )


def _coupon_document(coupon: TBankBondCoupon) -> EvidenceDocument:
    payload = asdict(coupon)
    key = "|".join(
        [
            coupon.instrument_uid,
            str(coupon.coupon_number),
            _time_key(coupon.coupon_date),
        ]
    )
    return EvidenceDocument(
        provider="tbank",
        document_type="bond_coupon",
        subject_uid=coupon.instrument_uid,
        provider_key=key,
        source_url=TBANK_BOND_COUPONS_SOURCE,
        published_at=None,
        effective_at=coupon.coupon_date,
        payload=payload,
        payout=PayoutEvidence(
            instrument_uid=coupon.instrument_uid,
            event_type="coupon",
            provider_key=key,
            announced_at=None,
            record_at=coupon.fix_date,
            expected_at=coupon.coupon_date,
            actual_at=None,
            amount=Decimal(coupon.pay_one_bond.value),
            currency=coupon.pay_one_bond.currency,
            status="scheduled",
            payload=payload,
        ),
    )


def _bond_event_status(
    bond_event: TBankBondEvent,
    assessed_at: datetime,
) -> tuple[
    Literal["announced", "scheduled", "cancelled", "paid", "defaulted", "observed"],
    bool,
]:
    confirmed_default = (
        bond_event.default_date is not None
        and bond_event.default_date <= assessed_at
    )
    confirmed_payment = (
        bond_event.real_pay_date is not None
        and bond_event.real_pay_date <= assessed_at
    )
    if confirmed_default:
        # T-Invest ED/ET explicitly confirm fulfillment after a default. Keep
        # the historical default fact, but do not describe a paid obligation as
        # still unpaid. A date alone or a future payment does not resolve it.
        resolved = (
            confirmed_payment
            and bond_event.execution.strip().upper() in {"ED", "ET"}
            and bond_event.real_pay_date is not None
            and bond_event.default_date is not None
            and bond_event.real_pay_date >= bond_event.default_date
            and (bond_event.event_date is None or bond_event.event_date <= assessed_at)
        )
        return ("paid", True) if resolved else ("defaulted", False)
    if confirmed_payment:
        return "paid", True
    return "observed", False


def _bond_event_document(
    bond_event: TBankBondEvent,
    assessed_at: datetime,
) -> EvidenceDocument:
    payload = asdict(bond_event)
    key = "|".join(
        [
            bond_event.instrument_uid,
            str(bond_event.event_number),
            bond_event.event_type,
            _time_key(bond_event.event_date),
        ]
    )
    status, confirmed_payment = _bond_event_status(bond_event, assessed_at)
    facts = (
        (
            EvidenceFact(
                subject_uid=bond_event.instrument_uid,
                fact_type="bond_event",
                fact_key="default_date",
                value_text=_time_key(bond_event.default_date) or None,
                effective_at=bond_event.default_date,
                published_at=bond_event.event_date,
                payload={
                    "event_type": bond_event.event_type,
                    "execution": bond_event.execution,
                },
            ),
        )
        if bond_event.default_date is not None
        else ()
    )
    return EvidenceDocument(
        provider="tbank",
        document_type="bond_event",
        subject_uid=bond_event.instrument_uid,
        provider_key=key,
        source_url=TBANK_BOND_EVENTS_SOURCE,
        published_at=bond_event.event_date,
        effective_at=(
            bond_event.default_date
            or bond_event.real_pay_date
            or bond_event.pay_date
            or bond_event.event_date
        ),
        payload=payload,
        facts=facts,
        payout=PayoutEvidence(
            instrument_uid=bond_event.instrument_uid,
            event_type="bond_event",
            provider_key=key,
            announced_at=bond_event.event_date,
            record_at=None,
            expected_at=bond_event.pay_date,
            actual_at=(
                bond_event.real_pay_date
                if confirmed_payment
                else None
            ),
            amount=(
                Decimal(bond_event.pay_one_bond.value)
                if bond_event.pay_one_bond is not None
                else None
            ),
            currency=(
                bond_event.pay_one_bond.currency
                if bond_event.pay_one_bond
                else None
            ),
            status=status,
            payload=payload,
        ),
    )


def _report_document(report: TBankAssetReport) -> EvidenceDocument:
    payload = asdict(report)
    key = (
        f"{report.instrument_uid}|{report.period_year}|{report.period_num}|"
        f"{report.period_type}|{_time_key(report.report_date)}"
    )
    return EvidenceDocument(
        provider="tbank",
        document_type="issuer_report_calendar",
        subject_uid=report.instrument_uid,
        provider_key=key,
        source_url=TBANK_ASSET_REPORTS_SOURCE,
        published_at=report.report_date,
        effective_at=report.report_date,
        payload=payload,
        facts=(
            EvidenceFact(
                subject_uid=report.instrument_uid,
                fact_type="issuer_report",
                fact_key="report_date",
                value_text=_time_key(report.report_date),
                effective_at=report.report_date,
                published_at=report.report_date,
                payload={
                    "period_year": report.period_year,
                    "period_num": report.period_num,
                    "period_type": report.period_type,
                },
            ),
        ),
    )


def _held_risk_state(
    *,
    position: TBankPortfolioPosition,
    default_date: datetime | None,
    resolved_default_date: datetime | None,
    rating_status: DataStatus,
    fundamental_status: DataStatus,
    metric_state: Literal["watch", "elevated"] | None,
    metric_reasons: tuple[str, ...],
    source_status: EvidenceStatus,
    evidence_stale: bool,
) -> tuple[RiskState, list[str]]:
    if default_date is not None:
        return "confirmed_default", ["tbank_bond_event_contains_default_date"]

    reasons = list(metric_reasons)
    if resolved_default_date is not None:
        reasons.append("tbank_default_obligation_fulfilled")
    if rating_status == "data_missing":
        reasons.append("credit_rating_feed_not_verified")
    if fundamental_status == "data_missing":
        reasons.append("fundamental_data_missing")
    elif fundamental_status == "stale":
        reasons.append("fundamental_data_stale")
    if evidence_stale:
        reasons.append("provider_evidence_stale")
    elif source_status != "received":
        reasons.append("provider_evidence_partial")
    if position.instrument_type == "etf":
        reasons.append("fund_look_through_not_verified")

    if evidence_stale:
        return "data_missing", reasons
    if metric_state is not None:
        return metric_state, reasons
    if resolved_default_date is not None:
        return "watch", reasons
    return ("data_missing" if reasons else "normal"), reasons


def _issuer_rating_risk(
    state: RiskState, reasons: list[str], ratings: tuple[TBankRating, ...],
    assessed_at: datetime, *, evidence_stale: bool,
) -> tuple[RiskState, list[str]]:
    if state == "confirmed_default" or not ratings or evidence_stale:
        return state, reasons
    notches = {rating_notch(rating, assessed_at) for rating in ratings}
    if "D" in notches:
        return "critical", [*reasons, "issuer_default_rating_requires_issue_verification"]
    if notches & {"CCC+", "CCC", "CCC-", "CC", "C"}:
        return "elevated", [*reasons, "issuer_very_low_credit_rating"]
    if any(rating.is_under_watch for rating in ratings):
        if state in {"normal", "data_missing"}:
            state = "watch"
        reasons.append("issuer_rating_under_watch")
    return state, reasons


def _held_position_assessment(
    position: TBankPortfolioPosition,
    *,
    metadata_by_uid: dict[str, TBankInstrumentMetadata],
    metadata_by_figi: dict[str, TBankInstrumentMetadata],
    fundamentals: dict[str, TBankAssetFundamental],
    defaults: dict[str, datetime],
    resolved_defaults: dict[str, datetime],
    source_status: EvidenceStatus,
    evidence_stale: bool,
    assessed_at: datetime,
    evidence_refreshed_at: datetime,
    ratings: tuple[TBankRating, ...] = (),
) -> InstrumentRiskAssessment:
    uid = position.instrument_uid or position.figi
    info = metadata_by_uid.get(position.instrument_uid)
    if info is None and position.figi:
        info = metadata_by_figi.get(position.figi)

    provider_uid = info.uid if info is not None else uid
    default_date = defaults.get(provider_uid)
    resolved_default_date = resolved_defaults.get(provider_uid)
    fundamental_status = _fundamental_status(info, fundamentals, assessed_at)
    current_fundamental = (
        fundamentals.get(info.asset_uid)
        if info is not None and info.asset_uid
        else None
    )
    metric_state, metric_reasons, metric_profile, metric_signals = (
        _fundamental_watch_signals(
            current_fundamental,
            status=fundamental_status,
        )
    )
    current_ratings = tuple(rating for rating in ratings if rating_notch(rating, assessed_at))
    rating_status: DataStatus = "data_missing"
    if position.instrument_type == "etf":
        rating_status = "not_applicable"
    elif current_ratings and not evidence_stale:
        rating_status = "received"
    state, reasons = _held_risk_state(
        position=position,
        default_date=default_date,
        resolved_default_date=resolved_default_date,
        rating_status=rating_status,
        fundamental_status=fundamental_status,
        metric_state=metric_state,
        metric_reasons=metric_reasons,
        source_status=source_status,
        evidence_stale=evidence_stale,
    )
    state, reasons = _issuer_rating_risk(
        state, reasons, current_ratings, assessed_at, evidence_stale=evidence_stale,
    )
    return InstrumentRiskAssessment(
        instrument_uid=uid,
        state=state,
        rating_status=rating_status,
        fundamental_status=fundamental_status,
        source_status=source_status,
        reasons=tuple(reasons),
        evidence={
            "assessed_at": assessed_at.isoformat(),
            "sector": info.sector if info else "",
            "asset_uid": info.asset_uid if info else "",
            "default_date": (
                default_date.isoformat() if default_date is not None else None
            ),
            "resolved_default_date": (
                resolved_default_date.isoformat() if resolved_default_date is not None else None
            ),
            "rating_policy": "observed_tbank_issuer_rating_not_issue_rating",
            "rating_source_url": TBANK_RATINGS_SOURCE,
            "ratings": [asdict(rating) for rating in ratings],
            "fundamental_max_age_days": FUNDAMENTAL_MAX_AGE.days,
            "evidence_retrieval_max_age_hours": int(
                EVIDENCE_RETRIEVAL_MAX_AGE.total_seconds() // 3600
            ),
            "evidence_refreshed_at": evidence_refreshed_at.isoformat(),
            "ruleset_version": RISK_RULESET_VERSION,
            "metric_profile": metric_profile,
            "metric_signals": metric_signals,
        },
    )


def build_tbank_evidence(
    bundle: BrokerObservationBundle,
    evidence: BrokerEvidenceSnapshot,
    *,
    assessed_at: datetime,
) -> tuple[tuple[EvidenceDocument, ...], tuple[InstrumentRiskAssessment, ...]]:
    """Normalize provider facts without turning missing data into a positive assertion."""
    if assessed_at.tzinfo is None:
        raise ValueError("assessment time must be timezone-aware")
    assessed_at = assessed_at.astimezone(UTC)

    fundamentals = {item.asset_uid: item for item in evidence.fundamentals}
    documents = [
        *(_rating_document(uid, rating) for uid, values in evidence.ratings.items()
          for rating in values),
        *(_fundamental_document(item) for item in evidence.fundamentals),
        *(_dividend_document(item) for item in evidence.dividends),
        *(_coupon_document(item) for item in evidence.coupons),
        *(_bond_event_document(item, assessed_at) for item in evidence.bond_events),
        *(_report_document(item) for item in evidence.reports),
    ]

    source_status, evidence_stale = _source_status(
        evidence,
        assessed_at=assessed_at,
    )
    metadata_by_uid = {item.uid: item for item in bundle.metadata}
    metadata_by_figi = {item.figi: item for item in bundle.metadata if item.figi}
    defaults: dict[str, datetime] = {}
    resolved_defaults: dict[str, datetime] = {}
    for item in evidence.bond_events:
        if item.default_date is None or item.default_date > assessed_at:
            continue
        status, _ = _bond_event_status(item, assessed_at)
        dates = resolved_defaults if status == "paid" else defaults
        dates[item.instrument_uid] = max(
            dates.get(item.instrument_uid, item.default_date), item.default_date,
        )
    assessments: list[InstrumentRiskAssessment] = []
    seen: set[str] = set()
    for position in bundle.portfolio.positions:
        if position.instrument_type == "currency" or Decimal(position.quantity) == 0:
            continue
        uid = position.instrument_uid or position.figi
        if uid in seen:
            continue
        seen.add(uid)
        info = metadata_by_uid.get(position.instrument_uid) or metadata_by_figi.get(position.figi)
        assessments.append(
            _held_position_assessment(
                position,
                metadata_by_uid=metadata_by_uid,
                metadata_by_figi=metadata_by_figi,
                fundamentals=fundamentals,
                defaults=defaults,
                resolved_defaults=resolved_defaults,
                source_status=source_status,
                evidence_stale=evidence_stale,
                assessed_at=assessed_at,
                evidence_refreshed_at=evidence.refreshed_at,
                ratings=evidence.ratings.get(info.uid if info is not None else uid, ()),
            )
        )
    return tuple(documents), tuple(assessments)


def _rating_document(instrument_uid: str, rating: TBankRating) -> EvidenceDocument:
    payload = {**asdict(rating), "rating_object": "issuer", "instrument_uid": instrument_uid}
    key = f"{rating.agency_name}:{rating.rating_date.isoformat()}"
    return EvidenceDocument(
        provider="tbank", document_type="issuer_rating", subject_uid=instrument_uid,
        provider_key=key, source_url=TBANK_RATINGS_SOURCE,
        published_at=rating.rating_date, effective_at=rating.rating_date, payload=payload,
        facts=(EvidenceFact(
            subject_uid=instrument_uid, fact_type="issuer_rating", fact_key=key,
            value_text=rating.rating_level, unit="agency_national_scale",
            effective_at=rating.rating_date, published_at=rating.rating_date, payload=payload,
        ),),
    )

def assess_candidate_fundamental_risk(
    info: TBankInstrumentMetadata,
    fundamental: TBankAssetFundamental | None,
    *,
    assessed_at: datetime,
) -> InstrumentRiskAssessment:
    """Assess a non-held candidate without inventing a credit rating."""
    if assessed_at.tzinfo is None:
        raise ValueError("assessment time must be timezone-aware")
    assessed_at = assessed_at.astimezone(UTC)
    fundamentals = (
        {fundamental.asset_uid: fundamental}
        if fundamental is not None
        else {}
    )
    fundamental_status = _fundamental_status(
        info,
        fundamentals,
        assessed_at,
    )
    metric_state, metric_reasons, metric_profile, metric_signals = (
        _fundamental_watch_signals(
            fundamental,
            status=fundamental_status,
        )
    )
    rating_status: DataStatus = (
        "data_missing" if info.instrument_type == "bond" else "not_applicable"
    )
    reasons = list(metric_reasons)
    if fundamental_status == "data_missing":
        reasons.append("fundamental_data_missing")
    elif fundamental_status == "stale":
        reasons.append("fundamental_data_stale")
    if rating_status == "data_missing":
        reasons.append("credit_rating_feed_not_verified")
    if info.instrument_type == "etf":
        reasons.append("fund_look_through_not_verified")

    if fundamental_status != "received" or metric_profile == "unknown":
        state: RiskState = "data_missing"
    elif info.instrument_type == "etf":
        state = "data_missing"
    elif metric_state is not None:
        state = metric_state
    else:
        state = "normal"

    return InstrumentRiskAssessment(
        instrument_uid=info.uid,
        state=state,
        rating_status=rating_status,
        fundamental_status=fundamental_status,
        source_status="received",
        reasons=tuple(reasons),
        evidence={
            "assessed_at": assessed_at.isoformat(),
            "sector": info.sector,
            "asset_uid": info.asset_uid,
            "rating_policy": "unknown_bucket_until_verified_feed",
            "ruleset_version": RISK_RULESET_VERSION,
            "metric_profile": metric_profile,
            "metric_signals": metric_signals,
        },
    )


def _metric_signal(
    code: str,
    metric: str,
    value: Decimal,
) -> dict[str, object]:
    return {
        "code": code,
        "metric": metric,
        "value": str(value),
    }


def _bank_watch_signals(
    item: TBankAssetFundamental,
) -> tuple[tuple[str, ...], tuple[dict[str, object], ...]]:
    reasons: list[str] = []
    signals: list[dict[str, object]] = []
    for metric in ("net_interest_margin_mrq", "roe", "roa"):
        raw = getattr(item, metric)
        if raw is None:
            continue
        value = Decimal(raw)
        if value < 0:
            code = f"{metric}_negative"
            reasons.append(code)
            signals.append(_metric_signal(code, metric, value))
    return tuple(reasons), tuple(signals)


def _corporate_watch_signals(
    item: TBankAssetFundamental,
) -> tuple[tuple[str, ...], tuple[dict[str, object], ...], bool]:
    reasons: list[str] = []
    signals: list[dict[str, object]] = []
    elevated = False

    if item.fixed_charge_coverage_ratio_fy is not None:
        value = Decimal(item.fixed_charge_coverage_ratio_fy)
        if value < 1:
            code = "fixed_charge_coverage_ratio_below_one"
            reasons.append(code)
            signals.append(
                _metric_signal(code, "fixed_charge_coverage_ratio_fy", value)
            )
            elevated = True

    if item.ebitda_ttm is not None:
        value = Decimal(item.ebitda_ttm)
        if value < 0:
            code = "ebitda_negative"
            reasons.append(code)
            signals.append(_metric_signal(code, "ebitda_ttm", value))

    if item.free_cash_flow_ttm is not None and item.total_debt_mrq is not None:
        free_cash_flow = Decimal(item.free_cash_flow_ttm)
        debt = Decimal(item.total_debt_mrq)
        if free_cash_flow < 0 and debt > 0:
            code = "free_cash_flow_negative_with_debt"
            reasons.append(code)
            signals.append(
                _metric_signal(code, "free_cash_flow_ttm", free_cash_flow)
            )

    if item.current_ratio_mrq is not None:
        value = Decimal(item.current_ratio_mrq)
        if value < 1:
            code = "current_ratio_below_one"
            reasons.append(code)
            signals.append(_metric_signal(code, "current_ratio_mrq", value))

    return tuple(reasons), tuple(signals), elevated


def _fundamental_profile(item: TBankAssetFundamental) -> str:
    if item.net_interest_margin_mrq is not None:
        return "bank_like"
    if any(
        value is not None
        for value in (
            item.ebitda_ttm,
            item.fixed_charge_coverage_ratio_fy,
            item.net_debt_to_ebitda,
            item.current_ratio_mrq,
        )
    ):
        return "corporate"
    return "unknown"


def _fundamental_watch_signals(
    item: TBankAssetFundamental | None,
    *,
    status: DataStatus,
) -> tuple[
    Literal["watch", "elevated"] | None,
    tuple[str, ...],
    str,
    tuple[dict[str, object], ...],
]:
    if item is None or status != "received":
        return None, (), "unknown", ()

    profile = _fundamental_profile(item)
    if profile == "unknown":
        return None, (), profile, ()

    if profile == "bank_like":
        reasons, signals = _bank_watch_signals(item)
        elevated = False
    else:
        reasons, signals, elevated = _corporate_watch_signals(item)

    if not reasons:
        return None, (), profile, ()
    return (
        "elevated" if elevated else "watch",
        reasons,
        profile,
        signals,
    )

def _fundamental_document(item: TBankAssetFundamental) -> EvidenceDocument:
    payload = asdict(item)
    facts: list[EvidenceFact] = []
    monetary_fields = set(MONETARY_FUNDAMENTAL_FIELDS)
    ratio_fields = set(RATIO_FUNDAMENTAL_FIELDS)
    source_scale_fields = set(SOURCE_SCALE_FUNDAMENTAL_FIELDS)
    for name in FUNDAMENTAL_FIELDS:
        raw = getattr(item, name)
        if raw is None:
            continue
        unit: str | None = None
        if name in ratio_fields:
            unit = "ratio"
        elif name in source_scale_fields:
            unit = "source_unit"
        facts.append(
            EvidenceFact(
                subject_uid=item.asset_uid,
                fact_type="fundamental",
                fact_key=name,
                value_numeric=Decimal(raw),
                currency=item.currency if name in monetary_fields else None,
                unit=unit,
                effective_at=item.fiscal_period_end_date,
                published_at=None,
                payload={"source_field": name},
            )
        )
    provider_key = "|".join(
        [
            item.asset_uid,
            _time_key(item.fiscal_period_start_date),
            _time_key(item.fiscal_period_end_date),
        ]
    )
    return EvidenceDocument(
        provider="tbank",
        document_type="asset_fundamentals",
        subject_uid=item.asset_uid,
        provider_key=provider_key,
        source_url=TBANK_FUNDAMENTALS_SOURCE,
        published_at=None,
        effective_at=item.fiscal_period_end_date,
        payload=payload,
        facts=tuple(facts),
    )


def _source_status(
    evidence: BrokerEvidenceSnapshot,
    *,
    assessed_at: datetime,
) -> tuple[EvidenceStatus, bool]:
    relevant = tuple(
        source for source in evidence.sources if source.id != "credit_ratings"
    )
    if not relevant:
        return "unavailable", True

    timestamps = (evidence.refreshed_at, *(source.retrieved_at for source in relevant))
    stale = any(
        timestamp.tzinfo is None
        or timestamp.astimezone(UTC) > assessed_at
        or assessed_at - timestamp.astimezone(UTC) > EVIDENCE_RETRIEVAL_MAX_AGE
        for timestamp in timestamps
    )
    if stale:
        return "partial", True
    if all(source.status == "received" for source in relevant):
        return "received", False
    if all(source.status == "unavailable" for source in relevant):
        return "unavailable", False
    return "partial", False


def _fundamental_status(
    info: TBankInstrumentMetadata | None,
    fundamentals: dict[str, TBankAssetFundamental],
    assessed_at: datetime,
) -> DataStatus:
    if info is None or not info.asset_uid:
        return "data_missing"
    item = fundamentals.get(info.asset_uid)
    if item is None:
        return "data_missing"
    if item.fiscal_period_end_date is None:
        return "data_missing"
    if not any(getattr(item, field) is not None for field in FUNDAMENTAL_FIELDS):
        return "data_missing"
    period_end = item.fiscal_period_end_date.astimezone(UTC)
    if period_end > assessed_at:
        return "data_missing"
    if assessed_at - period_end > FUNDAMENTAL_MAX_AGE:
        return "stale"
    return "received"


def _time_key(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.astimezone(UTC).isoformat()
