"""A sourced instrument card from one UID and its explicitly linked asset."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from .broker import BrokerService
from .tbank import TBankAssetFundamental, TBankInstrumentMetadata, TBankUnavailable

_INSTRUMENT_SOURCE = "https://developer.tbank.ru/invest/api/instruments-service-get-instrument-by"
_FUNDAMENTAL_SOURCE = (
    "https://developer.tbank.ru/invest/api/instruments-service-get-asset-fundamentals"
)
_TTM = "TTM · последние 12 месяцев"
_LATEST = "Последнее значение источника"
_SOURCE_UNIT = "ед. источника"

# Preserve the provider's scale. In particular, no fiscal year end is invented
# as the publication date of today's statistics and no ratio is multiplied by 100.
_METRICS = (
    ("market_capitalization", "Капитализация", "currency", _LATEST),
    ("pe_ratio_ttm", "P/E", "×", _TTM),
    ("dividend_yield_daily_ttm", "Дивидендная доходность", _SOURCE_UNIT, _TTM),
    (
        "forward_annual_dividend_yield", "Прогнозная дивидендная доходность", "%",
        "Форвардная оценка",
    ),
    ("price_to_sales_ttm", "P/S", "×", _TTM),
    ("price_to_book_ttm", "P/B", "×", _TTM),
    ("revenue_ttm", "Выручка", "currency", _TTM),
    ("net_income_ttm", "Чистая прибыль", "currency", _TTM),
    ("eps_ttm", "Прибыль на акцию", "per_share", _TTM),
    ("free_cash_flow_ttm", "Свободный денежный поток", "currency", _TTM),
    ("total_debt_to_ebitda_mrq", "Долг / EBITDA", "×", "MRQ · последний отчётный квартал"),
    ("dividend_payout_ratio_fy", "Доля прибыли на дивиденды", "%", "FY · последний отчётный год"),
    ("roe", "ROE", _SOURCE_UNIT, _LATEST),
)
_CORE_METRICS = {"market_capitalization", "pe_ratio_ttm", "dividend_yield_daily_ttm"}


def _metric_value(raw: str | None) -> str | None:
    if raw is None:
        return None
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise TBankUnavailable("instrument fundamental value is invalid") from exc
    if not value.is_finite():
        raise TBankUnavailable("instrument fundamental value is invalid")
    # GetAssetFundamentals explicitly uses zero for absence, not observed zero.
    return None if value == 0 else format(value, "f")


def _fundamental_metrics(
    fundamental: TBankAssetFundamental | None,
) -> tuple[list[dict[str, str]], set[str]]:
    if fundamental is None:
        return [], {"asset_fundamentals"}
    rows, missing = [], set()
    for key, label, unit, period in _METRICS:
        value = _metric_value(getattr(fundamental, key))
        if value is None:
            if key in _CORE_METRICS:
                missing.add("metric:" + key)
            continue
        if unit in {"currency", "per_share"}:
            if not fundamental.currency:
                missing.add("fundamental_currency")
                continue
            unit = fundamental.currency + ("/акцию" if unit == "per_share" else "")
        rows.append({
            "key": key, "label": label, "value": value, "unit": unit,
            "period": period, "source_url": _FUNDAMENTAL_SOURCE,
        })
    return rows, missing


def _instrument_requirements(metadata: TBankInstrumentMetadata) -> set[str]:
    missing = {
        "instrument:" + key
        for key in ("currency", "name", "ticker", "instrument_type", "exchange", "asset_uid")
        if not getattr(metadata, key)
    }
    if metadata.lot <= 0:
        missing.add("instrument:lot")
    return missing


def instrument_facts(
    *, user_id: UUID, instrument_uid: str, broker: BrokerService,
) -> dict[str, Any]:
    """Public card; BrokerService uses only the common server market credential."""
    metadata, fundamental = broker.instrument_facts(user_id, instrument_uid)
    if metadata.uid != instrument_uid.strip() or (
        fundamental is not None and fundamental.asset_uid != metadata.asset_uid
    ):
        raise TBankUnavailable("instrument facts identity mismatch")
    metrics, missing = _fundamental_metrics(fundamental)
    missing.update(_instrument_requirements(metadata))
    limitations = [
        "Показатели взяты из последней доступной статистики T-Invest. Точная дата оценки "
        "и публикации отдельных значений не раскрыта; время получения не заменяет эти даты.",
        "Нулевое значение статистики T-Invest означает отсутствие данных.",
    ]
    if any(row["unit"] == _SOURCE_UNIT for row in metrics):
        limitations.append(
            "Масштаб ROE и дивидендной доходности TTM не указан явно в контракте источника. "
            "Эти значения сохранены в исходных единицах без пересчёта в проценты."
        )
    if any(row["key"] == "forward_annual_dividend_yield" for row in metrics):
        limitations.append(
            "Форвардная дивидендная доходность — оценка источника, а не объявленная выплата "
            "или обещание дохода."
        )
    return {
        "instrument_uid": metadata.uid,
        "currency": metadata.currency or None,
        "name": metadata.name or None,
        "ticker": metadata.ticker or None,
        "instrument_type": metadata.instrument_type or None,
        "exchange": metadata.exchange or None,
        "lot": metadata.lot or None,
        "asset_uid": metadata.asset_uid or None,
        "metrics": metrics,
        "source_url": _INSTRUMENT_SOURCE,
        "observed_at": datetime.now(UTC).isoformat(),
        "data_as_of": None,
        "status": "partial" if missing else "available",
        "missing_requirements": sorted(missing),
        "limitations": limitations,
    }
