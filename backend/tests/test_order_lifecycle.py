"""End-to-end simulated recovery, with no broker, credentials or network calls."""
from dataclasses import replace
from decimal import Decimal, localcontext
import sqlite3

import pytest

from backend.order_lifecycle import OrderLifecycle, SimulatedAccountReport, SimulatedReport, rub_to_nano
from backend.paper_execution import AccountSnapshot, ExecutionError, OrderIntent, PaperJournal, SimulatedScope


class ReplayBroker:
    mode = "simulation"
    network_transport = False

    def __init__(self, scope):
        self.scope = scope
        self.submit_result = None
        self.lookup_result = None
        self.cancel_result = None
        self.snapshot_result = None
        self.submissions = []
        self.lookups = []
        self.cancellations = []
        self.snapshot_calls = []

    @staticmethod
    def answer(value, argument):
        if isinstance(value, BaseException):
            raise value
        return value(argument) if callable(value) else value

    def submit(self, command):
        self.submissions.append(command)
        return self.answer(self.submit_result, command)

    def lookup(self, request_id):
        self.lookups.append(request_id)
        return self.answer(self.lookup_result, request_id)

    def cancel(self, command):
        self.cancellations.append(command)
        return self.answer(self.cancel_result, command)

    def account_snapshot(self, next_revision):
        self.snapshot_calls.append(next_revision)
        return self.answer(self.snapshot_result, next_revision)


@pytest.fixture
def environment(tmp_path):
    now = [1000]
    scope = SimulatedScope("synthetic-owner", "synthetic-connection", "synthetic-account")
    path = tmp_path / "orders.paper.sqlite3"
    journal = PaperJournal(path, scope, clock=lambda: now[0])
    snapshot = AccountSnapshot(scope, 0, 1, now[0], rub_to_nano("5000"), {"synthetic-share": 10}, "a" * 64, True)
    journal.initialize_account(snapshot)
    intent = OrderIntent(scope, "synthetic-request", "synthetic-plan", "b" * 64, "c" * 64,
                         0, 1, "synthetic-share", "buy", 2, 1, rub_to_nano("1000"), rub_to_nano("10"), 2000)
    order_id = journal.prepare(intent)
    broker = ReplayBroker(scope)
    lease = journal.claim("synthetic-worker")
    lifecycle = OrderLifecycle(journal, broker, simulation_only=True)
    return {"now": now, "scope": scope, "path": path, "journal": journal, "snapshot": snapshot,
            "intent": intent, "order_id": order_id, "broker": broker, "lease": lease, "lifecycle": lifecycle}


def observation(env, *, state="active", lots=0, amount="0", fee="0", sequence=0):
    return SimulatedReport(env["scope"], env["order_id"], f"synthetic-observation-{sequence}", sequence,
                           state, lots, amount, fee)


def expected_reservation(env, amount="2010"):
    actual = env["journal"].status()["reserved_nanorub"]
    expected = rub_to_nano(amount)
    assert actual == expected


def account_report(snapshot, covered):
    return SimulatedAccountReport(snapshot, tuple(covered), snapshot.revision, snapshot.evidence_sha256)


def test_submit_is_committed_before_adapter_and_exactly_once(environment):
    env = environment
    def acknowledge(command):
        # A second connection can acquire a write lock while the adapter runs.
        with sqlite3.connect(env["path"], timeout=0) as database:
            database.execute("BEGIN IMMEDIATE")
            row = database.execute("SELECT state,sends FROM paper_orders WHERE id=?", (command["order_id"],)).fetchone()
            assert row == ("sending", 1)
        return observation(env)
    env["broker"].submit_result = acknowledge
    result = env["lifecycle"].dispatch(env["order_id"], env["lease"])
    assert result["state"] == "active"
    assert result["real_orders_enabled"] is False
    with pytest.raises(ExecutionError, match="paper_send_not_repeatable"):
        env["lifecycle"].dispatch(env["order_id"], env["lease"])
    assert len(env["broker"].submissions) == 1
    expected_reservation(env)


