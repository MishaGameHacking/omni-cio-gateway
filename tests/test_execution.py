from __future__ import annotations

import pytest

from omnicio.execution import (
    ExecutionStateError,
    provider_leg_status,
    run_status_for_legs,
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
