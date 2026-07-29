from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from omni_cio.contracts.v1.common import (
    AccountReference,
    Completeness,
    ContractMetadata,
    DataIssue,
    DataQuality,
    IssueSeverity,
    Money,
    QualityMetadata,
    SourceReference,
)
from omni_cio.contracts.v1.sell_tax import (
    SellTaxEvidenceMethod,
    SellTaxEvidenceStatus,
    SellTaxEvidenceV1,
)


_MONEY_TOLERANCE = Decimal("0.01")


class SellTaxEvidenceError(ValueError):
    """Sell-tax evidence cannot be constructed or bound safely."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise SellTaxEvidenceError("SELL_TAX_TIMESTAMP_MUST_BE_AWARE")
    return result.astimezone(timezone.utc)


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
        result = int(str(value).strip())
    except (ValueError, TypeError, OverflowError):
        return None
    return result if result > 0 else None


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


def _money_view(value: Money) -> dict[str, str]:
    return {
        "amount": format(value.amount, "f"),
        "currency": value.currency,
    }


def _payload_account(payload: Mapping[str, object]) -> str:
    account = _mapping(payload.get("account"))
    for key in (
        "masked_id",
        "masked_account_id",
        "id_masked",
        "account_id_masked",
    ):
        value = _text(account.get(key))
        if value:
            return value
    return ""


def _warning_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def build_confirmed_sell_tax_evidence(
    *,
    account: AccountReference,
    source: SourceReference,
    stable_key: str,
    instrument_uid: str,
    currency: str,
    lot_size: int,
    quantity_lots: int,
    gross_proceeds: Decimal,
    canonical_commission: Decimal,
    estimated_tax: Decimal,
    method: SellTaxEvidenceMethod,
    evidence_as_of: datetime,
    source_period_start: datetime | None = None,
    source_period_end: datetime | None = None,
    position_uid: str | None = None,
    zero_tax_reason: str | None = None,
) -> SellTaxEvidenceV1:
    """Build externally verified tax evidence for exact proposed sale terms."""

    if method == SellTaxEvidenceMethod.UNAVAILABLE:
        raise SellTaxEvidenceError("CONFIRMED_SELL_TAX_METHOD_REQUIRED")
    normalized_currency = currency.upper()
    evidence_time = _aware_utc(evidence_as_of)
    metadata = ContractMetadata(
        schema_name="sell_tax_evidence",
        retrieved_at=evidence_time,
        account=account,
        provenance=(
            source,
            SourceReference(
                provider="omni-cio",
                operation="build_confirmed_sell_tax_evidence",
                retrieved_at=evidence_time,
                source_id="1.0",
            ),
        ),
        quality=QualityMetadata(
            quality=DataQuality.VERIFIED,
            completeness=Completeness.COMPLETE,
            warnings=(
                "Estimated tax is evidence for a sale preview and is not a final tax liability.",
            ),
        ),
    )
    return SellTaxEvidenceV1(
        metadata=metadata,
        stable_key=stable_key,
        instrument_uid=instrument_uid,
        position_uid=position_uid,
        currency=normalized_currency,
        lot_size=lot_size,
        quantity_lots=quantity_lots,
        quantity_units=lot_size * quantity_lots,
        gross_proceeds=Money(
            amount=gross_proceeds,
            currency=normalized_currency,
        ),
        canonical_commission=Money(
            amount=canonical_commission,
            currency=normalized_currency,
        ),
        evidence_status=SellTaxEvidenceStatus.CONFIRMED,
        method=method,
        evidence_as_of=evidence_time,
        source_period_start=source_period_start,
        source_period_end=source_period_end,
        estimated_tax=Money(
            amount=estimated_tax,
            currency=normalized_currency,
        ),
        zero_tax_reason=zero_tax_reason,
        confirmed=True,
        final_tax_liability=False,
        no_legal_tax_guarantee=True,
        execution_ready=False,
        trading_methods=False,
    )


def build_unavailable_sell_tax_evidence(
    *,
    account: AccountReference,
    source: SourceReference,
    stable_key: str,
    instrument_uid: str,
    currency: str,
    lot_size: int,
    quantity_lots: int,
    gross_proceeds: Decimal,
    canonical_commission: Decimal,
    evidence_as_of: datetime,
    reason: str,
    position_uid: str | None = None,
) -> SellTaxEvidenceV1:
    """Represent missing tax evidence without inventing a zero value."""

    evidence_time = _aware_utc(evidence_as_of)
    normalized_currency = currency.upper()
    metadata = ContractMetadata(
        schema_name="sell_tax_evidence",
        retrieved_at=evidence_time,
        account=account,
        provenance=(
            source,
            SourceReference(
                provider="omni-cio",
                operation="build_unavailable_sell_tax_evidence",
                retrieved_at=evidence_time,
                source_id="1.0",
            ),
        ),
        quality=QualityMetadata(
            quality=DataQuality.DEGRADED,
            completeness=Completeness.INCOMPLETE,
            issues=(
                DataIssue(
                    code="SELL_TAX_EVIDENCE_UNAVAILABLE",
                    severity=IssueSeverity.ERROR,
                    message=reason,
                    component="sell_tax_evidence",
                ),
            ),
            warnings=(
                "No tax value is inferred from average position price, market value or order totals.",
            ),
        ),
    )
    return SellTaxEvidenceV1(
        metadata=metadata,
        stable_key=stable_key,
        instrument_uid=instrument_uid,
        position_uid=position_uid,
        currency=normalized_currency,
        lot_size=lot_size,
        quantity_lots=quantity_lots,
        quantity_units=lot_size * quantity_lots,
        gross_proceeds=Money(
            amount=gross_proceeds,
            currency=normalized_currency,
        ),
        canonical_commission=Money(
            amount=canonical_commission,
            currency=normalized_currency,
        ),
        evidence_status=SellTaxEvidenceStatus.UNAVAILABLE,
        method=SellTaxEvidenceMethod.UNAVAILABLE,
        evidence_as_of=evidence_time,
        estimated_tax=None,
        confirmed=False,
        final_tax_liability=False,
        no_legal_tax_guarantee=True,
        execution_ready=False,
        trading_methods=False,
    )


def enrich_sale_capacity_with_tax_evidence(
    sale_payload: Mapping[str, object],
    evidence: SellTaxEvidenceV1,
    *,
    stable_key: str,
    enriched_at: datetime | None = None,
) -> dict[str, object]:
    """Attach confirmed exact-term tax evidence to a read-only sale payload."""

    evaluation_time = _aware_utc(enriched_at)
    if not evidence.confirmed or evidence.estimated_tax is None:
        raise SellTaxEvidenceError("SELL_TAX_EVIDENCE_NOT_CONFIRMED")
    if evidence.evidence_as_of > evaluation_time:
        raise SellTaxEvidenceError("SELL_TAX_EVIDENCE_FROM_FUTURE")
    if evidence.stable_key != stable_key:
        raise SellTaxEvidenceError("SELL_TAX_STABLE_KEY_MISMATCH")
    if sale_payload.get("trading_methods") is not False:
        raise SellTaxEvidenceError("SELL_TAX_SOURCE_TRADING_ENABLED")

    payload: dict[str, object] = deepcopy(dict(sale_payload))
    quality = dict(_mapping(payload.get("quality")))
    if not (
        payload.get("status") == "ok"
        and payload.get("complete") is True
        and quality.get("complete") is True
        and quality.get("read_only") is True
        and quality.get("no_order_created") is True
        and quality.get("commission_double_count_protected") is True
        and quality.get("currency_consistent") is True
    ):
        raise SellTaxEvidenceError("SELL_TAX_SOURCE_INCOMPLETE")

    if _payload_account(payload) != evidence.metadata.account.masked_id:
        raise SellTaxEvidenceError("SELL_TAX_ACCOUNT_MISMATCH")

    request = _mapping(payload.get("request"))
    instrument = _mapping(payload.get("instrument"))
    market_price = _mapping(payload.get("market_price"))
    order_preview = dict(_mapping(payload.get("order_preview")))
    commission_summary = _mapping(payload.get("commission_summary"))

    source_uid = _text(request.get("instrument_uid") or instrument.get("uid"))
    if source_uid != evidence.instrument_uid:
        raise SellTaxEvidenceError("SELL_TAX_INSTRUMENT_MISMATCH")
    source_lots = _positive_int(request.get("quantity_lots"))
    lot_size = _positive_int(market_price.get("lot_size") or instrument.get("lot"))
    if source_lots != evidence.quantity_lots or lot_size != evidence.lot_size:
        raise SellTaxEvidenceError("SELL_TAX_QUANTITY_MISMATCH")
    if lot_size is None or source_lots is None:
        raise SellTaxEvidenceError("SELL_TAX_QUANTITY_UNAVAILABLE")
    if lot_size * source_lots != evidence.quantity_units:
        raise SellTaxEvidenceError("SELL_TAX_UNITS_MISMATCH")

    source_currency = _currency(
        market_price.get("currency") or instrument.get("currency")
    )
    if source_currency != evidence.currency:
        raise SellTaxEvidenceError("SELL_TAX_CURRENCY_MISMATCH")

    source_gross = _money(order_preview.get("gross_proceeds"))
    source_commission = _money(
        _mapping(commission_summary.get("canonical_commission"))
    )
    if source_gross is None or source_commission is None:
        raise SellTaxEvidenceError("SELL_TAX_TERMS_UNAVAILABLE")
    if (
        source_gross.currency != evidence.currency
        or source_commission.currency != evidence.currency
        or abs(source_gross.amount - evidence.gross_proceeds.amount)
        > _MONEY_TOLERANCE
        or abs(source_commission.amount - evidence.canonical_commission.amount)
        > _MONEY_TOLERANCE
    ):
        raise SellTaxEvidenceError("SELL_TAX_TERMS_MISMATCH")

    net_amount = (
        source_gross.amount
        - source_commission.amount
        - evidence.estimated_tax.amount
    )
    if net_amount < 0:
        raise SellTaxEvidenceError("SELL_TAX_NET_PROCEEDS_NEGATIVE")
    net_proceeds = Money(amount=net_amount, currency=evidence.currency)

    order_preview["net_proceeds"] = _money_view(net_proceeds)
    payload["order_preview"] = order_preview
    payload["tax_basis"] = {
        "status": "ok",
        "confirmed": True,
        "source": evidence.method.value,
        "evidence_as_of": evidence.evidence_as_of.isoformat(),
        "estimated_tax": _money_view(evidence.estimated_tax),
        "zero_tax_reason": evidence.zero_tax_reason,
        "final_tax_liability": False,
    }
    payload["calculation_checks"] = {
        "overall_status": "passed",
        "gross_proceeds_confirmed": True,
        "commission_confirmed": True,
        "tax_basis_confirmed": True,
        "net_proceeds_confirmed": True,
        "integrity_confirmed": True,
        "reason": "Exact-term verified tax evidence was bound to the live sale payload.",
        "tax_evidence_method": evidence.method.value,
    }
    quality["tax_basis_confirmed"] = True
    quality["calculation_integrity_confirmed"] = True
    payload["quality"] = quality
    warnings = _warning_list(payload.get("warnings"))
    warnings.append(
        "Estimated tax is not a final tax liability and must be refreshed before any future confirmation workflow."
    )
    payload["warnings"] = warnings
    payload["tax_evidence"] = {
        "schema_name": evidence.metadata.schema_name,
        "schema_version": evidence.metadata.schema_version,
        "method": evidence.method.value,
        "evidence_as_of": evidence.evidence_as_of.isoformat(),
        "confirmed": True,
        "final_tax_liability": False,
        "trading_methods": False,
    }
    payload["trading_methods"] = False
    return payload
