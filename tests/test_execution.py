from __future__ import annotations

from dataclasses import asdict, replace
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from test_execution_service import NOW, USER_ID, _leg, _run

from omnicio.execution import (
    ExecutionStateError,
    provider_leg_status,
    run_status_for_legs,
)
from omnicio.execution_store import (
    ExecutionLedgerError,
    ExecutionLegObservation,
    ExecutionStore,
    _transition_values,
)


@pytest.mark.parametrize(
    ("provider", "local"),
    [
        ("EXECUTION_REPORT_STATUS_NEW", "submitted"),
        ("EXECUTION_REPORT_STATUS_PARTIALLYFILL", "partially_filled"),
        ("EXECUTION_REPORT_STATUS_FILL", "filled"),
        ("EXECUTION_REPORT_STATUS_CANCELLED", "cancelled"),
        ("EXECUTION_REPORT_STATUS_REJECTED", "rejected"),
    ],
)
def test_provider_order_status_mapping_is_explicit(
    provider: str,
    local: str,
) -> None:
    assert provider_leg_status(provider) == local


def test_unknown_provider_order_status_fails_closed() -> None:
    with pytest.raises(
        ExecutionStateError,
        match="provider_order_status_unknown",
    ):
        provider_leg_status("EXECUTION_REPORT_STATUS_UNSPECIFIED")


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        (("shadow_filled", "shadow_filled"), "succeeded"),
        (("filled", "filled"), "succeeded"),
        (("filled", "partially_filled"), "running"),
        (("filled", "reconciling"), "reconciling"),
        (("cancelled", "pending"), "cancelled"),
        (("cancelled", "rejected"), "failed"),
        (("filled", "rejected"), "failed"),
        (("failed", "pending"), "failed"),
    ],
)
def test_run_status_is_derived_from_leg_state(
    statuses: tuple[str, ...],
    expected: str,
) -> None:
    assert run_status_for_legs(statuses) == expected  # type: ignore[arg-type]


def test_run_status_has_no_unreachable_terminal_fallback() -> None:
    terminal_sets = (
        ("filled",),
        ("shadow_filled",),
        ("filled", "shadow_filled"),
        ("rejected",),
        ("failed",),
        ("cancelled",),
        ("filled", "cancelled"),
    )
    assert [run_status_for_legs(statuses) for statuses in terminal_sets] == [
        "succeeded",
        "succeeded",
        "succeeded",
        "failed",
        "failed",
        "cancelled",
        "cancelled",
    ]


@pytest.mark.parametrize("stale", ["filled_lots", "observation_time"])
def test_reconciliation_cannot_overwrite_the_locked_newer_execution(stale: str) -> None:
    persisted = replace(_leg(status="partially_filled"), lots_executed=1,
                        executed_amount_rub=Decimal("1100"), last_checked_at=NOW)
    database = MagicMock()
    cursor = database.pool.connection.return_value.__enter__.return_value.cursor.return_value
    cursor = cursor.__enter__.return_value
    cursor.fetchone.side_effect = [asdict(_run()), asdict(persisted)]
    store = ExecutionStore(database)
    observed_at = NOW - timedelta(seconds=1) if stale == "observation_time" else NOW
    observation = ExecutionLegObservation(
        provider_status="EXECUTION_REPORT_STATUS_PARTIALLYFILL",
        lots_executed=0 if stale == "filled_lots" else 1,
        executed_amount_rub=Decimal("1000"),
    )
    with pytest.raises(ExecutionLedgerError, match="execution_leg_state_changed"):
        store.transition_leg(
            USER_ID, run_id=persisted.run_id, leg_id=persisted.id,
            expected_statuses=("submitted", "partially_filled", "reconciling"),
            new_status="partially_filled", event_type="provider_state_reconciled", details={},
            now=observed_at, observation=observation,
        )
    assert not any("UPDATE portfolio_execution" in call.args[0]
                   for call in cursor.execute.call_args_list)


@pytest.mark.parametrize("lots", [1, 2])
def test_execution_progress_allows_current_provider_monetary_corrections(lots: int) -> None:
    persisted = replace(_leg(status="partially_filled"), lots_executed=1,
                        executed_amount_rub=Decimal("1100"),
                        executed_commission_rub=Decimal("5"))
    assert _transition_values(
        persisted, lots_executed=lots, executed_amount_rub=Decimal("1099"),
        executed_commission_rub=Decimal("4"),
    ) == (lots, Decimal("1099"), Decimal("4"))
