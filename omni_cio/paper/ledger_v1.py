from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from decimal import Decimal

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
from omni_cio.contracts.v1.paper import PaperOrderStatus, PaperPurchaseResultV1
from omni_cio.contracts.v1.paper_ledger import (
    PaperAccountLedgerV1,
    PaperLedgerEventV1,
    PaperLedgerPositionV1,
    PaperLedgerSide,
)
from omni_cio.contracts.v1.paper_sell import PaperSaleResultV1


PaperResultV1 = PaperPurchaseResultV1 | PaperSaleResultV1
_MAX_EVENTS = 512
_MAX_POSITIONS = 256


class PaperAccountLedgerError(ValueError):
    """Paper results cannot be reduced into one safe account state."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise PaperAccountLedgerError("PAPER_LEDGER_TIMESTAMP_MUST_BE_AWARE")
    return result.astimezone(timezone.utc)


def _money(amount: Decimal, currency: str) -> Money:
    return Money(amount=amount, currency=currency)


def _validate_initial_positions(
    positions: tuple[PaperLedgerPositionV1, ...],
) -> tuple[PaperLedgerPositionV1, ...]:
    if len(positions) > _MAX_POSITIONS:
        raise PaperAccountLedgerError("PAPER_LEDGER_POSITION_LIMIT_EXCEEDED")
    keys = [position.stable_key for position in positions]
    if len(keys) != len(set(keys)):
        raise PaperAccountLedgerError("DUPLICATE_INITIAL_PAPER_POSITION")
    return tuple(sorted(positions, key=lambda position: position.stable_key))


def _purchase_event(
    result: PaperPurchaseResultV1,
    sequence: int,
    currency: str,
) -> PaperLedgerEventV1:
    return PaperLedgerEventV1(
        sequence=sequence,
        occurred_at=result.metadata.retrieved_at,
        scenario_id=result.scenario_id,
        side=PaperLedgerSide.PURCHASE,
        status=result.status,
        source_schema="paper_purchase_result",
        stable_key=result.stable_key,
        instrument_uid=result.instrument_uid,
        lot_size=result.lot_size,
        requested_lots=result.requested_lots,
        filled_lots=result.filled_lots,
        cash_before=result.paper_cash_before,
        cash_after=result.paper_cash_after,
        position_lots_before=result.position_lots_before,
        position_lots_after=result.position_lots_after,
        purchase_cost=result.total_cost,
        sale_net_proceeds=_money(Decimal("0"), currency),
        commission=result.commission,
        estimated_tax=_money(Decimal("0"), currency),
        paper_only=True,
        broker_order_created=False,
        execution_ready=False,
        trading_methods=False,
    )


def _sale_event(
    result: PaperSaleResultV1,
    sequence: int,
    currency: str,
) -> PaperLedgerEventV1:
    return PaperLedgerEventV1(
        sequence=sequence,
        occurred_at=result.metadata.retrieved_at,
        scenario_id=result.scenario_id,
        side=PaperLedgerSide.SALE,
        status=result.status,
        source_schema="paper_sale_result",
        stable_key=result.stable_key,
        instrument_uid=result.instrument_uid,
        lot_size=result.lot_size,
        requested_lots=result.requested_lots,
        filled_lots=result.filled_lots,
        cash_before=result.paper_cash_before,
        cash_after=result.paper_cash_after,
        position_lots_before=result.position_lots_before,
        position_lots_after=result.position_lots_after,
        purchase_cost=_money(Decimal("0"), currency),
        sale_net_proceeds=result.net_proceeds,
        commission=result.commission,
        estimated_tax=result.estimated_tax,
        paper_only=True,
        broker_order_created=False,
        execution_ready=False,
        trading_methods=False,
    )


def build_paper_account_ledger(
    *,
    account: AccountReference,
    currency: str,
    initial_cash: Decimal,
    initial_positions: Iterable[PaperLedgerPositionV1] = (),
    results: Iterable[PaperResultV1],
    built_at: datetime | None = None,
) -> PaperAccountLedgerV1:
    """Replay immutable purchase and sale paper results into one account snapshot."""

    evaluation_time = _aware_utc(built_at)
    normalized_currency = currency.upper()
    if len(normalized_currency) != 3 or not normalized_currency.isalpha():
        raise PaperAccountLedgerError("INVALID_PAPER_LEDGER_CURRENCY")
    if not initial_cash.is_finite() or initial_cash < 0:
        raise PaperAccountLedgerError("INVALID_INITIAL_PAPER_CASH")

    ordered_initial = _validate_initial_positions(tuple(initial_positions))
    result_tuple = tuple(results)
    if not result_tuple:
        raise PaperAccountLedgerError("PAPER_LEDGER_RESULTS_REQUIRED")
    if len(result_tuple) > _MAX_EVENTS:
        raise PaperAccountLedgerError("PAPER_LEDGER_EVENT_LIMIT_EXCEEDED")

    scenario_ids = [result.scenario_id for result in result_tuple]
    if len(scenario_ids) != len(set(scenario_ids)):
        raise PaperAccountLedgerError("DUPLICATE_PAPER_SCENARIO_ID")
    result_times = [result.metadata.retrieved_at for result in result_tuple]
    if result_times != sorted(result_times):
        raise PaperAccountLedgerError("PAPER_LEDGER_RESULTS_NOT_TIME_ORDERED")
    if result_times[-1] > evaluation_time:
        raise PaperAccountLedgerError("PAPER_LEDGER_BUILT_BEFORE_LAST_EVENT")

    events: list[PaperLedgerEventV1] = []
    provenance: list[SourceReference] = []
    rejected_issues: list[DataIssue] = []
    for sequence, result in enumerate(result_tuple, start=1):
        if result.metadata.account != account:
            raise PaperAccountLedgerError("PAPER_LEDGER_ACCOUNT_MISMATCH")
        if result.currency != normalized_currency:
            raise PaperAccountLedgerError("PAPER_LEDGER_CURRENCY_MISMATCH")
        if result.metadata.schema_name == "paper_purchase_result":
            if not isinstance(result, PaperPurchaseResultV1):
                raise PaperAccountLedgerError("PAPER_LEDGER_RESULT_TYPE_MISMATCH")
            event = _purchase_event(result, sequence, normalized_currency)
            operation = "paper_purchase_result"
        elif result.metadata.schema_name == "paper_sale_result":
            if not isinstance(result, PaperSaleResultV1):
                raise PaperAccountLedgerError("PAPER_LEDGER_RESULT_TYPE_MISMATCH")
            event = _sale_event(result, sequence, normalized_currency)
            operation = "paper_sale_result"
        else:
            raise PaperAccountLedgerError("UNSUPPORTED_PAPER_RESULT_SCHEMA")
        events.append(event)
        provenance.append(
            SourceReference(
                provider="omni-cio",
                operation=operation,
                retrieved_at=result.metadata.retrieved_at,
                source_id=result.scenario_id,
            )
        )
        if result.status == PaperOrderStatus.REJECTED:
            rejected_issues.append(
                DataIssue(
                    code="PAPER_LEDGER_REJECTED_EVENT",
                    severity=IssueSeverity.INFO,
                    message=(
                        "A rejected paper scenario was retained without changing state."
                    ),
                    component="paper_account_ledger",
                )
            )

    event_tuple = tuple(events)
    final_cash = event_tuple[-1].cash_after
    position_state: dict[str, PaperLedgerPositionV1] = {
        position.stable_key: position for position in ordered_initial
    }
    for event in event_tuple:
        if event.position_lots_after == 0:
            position_state.pop(event.stable_key, None)
        else:
            existing = position_state.get(event.stable_key)
            position_state[event.stable_key] = PaperLedgerPositionV1(
                stable_key=event.stable_key,
                instrument_uid=(
                    event.instrument_uid
                    if event.instrument_uid is not None
                    else existing.instrument_uid if existing is not None else None
                ),
                lot_size=event.lot_size,
                lots=event.position_lots_after,
            )
    final_positions = tuple(
        sorted(position_state.values(), key=lambda position: position.stable_key)
    )

    total_purchase_cost = sum(
        (event.purchase_cost.amount for event in event_tuple),
        Decimal("0"),
    )
    total_sale_proceeds = sum(
        (event.sale_net_proceeds.amount for event in event_tuple),
        Decimal("0"),
    )
    total_commission = sum(
        (event.commission.amount for event in event_tuple),
        Decimal("0"),
    )
    total_estimated_tax = sum(
        (event.estimated_tax.amount for event in event_tuple),
        Decimal("0"),
    )
    filled_purchase_lots = sum(
        event.filled_lots
        for event in event_tuple
        if event.side == PaperLedgerSide.PURCHASE
        and event.status != PaperOrderStatus.REJECTED
    )
    filled_sale_lots = sum(
        event.filled_lots
        for event in event_tuple
        if event.side == PaperLedgerSide.SALE
        and event.status != PaperOrderStatus.REJECTED
    )
    rejected_event_count = sum(
        1 for event in event_tuple if event.status == PaperOrderStatus.REJECTED
    )

    metadata = ContractMetadata(
        schema_name="paper_account_ledger",
        retrieved_at=evaluation_time,
        account=account,
        provenance=(
            *provenance,
            SourceReference(
                provider="omni-cio",
                operation="build_paper_account_ledger",
                retrieved_at=evaluation_time,
                source_id="1.0",
            ),
        ),
        quality=QualityMetadata(
            quality=DataQuality.VERIFIED,
            completeness=Completeness.COMPLETE,
            issues=tuple(rejected_issues),
            warnings=(
                "Paper-only ledger; no broker order is created or transmitted.",
                "The ledger is a deterministic snapshot reducer and is not a persistence backend.",
            ),
        ),
    )

    return PaperAccountLedgerV1(
        metadata=metadata,
        currency=normalized_currency,
        initial_cash=_money(initial_cash, normalized_currency),
        final_cash=final_cash,
        initial_positions=ordered_initial,
        final_positions=final_positions,
        events=event_tuple,
        scenario_ids=tuple(scenario_ids),
        total_purchase_cost=_money(total_purchase_cost, normalized_currency),
        total_sale_net_proceeds=_money(total_sale_proceeds, normalized_currency),
        total_commission=_money(total_commission, normalized_currency),
        total_estimated_tax=_money(total_estimated_tax, normalized_currency),
        filled_purchase_lots=filled_purchase_lots,
        filled_sale_lots=filled_sale_lots,
        rejected_event_count=rejected_event_count,
        paper_only=True,
        broker_order_created=False,
        no_cross_currency_aggregation=True,
        execution_ready=False,
        trading_methods=False,
    )
