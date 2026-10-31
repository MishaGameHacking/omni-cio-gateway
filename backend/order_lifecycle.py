"""SIMULATION-ONLY coordination of the existing durable paper order journal.

This module has no transport, endpoint, credential or application-worker wiring.
It accepts only an explicitly declared simulation double. The journal commits
before the double is called; a missing submit response is never permission to
send again. Recovery uses the original request ID, not a replacement order.

Reports contain already normalized RUB amounts, never bond-price percentages.
This is not a real broker adapter or investment-eligibility implementation.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
from typing import Protocol

try:
    from .paper_execution import AccountSnapshot, ExecutionError, Lease, MAX_AMOUNT, PaperJournal, SimulatedScope
except ImportError:
    from paper_execution import AccountSnapshot, ExecutionError, Lease, MAX_AMOUNT, PaperJournal, SimulatedScope


def rub_to_nano(value: str | Decimal | int) -> int:
    """Convert exact nonnegative simulated RUB; floats and rounding are refused."""
    if isinstance(value, bool) or not isinstance(value, (str, Decimal, int)):
        raise ExecutionError("simulation_exact_rub_required")
    try:
        amount = Decimal(value)
    except (InvalidOperation, ValueError):
        raise ExecutionError("simulation_exact_rub_required") from None
    if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -9:
        raise ExecutionError("simulation_exact_rub_required")
    if amount > Decimal(MAX_AMOUNT) / Decimal(1_000_000_000):
        raise ExecutionError("simulation_amount_out_of_bounds")
    with localcontext() as context:
        context.prec = 40
        return int(amount * Decimal(1_000_000_000))


@dataclass(frozen=True)
class SimulatedReport:
    scope: SimulatedScope
    request_id: str
    observation_id: str
    sequence: int
    state: str
    filled_lots: int
    executed_rub: str
    fee_rub: str


@dataclass(frozen=True)
class SimulatedAccountReport:
    """Explicit replay coverage bound to one independently observed snapshot.

    Coverage is an assertion by the normalized simulation double, not something
    inferred from a newer timestamp or proof of real broker settlement.
    """
    snapshot: AccountSnapshot
    covered_request_ids: tuple[str, ...]
    snapshot_revision: int
    evidence_sha256: str


class SimulationBroker(Protocol):
    """Contract for an in-memory/replay double, not a production transport."""
    mode: str
    network_transport: bool
    scope: SimulatedScope

    def submit(self, command: dict) -> SimulatedReport | None: ...

    def lookup(self, request_id: str) -> SimulatedReport | None: ...

    def cancel(self, command: dict) -> SimulatedReport | None: ...

    def account_snapshot(self, next_revision: int) -> SimulatedAccountReport | None: ...


class OrderLifecycle:
    """One explicit simulation step per call; no timer or real-order switch.

    The existing PaperJournal remains the sole durable authority. A process
    reopening it must claim a new fenced lease before resuming. Money and units
    stay reserved until a terminal report AND a fresh complete account snapshot
    explicitly covering that request have been accepted by that journal.
    """
    def __init__(self, journal: PaperJournal, broker: SimulationBroker, *, simulation_only: bool):
        if simulation_only is not True or not isinstance(journal, PaperJournal):
            raise ExecutionError("simulation_environment_required")
        self.journal = journal
        self.broker = broker
        self._adapter_guard()

    def _adapter_guard(self):
        if (getattr(self.broker, "mode", None) != "simulation"
                or getattr(self.broker, "network_transport", None) is not False
                or getattr(self.broker, "scope", None) != self.journal.scope):
            raise ExecutionError("simulation_adapter_scope_or_environment_invalid")

    def _row(self, order_id):
        self._adapter_guard()
        row = next((row for row in self.journal.status()["orders"] if row["id"] == order_id), None)
        if row is None:
            raise ExecutionError("paper_order_missing")
        return row

    def _result(self, order_id, outcome):
        return {"mode": "simulation", "real_orders_enabled": False,
                "order_id": order_id, "state": self._row(order_id)["state"], "outcome": outcome}

    def _observe(self, order_id, lease, report):
        self._adapter_guard()
        if (not isinstance(report, SimulatedReport) or report.scope != self.journal.scope
                or report.request_id != order_id):
            raise ExecutionError("simulation_report_binding_invalid")
        self.journal.observe(order_id, lease, observation_id=report.observation_id,
            sequence=report.sequence, state=report.state, filled_lots=report.filled_lots,
            executed_nanorub=rub_to_nano(report.executed_rub), fee_nanorub=rub_to_nano(report.fee_rub))

    def _uncertain(self, order_id, lease):
        try:
            self.journal.uncertain(order_id, lease)
        except ExecutionError:
            # A response can arrive after lease expiry. The already committed
            # sending record survives; the next fenced owner recovers it.
            pass

    def dispatch(self, order_id: str, lease: Lease) -> dict:
        self._adapter_guard()
        command = self.journal.begin_send(order_id, lease)
        try:
            report = self.broker.submit(command)
        except Exception:
            self._uncertain(order_id, lease)
            return self._result(order_id, "submit_outcome_unknown")
        if report is None:
            self._uncertain(order_id, lease)
            return self._result(order_id, "submit_outcome_unknown")
        try:
            self._observe(order_id, lease, report)
        except ExecutionError:
            self._uncertain(order_id, lease)
            raise
        return self._result(order_id, "report_recorded")

    def reconcile_order(self, order_id: str, lease: Lease) -> dict:
        row = self._row(order_id)
        if row["state"] not in {"sending", "unknown", "active", "partial", "cancelling"}:
            return self._result(order_id, "no_order_lookup_required")
        try:
            report = self.broker.lookup(order_id)
        except Exception:
            return self._result(order_id, "lookup_unavailable")
        if report is None:
            # Not found is ambiguous: lag/retention/transport gaps do not prove
            # that the original request never reached the exchange.
            return self._result(order_id, "lookup_unresolved")
        self._observe(order_id, lease, report)
        return self._result(order_id, "report_recorded")

    def cancel(self, order_id: str, lease: Lease) -> dict:
        row = self._row(order_id)
        if row["state"] in {"sending", "unknown", "cancelling"}:
            return self.reconcile_order(order_id, lease)
        command = self.journal.request_cancel(order_id, lease)
        if not command["dispatch_required"]:
            return self._result(order_id, "no_cancel_dispatch_required")
        try:
            report = self.broker.cancel(command)
        except Exception:
            return self._result(order_id, "cancel_outcome_unknown")
        if report is None:
            return self._result(order_id, "cancel_outcome_unknown")
        self._observe(order_id, lease, report)
        return self._result(order_id, "report_recorded")

    def reconcile_account(self, lease: Lease) -> dict:
        self._adapter_guard()
        status = self.journal.status()
        try:
            report = self.broker.account_snapshot(status["snapshot_revision"] + 1)
        except Exception:
            return {"mode": "simulation", "real_orders_enabled": False, "outcome": "account_lookup_unavailable"}
        if report is None:
            return {"mode": "simulation", "real_orders_enabled": False, "outcome": "account_lookup_unresolved"}
        self._adapter_guard()
        completed = self._account_coverage(report, status)
        self.journal.reconcile_account(report.snapshot, lease, completed_order_ids=completed)
        return {"mode": "simulation", "real_orders_enabled": False,
                "outcome": "account_reconciled", "released_orders": len(completed)}

    @staticmethod
    def _account_coverage(report, status):
        if not isinstance(report, SimulatedAccountReport) or not isinstance(report.snapshot, AccountSnapshot):
            raise ExecutionError("simulation_account_coverage_required")
        if (type(report.snapshot_revision) is not int or report.snapshot_revision != report.snapshot.revision
                or report.evidence_sha256 != report.snapshot.evidence_sha256):
            raise ExecutionError("simulation_account_coverage_binding_invalid")
        covered = report.covered_request_ids
        awaiting = {row["id"] for row in status["orders"] if row["state"] == "awaiting_reconciliation"}
        if (not isinstance(covered, tuple) or len(covered) > len(awaiting)
                or any(not isinstance(order_id, str) or order_id not in awaiting for order_id in covered)
                or len(set(covered)) != len(covered)):
            raise ExecutionError("simulation_account_coverage_invalid")
        return list(covered)

    def work(self) -> list[dict]:
        """List required next steps; never submit a reserved order implicitly."""
        self._adapter_guard()
        status = self.journal.status()
        actions = {"reserved": "dispatch", "sending": "lookup", "unknown": "lookup",
                   "active": "lookup", "partial": "lookup", "cancelling": "lookup",
                   "awaiting_reconciliation": "account_reconciliation"}
        if status["paused"]:
            actions.pop("reserved")
        return [{"order_id": row["id"], "action": actions[row["state"]], "mode": "simulation"}
                for row in status["orders"] if row["state"] in actions]
