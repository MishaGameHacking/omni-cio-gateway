from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.common import AccountReference, SourceReference
from omni_cio.contracts.v1.rebalancing import (
    RebalanceAlternativeKind,
    RebalanceAlternativeStatus,
    RebalanceAlternativeV1,
    RebalanceBandStatus,
    RebalanceBlocker,
    RebalanceDirection,
    RebalanceLineV1,
    ThresholdRebalancePlanV1,
)
from omni_cio.contracts.v1.sell_tax import (
    SellTaxEvidenceMethod,
    SellTaxEvidenceStatus,
    SellTaxEvidenceV1,
)
from omni_cio.pretrade import (
    SellTaxEvidenceError,
    build_confirmed_sell_tax_evidence,
    build_sell_pretrade_preview,
    build_unavailable_sell_tax_evidence,
    enrich_sale_capacity_with_tax_evidence,
)
from tests.test_sell_pretrade_preview_v1 import _metadata


NOW = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)
ACCOUNT = AccountReference(masked_id="***3118", account_type="ИИС")
STABLE_KEY = "uid:asset-a"
INSTRUMENT_UID = "asset-a"


def _source() -> SourceReference:
    return SourceReference(
        provider="verified-tax-source",
        operation="estimate_exact_sale_tax",
        retrieved_at=NOW - timedelta(seconds=5),
        source_id="tax-estimate-1",
    )


def _confirmed(*, estimated_tax: Decimal = Decimal("4"), zero_reason=None):
    return build_confirmed_sell_tax_evidence(
        account=ACCOUNT,
        source=_source(),
        stable_key=STABLE_KEY,
        instrument_uid=INSTRUMENT_UID,
        currency="rub",
        lot_size=1,
        quantity_lots=1,
        gross_proceeds=Decimal("100"),
        canonical_commission=Decimal("1"),
        estimated_tax=estimated_tax,
        method=SellTaxEvidenceMethod.BROKER_CONFIRMED_ESTIMATE,
        evidence_as_of=NOW - timedelta(seconds=2),
        zero_tax_reason=zero_reason,
    )


def _money(amount: str, currency: str = "RUB") -> dict[str, str]:
    return {"amount": amount, "currency": currency}


def _payload() -> dict[str, object]:
    source_time = NOW - timedelta(seconds=20)
    return {
        "status": "ok",
        "version": "3.9.1",
        "retrieved_at": NOW.isoformat(),
        "account": {"masked_id": "***3118"},
        "request": {
            "instrument_uid": INSTRUMENT_UID,
            "price_basis": "best_bid",
            "quantity_lots": 1,
            "direction": "ORDER_DIRECTION_SELL",
        },
        "instrument": {
            "uid": INSTRUMENT_UID,
            "currency": "RUB",
            "lot": 1,
        },
        "instrument_resolution": {"status": "resolved"},
        "market_price": {
            "status": "ok",
            "basis": "best_bid",
            "source": "T-Invest GetOrderBook best bid",
            "price": "98",
            "currency": "RUB",
            "lot_size": 1,
            "source_time": source_time.isoformat(),
        },
        "position_limits": {
            "status": "ok",
            "currency": "RUB",
            "position_lots": 5,
            "sell_max_lots": 5,
        },
        "open_orders": {
            "status": "ok",
            "checked": True,
            "conflicting_sell_lots": 0,
        },
        "order_preview": {
            "status": "ok",
            "lots_requested": 1,
            "initial_order_amount": _money("98"),
            "gross_proceeds": _money("100"),
            "executed_commission": _money("1"),
            "extra_bond": {"aci_value": _money("2")},
        },
        "commission_summary": {
            "status": "ok",
            "canonical_source": "executed_commission",
            "canonical_commission": _money("1"),
            "double_count_protection": True,
        },
        "tax_basis": {
            "status": "unavailable",
            "confirmed": False,
            "estimated_tax": {
                "amount": "unavailable",
                "currency": "RUB",
            },
        },
        "price_freshness": {
            "status": "fresh",
            "source_time": source_time.isoformat(),
            "age_seconds": "20",
            "fresh_threshold_seconds": "120",
        },
        "currency_consistency": {"status": "ok"},
        "calculation_checks": {
            "overall_status": "partial",
            "integrity_confirmed": False,
        },
        "quality": {
            "instrument_resolved": True,
            "position_availability_confirmed": True,
            "open_orders_checked": True,
            "tax_basis_confirmed": False,
            "commission_double_count_protected": True,
            "currency_consistent": True,
            "calculation_integrity_confirmed": False,
            "complete": True,
            "read_only": True,
            "no_order_created": True,
        },
        "complete": True,
        "component_errors": [],
        "trading_methods": False,
        "warnings": [],
    }