@pytest.mark.parametrize("response", [None, TimeoutError("response lost"), RuntimeError("adapter failure")])
def test_unknown_submit_restart_uses_original_id_and_never_resends(environment, response):
    env = environment
    env["broker"].submit_result = response
    first = env["lifecycle"].dispatch(env["order_id"], env["lease"])
    assert first["state"] == "unknown"
    env["now"][0] += 61
    reopened = PaperJournal(env["path"], env["scope"], clock=lambda: env["now"][0])
    lease = reopened.claim("restarted-worker")
    recovered = OrderLifecycle(reopened, env["broker"], simulation_only=True)
    for _ in range(3):
        result = recovered.reconcile_order(env["order_id"], lease)
        assert result["outcome"] == "lookup_unresolved"
    assert env["broker"].lookups == [env["order_id"]] * 3
    with pytest.raises(ExecutionError, match="paper_send_not_repeatable"):
        recovered.dispatch(env["order_id"], lease)
    assert len(env["broker"].submissions) == 1
    env["broker"].lookup_result = observation(env, state="partial", lots=1, amount="1000", fee="5")
    assert recovered.reconcile_order(env["order_id"], lease)["state"] == "partial"
    expected_reservation(env)
    assert reopened.verify_event_chain() is True


def test_process_crash_after_send_recovers_sending_record(environment):
    env = environment
    env["broker"].submit_result = KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        env["lifecycle"].dispatch(env["order_id"], env["lease"])
    assert env["journal"].status()["orders"][0]["state"] == "sending"
    env["now"][0] += 61
    new_lease = env["journal"].claim("restart-after-crash")
    assert env["lifecycle"].reconcile_order(env["order_id"], new_lease)["state"] == "unknown"
    assert len(env["broker"].submissions) == 1
    expected_reservation(env)


def test_partial_cancel_waits_for_terminal_report_and_independent_account(environment):
    env = environment
    env["broker"].submit_result = observation(env, state="partial", lots=1, amount="1000", fee="5")
    env["lifecycle"].dispatch(env["order_id"], env["lease"])
    env["broker"].cancel_result = TimeoutError("cancel response lost")
    assert env["lifecycle"].cancel(env["order_id"], env["lease"])["state"] == "cancelling"
    expected_reservation(env)
    assert env["lifecycle"].cancel(env["order_id"], env["lease"])["outcome"] == "lookup_unresolved"
    assert len(env["broker"].cancellations) == 1
    env["broker"].lookup_result = observation(env, state="cancelled", lots=1, amount="1000", fee="5", sequence=1)
    assert env["lifecycle"].reconcile_order(env["order_id"], env["lease"])["state"] == "awaiting_reconciliation"
    expected_reservation(env)
    assert env["lifecycle"].reconcile_account(env["lease"])["outcome"] == "account_lookup_unresolved"
    expected_reservation(env)
    env["now"][0] += 1
    snapshot = replace(env["snapshot"], revision=1, observed_at=env["now"][0],
        cash_nanorub=rub_to_nano("3995"), available_units={"synthetic-share": 11})
    env["broker"].snapshot_result = account_report(snapshot, [env["order_id"]])
    assert env["lifecycle"].reconcile_account(env["lease"])["released_orders"] == 1
    expected_reservation(env, "0")
    assert env["journal"].status()["orders"][0]["state"] == "cancelled"


def test_fill_wins_cancel_race_and_does_not_create_another_order(environment):
    env = environment
    env["broker"].submit_result = observation(env)
    env["lifecycle"].dispatch(env["order_id"], env["lease"])
    env["broker"].cancel_result = observation(env, state="filled", lots=2, amount="2000", fee="10", sequence=1)
    assert env["lifecycle"].cancel(env["order_id"], env["lease"])["state"] == "awaiting_reconciliation"
    expected_reservation(env)
    assert env["lifecycle"].cancel(env["order_id"], env["lease"])["outcome"] == "no_cancel_dispatch_required"
    assert len(env["broker"].submissions) == 1
    assert len(env["broker"].cancellations) == 1


def test_unsent_cancel_does_not_contact_adapter(environment):
    env = environment
    assert env["lifecycle"].cancel(env["order_id"], env["lease"])["state"] == "cancelled"
    assert env["broker"].submissions == []
    assert env["broker"].cancellations == []
    expected_reservation(env, "0")


