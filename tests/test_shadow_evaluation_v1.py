from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from omni_cio.contracts.v1.common import (
    AccountReference,
    Completeness,
    ContractMetadata,
    DataQuality,
    Money,
    QualityMetadata,
    SourceReference,
)
from omni_cio.contracts.v1.paper import (
    PaperJournalEventKind,
    PaperJournalEventV1,
    PaperOrderStatus,
    PaperPurchaseResultV1,
    PaperRejectReason,
)
from omni_cio.contracts.v1.shadow import (
    ShadowMarketObservationV1,
    ShadowOutcome,
)
from omni_cio.shadow import ShadowEvaluationError, evaluate_paper_purchase


NOW = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)
ACCOUNT = AccountReference(masked_id="***3118", account_type="ИИС")
KEY = "uid:asset-b"


def _metadata() -> ContractMetadata:
    return ContractMetadata(
        schema_name="paper_purchase_result",
        retrieved_at=NOW,
        account=ACCOUNT,
        provenance=(
            SourceReference(
                provider="omni-cio-test",
                operation="simulate_paper_purchase",
                retrieved_at=NOW,
                source_id="1.0",
            ),
        ),
        quality=QualityMetadata(
            quality=DataQuality.VERIFIED,
            completeness=Completeness.COMPLETE,
        ),
    )


def _paper_result(
    *,
    status: PaperOrderStatus = PaperOrderStatus.FILLED,
) -> PaperPurchaseResultV1:
    if status == PaperOrderStatus.REJECTED:
        return PaperPurchaseResultV1(
            metadata=_metadata(),
            scenario_id="paper.rejected-001",
            source_preview_schema_version="1.0",
            stable_key=KEY,
            instrument_uid="asset-b",
            currency="RUB",
            status=status,
            reject_reasons=(PaperRejectReason.INSUFFICIENT_PAPER_CASH,),
            requested_lots=3,
            filled_lots=0,
            unfilled_lots=3,
            lot_size=2,
            filled_units=0,
            gross_amount=Money(amount=Decimal("0"), currency="RUB"),
            commission=Money(amount=Decimal("0"), currency="RUB"),
            accrued_interest=Money(amount=Decimal("0"), currency="RUB"),
            total_cost=Money(amount=Decimal("0"), currency="RUB"),
            paper_cash_before=Money(amount=Decimal("500"), currency="RUB"),
            paper_cash_after=Money(amount=Decimal("500"), currency="RUB"),
            position_lots_before=0,
            position_lots_after=0,
            journal=(
                PaperJournalEventV1(
                    sequence=1,
                    occurred_at=NOW,
                    kind=PaperJournalEventKind.REJECTED,
                    message="Paper scenario rejected.",
                ),
            ),
        )

    partial = status == PaperOrderStatus.PARTIALLY_FILLED
    filled_lots = 1 if partial else 3
    gross = Decimal("100") if partial else Decimal("300")
    commission = Decimal("1") if partial else Decimal("3")
    return PaperPurchaseResultV1(
        metadata=_metadata(),
        scenario_id="paper.partial-001" if partial else "paper.full-001",
        source_preview_schema_version="1.0",
        stable_key=KEY,
        instrument_uid="asset-b",
        currency="RUB",
        status=status,
        requested_lots=3,
        filled_lots=filled_lots,
        unfilled_lots=3 - filled_lots,
        lot_size=2,
        filled_units=filled_lots * 2,
        gross_amount=Money(amount=gross, currency="RUB"),
        commission=Money(amount=commission, currency="RUB"),
        accrued_interest=Money(amount=Decimal("0"), currency="RUB"),
        total_cost=Money(amount=gross + commission, currency="RUB"),
        paper_cash_before=Money(amount=Decimal("500"), currency="RUB"),
        paper_cash_after=Money(
            amount=Decimal("500") - gross - commission,
            currency="RUB",
        ),
        position_lots_before=0,
        position_lots_after=filled_lots,
        journal=(
            PaperJournalEventV1(
                sequence=1,
                occurred_at=NOW,
                kind=PaperJournalEventKind.ACCEPTED,
                message="Paper scenario accepted.",
            ),
            PaperJournalEventV1(
                sequence=2,
                occurred_at=NOW,
                kind=PaperJournalEventKind.FILL,
                message="Paper fill recorded.",
            ),
        ),
    )


