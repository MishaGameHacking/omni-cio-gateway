from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock
from uuid import UUID

import pytest

from omnicio.broker import BrokerConnectionStatus
from omnicio.execution_service import (
    ExecutionServiceError,
    PortfolioExecutionService,
    SANDBOX_ORDER_TIMEOUT,
)
from omnicio.execution_store import ExecutionLegRecord, ExecutionRunRecord
from omnicio.tbank import (
    TBankMoney,
    TBankNotFound,
    TBankOrderPrice,
    TBankSandboxCancelResult,
    TBankSandboxMaxLots,
    TBankSandboxOrderState,
    TBankUnavailable,
)

USER_ID = UUID("00000000-0000-0000-0000-000000000801")
RUN_ID = UUID("00000000-0000-0000-0000-000000000802")
LEG_ID = UUID("00000000-0000-0000-0000-000000000803")
PROPOSAL_ID = UUID("00000000-0000-0000-0000-000000000804")
REQUEST_ID = UUID("00000000-0000-0000-0000-000000000805")
NOW = datetime(2026, 10, 3, 10, 0, tzinfo=UTC)


def _run(*, status: str = "running") -> ExecutionRunRecord:
    return ExecutionRunRecord(
        id=RUN_ID,
        user_id=USER_ID,
        proposal_id=PROPOSAL_ID,
        confirmed_action_id=1,
        proposal_version=2,
        proposal_hash=b"h" * 32,
        account_id="sandbox-account",
        mode="sandbox",
        provider_environment="sandbox",
        status=status,  # type: ignore[arg-type]
        error_code="",
        created_at=NOW - timedelta(minutes=1),
        updated_at=NOW - timedelta(minutes=1),
        finished_at=None,
    )


def _leg(
    *,
    status: str = "pending",
    action: str = "buy",
    submitted_at: datetime | None = None,
) -> ExecutionLegRecord:
    return ExecutionLegRecord(
        id=LEG_ID,
        run_id=RUN_ID,
        user_id=USER_ID,
        leg_index=0,
        action=action,
        instrument_uid="bond-uid",
        lots_requested=2,
        lots_executed=0,
        limit_price=Decimal("101.25"),
        limit_price_type="point",
        max_spend_rub=Decimal("2500") if action == "buy" else None,
        min_proceeds_rub=Decimal("1900") if action == "sell" else None,
        request_id=REQUEST_ID,
        provider_order_id=None,
        provider_status="",
        status=status,  # type: ignore[arg-type]
        executed_amount_rub=Decimal("0"),
        executed_commission_rub=Decimal("0"),
        submitted_at=submitted_at,
        last_checked_at=None,
        terminal_at=None,
    )


def _price(total: str = "2200") -> TBankOrderPrice:
    return TBankOrderPrice(
        total_order_amount=TBankMoney("RUB", total),
        initial_order_amount=TBankMoney("RUB", "2100"),
        executed_commission_rub=TBankMoney("RUB", "10"),
        service_commission=TBankMoney("RUB", "0"),
        deal_commission=TBankMoney("RUB", "10"),
        bond_aci_value=TBankMoney("RUB", "50"),
    )


def _provider_state(
    *,
    status: str = "EXECUTION_REPORT_STATUS_NEW",
    lots_executed: int = 0,
) -> TBankSandboxOrderState:
    return TBankSandboxOrderState(
        order_id="exchange-order-1",
        order_request_id=str(REQUEST_ID),
        instrument_uid="bond-uid",
        execution_report_status=status,
        lots_requested=2,
        lots_executed=lots_executed,
        total_order_amount=TBankMoney(
            "RUB",
            "1100" if lots_executed else "0",
        ),
        executed_commission=TBankMoney(
            "RUB",
            "5" if lots_executed else "0",
        ),
        direction="ORDER_DIRECTION_BUY",
        order_type="ORDER_TYPE_LIMIT",
    )


def _service() -> tuple[PortfolioExecutionService, Mock, Mock]:
    store = Mock()
    broker = Mock()
    service = PortfolioExecutionService(
        store=store,  # type: ignore[arg-type]
        broker=broker,  # type: ignore[arg-type]
    )
    return service, store, broker


