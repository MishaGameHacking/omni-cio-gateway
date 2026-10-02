"""Deterministic R3 evidence normalization and explainable risk-state derivation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal

from .broker import BrokerEvidenceSnapshot, BrokerObservationBundle
from .tbank import TBankAssetFundamental, TBankInstrumentMetadata

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

FUNDAMENTAL_MAX_AGE = timedelta(days=550)
TBANK_INSTRUMENTS_SOURCE = "https://developer.tbank.ru/invest/services/instruments/methods"


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

    documents: list[EvidenceDocument] = []
    fundamentals = {item.asset_uid: item for item in evidence.fundamentals}

    for item in evidence.fundamentals:
        documents.append(_fundamental_document(item, evidence.refreshed_at))

    for item in evidence.dividends:
        payload = asdict(item)
        effective_at = item.record_date or item.payment_date
        key = "|".join(
            [
                item.instrument_uid,
                _time_key(item.record_date),
                _time_key(item.payment_date),
                item.dividend_net.currency,
                item.dividend_net.value,
            ]
        )
        documents.append(
            EvidenceDocument(
                provider="tbank",
                document_type="dividend",
                subject_uid=item.instrument_uid,
                provider_key=key,
                source_url=TBANK_INSTRUMENTS_SOURCE,
                published_at=item.created_at or item.declared_date,
                effective_at=effective_at,
                payload=payload,
                payout=PayoutEvidence(
                    instrument_uid=item.instrument_uid,
                    event_type="dividend",
                    provider_key=key,
                    announced_at=item.declared_date or item.created_at,
                    record_at=item.record_date,
                    expected_at=item.payment_date,
                    actual_at=None,
                    amount=Decimal(item.dividend_net.value),
                    currency=item.dividend_net.currency,
                    status=(
                        "cancelled"
                        if item.dividend_type.strip().lower() == "cancelled"
                        else "scheduled"
                    ),
                    payload=payload,
                ),
            )
        )

    for item in evidence.coupons:
        payload = asdict(item)
        key = f"{item.instrument_uid}|{item.coupon_number}|{_time_key(item.coupon_date)}"
        documents.append(
            EvidenceDocument(
                provider="tbank",
                document_type="bond_coupon",
                subject_uid=item.instrument_uid,
                provider_key=key,
                source_url=TBANK_INSTRUMENTS_SOURCE,
                published_at=None,
                effective_at=item.coupon_date,
                payload=payload,
                payout=PayoutEvidence(
                    instrument_uid=item.instrument_uid,
                    event_type="coupon",
                    provider_key=key,
                    announced_at=None,
                    record_at=item.fix_date,
                    expected_at=item.coupon_date,
                    actual_at=None,
                    amount=Decimal(item.pay_one_bond.value),
                    currency=item.pay_one_bond.currency,
                    status="scheduled",
                    payload=payload,
                ),
            )
        )

    for item in evidence.bond_events:
        payload = asdict(item)
        key = f"{item.instrument_uid}|{item.event_number}|{item.event_type}|{_time_key(item.event_date)}"
        status: Literal["announced", "scheduled", "cancelled", "paid", "defaulted", "observed"]
        if item.default_date is not None:
            status = "defaulted"
        elif item.real_pay_date is not None:
            status = "paid"
        else:
            status = "observed"
        documents.append(
            EvidenceDocument(
                provider="tbank",
                document_type="bond_event",
                subject_uid=item.instrument_uid,
                provider_key=key,
                source_url=TBANK_INSTRUMENTS_SOURCE,
                published_at=item.event_date,
                effective_at=item.default_date or item.real_pay_date or item.pay_date or item.event_date,
                payload=payload,
                facts=(
                    EvidenceFact(
                        subject_uid=item.instrument_uid,
                        fact_type="bond_event",
                        fact_key="default_date",
                        value_text=_time_key(item.default_date) or None,
                        effective_at=item.default_date,
                        published_at=item.event_date,
                        payload={"event_type": item.event_type, "execution": item.execution},
                    ),
                ) if item.default_date is not None else (),
                payout=PayoutEvidence(
                    instrument_uid=item.instrument_uid,
                    event_type="bond_event",
                    provider_key=key,
                    announced_at=item.event_date,
                    record_at=None,
                    expected_at=item.pay_date,
                    actual_at=item.real_pay_date,
                    amount=(
                        Decimal(item.pay_one_bond.value)
                        if item.pay_one_bond is not None
                        else None
                    ),
                    currency=item.pay_one_bond.currency if item.pay_one_bond else None,
                    status=status,
                    payload=payload,
                ),
            )
        )

    for item in evidence.reports:
        payload = asdict(item)
        key = (
            f"{item.instrument_uid}|{item.period_year}|{item.period_num}|"
            f"{item.period_type}|{_time_key(item.report_date)}"
        )
        documents.append(
            EvidenceDocument(
                provider="tbank",
                document_type="issuer_report_calendar",
                subject_uid=item.instrument_uid,
                provider_key=key,
                source_url=TBANK_INSTRUMENTS_SOURCE,
                published_at=item.created_at,
                effective_at=item.report_date,
                payload=payload,
                facts=(
                    EvidenceFact(
                        subject_uid=item.instrument_uid,
                        fact_type="issuer_report",
                        fact_key="report_date",
                        value_text=_time_key(item.report_date),
                        effective_at=item.report_date,
                        published_at=item.created_at,
                        payload={
                            "period_year": item.period_year,
                            "period_num": item.period_num,
                            "period_type": item.period_type,
                        },
                    ),
                ),
            )
        )

    source_status: EvidenceStatus = (
        "partial"
        if any(source.status != "received" for source in evidence.sources if source.id != "credit_ratings")
        else "received"
    )
    metadata = {item.uid: item for item in bundle.metadata}
    defaults = {
        item.instrument_uid: item.default_date
        for item in evidence.bond_events
        if item.default_date is not None and item.default_date <= assessed_at
    }
    assessments: list[InstrumentRiskAssessment] = []
    seen: set[str] = set()
    for position in bundle.portfolio.positions:
        if position.instrument_type == "currency" or Decimal(position.quantity) == 0:
            continue
        uid = position.instrument_uid or position.figi
        if uid in seen:
            continue
        seen.add(uid)
        info = metadata.get(position.instrument_uid)
        fundamental_status = _fundamental_status(info, fundamentals, assessed_at)
        rating_status: DataStatus = (
            "not_applicable" if position.instrument_type == "etf" else "data_missing"
        )

        reasons: list[str] = []
        state: RiskState
        if uid in defaults:
            state = "confirmed_default"
            reasons.append("tbank_bond_event_contains_default_date")
        else:
            if rating_status == "data_missing":
                reasons.append("credit_rating_feed_not_verified")
            if fundamental_status == "data_missing":
                reasons.append("fundamental_data_missing")
            elif fundamental_status == "stale":
                reasons.append("fundamental_data_stale")
            if source_status != "received":
                reasons.append("provider_evidence_partial")
            if position.instrument_type == "etf":
                reasons.append("fund_look_through_not_verified")
            state = "data_missing" if reasons else "normal"

        assessments.append(
            InstrumentRiskAssessment(
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
                        defaults[uid].isoformat() if uid in defaults else None
                    ),
                    "rating_policy": "missing_until_licensed_feed_is_verified",
                    "fundamental_max_age_days": FUNDAMENTAL_MAX_AGE.days,
                },
            )
        )

    return tuple(documents), tuple(assessments)


def _fundamental_document(
    item: TBankAssetFundamental,
    retrieved_at: datetime,
) -> EvidenceDocument:
    payload = asdict(item)
    facts: list[EvidenceFact] = []
    monetary_fields = {
        "revenue_ttm",
        "ebitda_ttm",
        "net_income_ttm",
        "free_cash_flow_ttm",
        "total_debt_mrq",
    }
    ratio_fields = {
        "total_debt_to_equity_mrq",
        "total_debt_to_ebitda_mrq",
        "net_debt_to_ebitda",
        "current_ratio_mrq",
        "fixed_charge_coverage_ratio_fy",
        "net_interest_margin_mrq",
        "roe",
        "roa",
    }
    for name in (*sorted(monetary_fields), *sorted(ratio_fields)):
        raw = getattr(item, name)
        if raw is None:
            continue
        facts.append(
            EvidenceFact(
                subject_uid=item.asset_uid,
                fact_type="fundamental",
                fact_key=name,
                value_numeric=Decimal(raw),
                currency=item.currency if name in monetary_fields else None,
                unit="ratio" if name in ratio_fields else None,
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
        source_url=TBANK_INSTRUMENTS_SOURCE,
        published_at=None,
        effective_at=item.fiscal_period_end_date,
        payload=payload,
        facts=tuple(facts),
    )


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
    if assessed_at - item.fiscal_period_end_date.astimezone(UTC) > FUNDAMENTAL_MAX_AGE:
        return "stale"
    return "received"


def _time_key(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.astimezone(UTC).isoformat()
