"""Synthetic simulation contracts: no accounts, credentials or broker network."""
from dataclasses import replace
from pathlib import Path
import sqlite3
import threading

import pytest

from backend.paper_execution import (
    AccountSnapshot, ExecutionError, OrderIntent, PaperJournal, SimulatedScope,
)

SCOPE = SimulatedScope('synthetic-owner', 'synthetic-broker-generation-1', 'synthetic-paper-account')
NANO = 1_000_000_000


@pytest.fixture
def world(tmp_path):
    clock = [1000]
    path = tmp_path / 'execution.paper.sqlite3'
    journal = PaperJournal(path, SCOPE, clock=lambda: clock[0])
    snapshot = AccountSnapshot(SCOPE, 0, 1, 999, 1000*NANO, {'share': 100}, 'a'*64, True)
    journal.initialize_account(snapshot)
    return journal, snapshot, clock, path


def intent(key='one', **changes):
    values = dict(scope=SCOPE, idempotency_key=key, plan_id='synthetic-plan', plan_sha256='b'*64,
                  eligibility_sha256='c'*64, snapshot_revision=0, strategy_revision=1,
                  instrument='share', side='buy', lots=10, lot_size=1,
                  limit_nanorub_per_unit=10*NANO, fee_bound_nanorub=2*NANO, expires_at=2000)
    values.update(changes)
    return OrderIntent(**values)


def active(journal, key='one', **changes):
    lease = journal.claim('worker-one')
    order = journal.prepare(intent(key, **changes))
    journal.begin_send(order, lease)
    journal.observe(order, lease, observation_id='accepted', sequence=1,
                    state='active', filled_lots=0, executed_nanorub=0, fee_nanorub=0)
    return order, lease


def observe(journal, order, lease, state='filled', lots=10, value=100*NANO, fee=NANO, sequence=2, observation='fill'):
    journal.observe(order, lease, observation_id=observation, sequence=sequence, state=state,
                    filled_lots=lots, executed_nanorub=value, fee_nanorub=fee)


def test_idempotency_returns_existing_order_and_conflicts_do_not_mutate(world):
    journal, _, _, _ = world
    first = journal.prepare(intent())
    assert journal.prepare(intent()) == first
    before = journal.status()
    with pytest.raises(ExecutionError, match='idempotency_conflict'):
        journal.prepare(intent(lots=11))
    assert journal.status() == before
    assert before['reserved_nanorub'] == 102*NANO


def test_two_processes_cannot_reserve_the_same_cash(world):
    journal, _, clock, path = world
    barrier = threading.Barrier(2)
    results = []
    def prepare(key):
        other = PaperJournal(path, SCOPE, clock=lambda: clock[0])
        barrier.wait(timeout=3)
        try:
            results.append(other.prepare(intent(key, lots=60)))
        except ExecutionError as error:
            results.append(str(error))
    threads = [threading.Thread(target=prepare, args=(key,)) for key in ('left', 'right')]
    for thread in threads:thread.start()
    for thread in threads:thread.join(timeout=6)
    assert all(not thread.is_alive() for thread in threads)
    assert results.count('paper_observed_cash_insufficient') == 1
    assert len(journal.status()['orders']) == 1
    assert journal.status()['unreserved_nanorub'] == 398*NANO


def test_only_one_executor_and_fenced_renewal(world):
    journal, _, clock, _ = world
    first = journal.claim('first', seconds=2)
    with pytest.raises(ExecutionError, match='already_leased'):
        journal.claim('second')
    clock[0] += 2
    second = journal.claim('second')
    assert second.fence == first.fence + 1
    with pytest.raises(ExecutionError, match='fenced'):
        journal.renew(first)
    journal.renew(second)


