from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import UUID

import pytest

from omnicio.broker import BrokerConnectionStatus, BrokerService
from omnicio.execution_service import (
    ExecutionServiceError,
    PortfolioExecutionService,
)
from omnicio.execution_store import ExecutionLegRecord, ExecutionRunRecord
from omnicio.tbank import (
    TBankMoney,
    TBankNotFound,
    TBankSandboxCancelResult,
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
        live_mandate_id=None,
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
    broker = Mock(spec=BrokerService)
    broker.status.return_value = BrokerConnectionStatus(
        True, "sandbox", "sandbox-account", "Synthetic", NOW,
    )
    service = PortfolioExecutionService(
        store=store,  # type: ignore[arg-type]
        broker=broker,  # type: ignore[arg-type]
    )
    return service, store, broker


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
    assert {call[0] for call in broker.mock_calls} <= {"status", "sandbox_order_state"}
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


def test_sandbox_account_must_match_persisted_execution_account() -> None:
    service, _store, broker = _service()
    broker.status.return_value = BrokerConnectionStatus(
        connected=True,
        environment="prod",
        account_id="sandbox-account",
        account_name="Prod",
        verified_at=NOW,
    )

    run = _run()
    with pytest.raises(ExecutionServiceError, match="sandbox_account_mismatch"):
        service._require_sandbox_account(USER_ID, run)


@pytest.mark.parametrize("mode", ["sandbox", "live"])
@pytest.mark.parametrize("leg_status", [
    "submitting", "submitted", "partially_filled", "cancel_requested", "reconciling",
])
def test_reconcile_reads_one_old_request_and_never_posts_cancels_or_advances(mode, leg_status):
    service, store, broker = _service()
    environment = "prod" if mode == "live" else "sandbox"
    run = replace(
        _run(), mode=mode, provider_environment=environment,
        live_mandate_id=UUID(int=71) if mode == "live" else None,
    )
    broker.status.return_value = BrokerConnectionStatus(
        True, environment, run.account_id, "Synthetic", NOW,
    )
    leg = _leg(status=leg_status, submitted_at=NOW - timedelta(days=3))
    pending = replace(_leg(), id=UUID(int=72), request_id=UUID(int=73), leg_index=1)
    filled = replace(leg, status="filled", lots_executed=2)
    store.execution.side_effect = [(run, (leg, pending), ()), (run, (filled, pending), ())]
    reader = broker.live_order_state if mode == "live" else broker.sandbox_order_state
    reader.return_value = _provider_state(status="EXECUTION_REPORT_STATUS_FILL", lots_executed=2)

    result_run, result_legs = service.reconcile(USER_ID, RUN_ID, now=NOW)

    assert result_run == run
    assert result_legs == (filled, pending)
    reader.assert_called_once_with(USER_ID, request_id=str(REQUEST_ID), price_type="point")
    assert {call[0] for call in broker.mock_calls} <= {"status", mode + "_order_state"}
    store.create_run.assert_not_called()
    assert store.transition_leg.call_count == 1
    assert store.transition_leg.call_args.kwargs["new_status"] == "filled"
    assert store.transition_leg.call_args.kwargs["leg_id"] == LEG_ID


@pytest.mark.parametrize("mode", ["shadow", "sandbox", "live"])
def test_reconcile_pending_or_historical_shadow_never_invents_an_order(mode):
    service, store, broker = _service()
    run = replace(_run(), mode=mode)
    leg = _leg()
    store.execution.return_value = (run, (leg,), ())
    assert service.reconcile(USER_ID, RUN_ID, now=NOW) == (run, (leg,))
    assert broker.mock_calls == []
    store.transition_leg.assert_not_called()
    store.create_run.assert_not_called()


def test_reconcile_connection_change_never_persists_another_account_state():
    service, store, broker = _service()
    run, leg = _run(), _leg(status="submitted")
    store.execution.return_value = (run, (leg,), ())
    broker.status.side_effect = [
        BrokerConnectionStatus(True, "sandbox", run.account_id, "Synthetic", NOW),
        BrokerConnectionStatus(True, "sandbox", "different-account", "Other", NOW),
    ]
    broker.sandbox_order_state.return_value = _provider_state()
    with pytest.raises(ExecutionServiceError, match="account_mismatch"):
        service.reconcile(USER_ID, RUN_ID, now=NOW)
    store.transition_leg.assert_not_called()
    store.mark_run_reconciling.assert_not_called()
    assert {call[0] for call in broker.mock_calls} <= {"status", "sandbox_order_state"}


@pytest.mark.parametrize("submitted", [False, True])
def test_explicit_cancel_closes_old_plan_without_creating_another_order(submitted):
    service, store, broker = _service()
    leg = _leg(status="submitted" if submitted else "pending")
    store.execution.return_value = (_run(), (leg,), ())
    broker.cancel_sandbox_order.return_value = TBankSandboxCancelResult(cancelled_at=NOW)
    service.cancel(USER_ID, RUN_ID, now=NOW)
    assert {call[0] for call in broker.mock_calls} <= {"status", "cancel_sandbox_order"}
    if submitted:
        broker.cancel_sandbox_order.assert_called_once_with(USER_ID, request_id=str(REQUEST_ID))
        store.mark_run_reconciling.assert_called_once()
    else:
        broker.cancel_sandbox_order.assert_not_called()
        assert store.transition_leg.call_args.kwargs["new_status"] == "cancelled"


def test_pending_shadow_can_be_closed_without_any_provider_call():
    service, store, broker = _service()
    store.execution.return_value = (
        replace(_run(), mode="shadow", provider_environment=None),
        (_leg(),),
        (),
    )
    service.cancel(USER_ID, RUN_ID, now=NOW)
    assert broker.mock_calls == []
    assert store.transition_leg.call_args.kwargs["new_status"] == "cancelled"


def test_new_dispatch_timeout_is_reconciled_without_reposting_or_advancing():
    service, store, broker = _service()
    service.sandbox_enabled = True
    service.legal_versions = {"terms": "test"}
    service.research_store = Mock()
    service.research_store.evidence.return_value = {"version": 0}
    session = b"s" * 32
    now = datetime.now(UTC)
    payload = {"evidence_version": 0, "connection_verified_at": now.isoformat(), "legs": [{}]}
    store.strategy_proposal.return_value = {
        "created_session_digest": session,
        "payload": payload,
        "expires_at": now + timedelta(minutes=2),
    }
    current = [_leg()]
    store.execution.side_effect = lambda *args: (_run(), tuple(current), ())

    def transition(*args, **kwargs):
        current[0] = replace(current[0], status=kwargs["new_status"])

    def unknown(*args, **kwargs):
        current[0] = replace(current[0], status="reconciling")

    store.transition_leg.side_effect = transition
    store.mark_run_reconciling.side_effect = unknown
    broker.submit_limit_order.side_effect = TBankUnavailable("timeout")
    broker.sandbox_order_state.side_effect = TBankNotFound("not-yet-visible")
    with patch.object(service, "_dispatch_preflight"):
        service.dispatch(USER_ID, RUN_ID, session_digest=session, expected_leg_id=LEG_ID)
        service.dispatch(USER_ID, RUN_ID, session_digest=session, expected_leg_id=LEG_ID)
    broker.submit_limit_order.assert_called_once()
    assert broker.submit_limit_order.call_args.kwargs["request_id"] == str(REQUEST_ID)
    assert store.transition_leg.call_args.kwargs["new_status"] == "submitting"
    assert store.transition_leg.call_args.kwargs["strategy_authority"][0] == session
    broker.sandbox_order_state.assert_called_once_with(
        USER_ID, request_id=str(REQUEST_ID), price_type="point"
    )


def test_retrying_completed_leg_returns_receipt_and_cannot_advance_next_leg():
    service, store, broker = _service()
    completed = replace(_leg(), status="shadow_filled", lots_executed=2)
    pending = replace(_leg(), id=UUID(int=999), leg_index=1)
    store.execution.return_value = (replace(_run(), mode="shadow"), (completed, pending), ())
    result = service.dispatch(USER_ID, RUN_ID, session_digest=b"s" * 32, expected_leg_id=LEG_ID)
    assert result["legs"][1]["status"] == "pending"
    assert broker.mock_calls == []
    store.transition_leg.assert_not_called()
    with pytest.raises(ExecutionServiceError, match="execution_leg_not_found"):
        service.dispatch(USER_ID, RUN_ID, session_digest=b"s" * 32, expected_leg_id=UUID(int=1000))