@pytest.mark.parametrize("changed", [{"mode": "live"}, {"network_transport": True}, {"scope": SimulatedScope("other", "other", "other")}])
def test_runtime_adapter_changes_are_rejected_before_dispatch(environment, changed):
    env = environment
    for key, value in changed.items():
        setattr(env["broker"], key, value)
    with pytest.raises(ExecutionError, match="simulation_adapter_scope_or_environment_invalid"):
        env["lifecycle"].dispatch(env["order_id"], env["lease"])
    assert env["broker"].submissions == []
    assert env["journal"].status()["orders"][0]["state"] == "reserved"


@pytest.mark.parametrize("field,value", [("scope", SimulatedScope("other", "other", "other")), ("request_id", "other-order"), ("fee_rub", "11"), ("executed_rub", "NaN")])
def test_invalid_submit_report_keeps_uncertain_reservation(environment, field, value):
    env = environment
    env["broker"].submit_result = replace(observation(env), **{field: value})
    with pytest.raises(ExecutionError):
        env["lifecycle"].dispatch(env["order_id"], env["lease"])
    assert env["journal"].status()["orders"][0]["state"] == "unknown"
    expected_reservation(env)


def test_paused_journal_blocks_new_send_but_allows_reconciliation(environment):
    env = environment
    env["journal"].pause(True)
    assert env["lifecycle"].work() == []
    with pytest.raises(ExecutionError, match="paper_new_orders_paused"):
        env["lifecycle"].dispatch(env["order_id"], env["lease"])
    assert env["broker"].submissions == []
    env["journal"].pause(False)
    env["lifecycle"].dispatch(env["order_id"], env["lease"])
    env["journal"].pause(True)
    assert env["lifecycle"].work() == [{"order_id": env["order_id"], "action": "lookup", "mode": "simulation"}]
    env["broker"].lookup_result = observation(env)
    assert env["lifecycle"].reconcile_order(env["order_id"], env["lease"])["state"] == "active"


def test_unknown_order_blocks_another_reserved_order(environment):
    env = environment
    second_id = env["journal"].prepare(replace(env["intent"], idempotency_key="second-request"))
    env["lifecycle"].dispatch(env["order_id"], env["lease"])
    with pytest.raises(ExecutionError, match="paper_unknown_order_reconciliation_required"):
        env["lifecycle"].dispatch(second_id, env["lease"])
    assert len(env["broker"].submissions) == 1
    expected_reservation(env, "4020")


def test_work_listing_is_read_only_and_does_not_dispatch(environment):
    env = environment
    assert env["lifecycle"].work() == [{"order_id": env["order_id"], "action": "dispatch", "mode": "simulation"}]
    assert env["broker"].submissions == []
    assert env["journal"].prepare(env["intent"]) == env["order_id"]
    conflicting_intent = replace(env["intent"], lots=1)
    with pytest.raises(ExecutionError, match="paper_idempotency_conflict"):
        env["journal"].prepare(conflicting_intent)
    expected_reservation(env)


def test_late_response_after_lease_expiry_cannot_commit_as_old_worker(environment):
    env = environment
    def late_response(_command):
        env["now"][0] += 61
        return observation(env)
    env["broker"].submit_result = late_response
    with pytest.raises(ExecutionError, match="paper_executor_fenced"):
        env["lifecycle"].dispatch(env["order_id"], env["lease"])
    assert env["journal"].status()["orders"][0]["state"] == "sending"
    lease = env["journal"].claim("next-worker")
    env["broker"].lookup_result = observation(env)
    assert env["lifecycle"].reconcile_order(env["order_id"], lease)["state"] == "active"
    assert len(env["broker"].submissions) == 1
    expected_reservation(env)


def test_duplicate_report_is_idempotent(environment):
    env = environment
    report = observation(env, state="partial", lots=1, amount="1000", fee="5")
    env["broker"].submit_result = report
    env["broker"].lookup_result = report
    env["lifecycle"].dispatch(env["order_id"], env["lease"])
    for _ in range(3):
        assert env["lifecycle"].reconcile_order(env["order_id"], env["lease"])["state"] == "partial"
    expected_reservation(env)
    with sqlite3.connect(env["path"]) as database:
        observations = database.execute("SELECT COUNT(*) FROM paper_observations").fetchone()[0]
    assert observations == 1
    assert env["journal"].verify_event_chain() is True