def _plan() -> ThresholdRebalancePlanV1:
    line = RebalanceLineV1(
        stable_key=STABLE_KEY,
        currency="RUB",
        current_value=Decimal("500"),
        current_weight=Decimal("0.5"),
        lower_weight=Decimal("0.35"),
        target_weight=Decimal("0.4"),
        upper_weight=Decimal("0.45"),
        band_status=RebalanceBandStatus.ABOVE,
        direction=RebalanceDirection.REDUCE,
        deviation_from_target=Decimal("0.1"),
        value_to_nearest_band=Decimal("50"),
        value_to_target=Decimal("100"),
        sale_required=True,
    )
    alternatives = (
        RebalanceAlternativeV1(
            alternative_id="rebalance.no_action",
            kind=RebalanceAlternativeKind.NO_ACTION,
            status=RebalanceAlternativeStatus.AVAILABLE,
            title="Keep",
            rationale="No action remains available.",
            uses_sales=False,
            available_cash=Decimal("80"),
            planned_add_value=Decimal("0"),
            planned_reduce_value=Decimal("0"),
            residual_cash=Decimal("80"),
        ),
        RebalanceAlternativeV1(
            alternative_id="rebalance.cash_first",
            kind=RebalanceAlternativeKind.CASH_FIRST,
            status=RebalanceAlternativeStatus.PREFERRED,
            title="Cash first",
            rationale="Use cash without selling.",
            uses_sales=False,
            available_cash=Decimal("80"),
            planned_add_value=Decimal("80"),
            planned_reduce_value=Decimal("0"),
            residual_cash=Decimal("0"),
        ),
        RebalanceAlternativeV1(
            alternative_id="rebalance.full_threshold",
            kind=RebalanceAlternativeKind.FULL_THRESHOLD,
            status=RebalanceAlternativeStatus.BLOCKED,
            title="Full repair",
            rationale="Requires live sale preview and tax evidence.",
            uses_sales=True,
            available_cash=Decimal("80"),
            planned_add_value=Decimal("100"),
            planned_reduce_value=Decimal("100"),
            residual_cash=Decimal("80"),
            blockers=(
                RebalanceBlocker.LIVE_PREVIEW_REQUIRED,
                RebalanceBlocker.SALES_REQUIRE_TAX_BASIS,
            ),
        ),
    )
    return ThresholdRebalancePlanV1(
        metadata=_metadata(),
        source_decision_schema_version="1.0",
        lines=(line,),
        alternatives=alternatives,
        preferred_alternative_id="rebalance.cash_first",
        decision_ready=True,
        breach_count=1,
        below_count=0,
        above_count=1,
        inside_count=0,
    )


def test_confirmed_evidence_is_exact_term_and_read_only() -> None:
    evidence = _confirmed()

    assert evidence.evidence_status == SellTaxEvidenceStatus.CONFIRMED
    assert evidence.method == SellTaxEvidenceMethod.BROKER_CONFIRMED_ESTIMATE
    assert evidence.currency == "RUB"
    assert evidence.quantity_units == 1
    assert evidence.estimated_tax is not None
    assert evidence.estimated_tax.amount == Decimal("4")
    assert evidence.confirmed is True
    assert evidence.final_tax_liability is False
    assert evidence.execution_ready is False
    assert evidence.trading_methods is False


def test_zero_tax_requires_verified_reason() -> None:
    with pytest.raises(ValidationError, match="confirmed zero tax requires"):
        _confirmed(estimated_tax=Decimal("0"))

    evidence = _confirmed(
        estimated_tax=Decimal("0"),
        zero_reason="Broker confirmed zero estimated tax for these exact terms.",
    )
    assert evidence.estimated_tax is not None
    assert evidence.estimated_tax.amount == 0


def test_unavailable_evidence_never_invents_zero() -> None:
    evidence = build_unavailable_sell_tax_evidence(
        account=ACCOUNT,
        source=_source(),
        stable_key=STABLE_KEY,
        instrument_uid=INSTRUMENT_UID,
        currency="RUB",
        lot_size=1,
        quantity_lots=1,
        gross_proceeds=Decimal("100"),
        canonical_commission=Decimal("1"),
        evidence_as_of=NOW,
        reason="Verified tax evidence is not available.",
    )

    assert evidence.evidence_status == SellTaxEvidenceStatus.UNAVAILABLE
    assert evidence.method == SellTaxEvidenceMethod.UNAVAILABLE
    assert evidence.estimated_tax is None
    assert evidence.confirmed is False


def test_enrichment_is_non_mutating_and_reconciles_net_proceeds() -> None:
    payload = _payload()
    original = deepcopy(payload)

    enriched = enrich_sale_capacity_with_tax_evidence(
        payload,
        _confirmed(),
        stable_key=STABLE_KEY,
        enriched_at=NOW,
    )

    assert payload == original
    assert enriched["trading_methods"] is False
    assert enriched["tax_basis"] == {
        "status": "ok",
        "confirmed": True,
        "source": "broker_confirmed_estimate",
        "evidence_as_of": (NOW - timedelta(seconds=2)).isoformat(),
        "estimated_tax": _money("4"),
        "zero_tax_reason": None,
        "final_tax_liability": False,
    }
    order_preview = enriched["order_preview"]
    assert isinstance(order_preview, dict)
    assert order_preview["net_proceeds"] == _money("95")
    checks = enriched["calculation_checks"]
    assert isinstance(checks, dict)
    assert checks["integrity_confirmed"] is True
    quality = enriched["quality"]
    assert isinstance(quality, dict)
    assert quality["tax_basis_confirmed"] is True
    assert quality["calculation_integrity_confirmed"] is True