def test_timeout_preserves_reservation_and_does_not_resend(world):
    journal, _, _, _ = world
    lease = journal.claim('one')
    order = journal.prepare(intent())
    command = journal.begin_send(order, lease)
    assert command['mode'] == 'simulation'
    journal.uncertain(order, lease)
    assert journal.status()['reserved_nanorub'] == 102*NANO
    with pytest.raises(ExecutionError, match='send_not_repeatable'):
        journal.begin_send(order, lease)
    second = journal.prepare(intent('second'))
    with pytest.raises(ExecutionError, match='unknown_order_reconciliation'):
        journal.begin_send(second, lease)


def test_crash_between_send_intent_and_response_recovers_unknown(world):
    journal, _, clock, path = world
    first = journal.claim('before-crash', seconds=1)
    order = journal.prepare(intent())
    journal.begin_send(order, first)
    clock[0] += 1
    recovered = PaperJournal(path, SCOPE, clock=lambda: clock[0])
    second = recovered.claim('after-crash')
    assert recovered.status()['orders'][0]['state'] == 'unknown'
    assert recovered.status()['orders'][0]['sends'] == 1
    with pytest.raises(ExecutionError, match='fenced'):
        observe(journal, order, first)
    observe(recovered, order, second)
    assert recovered.status()['orders'][0]['state'] == 'awaiting_reconciliation'
    assert recovered.status()['reserved_nanorub'] == 102*NANO


def test_partial_cancel_race_retains_fills_and_hold_until_account_reconciliation(world):
    journal, snapshot, clock, _ = world
    order, lease = active(journal)
    observe(journal, order, lease, state='partial', lots=4, value=40*NANO, fee=400_000_000)
    cancel = journal.request_cancel(order, lease)
    assert cancel['dispatch_required'] is True
    assert journal.request_cancel(order, lease)['cancel_id'] == cancel['cancel_id']
    # A further execution wins the race with the cancellation request.
    observe(journal, order, lease, state='cancelled', lots=6, value=60*NANO, fee=600_000_000,
            sequence=3, observation='cancel-confirmed')
    assert journal.status()['reserved_nanorub'] == 102*NANO
    clock[0] += 1
    after = replace(snapshot, revision=1, observed_at=clock[0], cash_nanorub=939_400_000_000,
                    available_units={'share': 106}, evidence_sha256='d'*64)
    journal.reconcile_account(after, lease, completed_order_ids=[order])
    status = journal.status()
    assert status['reserved_nanorub'] == 0
    assert status['cash_nanorub'] == after.cash_nanorub
    assert status['orders'][0]['state'] == 'cancelled'
    assert status['orders'][0]['filled_lots'] == 6
    assert journal.verify_event_chain()


def test_pause_does_not_stop_fill_observation_or_account_reconciliation(world):
    journal, snapshot, clock, _ = world
    order, lease = active(journal)
    journal.pause(True)
    observe(journal, order, lease)
    with pytest.raises(ExecutionError, match='paused'):
        journal.prepare(intent('new'))
    clock[0] += 1
    after = replace(snapshot, revision=1, observed_at=clock[0], cash_nanorub=899*NANO,
                    available_units={'share': 110}, evidence_sha256='d'*64)
    journal.reconcile_account(after, lease, completed_order_ids=[order])
    assert journal.status()['orders'][0]['state'] == 'filled'
    assert journal.status()['paused'] is True


def test_unknown_send_cannot_be_released_by_claimed_cash_snapshot(world):
    journal, snapshot, clock, _ = world
    lease = journal.claim('worker')
    order = journal.prepare(intent())
    journal.begin_send(order, lease)
    journal.uncertain(order, lease)
    with pytest.raises(ExecutionError, match='not_reconciliable'):
        journal.reconcile_account(replace(snapshot, revision=1, observed_at=clock[0]), lease,
                                  completed_order_ids=[order])
    assert journal.status()['reserved_nanorub'] == 102*NANO


def test_cancelling_unknown_order_does_not_hide_pending_reconciliation(world):
    journal, _, _, _ = world
    lease = journal.claim('worker')
    first = journal.prepare(intent())
    journal.begin_send(first, lease)
    journal.uncertain(first, lease)
    journal.request_cancel(first, lease)
    second = journal.prepare(intent('second'))
    with pytest.raises(ExecutionError, match='reconciliation_required'):
        journal.begin_send(second, lease)


