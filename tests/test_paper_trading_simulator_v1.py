from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

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
from omni_cio.contracts.v1.paper import (
    PaperJournalEventKind,
    PaperOrderStatus,
    PaperRejectReason,
)
from omni_cio.contracts.v1.pretrade import (
    PreTradeBlocker,
    PreTradePreviewV1,
    PreviewFreshnessStatus,
    PreviewPriceBasis,
)
from omni_cio.paper import PaperSimulatorError, simulate_paper_purchase


NOW = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)
ACCOUNT = AccountReference(masked_id="***3118", account_type="ИИС")
KEY = "uid:asset-b"


def _metadata(*, blocked: bool = False) -> ContractMetadata:
    return ContractMetadata(
        schema_name="pretrade_preview",
        retrieved_at=NOW,
        account=ACCOUNT,
        provenance=(
            SourceReference(
                provider="omni-cio-test",
                operation="build_pretrade_preview",
                retrieved_at=NOW,
                source_id="1.0",
            ),
        ),
        quality=QualityMetadata(
            quality=DataQuality.DEGRADED if blocked else DataQuality.VERIFIED,
            completeness=(
                Completeness.INCOMPLETE if blocked else Completeness.COMPLETE
            ),
            issues=(
                DataIssue(
                    code="PRETRADE_PRICE_STALE",
                    severity=IssueSeverity.ERROR,
                    message="Price is stale.",
                    component="pretrade_preview",
                ),
            )
            if blocked
            else (),
        ),
    )


def _preview(
    *,
    blocked: bool = False,
    accrued_interest: Decimal = Decimal("0"),
) -> PreTradePreviewV1:
    initial = Decimal("300")
    commission = Decimal("3")
    total = initial + commission + accrued_interest
    own_funds = Decimal("500")
    blockers = (PreTradeBlocker.PRICE_STALE,) if blocked else ()
    price_age = Decimal("121") if blocked else Decimal("0")
    price_time = NOW - timedelta(seconds=int(price_age))
    return PreTradePreviewV1(
        metadata=_metadata(blocked=blocked),
        stable_key=KEY,
        instrument_uid="asset-b",
        currency="RUB",
        price_basis=PreviewPriceBasis.BEST_ASK,
        price_source="T-Invest GetOrderBook best ask",
        price_time=price_time,
        evaluated_at=NOW,
        price_age_seconds=price_age,
        max_price_age_seconds=Decimal("120"),
        freshness_status=(
            PreviewFreshnessStatus.STALE
            if blocked
            else PreviewFreshnessStatus.FRESH
        ),
        unit_price=Decimal("100"),
        lot_size=2,
        quantity_lots=3,
        initial_order_amount=Money(amount=initial, currency="RUB"),
        canonical_commission=Money(amount=commission, currency="RUB"),
        accrued_interest=Money(amount=accrued_interest, currency="RUB"),
        total_order_amount=Money(amount=total, currency="RUB"),
        own_funds=Money(amount=own_funds, currency="RUB"),
        remaining_cash=Money(amount=own_funds - total, currency="RUB"),
        target_value_limit=Money(amount=Decimal("400"), currency="RUB"),
        affordable=True,
        source_complete=not blocked,
        integrity_confirmed=not blocked,
        blockers=blockers,
        preview_ready=not blocked,
    )


def test_full_paper_fill_reconciles_cash_position_and_journal() -> None:
    result = simulate_paper_purchase(
        _preview(),
        scenario_id="paper.full-001",
        fill_lots=3,
        paper_cash=Decimal("500"),
        position_lots=4,
        simulated_at=NOW,
    )

    assert result.status == PaperOrderStatus.FILLED
    assert result.filled_lots == 3
    assert result.unfilled_lots == 0
    assert result.filled_units == 6
    assert result.gross_amount.amount == Decimal("300")
    assert result.commission.amount == Decimal("3")
    assert result.total_cost.amount == Decimal("303")
    assert result.paper_cash_after.amount == Decimal("197")
    assert result.position_lots_after == 7
    assert tuple(event.kind for event in result.journal) == (
        PaperJournalEventKind.ACCEPTED,
        PaperJournalEventKind.FILL,
    )
    assert result.paper_only is True
    assert result.broker_order_created is False
    assert result.trading_methods is False


def test_partial_fill_prorates_amounts_and_commission() -> None:
    result = simulate_paper_purchase(
        _preview(),
        scenario_id="paper.partial-001",
        fill_lots=1,
        paper_cash=Decimal("500"),
        simulated_at=NOW,
    )

    assert result.status == PaperOrderStatus.PARTIALLY_FILLED
    assert result.filled_lots == 1
    assert result.unfilled_lots == 2
    assert result.gross_amount.amount == Decimal("100.000000000")
    assert result.commission.amount == Decimal("1.000000000")
    assert result.total_cost.amount == Decimal("101.000000000")
    assert result.paper_cash_after.amount == Decimal("399.000000000")


