from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from omni_cio.contracts.v1.common import (
    Completeness,
    ContractMetadata,
    DataIssue,
    DataQuality,
    IssueSeverity,
    Money,
    QualityMetadata,
    SourceReference,
)
from omni_cio.contracts.v1.pretrade import (
    PreTradeBlocker,
    PreTradePreviewV1,
    PreviewFreshnessStatus,
    PreviewPriceBasis,
)
from omni_cio.contracts.v1.rebalancing import (
    RebalanceAlternativeKind,
    RebalanceAlternativeStatus,
    RebalanceDirection,
    ThresholdRebalancePlanV1,
)


class PreTradeOrchestratorError(ValueError):
    """The supplied preview data cannot be normalized safely."""


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    return str(value or "").strip()


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError, AttributeError):
        return None
    return result if result.is_finite() else None


def _positive_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = int(str(value))
    except (ValueError, TypeError, OverflowError):
        return None
    return result if result > 0 else None


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise PreTradeOrchestratorError("PRETRADE_TIMESTAMP_MUST_BE_AWARE")
    return result.astimezone(timezone.utc)


def _timestamp(value: object) -> datetime | None:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        text = value.strip()
        if not text or text.lower() in {
            "unavailable",
            "not_applicable",
            "unknown",
        }:
            return None
        try:
            result = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if result.tzinfo is None or result.utcoffset() is None:
        return None
    return result.astimezone(timezone.utc)


def _currency(value: object) -> str:
    text = _text(value).upper()
    return text if len(text) == 3 and text.isalpha() else ""


def _money(value: object) -> Money | None:
    data = _mapping(value)
    amount = _decimal(data.get("amount"))
    currency = _currency(data.get("currency"))
    if amount is None or not currency:
        return None
    return Money(amount=amount, currency=currency)


def _append(blockers: list[PreTradeBlocker], blocker: PreTradeBlocker) -> None:
    if blocker not in blockers:
        blockers.append(blocker)


def _payload_account(payload: Mapping[str, object]) -> str:
    account = _mapping(payload.get("account"))
    for key in (
        "masked_id",
        "masked_account_id",
        "id_masked",
        "account_id_masked",
        "id",
        "account_id",
    ):
        value = _text(account.get(key))
        if value:
            return value
    return ""


def _price_basis(value: object) -> PreviewPriceBasis:
    text = _text(value).lower()
    try:
        return PreviewPriceBasis(text)
    except ValueError:
        return PreviewPriceBasis.UNKNOWN


def _source_reference(payload: Mapping[str, object], fallback: datetime) -> SourceReference:
    retrieved_at = _timestamp(payload.get("retrieved_at")) or fallback
    return SourceReference(
        provider="t-invest",
        operation="getPurchaseCapacityPreview",
        retrieved_at=retrieved_at,
        source_id=_text(payload.get("version")) or None,
    )


