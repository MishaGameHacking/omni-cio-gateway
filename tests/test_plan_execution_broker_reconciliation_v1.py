from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
import json

import pytest

from omni_cio.contracts.v1.plan_execution import BrokerExecutionStatus
from omni_cio.plan_execution.broker_reconciliation_v1 import (
    PlanExecutionBrokerStateError,
    broker_snapshot_from_proposal,
)
from omni_cio.real_trading.models_v1 import RealTradeProposalV1
from tests.v9_execution_fixture import NOW


def _money(value: Decimal) -> dict[str, object]:
    units = int(value)
    nano = int((value - Decimal(units)) * Decimal("1000000000"))
    return {"currency": "RUB", "units": str(units), "nano": nano}


def _proposal(quantity_lots: int = 10) -> RealTradeProposalV1:
    return RealTradeProposalV1(
        proposal_id="proposal-parser-0001",
        order_id="request-parser-0001",
        account_id="masked-account",
        instrument_uid="uid-share-core-0001",
        ticker="CORE",
        isin="RU000A000001",
        direction="BUY",
        quantity_lots=quantity_lots,
        limit_price=Decimal("100.1"),
        rationale="WP12 parser test",
        preview_total_rub=Decimal("1001"),
        preview_commission_rub=Decimal("1"),
        available_lots=100,
        market_retrieved_at=NOW,
        created_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
        confirmation_code="PARSER01",
        state="submitted",
        submitted_at=NOW,
    )


def _response(
    *,
    status: str,
    requested: int = 10,
    executed: int = 10,
    total: Decimal = Decimal("1002"),
    commission: Decimal = Decimal("1"),
) -> str:
    return json.dumps(
        {
            "executionReportStatus": status,
            "lotsRequested": requested,
            "lotsExecuted": executed,
            "totalOrderAmount": _money(total),
            "executedCommission": _money(commission),
            "executedOrderPrice": _money(Decimal("100.1")),
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def test_parser_accepts_filled_and_preserves_broker_totals() -> None:
    proposal = replace(
        _proposal(),
        broker_response_json=_response(status=BrokerExecutionStatus.FILLED.value),
    )
    snapshot = broker_snapshot_from_proposal(proposal)

    assert snapshot.status is BrokerExecutionStatus.FILLED
    assert snapshot.lots_requested == 10
    assert snapshot.lots_executed == 10
    assert snapshot.total_order_amount_rub == Decimal("1002")
    assert snapshot.executed_commission_rub == Decimal("1")
    assert snapshot.executed_order_price_rub == Decimal("100.1")
    assert len(snapshot.response_sha256) == 64


def test_parser_accepts_active_partial_fill_without_marking_terminal() -> None:
    proposal = replace(
        _proposal(),
        broker_response_json=_response(
            status=BrokerExecutionStatus.PARTIALLY_FILLED.value,
            executed=4,
            total=Decimal("400.8"),
            commission=Decimal("0.4"),
        ),
    )
    snapshot = broker_snapshot_from_proposal(proposal)

    assert snapshot.status is BrokerExecutionStatus.PARTIALLY_FILLED
    assert snapshot.lots_executed == 4


@pytest.mark.parametrize(
    "payload",
    [
        _response(
            status=BrokerExecutionStatus.FILLED.value,
            requested=11,
            executed=11,
        ),
        _response(
            status=BrokerExecutionStatus.FILLED.value,
            requested=10,
            executed=9,
        ),
        _response(
            status=BrokerExecutionStatus.PARTIALLY_FILLED.value,
            requested=10,
            executed=11,
        ),
        _response(
            status=BrokerExecutionStatus.PARTIALLY_FILLED.value,
            requested=10,
            executed=4,
            total=Decimal("0"),
        ),
        _response(status="EXECUTION_REPORT_STATUS_NOT_REAL"),
    ],
)
def test_parser_fails_closed_on_inconsistent_broker_state(payload: str) -> None:
    proposal = replace(_proposal(), broker_response_json=payload)
    with pytest.raises(PlanExecutionBrokerStateError):
        broker_snapshot_from_proposal(proposal)


def test_parser_rejects_missing_or_non_object_broker_response() -> None:
    with pytest.raises(PlanExecutionBrokerStateError):
        broker_snapshot_from_proposal(_proposal())

    with pytest.raises(PlanExecutionBrokerStateError):
        broker_snapshot_from_proposal(
            replace(_proposal(), broker_response_json="[]")
        )