def test_sale_proceeds_are_never_available_before_independent_snapshot(world):
    journal, _, _, _ = world
    sale, lease = active(journal, side='sell', lots=100)
    observe(journal, sale, lease, lots=100, value=1000*NANO)
    # The prospective 1,000 RUB sale is not added to the observed 1,000 RUB.
    with pytest.raises(ExecutionError, match='cash_insufficient'):
        journal.prepare(intent('new-buy', lots=120))
    assert journal.status()['cash_nanorub'] == 1000*NANO
    assert journal.status()['reserved_units'] == {'share': 100}


def test_duplicate_and_conflicting_observations_do_not_double_count(world):
    journal, _, _, _ = world
    order, lease = active(journal)
    observe(journal, order, lease)
    before = journal.status()
    observe(journal, order, lease)
    assert journal.status() == before
    with pytest.raises(ExecutionError, match='identity_conflict'):
        observe(journal, order, lease, fee=2*NANO)
    assert journal.status() == before


def test_old_observation_cannot_rewind_cumulative_execution(world):
    journal, _, _, _ = world
    order, lease = active(journal)
    observe(journal, order, lease)
    before = journal.status()
    with pytest.raises(ExecutionError, match='sequence_not_new'):
        observe(journal, order, lease, state='partial', lots=5, value=50*NANO, sequence=1, observation='late-old')
    assert journal.status() == before


def test_terminal_state_cannot_revert_to_active_or_another_terminal(world):
    journal, _, _, _ = world
    order, lease = active(journal)
    observe(journal, order, lease, state='cancelled', lots=0, value=0, fee=0)
    with pytest.raises(ExecutionError, match='terminal_observation_conflict'):
        observe(journal, order, lease, state='active', lots=0, value=0, fee=0, sequence=3, observation='late-active')
    assert journal.status()['orders'][0]['terminal_state'] == 'cancelled'


def test_partial_average_cannot_hide_a_new_fill_above_limit(world):
    journal, _, _, _ = world
    order, lease = active(journal)
    observe(journal, order, lease, state='partial', lots=5, value=40*NANO, fee=0)
    # Cumulative 95 RUB remains under 100, but the last five cost 11 each.
    with pytest.raises(ExecutionError, match='incremental_limit_price_breached'):
        observe(journal, order, lease, value=95*NANO, sequence=3, observation='bad-price')


def test_manual_account_change_invalidates_unsent_plans(world):
    journal, snapshot, clock, _ = world
    order = journal.prepare(intent())
    lease = journal.claim('worker')
    after = replace(snapshot, revision=1, observed_at=clock[0], cash_nanorub=800*NANO,
                    available_units={'share': 120}, evidence_sha256='d'*64)
    journal.reconcile_account(after, lease, completed_order_ids=[])
    assert journal.status()['orders'][0]['state'] == 'invalidated'
    assert journal.status()['reserved_nanorub'] == 0
    with pytest.raises(ExecutionError, match='send_not_repeatable'):
        journal.begin_send(order, lease)
    with pytest.raises(ExecutionError, match='revision_stale'):
        journal.prepare(intent('stale-plan'))
    journal.prepare(intent('new-plan', snapshot_revision=1))


def test_unsent_cancel_releases_hold_without_broker_or_snapshot(world):
    journal, _, _, _ = world
    order = journal.prepare(intent())
    lease = journal.claim('worker')
    assert journal.request_cancel(order, lease)['dispatch_required'] is False
    assert journal.status()['reserved_nanorub'] == 0
    assert journal.status()['orders'][0]['sends'] == 0