def build_pretrade_preview(
    purchase_payload: Mapping[str, object],
    rebalance_plan: ThresholdRebalancePlanV1,
    *,
    stable_key: str,
    evaluated_at: datetime | None = None,
    max_price_age_seconds: Decimal = Decimal("120"),
) -> PreTradePreviewV1:
    """Convert a legacy purchase preview into a strict fail-closed contract."""

    evaluation_time = _aware_utc(evaluated_at)
    if not max_price_age_seconds.is_finite() or max_price_age_seconds <= 0:
        raise PreTradeOrchestratorError("INVALID_PRICE_FRESHNESS_THRESHOLD")

    matching_lines = [
        line for line in rebalance_plan.lines if line.stable_key == stable_key
    ]
    if len(matching_lines) != 1:
        raise PreTradeOrchestratorError("REBALANCE_LINE_NOT_FOUND_OR_DUPLICATE")
    line = matching_lines[0]

    blockers: list[PreTradeBlocker] = []
    if not rebalance_plan.decision_ready:
        _append(blockers, PreTradeBlocker.PLAN_NOT_READY)
    if line.direction != RebalanceDirection.ADD or line.sale_required:
        _append(blockers, PreTradeBlocker.TARGET_NOT_ADD)

    cash_first = next(
        alternative
        for alternative in rebalance_plan.alternatives
        if alternative.kind == RebalanceAlternativeKind.CASH_FIRST
    )
    if (
        cash_first.status == RebalanceAlternativeStatus.BLOCKED
        or cash_first.planned_add_value <= 0
    ):
        _append(blockers, PreTradeBlocker.CASH_FIRST_NOT_AVAILABLE)

    payload_account = _payload_account(purchase_payload)
    if payload_account != rebalance_plan.metadata.account.masked_id:
        _append(blockers, PreTradeBlocker.ACCOUNT_MISMATCH)

    request = _mapping(purchase_payload.get("request"))
    instrument = _mapping(purchase_payload.get("instrument"))
    instrument_resolution = _mapping(purchase_payload.get("instrument_resolution"))
    market_price = _mapping(purchase_payload.get("market_price"))
    own_funds_data = _mapping(purchase_payload.get("own_funds"))
    order_preview = _mapping(purchase_payload.get("order_preview"))
    quality = _mapping(purchase_payload.get("quality"))
    commission_summary = _mapping(purchase_payload.get("commission_summary"))
    calculation_checks = _mapping(purchase_payload.get("calculation_checks"))
    currency_consistency = _mapping(purchase_payload.get("currency_consistency"))

    source_complete = (
        purchase_payload.get("status") == "ok"
        and purchase_payload.get("complete") is True
        and quality.get("complete") is True
        and purchase_payload.get("trading_methods") is False
    )
    if not source_complete:
        _append(blockers, PreTradeBlocker.SOURCE_INCOMPLETE)

    instrument_resolved = (
        quality.get("instrument_resolved") is True
        and instrument_resolution.get("status") == "resolved"
    )
    if not instrument_resolved:
        _append(blockers, PreTradeBlocker.INSTRUMENT_UNRESOLVED)

    currency = line.currency
    price_basis = _price_basis(
        market_price.get("basis") or request.get("price_basis")
    )
    if price_basis == PreviewPriceBasis.MANUAL:
        _append(blockers, PreTradeBlocker.MANUAL_PRICE_NOT_ALLOWED)

    price = _decimal(market_price.get("price"))
    if price is None or price <= 0 or market_price.get("status") != "ok":
        price = None
        _append(blockers, PreTradeBlocker.PRICE_UNAVAILABLE)

    price_time = _timestamp(
        market_price.get("source_time")
        or _mapping(purchase_payload.get("price_freshness")).get("source_time")
    )
    price_age: Decimal | None = None
    if price_basis == PreviewPriceBasis.MANUAL:
        freshness_status = PreviewFreshnessStatus.MANUAL_INPUT
    elif price_time is None:
        freshness_status = PreviewFreshnessStatus.UNKNOWN
        _append(blockers, PreTradeBlocker.PRICE_TIME_UNKNOWN)
    else:
        raw_age = Decimal(str((evaluation_time - price_time).total_seconds()))
        if raw_age < 0:
            freshness_status = PreviewFreshnessStatus.UNKNOWN
            _append(blockers, PreTradeBlocker.PRICE_TIME_IN_FUTURE)
        else:
            price_age = raw_age
            if raw_age > max_price_age_seconds:
                freshness_status = PreviewFreshnessStatus.STALE
                _append(blockers, PreTradeBlocker.PRICE_STALE)
            else:
                freshness_status = PreviewFreshnessStatus.FRESH

    lot_size = _positive_int(market_price.get("lot_size") or instrument.get("lot"))
    quantity_lots = _positive_int(request.get("quantity_lots"))
    if lot_size is None or quantity_lots is None:
        _append(blockers, PreTradeBlocker.LOT_INVALID)

    initial_order_amount = _money(order_preview.get("initial_order_amount"))
    total_order_amount = _money(order_preview.get("total_order_amount"))
    canonical_commission = _money(
        _mapping(commission_summary.get("canonical_commission"))
    )
    accrued_interest = _money(
        _mapping(_mapping(order_preview.get("extra_bond")).get("aci_value"))
    )

    own_amount = _decimal(own_funds_data.get("buy_money_amount"))
    own_currency = _currency(own_funds_data.get("currency"))
    own_funds = (
        Money(amount=own_amount, currency=own_currency)
        if own_amount is not None and own_currency
        else None
    )
    remaining_amount = _decimal(purchase_payload.get("remaining_cash_estimate"))
    remaining_currency = _currency(
        purchase_payload.get("remaining_cash_currency")
    )
    remaining_cash = (
        Money(amount=remaining_amount, currency=remaining_currency)
        if remaining_amount is not None and remaining_currency
        else None
    )

    if canonical_commission is None:
        _append(blockers, PreTradeBlocker.COMMISSION_UNAVAILABLE)

    money_values = (
        initial_order_amount,
        canonical_commission,
        accrued_interest,
        total_order_amount,
        own_funds,
        remaining_cash,
    )
    if (
        currency_consistency.get("status") != "ok"
        or any(
            money is not None and money.currency != currency
            for money in money_values
        )
    ):
        _append(blockers, PreTradeBlocker.CURRENCY_MISMATCH)

    integrity_confirmed = (
        calculation_checks.get("integrity_confirmed") is True
        and quality.get("calculation_integrity_confirmed") is True
        and quality.get("commission_double_count_protected") is True
        and quality.get("currency_consistent") is True
    )
    if not integrity_confirmed:
        _append(blockers, PreTradeBlocker.ARITHMETIC_INTEGRITY_FAILED)

    affordability_confirmed = purchase_payload.get("affordability_confirmed") is True
    affordable = purchase_payload.get("affordable") == "yes"
    if not affordability_confirmed:
        _append(blockers, PreTradeBlocker.AFFORDABILITY_UNCONFIRMED)
    elif not affordable:
        _append(blockers, PreTradeBlocker.INSUFFICIENT_FUNDS)

    target_value_limit = Money(amount=line.value_to_target, currency=currency)
    if (
        total_order_amount is not None
        and total_order_amount.amount > line.value_to_target + Decimal("0.01")
    ):
        _append(blockers, PreTradeBlocker.TARGET_BAND_OVERSHOOT)

    data_issues = tuple(
        DataIssue(
            code=f"PRETRADE_{blocker.value.upper()}",
            severity=IssueSeverity.ERROR,
            message=f"Pre-trade gate is open: {blocker.value}.",
            component="pretrade_preview",
        )
        for blocker in blockers
    )
    metadata = ContractMetadata(
        schema_name="pretrade_preview",
        retrieved_at=evaluation_time,
        account=rebalance_plan.metadata.account,
        provenance=(
            *rebalance_plan.metadata.provenance,
            _source_reference(purchase_payload, evaluation_time),
            SourceReference(
                provider="omni-cio",
                operation="build_pretrade_preview",
                retrieved_at=evaluation_time,
                source_id="1.0",
            ),
        ),
        quality=QualityMetadata(
            quality=DataQuality.VERIFIED if not blockers else DataQuality.DEGRADED,
            completeness=(
                Completeness.COMPLETE if not blockers else Completeness.INCOMPLETE
            ),
            issues=data_issues,
            warnings=(
                "Analytical preview only; it cannot create, replace, cancel, or submit an order.",
            ),
        ),
    )

    return PreTradePreviewV1(
        metadata=metadata,
        stable_key=stable_key,
        instrument_uid=_text(
            request.get("instrument_uid") or instrument.get("uid")
        )
        or None,
        currency=currency,
        price_basis=price_basis,
        price_source=_text(market_price.get("source")) or "unavailable",
        price_time=price_time,
        evaluated_at=evaluation_time,
        price_age_seconds=price_age,
        max_price_age_seconds=max_price_age_seconds,
        freshness_status=freshness_status,
        unit_price=price,
        lot_size=lot_size,
        quantity_lots=quantity_lots,
        initial_order_amount=initial_order_amount,
        canonical_commission=canonical_commission,
        accrued_interest=accrued_interest,
        total_order_amount=total_order_amount,
        own_funds=own_funds,
        remaining_cash=remaining_cash,
        target_value_limit=target_value_limit,
        affordable=affordable,
        source_complete=source_complete,
        integrity_confirmed=integrity_confirmed,
        blockers=tuple(blockers),
        preview_ready=not blockers,
        execution_ready=False,
        trading_methods=False,
    )
