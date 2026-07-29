from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from omni_cio.contracts.v1.common import (
    Completeness,
    ContractMetadata,
    DataQuality,
    Money,
    QualityMetadata,
    SourceReference,
)
from omni_cio.contracts.v1.paper import PaperOrderStatus, PaperPurchaseResultV1
from omni_cio.contracts.v1.shadow import ShadowMarketObservationV1
from omni_cio.contracts.v1.shadow_series import (
    ShadowPurchaseSeriesV1,
    ShadowSeriesPointV1,
)
from omni_cio.shadow.evaluator_v1 import evaluate_paper_purchase


_MAX_OBSERVATIONS = 256


class ShadowSeriesEvaluationError(ValueError):
    """The supplied paper result or observation series cannot be evaluated safely."""


def evaluate_paper_purchase_series(
    paper_result: PaperPurchaseResultV1,
    observations: Sequence[ShadowMarketObservationV1],
) -> ShadowPurchaseSeriesV1:
    """Build a deterministic no-lookahead ledger from ordered observations."""

    if paper_result.status == PaperOrderStatus.REJECTED:
        raise ShadowSeriesEvaluationError("REJECTED_PAPER_RESULT_NOT_EVALUABLE")
    if not observations:
        raise ShadowSeriesEvaluationError("SHADOW_SERIES_OBSERVATIONS_REQUIRED")
    if len(observations) > _MAX_OBSERVATIONS:
        raise ShadowSeriesEvaluationError("SHADOW_SERIES_OBSERVATION_LIMIT_EXCEEDED")

    evaluated_from = paper_result.metadata.retrieved_at
    previous_timestamp = evaluated_from
    for observation in observations:
        if observation.stable_key != paper_result.stable_key:
            raise ShadowSeriesEvaluationError("SHADOW_SERIES_INSTRUMENT_MISMATCH")
        if observation.currency != paper_result.currency:
            raise ShadowSeriesEvaluationError("SHADOW_SERIES_CURRENCY_MISMATCH")
        if observation.observed_at <= evaluated_from:
            raise ShadowSeriesEvaluationError(
                "SHADOW_SERIES_LOOKAHEAD_OR_NON_FORWARD_OBSERVATION"
            )
        if observation.observed_at <= previous_timestamp:
            raise ShadowSeriesEvaluationError(
                "SHADOW_SERIES_OBSERVATIONS_NOT_STRICTLY_ORDERED"
            )
        previous_timestamp = observation.observed_at

    currency = paper_result.currency
    running_peak = Decimal("0")
    points: list[ShadowSeriesPointV1] = []
    for sequence, observation in enumerate(observations, start=1):
        evaluation = evaluate_paper_purchase(paper_result, observation)
        current_value = evaluation.observed_full_market_value.amount
        running_peak = max(running_peak, current_value)
        drawdown_amount = running_peak - current_value
        drawdown_ratio = (
            drawdown_amount / running_peak if running_peak > 0 else Decimal("0")
        )
        points.append(
            ShadowSeriesPointV1(
                sequence=sequence,
                observed_at=evaluation.observed_at,
                holding_seconds=evaluation.holding_seconds,
                currency=currency,
                full_market_value=evaluation.observed_full_market_value,
                gross_value_change=evaluation.gross_value_change,
                net_value_change_after_entry_costs=(
                    evaluation.net_value_change_after_entry_costs
                ),
                return_on_total_cost=evaluation.return_on_total_cost,
                running_peak_market_value=Money(
                    amount=running_peak,
                    currency=currency,
                ),
                drawdown_amount=Money(
                    amount=drawdown_amount,
                    currency=currency,
                ),
                drawdown_ratio=drawdown_ratio,
                outcome=evaluation.outcome,
                observation_source=evaluation.observation_source,
                observation_source_id=evaluation.observation_source_id,
                no_lookahead=True,
                paper_only=True,
                trading_methods=False,
            )
        )

    point_tuple = tuple(points)
    final_point = point_tuple[-1]
    last_observation = observations[-1]
    entry_security_amount = (
        paper_result.gross_amount.amount + paper_result.accrued_interest.amount
    )
    max_drawdown_amount = max(point.drawdown_amount.amount for point in point_tuple)
    max_drawdown_ratio = max(point.drawdown_ratio for point in point_tuple)
    total_holding_seconds = Decimal(
        str((last_observation.observed_at - evaluated_from).total_seconds())
    )

    observation_provenance = tuple(
        SourceReference(
            provider=observation.source,
            operation="shadow_market_observation",
            retrieved_at=observation.observed_at,
            source_id=observation.source_id,
        )
        for observation in observations
    )
    metadata = ContractMetadata(
        schema_name="shadow_purchase_series",
        retrieved_at=last_observation.observed_at,
        account=paper_result.metadata.account,
        provenance=(
            *paper_result.metadata.provenance,
            *observation_provenance,
            SourceReference(
                provider="omni-cio",
                operation="evaluate_paper_purchase_series",
                retrieved_at=last_observation.observed_at,
                source_id="1.0",
            ),
        ),
        quality=QualityMetadata(
            quality=DataQuality.VERIFIED,
            completeness=Completeness.COMPLETE,
            warnings=(
                "Shadow series is hypothetical and is not a broker execution.",
                "No exit commission, slippage or tax is inferred.",
                "Bond observations must include accrued interest in full value.",
                "This ledger is not a strategy backtest or performance claim.",
            ),
        ),
    )

    return ShadowPurchaseSeriesV1(
        metadata=metadata,
        scenario_id=paper_result.scenario_id,
        stable_key=paper_result.stable_key,
        instrument_uid=paper_result.instrument_uid,
        currency=currency,
        paper_status=paper_result.status,
        evaluated_from=evaluated_from,
        first_observed_at=observations[0].observed_at,
        last_observed_at=last_observation.observed_at,
        total_holding_seconds=total_holding_seconds,
        observation_count=len(point_tuple),
        filled_lots=paper_result.filled_lots,
        filled_units=paper_result.filled_units,
        entry_security_value=Money(
            amount=entry_security_amount,
            currency=currency,
        ),
        entry_commission=paper_result.commission,
        entry_total_cost=paper_result.total_cost,
        points=point_tuple,
        peak_market_value=Money(
            amount=max(point.full_market_value.amount for point in point_tuple),
            currency=currency,
        ),
        max_drawdown_amount=Money(
            amount=max_drawdown_amount,
            currency=currency,
        ),
        max_drawdown_ratio=max_drawdown_ratio,
        final_market_value=final_point.full_market_value,
        final_net_value_change_after_entry_costs=(
            final_point.net_value_change_after_entry_costs
        ),
        final_return_on_total_cost=final_point.return_on_total_cost,
        final_outcome=final_point.outcome,
        no_lookahead=True,
        observations_strictly_ordered=True,
        no_cross_currency_aggregation=True,
        paper_only=True,
        broker_order_created=False,
        execution_ready=False,
        trading_methods=False,
    )