@pytest.mark.parametrize('changes', [
    {'lots': 0}, {'lots': -1}, {'lots': True}, {'lot_size': 0}, {'limit_nanorub_per_unit': 1.0},
    {'fee_bound_nanorub': -1}, {'side': 'withdraw'}, {'plan_sha256': 'fake'},
    {'eligibility_sha256': ''}, {'expires_at': 1000}, {'snapshot_revision': 2},
    {'strategy_revision': 0}, {'lots': 9_000_000_000_000_000_000},
    {'scope': SimulatedScope('other-owner', 'synthetic-broker-generation-1', 'synthetic-paper-account')},
])
def test_invalid_or_stale_plan_is_rejected_without_reservation(world, changes):
    journal, _, _, _ = world
    with pytest.raises(ExecutionError):
        journal.prepare(intent(**changes))
    assert journal.status()['orders'] == []
    assert journal.status()['reserved_nanorub'] == 0


@pytest.mark.parametrize('changes', [
    {'lots': 11}, {'value': 101*NANO}, {'fee': 3*NANO},
    {'state': 'filled', 'lots': 5, 'value': 50*NANO},
    {'state': 'active', 'lots': 1, 'value': 10*NANO},
    {'state': 'rejected', 'lots': 1, 'value': 10*NANO},
    {'state': 'cancelled', 'lots': 10, 'value': 100*NANO},
])
def test_invalid_execution_receipt_does_not_change_state(world, changes):
    journal, _, _, _ = world
    order, lease = active(journal)
    before = journal.status()
    with pytest.raises(ExecutionError):observe(journal, order, lease, **changes)
    assert journal.status() == before


def test_expired_lease_and_clock_rollback_cannot_send(world):
    journal, _, clock, _ = world
    order = journal.prepare(intent())
    lease = journal.claim('worker', seconds=2)
    clock[0] += 2
    with pytest.raises(ExecutionError, match='fenced'):
        journal.begin_send(order, lease)
    clock[0] = 999
    with pytest.raises(ExecutionError, match='clock_moved_backwards'):
        journal.renew(lease)


def test_separate_database_scope_and_identity_are_mandatory(world, tmp_path):
    _, _, clock, path = world
    with pytest.raises(ExecutionError, match='binding_mismatch'):
        PaperJournal(path, SimulatedScope('other', 'broker', 'account'), clock=lambda: clock[0])
    with pytest.raises(ExecutionError, match='separate_database'):
        PaperJournal(tmp_path/'backend.db', SCOPE)
    foreign = tmp_path/'foreign.paper.sqlite3'
    with sqlite3.connect(foreign) as db:db.execute('CREATE TABLE do_not_touch (value TEXT)')
    with pytest.raises(ExecutionError, match='database_identity_mismatch'):
        PaperJournal(foreign, SCOPE)
    with sqlite3.connect(foreign) as db:
        assert [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")] == ['do_not_touch']


def test_event_chain_detects_accidental_edit_without_claiming_authenticity(world):
    journal, _, _, path = world
    journal.prepare(intent())
    assert journal.verify_event_chain()
    with sqlite3.connect(path) as db:
        db.execute("UPDATE paper_events SET payload_json='{}' WHERE sequence=1")
    assert journal.verify_event_chain() is False


def test_bounded_scenario_command_retains_synthetic_receipts_and_refuses_overwrite(tmp_path):
    import json
    import subprocess
    import sys
    root = Path(__file__).resolve().parents[2]
    output = tmp_path/'scenario-evidence'
    command = [sys.executable, str(root/'tools/run_paper_execution.py'), '--output-directory', str(output)]
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report['mode'] == 'simulation'
    assert report['owner_portfolio_used'] is False
    assert report['real_orders_enabled'] is False
    assert report['sandbox_tested'] is False
    assert len(report['scenarios']) == 3
    assert all(row['passed'] and row['send_intents'] <= 1 for row in report['scenarios'])
    original = (output/'report.json').read_bytes()
    second = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=15)
    assert second.returncode != 0
    assert (output/'report.json').read_bytes() == original


