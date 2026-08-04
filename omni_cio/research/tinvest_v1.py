from __future__ import annotations

from collections.abc import Callable, Iterable
from contextlib import AbstractContextManager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Protocol

from t_tech.invest import Client

from omni_cio.contracts.v1.market import SourceAuthority
from omni_cio.contracts.v1.portfolio import InstrumentType
from omni_cio.contracts.v1.research_evidence import (
    EvidenceCoverageProbeV1,
    EvidenceFactType,
    EvidenceRecordV1,
    EvidenceSourceClass,
    EvidenceUse,
    EvidenceValueType,
    EvidenceValueV1,
    ResearchSourceV1,
    ResearchTargetV1,
    make_evidence_record,
)


class _ClientProtocol(Protocol):
    instruments: Any


ClientFactory = Callable[[str], AbstractContextManager[_ClientProtocol]]


_MONEY_FUNDAMENTALS = {
    "market_capitalization",
    "revenue_ttm",
    "ebitda_ttm",
    "net_income_ttm",
    "free_cash_flow_ttm",
    "total_debt_mrq",
}
_FUNDAMENTAL_FIELDS = (
    "market_capitalization",
    "revenue_ttm",
    "ebitda_ttm",
    "net_income_ttm",
    "free_cash_flow_ttm",
    "total_debt_mrq",
    "net_debt_to_ebitda",
    "total_debt_to_ebitda_mrq",
    "pe_ratio_ttm",
    "price_to_book_ttm",
    "roe",
    "roa",
    "roic",
    "dividend_yield_daily_ttm",
)
_TINVEST_PROVIDER_NAMES = {"t-invest", "t-bank", "tbank"}


class TInvestResearchAdapterError(RuntimeError):
    """Read-only broker research source could not be normalized safely."""