@pytest.mark.parametrize("field,value", [("scope", SimulatedScope("other", "other", "other")), ("complete", False), ("revision", 2)])
def test_invalid_account_snapshot_does_not_release_terminal_reservation(environment, field, value):
    env = environment
    env["broker"].submit_result = observation(env, state="filled", lots=2, amount="2000", fee="10")
    env["lifecycle"].dispatch(env["order_id"], env["lease"])
    snapshot = replace(env["snapshot"], revision=1, cash_nanorub=rub_to_nano("2990"),
                       available_units={"synthetic-share": 12})
    env["broker"].snapshot_result = account_report(replace(snapshot, **{field: value}), [env["order_id"]])
    with pytest.raises(ExecutionError):
        env["lifecycle"].reconcile_account(env["lease"])
    expected_reservation(env)
    assert env["journal"].status()["orders"][0]["state"] == "awaiting_reconciliation"


def test_new_snapshot_revision_with_old_balances_does_not_imply_order_coverage(environment):
    env = environment
    env["broker"].submit_result = observation(env, state="filled", lots=2, amount="2000", fee="10")
    env["lifecycle"].dispatch(env["order_id"], env["lease"])
    lagging = replace(env["snapshot"], revision=1)
    env["broker"].snapshot_result = lagging
    with pytest.raises(ExecutionError, match="simulation_account_coverage_required"):
        env["lifecycle"].reconcile_account(env["lease"])
    expected_reservation(env)
    env["broker"].snapshot_result = account_report(lagging, [])
    result = env["lifecycle"].reconcile_account(env["lease"])
    assert result["released_orders"] == 0
    expected_reservation(env)
    assert env["journal"].status()["orders"][0]["state"] == "awaiting_reconciliation"


def test_account_coverage_releases_only_the_explicitly_covered_subset(environment):
    env = environment
    second_id = env["journal"].prepare(replace(env["intent"], idempotency_key="second-request"))
    first_report = observation(env, state="filled", lots=2, amount="2000", fee="10")
    env["broker"].submit_result = first_report
    env["lifecycle"].dispatch(env["order_id"], env["lease"])
    env["broker"].submit_result = replace(first_report, request_id=second_id, observation_id="second-observation")
    env["lifecycle"].dispatch(second_id, env["lease"])
    expected_reservation(env, "4020")
    snapshot = replace(env["snapshot"], revision=1, cash_nanorub=rub_to_nano("2990"),
                       available_units={"synthetic-share": 12})
    env["broker"].snapshot_result = account_report(snapshot, [env["order_id"]])
    assert env["lifecycle"].reconcile_account(env["lease"])["released_orders"] == 1
    expected_reservation(env)
    states = {row["id"]: row["state"] for row in env["journal"].status()["orders"]}
    assert states[env["order_id"]] == "filled"
    assert states[second_id] == "awaiting_reconciliation"


@pytest.mark.parametrize("field,value", [("snapshot_revision", 2), ("evidence_sha256", "d" * 64), ("covered_request_ids", ("other-order",))])
def test_account_coverage_cannot_be_rebound_to_another_snapshot_or_order(environment, field, value):
    env = environment
    env["broker"].submit_result = observation(env, state="filled", lots=2, amount="2000", fee="10")
    env["lifecycle"].dispatch(env["order_id"], env["lease"])
    snapshot = replace(env["snapshot"], revision=1, cash_nanorub=rub_to_nano("2990"))
    report = account_report(snapshot, [env["order_id"]])
    env["broker"].snapshot_result = replace(report, **{field: value})
    with pytest.raises(ExecutionError, match="simulation_account_coverage"):
        env["lifecycle"].reconcile_account(env["lease"])
    expected_reservation(env)


@pytest.mark.parametrize("value", [0.1, True, "NaN", "Infinity", "-0.01", "0.0000000001", "9000000000.000000001", "1e1000000", "not money"])
def test_money_conversion_rejects_rounding_nonfinite_negative_and_overflow(value):
    with pytest.raises(ExecutionError):
        rub_to_nano(value)


def test_money_conversion_is_exact_even_with_low_ambient_precision():
    with localcontext() as context:
        context.prec = 2
        actual = rub_to_nano(Decimal("123456.000000001"))
    assert actual == 123456000000001


def test_explicit_simulation_environment_is_required(environment):
    env = environment
    with pytest.raises(ExecutionError, match="simulation_environment_required"):
        OrderLifecycle(env["journal"], env["broker"], simulation_only=False)
