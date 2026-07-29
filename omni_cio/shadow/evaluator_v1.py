from __future__ import annotations

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
from omni_cio.contracts.v1.shadow import (
    ShadowMarketObservationV1,
    ShadowOutcome,
    ShadowPurchaseEvaluationV1,
)


class ShadowEvaluationError(ValueError):
    """The supplied paper result or observation cannot be evaluated safely."""


def evaluate_paper_purchase(
    paper_result: PaperPurchaseResultV1,
    observation: ShadowMarketObservationV1,
) -> ShadowPurchaseEvaluationV1:
    """Measure a filled paper purchase using only a later market observation."""

    if paper_result.status == PaperOrderStatus.REJECTED:
        raise ShadowEvaluationError("REJECTED_PAPER_RESULT_NOT_EVALUABLE")
    if observation.stable_key != paper_result.stable_key:
        raise ShadowEvaluationError("SHADOW_INSTRUMENT_MISMATCH")
    if observation.currency != paper_result.currency:
        raise ShadowEvaluationError("SHADOW_CURRENCY_MISMATCH")

    evaluated_from = paper_result.metadata.retrieved_at
    if observation.observed_at <= evaluated_from:
        raise ShadowEvaluationError("SHADOW_LOOKAHEAD_OR_NON_FORWARD_OBSERVATION")

    currency = paper_result.currency
    entry_security_amount = (
        paper_result.gross_amount.amount
        + paper_result.accrued_interest.amount
    )
    gross_change_amount = (
        observation.full_market_value.amount - entry_security_amount
    )
    net_change_amount = (
        observation.full_market_value.amount - paper_result.total_cost.amount
    )
    return_ratio = (
        net_change_amount / paper_result.total_cost.amount
        if paper_result.total_cost.amount > 0
        else Decimal("0")
    )
    outcome = (
        ShadowOutcome.PROFIT
        if net_change_amount > 0
        else ShadowOutcome.LOSS
        if net_change_amount < 0
        else ShadowOutcome.FLAT
    )
    holding_seconds = Decimal(
        str((observation.observed_at - evaluated_from).total_seconds())
    )

    metadata = ContractMetadata(
        schema_name="shadow_purchase_evaluation",
        retrieved_at=observation.observed_at,
        account=paper_result.metadata.account,
        provenance=(
            *paper_result.metadata.provenance,
            SourceReference(
                provider=observation.source,
                operation="shadow_market_observation",
                retrieved_at=observation.observed_at,
                source_id=observation.source_id,
            ),
            SourceReference(
                provider="omni-cio",
                operation="evaluate_paper_purchase",
                retrieved_at=observation.observed_at,
                source_id="1.0",
            ),
        ),
        quality=QualityMetadata(
            quality=DataQuality.VERIFIED,
            completeness=Completeness.COMPLETE,
            warnings=(
                "Shadow result is hypothetical and does not represent a broker execution.",
                "Observed full market value must include accrued interest for bonds.",
            ),
        ),
    )

    return ShadowPurchaseEvaluationV1(
        metadata=metadata,
        scenario_id=paper_result.scenario_id,
        stable_key=paper_result.stable_key,
        instrument_uid=paper_result.instrument_uid,
        currency=currency,
        paper_status=paper_result.status,
        evaluated_from=evaluated_from,
        observed_at=observation.observed_at,
        holding_seconds=holding_seconds,
        filled_lots=paper_result.filled_lots,
        filled_units=paper_result.filled_units,
        entry_gross_amount=paper_result.gross_amount,
        entry_accrued_interest=paper_result.accrued_interest,
        entry_security_value=Money(
            amount=entry_security_amount,
            currency=currency,
        ),
        entry_commission=paper_result.commission,
        entry_total_cost=paper_result.total_cost,
        observed_full_market_value=observation.full_market_value,
        gross_value_change=Money(
            amount=gross_change_amount,
            currency=currency,
        ),
        net_value_change_after_entry_costs=Money(
            amount=net_change_amount,
            currency=currency,
        ),
        return_on_total_cost=return_ratio,
        outcome=outcome,
        observation_source=observation.source,
        observation_source_id=observation.source_id,
        no_lookahead=True,
        no_cross_currency_aggregation=True,
        paper_only=True,
        broker_order_created=False,
        execution_ready=False,
        trading_methods=False,
    )
