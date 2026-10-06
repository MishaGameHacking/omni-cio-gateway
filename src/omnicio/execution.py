"""State rules for reading and reconciling existing execution records."""

from __future__ import annotations

from typing import Literal

ExecutionMode = Literal["shadow", "sandbox", "live"]
ExecutionRunStatus = Literal[
    "created",
    "running",
    "reconciling",
    "succeeded",
    "cancelled",
    "failed",
]
ExecutionLegStatus = Literal[
    "pending",
    "submitting",
    "submitted",
    "partially_filled",
    "filled",
    "cancel_requested",
    "cancelled",
    "rejected",
    "reconciling",
    "failed",
    "shadow_filled",
]

_PROVIDER_STATUS_TO_LEG: dict[str, ExecutionLegStatus] = {
    "EXECUTION_REPORT_STATUS_NEW": "submitted",
    "EXECUTION_REPORT_STATUS_PARTIALLYFILL": "partially_filled",
    "EXECUTION_REPORT_STATUS_FILL": "filled",
    "EXECUTION_REPORT_STATUS_CANCELLED": "cancelled",
    "EXECUTION_REPORT_STATUS_REJECTED": "rejected",
}


class ExecutionStateError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def provider_leg_status(value: str) -> ExecutionLegStatus:
    try:
        return _PROVIDER_STATUS_TO_LEG[value]
    except KeyError as exc:
        raise ExecutionStateError("provider_order_status_unknown") from exc


def run_status_for_legs(
    statuses: tuple[ExecutionLegStatus, ...],
) -> ExecutionRunStatus:
    if not statuses:
        return "failed"
    if all(status in {"filled", "shadow_filled"} for status in statuses):
        return "succeeded"
    if any(status in {"failed", "rejected"} for status in statuses):
        return "failed"
    if any(status == "cancelled" for status in statuses):
        return "cancelled"
    if any(status == "reconciling" for status in statuses):
        return "reconciling"
    return "running"