def test_partial_fill_prorates_bond_accrued_interest() -> None:
    result = simulate_paper_purchase(
        _preview(accrued_interest=Decimal("6")),
        scenario_id="paper.bond-aci-001",
        fill_lots=1,
        paper_cash=Decimal("500"),
        simulated_at=NOW,
    )

    assert result.accrued_interest.amount == Decimal("2.000000000")
    assert result.total_cost.amount == Decimal("103.000000000")
    assert result.paper_cash_after.amount == Decimal("397.000000000")


def test_insufficient_paper_cash_rejects_without_state_change() -> None:
    result = simulate_paper_purchase(
        _preview(),
        scenario_id="paper.reject-cash-001",
        fill_lots=3,
        paper_cash=Decimal("302"),
        position_lots=5,
        simulated_at=NOW,
    )

    assert result.status == PaperOrderStatus.REJECTED
    assert result.reject_reasons == (
        PaperRejectReason.INSUFFICIENT_PAPER_CASH,
    )
    assert result.filled_lots == 0
    assert result.total_cost.amount == 0
    assert result.paper_cash_after.amount == Decimal("302")
    assert result.position_lots_after == 5
    assert tuple(event.kind for event in result.journal) == (
        PaperJournalEventKind.REJECTED,
    )


def test_blocked_preview_is_rejected_without_broker_activity() -> None:
    result = simulate_paper_purchase(
        _preview(blocked=True),
        scenario_id="paper.reject-preview-001",
        fill_lots=1,
        paper_cash=Decimal("500"),
        simulated_at=NOW,
    )

    assert result.status == PaperOrderStatus.REJECTED
    assert PaperRejectReason.PREVIEW_NOT_READY in result.reject_reasons
    assert result.metadata.quality.quality == DataQuality.DEGRADED
    assert result.broker_order_created is False


def test_invalid_and_excess_fill_lots_are_distinct_rejections() -> None:
    invalid = simulate_paper_purchase(
        _preview(),
        scenario_id="paper.reject-invalid-001",
        fill_lots=0,
        paper_cash=Decimal("500"),
        simulated_at=NOW,
    )
    assert invalid.reject_reasons == (PaperRejectReason.INVALID_FILL_LOTS,)

    excess = simulate_paper_purchase(
        _preview(),
        scenario_id="paper.reject-excess-001",
        fill_lots=4,
        paper_cash=Decimal("500"),
        simulated_at=NOW,
    )
    assert excess.reject_reasons == (PaperRejectReason.FILL_EXCEEDS_REQUESTED,)


def test_negative_cash_and_position_are_invalid_inputs() -> None:
    with pytest.raises(PaperSimulatorError, match="INVALID_PAPER_CASH"):
        simulate_paper_purchase(
            _preview(),
            scenario_id="paper.invalid-cash-001",
            fill_lots=1,
            paper_cash=Decimal("-1"),
            simulated_at=NOW,
        )

    with pytest.raises(PaperSimulatorError, match="INVALID_PAPER_POSITION_LOTS"):
        simulate_paper_purchase(
            _preview(),
            scenario_id="paper.invalid-position-001",
            fill_lots=1,
            paper_cash=Decimal("500"),
            position_lots=-1,
            simulated_at=NOW,
        )


def test_simulation_is_deterministic_for_same_inputs() -> None:
    first = simulate_paper_purchase(
        _preview(),
        scenario_id="paper.deterministic-001",
        fill_lots=2,
        paper_cash=Decimal("500"),
        position_lots=1,
        simulated_at=NOW,
    )
    second = simulate_paper_purchase(
        _preview(),
        scenario_id="paper.deterministic-001",
        fill_lots=2,
        paper_cash=Decimal("500"),
        position_lots=1,
        simulated_at=NOW,
    )

    assert first == second


def test_preview_is_not_mutated() -> None:
    preview = _preview()
    original = deepcopy(preview)
    simulate_paper_purchase(
        preview,
        scenario_id="paper.immutable-001",
        fill_lots=1,
        paper_cash=Decimal("500"),
        simulated_at=NOW,
    )
    assert preview == original


def test_paper_result_has_no_real_execution_identifiers() -> None:
    result = simulate_paper_purchase(
        _preview(),
        scenario_id="paper.no-execution-001",
        fill_lots=1,
        paper_cash=Decimal("500"),
        simulated_at=NOW,
    )
    payload = result.model_dump(mode="json")
    forbidden = {
        "order_id",
        "confirmation_id",
        "idempotency_key",
        "broker_method",
        "post_order",
        "cancel_order",
        "replace_order",
    }

    def keys(value: object) -> set[str]:
        if isinstance(value, dict):
            return set(value) | set().union(*(keys(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(item) for item in value))
        return set()

    assert keys(payload).isdisjoint(forbidden)
    assert payload["execution_ready"] is False
    assert payload["broker_order_created"] is False


def test_simulator_module_has_no_network_or_broker_imports() -> None:
    from pathlib import Path

    source = Path("omni_cio/paper/simulator_v1.py").read_text(encoding="utf-8")
    forbidden = (
        "import grpc",
        "import requests",
        "import httpx",
        "from t_tech",
        "from tinkoff",
        "post_order",
    )
    assert all(value not in source for value in forbidden)