def _utc(value: datetime | None = None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise TInvestResearchAdapterError("TIN_RESEARCH_TIMESTAMP_MUST_BE_AWARE")
    return result.astimezone(timezone.utc)


def _timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _utc(value)
    to_datetime = getattr(value, "ToDatetime", None)
    if callable(to_datetime):
        result = to_datetime()
        if isinstance(result, datetime):
            if result.tzinfo is None:
                result = result.replace(tzinfo=timezone.utc)
            return result.astimezone(timezone.utc)
    return None


def _decimal_text(value: object) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        decimal_value = value
    elif isinstance(value, (int, float)):
        decimal_value = Decimal(str(value))
    else:
        units = getattr(value, "units", None)
        nano = getattr(value, "nano", None)
        if isinstance(units, int) and isinstance(nano, int):
            decimal_value = Decimal(units) + Decimal(nano) / Decimal("1000000000")
        else:
            return None
    if not decimal_value.is_finite() or decimal_value == 0:
        return None
    return format(decimal_value.normalize(), "f")


def _enum_text(value: object) -> str:
    if value is None:
        return "unspecified"
    name = getattr(value, "name", None)
    if isinstance(name, str) and name:
        return name.lower()
    return str(value).strip().lower() or "unspecified"


def _source(method: str, retrieved_at: datetime) -> ResearchSourceV1:
    return ResearchSourceV1(
        provider="T-Invest",
        source_class=EvidenceSourceClass.BROKER,
        authority=SourceAuthority.PRIMARY,
        source_id=method,
        retrieved_at=retrieved_at,
    )


def _fundamental_records(
    *,
    target: ResearchTargetV1,
    rows: Iterable[object],
    retrieved_at: datetime,
) -> tuple[EvidenceRecordV1, ...]:
    source = _source("GetAssetFundamentals", retrieved_at)
    records: list[EvidenceRecordV1] = []
    for row in rows:
        row_asset_uid = str(getattr(row, "asset_uid", "") or "")
        if target.asset_uid is None or row_asset_uid != target.asset_uid:
            continue
        currency = str(getattr(row, "currency", "") or "").upper()
        for field in _FUNDAMENTAL_FIELDS:
            canonical = _decimal_text(getattr(row, field, None))
            # T-Invest documents zero as an unavailable fundamental value. It is
            # deliberately omitted rather than converted into an economic zero.
            if canonical is None:
                continue
            money = field in _MONEY_FUNDAMENTALS
            if money and len(currency) != 3:
                continue
            records.append(
                make_evidence_record(
                    instrument_uid=target.instrument_uid,
                    fact_type=EvidenceFactType.FUNDAMENTAL,
                    fact_key=f"fundamental.{field}",
                    value=EvidenceValueV1(
                        value_type=(
                            EvidenceValueType.MONEY
                            if money
                            else EvidenceValueType.DECIMAL
                        ),
                        canonical_value=canonical,
                        currency=currency if money else None,
                    ),
                    source=source,
                    use=EvidenceUse.DECISION_GRADE,
                    source_record_id=f"{target.asset_uid}:{field}",
                    material=True,
                )
            )
    return tuple(records)


def _report_records(
    *,
    target: ResearchTargetV1,
    rows: Iterable[object],
    retrieved_at: datetime,
) -> tuple[EvidenceRecordV1, ...]:
    source = _source("GetAssetReports", retrieved_at)
    records: list[EvidenceRecordV1] = []
    for row in rows:
        report_date = _timestamp(getattr(row, "report_date", None))
        if report_date is None:
            continue
        created_at = _timestamp(getattr(row, "created_at", None))
        year = int(getattr(row, "period_year", 0) or 0)
        number = int(getattr(row, "period_num", 0) or 0)
        period_type = _enum_text(getattr(row, "period_type", None))
        source_record_id = f"{period_type}:{year}:{number}:{report_date.isoformat()}"
        records.append(
            make_evidence_record(
                instrument_uid=target.instrument_uid,
                fact_type=EvidenceFactType.REPORT,
                fact_key=f"report.{period_type}.{year}.{number}",
                value=EvidenceValueV1(
                    value_type=EvidenceValueType.DATETIME,
                    canonical_value=report_date.isoformat(),
                ),
                source=source,
                use=EvidenceUse.DECISION_GRADE,
                source_record_id=source_record_id,
                published_at=created_at or report_date,
                effective_at=report_date,
                material=True,
            )
        )
    return tuple(records)


def _dividend_records(
    *,
    target: ResearchTargetV1,
    rows: Iterable[object],
    retrieved_at: datetime,
) -> tuple[EvidenceRecordV1, ...]:
    source = _source("GetDividends", retrieved_at)
    records: list[EvidenceRecordV1] = []
    for row in rows:
        record_date = _timestamp(getattr(row, "record_date", None))
        declared_date = _timestamp(getattr(row, "declared_date", None))
        money = getattr(row, "dividend_net", None)
        canonical = _decimal_text(money)
        currency = str(getattr(money, "currency", "") or "").upper()
        if canonical is None or len(currency) != 3 or record_date is None:
            continue
        record_id = f"{record_date.isoformat()}:{canonical}:{currency}"
        records.append(
            make_evidence_record(
                instrument_uid=target.instrument_uid,
                fact_type=EvidenceFactType.DIVIDEND,
                fact_key=f"dividend.record.{record_date.date().isoformat()}",
                value=EvidenceValueV1(
                    value_type=EvidenceValueType.MONEY,
                    canonical_value=canonical,
                    currency=currency,
                ),
                source=source,
                use=EvidenceUse.DECISION_GRADE,
                source_record_id=record_id,
                published_at=declared_date,
                effective_at=record_date,
                material=True,
            )
        )
    return tuple(records)


def _bond_event_records(
    *,
    target: ResearchTargetV1,
    rows: Iterable[object],
    retrieved_at: datetime,
) -> tuple[EvidenceRecordV1, ...]:
    source = _source("GetBondEvents", retrieved_at)
    records: list[EvidenceRecordV1] = []
    for row in rows:
        event_date = _timestamp(getattr(row, "event_date", None))
        if event_date is None:
            continue
        event_number = int(getattr(row, "event_number", 0) or 0)
        event_type = _enum_text(getattr(row, "event_type", None))
        records.append(
            make_evidence_record(
                instrument_uid=target.instrument_uid,
                fact_type=(
                    EvidenceFactType.COUPON
                    if "cpn" in event_type or "coupon" in event_type
                    else EvidenceFactType.CORPORATE_EVENT
                ),
                fact_key=f"bond_event.{event_type}.{event_number}",
                value=EvidenceValueV1(
                    value_type=EvidenceValueType.DATETIME,
                    canonical_value=event_date.isoformat(),
                ),
                source=source,
                use=EvidenceUse.DECISION_GRADE,
                source_record_id=f"{event_type}:{event_number}",
                published_at=_timestamp(getattr(row, "rate_date", None)),
                effective_at=event_date,
                material=True,
            )
        )
    return tuple(records)


def _tinvest_asset_identity_ready(target: ResearchTargetV1) -> bool:
    if target.asset_uid is None or target.asset_uid_source is None:
        return False
    return target.asset_uid_source.provider.strip().casefold() in _TINVEST_PROVIDER_NAMES


class TInvestResearchAdapterV1:
    """Read-only normalization of structured T-Invest research surfaces."""

    def __init__(
        self,
        token: str,
        *,
        client_factory: ClientFactory | None = None,
    ) -> None:
        if not token:
            raise TInvestResearchAdapterError("TIN_RESEARCH_TOKEN_REQUIRED")
        self._token = token
        self._client_factory = client_factory or Client

    def fetch(
        self,
        *,
        target: ResearchTargetV1,
        retrieved_at: datetime | None = None,
        lookback_days: int = 730,
        lookahead_days: int = 370,
    ) -> tuple[tuple[EvidenceRecordV1, ...], tuple[EvidenceCoverageProbeV1, ...]]:
        now = _utc(retrieved_at)
        start = now - timedelta(days=lookback_days)
        end = now + timedelta(days=lookahead_days)
        records: list[EvidenceRecordV1] = []
        probes: list[EvidenceCoverageProbeV1] = []

        with self._client_factory(self._token) as client:
            if _tinvest_asset_identity_ready(target):
                try:
                    response = client.instruments.get_asset_fundamentals(
                        assets=[target.asset_uid]
                    )
                    rows = tuple(getattr(response, "fundamentals", ()) or ())
                    normalized = _fundamental_records(
                        target=target,
                        rows=rows,
                        retrieved_at=now,
                    )
                    records.extend(normalized)
                    probes.append(
                        EvidenceCoverageProbeV1(
                            instrument_uid=target.instrument_uid,
                            fact_type=EvidenceFactType.FUNDAMENTAL,
                            source_class=EvidenceSourceClass.BROKER,
                            checked_at=now,
                            success=True,
                            record_count=len(normalized),
                        )
                    )
                except Exception as exc:
                    probes.append(
                        EvidenceCoverageProbeV1(
                            instrument_uid=target.instrument_uid,
                            fact_type=EvidenceFactType.FUNDAMENTAL,
                            source_class=EvidenceSourceClass.BROKER,
                            checked_at=now,
                            success=False,
                            source_error=type(exc).__name__,
                        )
                    )
            else:
                error = (
                    "asset_uid_missing"
                    if target.asset_uid is None
                    else "asset_uid_source_not_tinvest"
                )
                probes.append(
                    EvidenceCoverageProbeV1(
                        instrument_uid=target.instrument_uid,
                        fact_type=EvidenceFactType.FUNDAMENTAL,
                        source_class=EvidenceSourceClass.BROKER,
                        checked_at=now,
                        success=False,
                        source_error=error,
                    )
                )

            for fact_type, method_name, response_attr, normalizer in (
                (
                    EvidenceFactType.REPORT,
                    "get_asset_reports",
                    "events",
                    _report_records,
                ),
                (
                    EvidenceFactType.DIVIDEND,
                    "get_dividends",
                    "dividends",
                    _dividend_records,
                ),
            ):
                try:
                    method = getattr(client.instruments, method_name)
                    response = method(
                        instrument_id=target.instrument_uid,
                        from_=start,
                        to=end,
                    )
                    rows = tuple(getattr(response, response_attr, ()) or ())
                    normalized = normalizer(
                        target=target,
                        rows=rows,
                        retrieved_at=now,
                    )
                    records.extend(normalized)
                    probes.append(
                        EvidenceCoverageProbeV1(
                            instrument_uid=target.instrument_uid,
                            fact_type=fact_type,
                            source_class=EvidenceSourceClass.BROKER,
                            checked_at=now,
                            success=True,
                            record_count=len(normalized),
                        )
                    )
                except Exception as exc:
                    probes.append(
                        EvidenceCoverageProbeV1(
                            instrument_uid=target.instrument_uid,
                            fact_type=fact_type,
                            source_class=EvidenceSourceClass.BROKER,
                            checked_at=now,
                            success=False,
                            source_error=type(exc).__name__,
                        )
                    )

            if target.instrument_type is InstrumentType.BOND:
                try:
                    response = client.instruments.get_bond_events(
                        instrument_id=target.instrument_uid,
                        from_=start,
                        to=end,
                        type=0,
                    )
                    rows = tuple(getattr(response, "events", ()) or ())
                    normalized = _bond_event_records(
                        target=target,
                        rows=rows,
                        retrieved_at=now,
                    )
                    records.extend(normalized)
                    probes.append(
                        EvidenceCoverageProbeV1(
                            instrument_uid=target.instrument_uid,
                            fact_type=EvidenceFactType.CORPORATE_EVENT,
                            source_class=EvidenceSourceClass.BROKER,
                            checked_at=now,
                            success=True,
                            record_count=len(normalized),
                        )
                    )
                except Exception as exc:
                    probes.append(
                        EvidenceCoverageProbeV1(
                            instrument_uid=target.instrument_uid,
                            fact_type=EvidenceFactType.CORPORATE_EVENT,
                            source_class=EvidenceSourceClass.BROKER,
                            checked_at=now,
                            success=False,
                            source_error=type(exc).__name__,
                        )
                    )

        return tuple(records), tuple(probes)