def _observation(
    amount: str,
    *,
    observed_at: datetime | None = None,
    currency: str = "RUB",
    stable_key: str = KEY,
) -> ShadowMarketObservationV1:
    return ShadowMarketObservationV1(
        stable_key=stable_key,
        currency=currency,
        observed_at=observed_at or NOW + timedelta(days=1),
        full_market_value=Money(amount=Decimal(amount), currency=currency),
        source="MOEX ISS test fixture",
        source_id="observation-001",
    )


def test_profit_evaluation_separates_gross_change_and_commission_drag() -> None:
    result = evaluate_paper_purchase(
        _paper_result(),
        _observation("330"),
    )

    assert result.outcome == ShadowOutcome.PROFIT
    assert result.holding_seconds == Decimal("86400.0")
    assert result.entry_security_value.amount == Decimal("300")
    assert result.entry_total_cost.amount == Decimal("303")
    assert result.gross_value_change.amount == Decimal("30")
    assert result.net_value_change_after_entry_costs.amount == Decimal("27")
    assert result.return_on_total_cost == Decimal("27") / Decimal("303")
    assert result.no_lookahead is True
    assert result.no_cross_currency_aggregation is True
    assert result.paper_only is True
    assert result.broker_order_created is False


def test_loss_and_flat_outcomes_are_exact() -> None:
    loss = evaluate_paper_purchase(_paper_result(), _observation("290"))
    assert loss.outcome == ShadowOutcome.LOSS
    assert loss.net_value_change_after_entry_costs.amount == Decimal("-13")

    flat = evaluate_paper_purchase(_paper_result(), _observation("303"))
    assert flat.outcome == ShadowOutcome.FLAT
    assert flat.net_value_change_after_entry_costs.amount == Decimal("0")
    assert flat.gross_value_change.amount == Decimal("3")


def test_partial_fill_uses_actual_paper_cost_and_units() -> None:
    result = evaluate_paper_purchase(
        _paper_result(status=PaperOrderStatus.PARTIALLY_FILLED),
        _observation("110"),
    )

    assert result.paper_status == PaperOrderStatus.PARTIALLY_FILLED
    assert result.filled_lots == 1
    assert result.filled_units == 2
    assert result.entry_total_cost.amount == Decimal("101")
    assert result.net_value_change_after_entry_costs.amount == Decimal("9")


def test_rejected_paper_result_is_not_evaluable() -> None:
    with pytest.raises(
        ShadowEvaluationError,
        match="REJECTED_PAPER_RESULT_NOT_EVALUABLE",
    ):
        evaluate_paper_purchase(
            _paper_result(status=PaperOrderStatus.REJECTED),
            _observation("0"),
        )


def test_equal_or_earlier_observation_is_blocked_as_lookahead() -> None:
    for observed_at in (NOW, NOW - timedelta(seconds=1)):
        with pytest.raises(
            ShadowEvaluationError,
            match="SHADOW_LOOKAHEAD_OR_NON_FORWARD_OBSERVATION",
        ):
            evaluate_paper_purchase(
                _paper_result(),
                _observation("300", observed_at=observed_at),
            )


def test_currency_and_instrument_mismatch_are_fail_closed() -> None:
    with pytest.raises(ShadowEvaluationError, match="SHADOW_CURRENCY_MISMATCH"):
        evaluate_paper_purchase(
            _paper_result(),
            _observation("330", currency="USD"),
        )

    with pytest.raises(ShadowEvaluationError, match="SHADOW_INSTRUMENT_MISMATCH"):
        evaluate_paper_purchase(
            _paper_result(),
            _observation("330", stable_key="uid:other-asset"),
        )


def test_shadow_evaluation_is_deterministic() -> None:
    paper = _paper_result()
    observation = _observation("330")
    assert evaluate_paper_purchase(paper, observation) == evaluate_paper_purchase(
        paper,
        observation,
    )


def test_shadow_result_contains_no_execution_identifiers() -> None:
    payload = evaluate_paper_purchase(
        _paper_result(),
        _observation("330"),
    ).model_dump(mode="json")
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
    assert payload["trading_methods"] is False


def test_shadow_module_has_no_network_or_broker_imports() -> None:
    from pathlib import Path

    source = Path("omni_cio/shadow/evaluator_v1.py").read_text(encoding="utf-8")
    forbidden = (
        "import grpc",
        "import requests",
        "import httpx",
        "from t_tech",
        "from tinkoff",
        "post_order",
    )
    assert all(value not in source for value in forbidden)
