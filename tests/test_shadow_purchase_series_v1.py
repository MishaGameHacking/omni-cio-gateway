from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

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
from omni_cio.contracts.v1.shadow import ShadowMarketObservationV1, ShadowOutcome
from omni_cio.contracts.v1.shadow_series import ShadowPurchaseSeriesV1
from omni_cio.shadow import (
    ShadowSeriesEvaluationError,
    evaluate_paper_purchase_series,
)


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
            scenario_id="paper.rejected-series",
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
        scenario_id="paper.partial-series" if partial else "paper.full-series",
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
    day: int,
    *,
    currency: str = "RUB",
    stable_key: str = KEY,
    observed_at: datetime | None = None,
) -> ShadowMarketObservationV1:
    timestamp = observed_at or NOW + timedelta(days=day)
    return ShadowMarketObservationV1(
        stable_key=stable_key,
        currency=currency,
        observed_at=timestamp,
        full_market_value=Money(amount=Decimal(amount), currency=currency),
        source="MOEX ISS series fixture",
        source_id=f"observation-{day}",
    )


def test_rising_series_reconciles_peak_final_return_and_holding_period() -> None:
    result = evaluate_paper_purchase_series(
        _paper_result(),
        (_observation("300", 1), _observation("330", 2), _observation("360", 3)),
    )

    assert result.observation_count == 3
    assert [point.sequence for point in result.points] == [1, 2, 3]
    assert result.total_holding_seconds == Decimal("259200.0")
    assert result.peak_market_value.amount == Decimal("360")
    assert result.max_drawdown_amount.amount == Decimal("0")
    assert result.max_drawdown_ratio == Decimal("0")
    assert result.final_net_value_change_after_entry_costs.amount == Decimal("57")
    assert result.final_return_on_total_cost == Decimal("57") / Decimal("303")
    assert result.final_outcome == ShadowOutcome.PROFIT
    assert result.no_lookahead is True
    assert result.observations_strictly_ordered is True
    assert result.trading_methods is False


def test_peak_then_drop_produces_exact_running_and_max_drawdown() -> None:
    result = evaluate_paper_purchase_series(
        _paper_result(),
        (_observation("300", 1), _observation("360", 2), _observation("270", 3)),
    )

    assert [point.running_peak_market_value.amount for point in result.points] == [
        Decimal("300"),
        Decimal("360"),
        Decimal("360"),
    ]
    assert result.points[-1].drawdown_amount.amount == Decimal("90")
    assert result.points[-1].drawdown_ratio == Decimal("0.25")
    assert result.max_drawdown_amount.amount == Decimal("90")
    assert result.max_drawdown_ratio == Decimal("0.25")
    assert result.final_outcome == ShadowOutcome.LOSS


def test_commission_can_make_net_result_negative_while_gross_change_is_positive() -> None:
    result = evaluate_paper_purchase_series(
        _paper_result(),
        (_observation("301", 1),),
    )

    point = result.points[0]
    assert point.gross_value_change.amount == Decimal("1")
    assert point.net_value_change_after_entry_costs.amount == Decimal("-2")
    assert point.outcome == ShadowOutcome.LOSS


def test_partial_fill_uses_actual_cost_units_and_lots() -> None:
    result = evaluate_paper_purchase_series(
        _paper_result(status=PaperOrderStatus.PARTIALLY_FILLED),
        (_observation("110", 1), _observation("95", 2)),
    )

    assert result.paper_status == PaperOrderStatus.PARTIALLY_FILLED
    assert result.filled_lots == 1
    assert result.filled_units == 2
    assert result.entry_total_cost.amount == Decimal("101")
    assert result.final_net_value_change_after_entry_costs.amount == Decimal("-6")