def test_reconciliation_is_one_transaction_even_when_second_order_is_unknown(world):
    journal, snapshot, clock, _ = world
    first, lease = active(journal)
    observe(journal, first, lease)
    second = journal.prepare(intent('second'))
    journal.begin_send(second, lease)
    journal.uncertain(second, lease)
    original = journal.status()
    after = replace(snapshot, revision=1, observed_at=clock[0], cash_nanorub=899*NANO,
                    available_units={'share': 110}, evidence_sha256='d'*64)
    with pytest.raises(ExecutionError, match='not_reconciliable'):
        journal.reconcile_account(after, lease, completed_order_ids=[first, second])
    assert journal.status() == original
    assert journal.verify_event_chain()


def test_ledger_write_failure_rolls_back_reservation(world, monkeypatch):
    journal, _, _, _ = world
    def fail(*args):raise sqlite3.OperationalError('synthetic journal write failure')
    monkeypatch.setattr(journal, '_event', fail)
    with pytest.raises(sqlite3.OperationalError):journal.prepare(intent())
    assert journal.status()['orders'] == []
    assert journal.status()['reserved_nanorub'] == 0


def test_position_reservations_prevent_two_sales_of_the_same_units(world):
    journal, _, _, _ = world
    journal.prepare(intent('first-sale', side='sell', lots=60))
    with pytest.raises(ExecutionError, match='available_position_insufficient'):
        journal.prepare(intent('second-sale', side='sell', lots=60))
    assert journal.status()['reserved_units'] == {'share': 60}


def test_snapshot_before_terminal_observation_cannot_release_funds(world):
    journal, snapshot, _, _ = world
    order, lease = active(journal)
    observe(journal, order, lease)
    with pytest.raises(ExecutionError, match='not_reconciliable'):
        journal.reconcile_account(replace(snapshot, revision=1), lease, completed_order_ids=[order])
    assert journal.status()['reserved_nanorub'] == 102*NANO


def test_cancellation_reconciliation_is_allowed_while_paused(world):
    journal, _, _, _ = world
    order, lease = active(journal)
    journal.pause(True)
    assert journal.request_cancel(order, lease)['dispatch_required'] is True
    observe(journal, order, lease, state='cancelled', lots=0, value=0, fee=0)
    assert journal.status()['orders'][0]['state'] == 'awaiting_reconciliation'
    assert journal.status()['reserved_nanorub'] == 102*NANO


def test_changed_cash_snapshot_cannot_hide_reserved_capacity_deficit(world):
    journal, snapshot, clock, _ = world
    _, lease = active(journal)
    journal.reconcile_account(replace(snapshot, revision=1, observed_at=clock[0], cash_nanorub=50*NANO,
                                      evidence_sha256='d'*64), lease, completed_order_ids=[])
    assert journal.status()['unreserved_nanorub'] == -52*NANO
    with pytest.raises(ExecutionError, match='cash_insufficient'):
        journal.prepare(intent('new', snapshot_revision=1, lots=1))


@pytest.mark.parametrize('complete', [False, 1, 'true'])
def test_unverified_snapshot_never_initializes_an_account(tmp_path, complete):
    journal = PaperJournal(tmp_path/'incomplete.paper.sqlite3', SCOPE, clock=lambda: 1000)
    snapshot = AccountSnapshot(SCOPE, 0, 1, 999, 1000*NANO, {}, 'a'*64, complete)
    with pytest.raises(ExecutionError, match='complete_account_snapshot_required'):
        journal.initialize_account(snapshot)


def test_duplicate_reconciliation_ids_do_not_partially_release(world):
    journal, snapshot, clock, _ = world
    order, lease = active(journal)
    observe(journal, order, lease)
    with pytest.raises(ExecutionError, match='reconciliation_orders_invalid'):
        journal.reconcile_account(replace(snapshot, revision=1, observed_at=clock[0]), lease,
                                  completed_order_ids=[order, order])
    assert journal.status()['reserved_nanorub'] == 102*NANO
