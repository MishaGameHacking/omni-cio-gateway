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
from omni_cio.contracts.v1.pretrade import PreviewFreshnessStatus
from omni_cio.contracts.v1.rebalancing import (
    RebalanceAlternativeKind,
    RebalanceBlocker,
    RebalanceDirection,
    ThresholdRebalancePlanV1,
)
from omni_cio.contracts.v1.sell_pretrade import (
    SellPreTradeBlocker,
    SellPreTradePreviewV1,
    SellPreviewPriceBasis,
)


_MONEY_TOLERANCE = Decimal("0.01")
_WEIGHT_TOLERANCE = Decimal("0.000000001")
_ALLOWED_FULL_THRESHOLD_BLOCKERS = {
    RebalanceBlocker.LIVE_PREVIEW_REQUIRED,
    RebalanceBlocker.SALES_REQUIRE_TAX_BASIS,
}


class SellPreTradeOrchestratorError(ValueError):
    """The supplied read-only sale evidence cannot be normalized safely."""


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


def _nonnegative_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = int(str(value))
    except (ValueError, TypeError, OverflowError):
        return None
    return result if result >= 0 else None


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise SellPreTradeOrchestratorError("SELL_PRETRADE_TIMESTAMP_MUST_BE_AWARE")
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


def _append(
    blockers: list[SellPreTradeBlocker],
    blocker: SellPreTradeBlocker,
) -> None:
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


def _price_basis(value: object) -> SellPreviewPriceBasis:
    text = _text(value).lower()
    try:
        return SellPreviewPriceBasis(text)
    except ValueError:
        return SellPreviewPriceBasis.UNKNOWN


def _source_reference(
    payload: Mapping[str, object],
    fallback: datetime,
) -> SourceReference:
    retrieved_at = _timestamp(payload.get("retrieved_at")) or fallback
    return SourceReference(
        provider="t-invest",
        operation="getSaleCapacityPreview",
        retrieved_at=retrieved_at,
        source_id=_text(payload.get("version")) or None,
    )