def test_preflight_blocks_overspend_before_any_sandbox_mutation() -> None:
    service, store, broker = _service()
    broker.sandbox_max_lots.return_value = TBankSandboxMaxLots(
        buy_max_lots=10,
        sell_max_lots=10,
        buy_money_amount=TBankMoney("RUB", "10000"),
        currency="RUB",
    )
    broker.sandbox_order_price.return_value = _price("2600")

    with pytest.raises(ExecutionServiceError, match="would_overspend"):
        service._submit_pending(USER_ID, _run(), _leg(), NOW)

    broker.post_sandbox_order.assert_not_called()
    store.transition_leg.assert_not_called()


def test_ambiguous_submit_never_reposts_and_enters_reconciliation() -> None:
    service, store, broker = _service()
    broker.sandbox_max_lots.return_value = TBankSandboxMaxLots(
        buy_max_lots=10,
        sell_max_lots=10,
        buy_money_amount=TBankMoney("RUB", "10000"),
        currency="RUB",
    )
    broker.sandbox_order_price.return_value = _price()
    broker.post_sandbox_order.side_effect = TBankUnavailable("timeout")

    status = service._submit_pending(USER_ID, _run(), _leg(), NOW)

    assert status == "reconciling"
    broker.post_sandbox_order.assert_called_once()
    store.transition_leg.assert_called_once()
    assert store.transition_leg.call_args.kwargs["new_status"] == "submitting"
    store.mark_run_reconciling.assert_called_once()
    details = store.mark_run_reconciling.call_args.kwargs["details"]
    assert details["retry_post_order"] is False


def test_reconcile_not_found_keeps_same_request_id_without_post_retry() -> None:
    service, store, broker = _service()
    broker.sandbox_order_state.side_effect = TBankNotFound("missing")

    result = service._reconcile_leg(
        USER_ID,
        _run(status="reconciling"),
        _leg(status="reconciling"),
        NOW,
    )

    assert result == "reconciling"
    broker.sandbox_order_state.assert_called_once_with(
        USER_ID,
        request_id=str(REQUEST_ID),
        price_type="point",
    )
    broker.post_sandbox_order.assert_not_called()
    details = store.mark_run_reconciling.call_args.kwargs["details"]
    assert details["retry_post_order"] is False


def test_partial_fill_is_persisted_without_advancing_next_leg() -> None:
    service, store, broker = _service()
    state = _provider_state(
        status="EXECUTION_REPORT_STATUS_PARTIALLYFILL",
        lots_executed=1,
    )

    result = service._record_provider_state(
        USER_ID,
        _run(),
        _leg(status="submitted"),
        state,
        NOW,
        expected_statuses=("submitted",),
        event_type="sandbox_order_reconciled",
    )

    assert result == "partially_filled"
    kwargs = store.transition_leg.call_args.kwargs
    assert kwargs["new_status"] == "partially_filled"
    assert kwargs["lots_executed"] == 1
    assert kwargs["executed_amount_rub"] == Decimal("1100")
    assert kwargs["executed_commission_rub"] == Decimal("5")


def test_timeout_requests_cancel_using_persisted_request_id() -> None:
    service, store, broker = _service()
    broker.cancel_sandbox_order.return_value = TBankSandboxCancelResult(
        cancelled_at=NOW
    )
    submitted = _leg(
        status="submitted",
        submitted_at=NOW - SANDBOX_ORDER_TIMEOUT,
    )

    service._request_cancel(USER_ID, _run(), submitted, NOW)

    first = store.transition_leg.call_args
    assert first.kwargs["new_status"] == "cancel_requested"
    broker.cancel_sandbox_order.assert_called_once_with(
        USER_ID,
        request_id=str(REQUEST_ID),
    )
    store.mark_run_reconciling.assert_called_once()
    assert (
        store.mark_run_reconciling.call_args.kwargs["error_code"]
        == "sandbox_cancel_acknowledged"
    )


def test_sandbox_account_must_match_persisted_execution_account() -> None:
    service, _store, broker = _service()
    broker.status.return_value = BrokerConnectionStatus(
        connected=True,
        environment="prod",
        account_id="sandbox-account",
        account_name="Prod",
        verified_at=NOW,
    )

    with pytest.raises(ExecutionServiceError, match="sandbox_account_mismatch"):
        service._require_sandbox_account(USER_ID, _run())