def test_enriched_payload_can_build_ready_typed_preview_without_execution() -> None:
    enriched = enrich_sale_capacity_with_tax_evidence(
        _payload(),
        _confirmed(),
        stable_key=STABLE_KEY,
        enriched_at=NOW,
    )

    preview = build_sell_pretrade_preview(
        enriched,
        _plan(),
        stable_key=STABLE_KEY,
        evaluated_at=NOW,
    )

    assert preview.preview_ready is True
    assert preview.blockers == ()
    assert preview.tax_basis_confirmed is True
    assert preview.estimated_tax is not None
    assert preview.estimated_tax.amount == Decimal("4")
    assert preview.net_proceeds is not None
    assert preview.net_proceeds.amount == Decimal("95")
    assert preview.execution_ready is False
    assert preview.trading_methods is False


def test_unconfirmed_evidence_cannot_enrich_payload() -> None:
    evidence = build_unavailable_sell_tax_evidence(
        account=ACCOUNT,
        source=_source(),
        stable_key=STABLE_KEY,
        instrument_uid=INSTRUMENT_UID,
        currency="RUB",
        lot_size=1,
        quantity_lots=1,
        gross_proceeds=Decimal("100"),
        canonical_commission=Decimal("1"),
        evidence_as_of=NOW,
        reason="Unavailable.",
    )
    with pytest.raises(SellTaxEvidenceError, match="NOT_CONFIRMED"):
        enrich_sale_capacity_with_tax_evidence(
            _payload(), evidence, stable_key=STABLE_KEY, enriched_at=NOW
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (lambda payload: payload["account"].update(masked_id="***9999"), "ACCOUNT_MISMATCH"),
        (lambda payload: payload["request"].update(instrument_uid="asset-b"), "INSTRUMENT_MISMATCH"),
        (lambda payload: payload["request"].update(quantity_lots=2), "QUANTITY_MISMATCH"),
        (lambda payload: payload["market_price"].update(currency="USD"), "CURRENCY_MISMATCH"),
        (lambda payload: payload["order_preview"].update(gross_proceeds=_money("101")), "TERMS_MISMATCH"),
        (lambda payload: payload["commission_summary"].update(canonical_commission=_money("2")), "TERMS_MISMATCH"),
    ),
)
def test_mismatched_live_terms_are_rejected(mutation, message: str) -> None:
    payload = _payload()
    mutation(payload)

    with pytest.raises(SellTaxEvidenceError, match=message):
        enrich_sale_capacity_with_tax_evidence(
            payload,
            _confirmed(),
            stable_key=STABLE_KEY,
            enriched_at=NOW,
        )


def test_incomplete_or_trading_enabled_source_is_rejected() -> None:
    incomplete = _payload()
    incomplete["complete"] = False
    with pytest.raises(SellTaxEvidenceError, match="SOURCE_INCOMPLETE"):
        enrich_sale_capacity_with_tax_evidence(
            incomplete, _confirmed(), stable_key=STABLE_KEY, enriched_at=NOW
        )

    trading = _payload()
    trading["trading_methods"] = True
    with pytest.raises(SellTaxEvidenceError, match="SOURCE_TRADING_ENABLED"):
        enrich_sale_capacity_with_tax_evidence(
            trading, _confirmed(), stable_key=STABLE_KEY, enriched_at=NOW
        )


def test_future_evidence_is_rejected() -> None:
    evidence_data = _confirmed().model_dump()
    evidence_data["evidence_as_of"] = NOW + timedelta(seconds=1)
    evidence_data["metadata"] = {
        **evidence_data["metadata"],
        "retrieved_at": NOW + timedelta(seconds=1),
    }
    evidence = SellTaxEvidenceV1.model_validate(evidence_data)

    with pytest.raises(SellTaxEvidenceError, match="FROM_FUTURE"):
        enrich_sale_capacity_with_tax_evidence(
            _payload(), evidence, stable_key=STABLE_KEY, enriched_at=NOW
        )


def test_contract_rejects_quantity_and_currency_tampering() -> None:
    data = _confirmed().model_dump()
    data["quantity_units"] = 2
    with pytest.raises(ValidationError, match="quantity units"):
        SellTaxEvidenceV1.model_validate(data)

    data = _confirmed().model_dump()
    data["estimated_tax"] = _money("4", "USD")
    with pytest.raises(ValidationError, match="estimated tax currency"):
        SellTaxEvidenceV1.model_validate(data)