def build_sell_pretrade_preview(
    sale_payload: Mapping[str, object],
    rebalance_plan: ThresholdRebalancePlanV1,
    *,
    stable_key: str,
    evaluated_at: datetime | None = None,
    max_price_age_seconds: Decimal = Decimal("120"),
) -> SellPreTradePreviewV1:
    """Build a strict non-executing sell preview from normalized read-only evidence."""

    evaluation_time = _aware_utc(evaluated_at)
    if not max_price_age_seconds.is_finite() or max_price_age_seconds <= 0:
        raise SellPreTradeOrchestratorError(
            "INVALID_SELL_PRICE_FRESHNESS_THRESHOLD"
        )

    matching_lines = [
        line for line in rebalance_plan.lines if line.stable_key == stable_key
    ]
    if len(matching_lines) != 1:
        raise SellPreTradeOrchestratorError(
            "SELL_REBALANCE_LINE_NOT_FOUND_OR_DUPLICATE"
        )
    line = matching_lines[0]

    blockers: list[SellPreTradeBlocker] = []
    if not rebalance_plan.decision_ready:
        _append(blockers, SellPreTradeBlocker.PLAN_NOT_READY)
    if line.direction != RebalanceDirection.REDUCE or not line.sale_required:
        _append(blockers, SellPreTradeBlocker.TARGET_NOT_REDUCE)

    full_threshold = next(
        alternative
        for alternative in rebalance_plan.alternatives
        if alternative.kind == RebalanceAlternativeKind.FULL_THRESHOLD
    )
    unexpected_full_blockers = (
        set(full_threshold.blockers) - _ALLOWED_FULL_THRESHOLD_BLOCKERS
    )
    if (
        not full_threshold.uses_sales
        or full_threshold.planned_reduce_value <= 0
        or bool(unexpected_full_blockers)
    ):
        _append(blockers, SellPreTradeBlocker.SALE_ALTERNATIVE_NOT_AVAILABLE)

    payload_account = _payload_account(sale_payload)
    if payload_account != rebalance_plan.metadata.account.masked_id:
        _append(blockers, SellPreTradeBlocker.ACCOUNT_MISMATCH)

    request = _mapping(sale_payload.get("request"))
    instrument = _mapping(sale_payload.get("instrument"))
    instrument_resolution = _mapping(sale_payload.get("instrument_resolution"))
    market_price = _mapping(sale_payload.get("market_price"))
    position_limits = _mapping(sale_payload.get("position_limits"))
    open_orders = _mapping(sale_payload.get("open_orders"))
    order_preview = _mapping(sale_payload.get("order_preview"))
    quality = _mapping(sale_payload.get("quality"))
    commission_summary = _mapping(sale_payload.get("commission_summary"))
    tax_basis = _mapping(sale_payload.get("tax_basis"))
    calculation_checks = _mapping(sale_payload.get("calculation_checks"))
    currency_consistency = _mapping(sale_payload.get("currency_consistency"))

    source_complete = (
        sale_payload.get("status") == "ok"
        and sale_payload.get("complete") is True
        and quality.get("complete") is True
        and sale_payload.get("trading_methods") is False
        and quality.get("read_only") is True
        and quality.get("no_order_created") is True
    )
    if not source_complete:
        _append(blockers, SellPreTradeBlocker.SOURCE_INCOMPLETE)

    direction = _text(request.get("direction")).upper()
    if direction not in {"SELL", "ORDER_DIRECTION_SELL"}:
        _append(blockers, SellPreTradeBlocker.DIRECTION_MISMATCH)

    instrument_resolved = (
        quality.get("instrument_resolved") is True
        and instrument_resolution.get("status") == "resolved"
    )
    if not instrument_resolved:
        _append(blockers, SellPreTradeBlocker.INSTRUMENT_UNRESOLVED)

    currency = line.currency
    price_basis = _price_basis(
        market_price.get("basis") or request.get("price_basis")
    )
    if price_basis == SellPreviewPriceBasis.MANUAL:
        _append(blockers, SellPreTradeBlocker.MANUAL_PRICE_NOT_ALLOWED)

    price = _decimal(market_price.get("price"))
    if price is None or price <= 0 or market_price.get("status") != "ok":
        price = None
        _append(blockers, SellPreTradeBlocker.PRICE_UNAVAILABLE)

    price_time = _timestamp(
        market_price.get("source_time")
        or _mapping(sale_payload.get("price_freshness")).get("source_time")
    )
    price_age: Decimal | None = None
    if price_basis == SellPreviewPriceBasis.MANUAL:
        freshness_status = PreviewFreshnessStatus.MANUAL_INPUT
    elif price_time is None:
        freshness_status = PreviewFreshnessStatus.UNKNOWN
        _append(blockers, SellPreTradeBlocker.PRICE_TIME_UNKNOWN)
    else:
        raw_age = Decimal(str((evaluation_time - price_time).total_seconds()))
        if raw_age < 0:
            freshness_status = PreviewFreshnessStatus.UNKNOWN
            _append(blockers, SellPreTradeBlocker.PRICE_TIME_IN_FUTURE)
        else:
            price_age = raw_age
            if raw_age > max_price_age_seconds:
                freshness_status = PreviewFreshnessStatus.STALE
                _append(blockers, SellPreTradeBlocker.PRICE_STALE)
            else:
                freshness_status = PreviewFreshnessStatus.FRESH

    lot_size = _positive_int(market_price.get("lot_size") or instrument.get("lot"))
    quantity_lots = _positive_int(request.get("quantity_lots"))
    quantity_units = (
        lot_size * quantity_lots
        if lot_size is not None and quantity_lots is not None
        else None
    )
    if lot_size is None or quantity_lots is None:
        _append(blockers, SellPreTradeBlocker.LOT_INVALID)

    position_lots = _positive_int(
        position_limits.get("position_lots")
        or position_limits.get("current_position_lots")
    )
    sell_max_lots = _nonnegative_int(position_limits.get("sell_max_lots"))
    position_availability_confirmed = (
        position_limits.get("status") == "ok"
        and quality.get("position_availability_confirmed") is True
        and position_lots is not None
        and sell_max_lots is not None
    )
    if not position_availability_confirmed:
        _append(blockers, SellPreTradeBlocker.POSITION_LIMITS_UNAVAILABLE)

    open_orders_checked = (
        open_orders.get("status") == "ok"
        and open_orders.get("checked") is True
        and quality.get("open_orders_checked") is True
    )
    conflicting_open_sell_lots = _nonnegative_int(
        open_orders.get("conflicting_sell_lots")
    )
    if not open_orders_checked or conflicting_open_sell_lots is None:
        _append(blockers, SellPreTradeBlocker.OPEN_ORDERS_UNCHECKED)
    available_after_open_orders_lots = (
        max(0, position_lots - conflicting_open_sell_lots)
        if position_lots is not None and conflicting_open_sell_lots is not None
        else None
    )

    remaining_position_lots: int | None = None
    if position_lots is not None and quantity_lots is not None:
        if quantity_lots > position_lots:
            _append(blockers, SellPreTradeBlocker.POSITION_INSUFFICIENT)
            _append(blockers, SellPreTradeBlocker.SHORT_SALE_FORBIDDEN)
        else:
            remaining_position_lots = position_lots - quantity_lots
    if (
        quantity_lots is not None
        and sell_max_lots is not None
        and quantity_lots > sell_max_lots
    ):
        _append(blockers, SellPreTradeBlocker.POSITION_INSUFFICIENT)
    if (
        quantity_lots is not None
        and available_after_open_orders_lots is not None
        and quantity_lots > available_after_open_orders_lots
    ):
        _append(blockers, SellPreTradeBlocker.OPEN_ORDER_CONFLICT)
        _append(blockers, SellPreTradeBlocker.POSITION_INSUFFICIENT)

    current_position_value = Money(amount=line.current_value, currency=currency)
    source_position_value = _money(position_limits.get("current_position_value"))
    if source_position_value is not None and (
        source_position_value.currency != currency
        or abs(source_position_value.amount - line.current_value) > _MONEY_TOLERANCE
    ):
        _append(blockers, SellPreTradeBlocker.POSITION_VALUE_MISMATCH)

    gross_security_proceeds = _money(order_preview.get("initial_order_amount"))
    accrued_interest_proceeds = _money(
        _mapping(order_preview.get("extra_bond")).get("aci_value")
    )
    canonical_commission = _money(
        _mapping(commission_summary.get("canonical_commission"))
    )
    estimated_tax = _money(tax_basis.get("estimated_tax"))

    if canonical_commission is None or canonical_commission.amount < 0:
        _append(blockers, SellPreTradeBlocker.COMMISSION_UNAVAILABLE)
    tax_basis_confirmed = (
        tax_basis.get("status") == "ok"
        and tax_basis.get("confirmed") is True
        and quality.get("tax_basis_confirmed") is True
        and estimated_tax is not None
        and estimated_tax.amount >= 0
    )
    if not tax_basis_confirmed:
        _append(blockers, SellPreTradeBlocker.TAX_BASIS_UNAVAILABLE)

    gross_proceeds = (
        Money(
            amount=gross_security_proceeds.amount
            + (
                accrued_interest_proceeds.amount
                if accrued_interest_proceeds is not None
                else Decimal("0")
            ),
            currency=currency,
        )
        if gross_security_proceeds is not None
        and gross_security_proceeds.currency == currency
        and (
            accrued_interest_proceeds is None
            or accrued_interest_proceeds.currency == currency
        )
        else None
    )
    net_proceeds = (
        Money(
            amount=(
                gross_proceeds.amount
                - canonical_commission.amount
                - estimated_tax.amount
            ),
            currency=currency,
        )
        if gross_proceeds is not None
        and canonical_commission is not None
        and canonical_commission.currency == currency
        and estimated_tax is not None
        and estimated_tax.currency == currency
        else None
    )
    if net_proceeds is not None and net_proceeds.amount < 0:
        _append(blockers, SellPreTradeBlocker.ARITHMETIC_INTEGRITY_FAILED)

    supplied_gross = _money(order_preview.get("gross_proceeds"))
    supplied_net = _money(order_preview.get("net_proceeds"))
    computed_amounts_match = True
    if supplied_gross is not None and gross_proceeds is not None:
        computed_amounts_match = computed_amounts_match and (
            supplied_gross.currency == currency
            and abs(supplied_gross.amount - gross_proceeds.amount)
            <= _MONEY_TOLERANCE
        )
    if supplied_net is not None and net_proceeds is not None:
        computed_amounts_match = computed_amounts_match and (
            supplied_net.currency == currency
            and abs(supplied_net.amount - net_proceeds.amount)
            <= _MONEY_TOLERANCE
        )

    money_values = (
        source_position_value,
        gross_security_proceeds,
        accrued_interest_proceeds,
        canonical_commission,
        estimated_tax,
        supplied_gross,
        supplied_net,
    )
    if (
        currency_consistency.get("status") != "ok"
        or any(
            money is not None and money.currency != currency
            for money in money_values
        )
    ):
        _append(blockers, SellPreTradeBlocker.CURRENCY_MISMATCH)

    sold_position_value: Money | None = None
    estimated_post_sale_position_value: Money | None = None
    estimated_portfolio_value_before: Money | None = None
    estimated_portfolio_value_after: Money | None = None
    estimated_post_sale_weight: Decimal | None = None
    if (
        position_lots is not None
        and quantity_lots is not None
        and quantity_lots <= position_lots
    ):
        sold_amount = (
            line.current_value
            * Decimal(quantity_lots)
            / Decimal(position_lots)
        )
        sold_position_value = Money(amount=sold_amount, currency=currency)
        remaining_value = line.current_value - sold_amount
        estimated_post_sale_position_value = Money(
            amount=remaining_value,
            currency=currency,
        )
        if line.current_weight > 0:
            portfolio_before_amount = line.current_value / line.current_weight
            estimated_portfolio_value_before = Money(
                amount=portfolio_before_amount,
                currency=currency,
            )
            if net_proceeds is not None:
                portfolio_after_amount = (
                    portfolio_before_amount - sold_amount + net_proceeds.amount
                )
                if portfolio_after_amount > 0:
                    estimated_portfolio_value_after = Money(
                        amount=portfolio_after_amount,
                        currency=currency,
                    )
                    estimated_post_sale_weight = (
                        remaining_value / portfolio_after_amount
                    )

    if (
        sold_position_value is not None
        and sold_position_value.amount > line.value_to_target + _MONEY_TOLERANCE
    ):
        _append(blockers, SellPreTradeBlocker.TARGET_REDUCTION_OVERSHOOT)
    if (
        estimated_post_sale_weight is not None
        and estimated_post_sale_weight + _WEIGHT_TOLERANCE < line.lower_weight
    ):
        _append(blockers, SellPreTradeBlocker.POST_SALE_BAND_UNDERSHOOT)

    integrity_confirmed = (
        calculation_checks.get("integrity_confirmed") is True
        and quality.get("calculation_integrity_confirmed") is True
        and quality.get("commission_double_count_protected") is True
        and quality.get("currency_consistent") is True
        and computed_amounts_match
        and gross_security_proceeds is not None
        and gross_proceeds is not None
        and canonical_commission is not None
        and estimated_tax is not None
        and net_proceeds is not None
        and net_proceeds.amount >= 0
    )
    if not integrity_confirmed:
        _append(blockers, SellPreTradeBlocker.ARITHMETIC_INTEGRITY_FAILED)

    data_issues = tuple(
        DataIssue(
            code=f"SELL_PRETRADE_{blocker.value.upper()}",
            severity=IssueSeverity.ERROR,
            message=f"Sell pre-trade gate is open: {blocker.value}.",
            component="sell_pretrade_preview",
        )
        for blocker in blockers
    )
    metadata = ContractMetadata(
        schema_name="sell_pretrade_preview",
        retrieved_at=evaluation_time,
        account=rebalance_plan.metadata.account,
        provenance=(
            *rebalance_plan.metadata.provenance,
            _source_reference(sale_payload, evaluation_time),
            SourceReference(
                provider="omni-cio",
                operation="build_sell_pretrade_preview",
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
                "Analytical sale preview only; no order is created or submitted.",
                "Estimated tax is caller-supplied evidence and must be refreshed before any future confirmation workflow.",
                "Broker total_order_amount is not used because sale proceeds are recomputed from security proceeds, accrued interest, commission and estimated tax.",
            ),
        ),
    )

    return SellPreTradePreviewV1(
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
        quantity_units=quantity_units,
        position_lots=position_lots,
        sell_max_lots=sell_max_lots,
        conflicting_open_sell_lots=conflicting_open_sell_lots,
        available_after_open_orders_lots=available_after_open_orders_lots,
        remaining_position_lots=remaining_position_lots,
        current_position_value=current_position_value,
        sold_position_value=sold_position_value,
        gross_security_proceeds=gross_security_proceeds,
        accrued_interest_proceeds=accrued_interest_proceeds,
        gross_proceeds=gross_proceeds,
        canonical_commission=canonical_commission,
        estimated_tax=estimated_tax,
        net_proceeds=net_proceeds,
        estimated_post_sale_position_value=estimated_post_sale_position_value,
        estimated_portfolio_value_before=estimated_portfolio_value_before,
        estimated_portfolio_value_after=estimated_portfolio_value_after,
        current_weight=line.current_weight,
        lower_weight=line.lower_weight,
        target_weight=line.target_weight,
        upper_weight=line.upper_weight,
        estimated_post_sale_weight=estimated_post_sale_weight,
        reduction_value_limit=Money(
            amount=line.value_to_target,
            currency=currency,
        ),
        tax_basis_confirmed=tax_basis_confirmed,
        open_orders_checked=open_orders_checked,
        position_availability_confirmed=position_availability_confirmed,
        source_complete=source_complete,
        integrity_confirmed=integrity_confirmed,
        blockers=tuple(blockers),
        preview_ready=not blockers,
        no_short_sale=True,
        no_cross_currency_aggregation=True,
        execution_ready=False,
        trading_methods=False,
    )