def test_empty_rejected_and_oversized_series_fail_closed() -> None:
    with pytest.raises(
        ShadowSeriesEvaluationError,
        match="SHADOW_SERIES_OBSERVATIONS_REQUIRED",
    ):
        evaluate_paper_purchase_series(_paper_result(), ())

    with pytest.raises(
        ShadowSeriesEvaluationError,
        match="REJECTED_PAPER_RESULT_NOT_EVALUABLE",
    ):
        evaluate_paper_purchase_series(
            _paper_result(status=PaperOrderStatus.REJECTED),
            (_observation("0", 1),),
        )

    observations = tuple(_observation("300", day) for day in range(1, 258))
    with pytest.raises(
        ShadowSeriesEvaluationError,
        match="SHADOW_SERIES_OBSERVATION_LIMIT_EXCEEDED",
    ):
        evaluate_paper_purchase_series(_paper_result(), observations)


def test_equal_unsorted_or_pre_entry_timestamps_fail_closed() -> None:
    duplicate_time = NOW + timedelta(days=1)
    with pytest.raises(
        ShadowSeriesEvaluationError,
        match="SHADOW_SERIES_OBSERVATIONS_NOT_STRICTLY_ORDERED",
    ):
        evaluate_paper_purchase_series(
            _paper_result(),
            (
                _observation("300", 1, observed_at=duplicate_time),
                _observation("310", 2, observed_at=duplicate_time),
            ),
        )

    with pytest.raises(
        ShadowSeriesEvaluationError,
        match="SHADOW_SERIES_OBSERVATIONS_NOT_STRICTLY_ORDERED",
    ):
        evaluate_paper_purchase_series(
            _paper_result(),
            (_observation("310", 2), _observation("300", 1)),
        )

    with pytest.raises(
        ShadowSeriesEvaluationError,
        match="SHADOW_SERIES_LOOKAHEAD_OR_NON_FORWARD_OBSERVATION",
    ):
        evaluate_paper_purchase_series(
            _paper_result(),
            (_observation("300", 1, observed_at=NOW),),
        )


def test_identity_and_currency_mismatches_fail_closed() -> None:
    with pytest.raises(
        ShadowSeriesEvaluationError,
        match="SHADOW_SERIES_INSTRUMENT_MISMATCH",
    ):
        evaluate_paper_purchase_series(
            _paper_result(),
            (_observation("300", 1, stable_key="uid:other"),),
        )

    with pytest.raises(
        ShadowSeriesEvaluationError,
        match="SHADOW_SERIES_CURRENCY_MISMATCH",
    ):
        evaluate_paper_purchase_series(
            _paper_result(),
            (_observation("300", 1, currency="USD"),),
        )


def test_series_is_deterministic_and_does_not_mutate_inputs() -> None:
    paper = _paper_result()
    observations = (_observation("300", 1), _observation("330", 2))
    paper_before = deepcopy(paper)
    observations_before = deepcopy(observations)

    first = evaluate_paper_purchase_series(paper, observations)
    second = evaluate_paper_purchase_series(paper, observations)

    assert first == second
    assert paper == paper_before
    assert observations == observations_before


def test_contract_rejects_tampered_drawdown_summary() -> None:
    result = evaluate_paper_purchase_series(
        _paper_result(),
        (_observation("360", 1), _observation("270", 2)),
    )
    payload = result.model_dump(mode="python")
    payload["max_drawdown_amount"] = Money(
        amount=Decimal("1"),
        currency="RUB",
    )

    with pytest.raises(ValidationError, match="maximum drawdown amount"):
        ShadowPurchaseSeriesV1.model_validate(payload)


def test_series_contains_no_execution_identifiers_or_broker_imports() -> None:
    result = evaluate_paper_purchase_series(
        _paper_result(),
        (_observation("330", 1),),
    )
    payload = result.model_dump(mode="json")
    serialized = str(payload).lower()
    forbidden_fields = (
        "order_id",
        "confirmation_id",
        "idempotency_key",
        "post_order",
        "cancel_order",
        "replace_order",
    )
    assert all(marker not in serialized for marker in forbidden_fields)
    assert payload["broker_order_created"] is False
    assert payload["execution_ready"] is False
    assert payload["trading_methods"] is False

    source = Path("omni_cio/shadow/series_v1.py").read_text(encoding="utf-8")
    forbidden_imports = (
        "import grpc",
        "import requests",
        "import httpx",
        "from t_tech",
        "from tinkoff",
        "http.client",
        "urllib.request",
    )
    assert all(marker not in source for marker in forbidden_imports)
