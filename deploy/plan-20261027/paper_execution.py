"""Durable SIMULATION-ONLY order journal; never imports a broker or credentials.

This is the N08 simulator boundary, not a production trading adapter. Amounts
are integer nano-RUB per instrument unit, not bond-price percentages. Evidence
and eligibility digests reference a separately checked simulated plan; they
are not financial attestations. No method can send a network request.

Reservations survive unknown sends, fills, cancellations and restarts. Only a
complete independent simulated account snapshot can release a sent order's
reservation. Expected sale proceeds are never counted as available cash.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
from typing import Callable
import uuid

APPLICATION_ID = 0x41415031
MAX_AMOUNT = 9_000_000_000_000_000_000
MAX_ORDERS = 1000
TERMINAL = frozenset({'filled', 'cancelled', 'rejected', 'invalidated'})
HOLDING = frozenset({'reserved', 'sending', 'unknown', 'active', 'partial', 'cancelling', 'awaiting_reconciliation'})


class ExecutionError(ValueError):
    """Sanitized simulation contract or state error."""


def _text(value, limit=120):
    if (not isinstance(value, str) or not 1 <= len(value) <= limit or value != value.strip()
            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise ExecutionError('paper_identity_invalid')
    return value


def _integer(value, *, minimum=0, maximum=MAX_AMOUNT):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ExecutionError('paper_integer_out_of_bounds')
    return value


def _digest(value):
    if not isinstance(value, str) or re.fullmatch(r'[0-9a-f]{64}', value) is None:
        raise ExecutionError('paper_evidence_digest_invalid')
    return value


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def _hash(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


@dataclass(frozen=True)
class SimulatedScope:
    owner: str
    broker_connection: str
    account: str

    def key(self):
        for value in asdict(self).values():
            _text(value)
        return _hash(asdict(self))


@dataclass(frozen=True)
class AccountSnapshot:
    scope: SimulatedScope
    revision: int
    strategy_revision: int
    observed_at: int
    cash_nanorub: int
    available_units: dict[str, int]
    evidence_sha256: str
    complete: bool

    def validated(self):
        if not isinstance(self.scope, SimulatedScope):
            raise ExecutionError('paper_scope_invalid')
        self.scope.key()
        for value in (self.revision, self.strategy_revision, self.observed_at, self.cash_nanorub):
            _integer(value)
        _digest(self.evidence_sha256)
        if self.complete is not True or not isinstance(self.available_units, dict) or len(self.available_units) > 10000:
            raise ExecutionError('paper_complete_account_snapshot_required')
        for instrument, amount in self.available_units.items():
            _text(instrument)
            _integer(amount)
        return asdict(self)


@dataclass(frozen=True)
class OrderIntent:
    scope: SimulatedScope
    idempotency_key: str
    plan_id: str
    plan_sha256: str
    eligibility_sha256: str
    snapshot_revision: int
    strategy_revision: int
    instrument: str
    side: str
    lots: int
    lot_size: int
    limit_nanorub_per_unit: int
    fee_bound_nanorub: int
    expires_at: int

    def validated(self):
        if not isinstance(self.scope, SimulatedScope):
            raise ExecutionError('paper_scope_invalid')
        self.scope.key()
        for value in (self.idempotency_key, self.plan_id, self.instrument):
            _text(value)
        for value in (self.plan_sha256, self.eligibility_sha256):
            _digest(value)
        for value in (self.snapshot_revision, self.strategy_revision, self.fee_bound_nanorub, self.expires_at):
            _integer(value)
        for value in (self.lots, self.lot_size, self.limit_nanorub_per_unit):
            _integer(value, minimum=1)
        if self.side not in {'buy', 'sell'}:
            raise ExecutionError('paper_direction_invalid')
        _integer(self.lots * self.lot_size)
        _integer(self.lots * self.lot_size * self.limit_nanorub_per_unit + self.fee_bound_nanorub)
        return asdict(self)


@dataclass(frozen=True)
class Lease:
    owner: str
    fence: int
    token: str


class PaperJournal:
    """One simulated account in an explicitly named, separate SQLite database.

    The supplied clock is for deterministic replay/testing. A caller cannot
    configure a real broker endpoint: there is no transport in this module.
    """
    def __init__(self, path: str | Path, scope: SimulatedScope, *, clock: Callable[[], int] | None = None):
        self.path = Path(path).absolute()
        if (self.path.suffixes[-2:] != ['.paper', '.sqlite3'] or self.path.is_symlink()
                or not self.path.parent.is_dir()):
            raise ExecutionError('paper_separate_database_required')
        if not isinstance(scope, SimulatedScope):
            raise ExecutionError('paper_scope_invalid')
        self.scope = scope
        self.scope_key = scope.key()
        self.clock = clock or (lambda: int(time.time()))
        created = False
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        except FileExistsError:
            pass
        else:
            os.close(fd)
            created = True
        with self._connection() as db:
            marker = db.execute('PRAGMA application_id').fetchone()[0]
            if not created and marker != APPLICATION_ID:
                raise ExecutionError('paper_database_identity_mismatch')
            if created:
                db.execute(f'PRAGMA application_id={APPLICATION_ID}')
                db.execute('BEGIN IMMEDIATE')
                for statement in (
                    '''CREATE TABLE paper_meta (singleton INTEGER PRIMARY KEY CHECK(singleton=1), scope_key TEXT NOT NULL,
                       snapshot_json TEXT, paused INTEGER NOT NULL DEFAULT 0, fence INTEGER NOT NULL DEFAULT 0,
                       lease_owner TEXT, lease_token TEXT, lease_until INTEGER NOT NULL DEFAULT 0, last_time INTEGER NOT NULL DEFAULT 0)''',
                    '''CREATE TABLE paper_orders (id TEXT PRIMARY KEY, request_key TEXT NOT NULL UNIQUE,
                       intent_json TEXT NOT NULL, intent_hash TEXT NOT NULL, state TEXT NOT NULL,
                       terminal_state TEXT, sends INTEGER NOT NULL DEFAULT 0, sent_fence INTEGER,
                       observed_sequence INTEGER NOT NULL DEFAULT -1, filled_lots INTEGER NOT NULL DEFAULT 0,
                       executed_nanorub INTEGER NOT NULL DEFAULT 0, fee_nanorub INTEGER NOT NULL DEFAULT 0,
                       terminal_observed_at INTEGER, created_at INTEGER NOT NULL)''',
                    '''CREATE TABLE paper_observations (order_id TEXT NOT NULL, observation_id TEXT NOT NULL,
                       digest TEXT NOT NULL, payload_json TEXT NOT NULL, received_at INTEGER NOT NULL,
                       PRIMARY KEY(order_id,observation_id))''',
                    '''CREATE TABLE paper_events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, order_id TEXT,
                       kind TEXT NOT NULL, payload_json TEXT NOT NULL, at INTEGER NOT NULL,
                       previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL)''',
                ):
                    db.execute(statement)
                db.execute('INSERT INTO paper_meta(singleton,scope_key) VALUES(1,?)', (self.scope_key,))
                db.commit()
            row = db.execute('SELECT scope_key FROM paper_meta WHERE singleton=1').fetchone()
            if row is None or row['scope_key'] != self.scope_key:
                raise ExecutionError('paper_account_binding_mismatch')

    @contextmanager
    def _connection(self):
        db = sqlite3.connect(self.path.as_uri() + '?mode=rw', uri=True, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('PRAGMA synchronous=FULL')
            yield db
        finally:
            db.close()

    @contextmanager
    def _transaction(self):
        with self._connection() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def _now(self):
        return _integer(self.clock())

    def _meta(self, db):
        value = db.execute('SELECT * FROM paper_meta WHERE singleton=1').fetchone()
        if value is None or value['scope_key'] != self.scope_key:
            raise ExecutionError('paper_account_binding_mismatch')
        if self._now() < value['last_time']:
            raise ExecutionError('paper_clock_moved_backwards')
        return value

    def _snapshot(self, db):
        meta = self._meta(db)
        if meta['snapshot_json'] is None:
            raise ExecutionError('paper_account_not_initialized')
        return json.loads(meta['snapshot_json'])

    def _order(self, db, order_id):
        row = db.execute('SELECT * FROM paper_orders WHERE id=?', (_text(order_id),)).fetchone()
        if row is None:
            raise ExecutionError('paper_order_missing')
        return row

    def _event(self, db, order_id, kind, payload):
        previous = db.execute('SELECT event_hash FROM paper_events ORDER BY sequence DESC LIMIT 1').fetchone()
        previous_hash = previous[0] if previous else '0' * 64
        at = self._now()
        if at < self._meta(db)['last_time']:
            raise ExecutionError('paper_clock_moved_backwards')
        db.execute('UPDATE paper_meta SET last_time=? WHERE singleton=1', (at,))
        encoded = _json(payload)
        event_hash = _hash([previous_hash, order_id, kind, encoded, at])
        db.execute('INSERT INTO paper_events(order_id,kind,payload_json,at,previous_hash,event_hash) VALUES(?,?,?,?,?,?)',
                   (order_id, kind, encoded, at, previous_hash, event_hash))

    def _lease(self, db, lease):
        if not isinstance(lease, Lease):
            raise ExecutionError('paper_lease_required')
        meta = self._meta(db)
        if (meta['lease_owner'] != lease.owner or meta['lease_token'] != lease.token
                or meta['fence'] != lease.fence or meta['lease_until'] <= self._now()):
            raise ExecutionError('paper_executor_fenced')
        return meta

    def _reserves(self, db):
        cash, positions = 0, {}
        for row in db.execute('SELECT intent_json,state FROM paper_orders'):
            if row['state'] not in HOLDING:
                continue
            intent = json.loads(row['intent_json'])
            units = intent['lots'] * intent['lot_size']
            # Sell fees are reserved from already observed cash too. No future
            # sale proceeds, partial fills or cancellation requests fund orders.
            cash += intent['fee_bound_nanorub']
            if intent['side'] == 'buy':
                cash += units * intent['limit_nanorub_per_unit']
            else:
                positions[intent['instrument']] = positions.get(intent['instrument'], 0) + units
        return cash, positions

    def initialize_account(self, snapshot: AccountSnapshot):
        data = snapshot.validated()
        if snapshot.scope != self.scope or snapshot.revision != 0 or snapshot.observed_at > self._now():
            raise ExecutionError('paper_initial_snapshot_invalid')
        with self._transaction() as db:
            meta = self._meta(db)
            if meta['snapshot_json'] is not None:
                if json.loads(meta['snapshot_json']) == data:
                    return
                raise ExecutionError('paper_account_already_initialized')
            db.execute('UPDATE paper_meta SET snapshot_json=? WHERE singleton=1', (_json(data),))
            self._event(db, None, 'account_initialized', {'evidence_sha256': snapshot.evidence_sha256})

    def claim(self, owner: str, *, seconds=60) -> Lease:
        _text(owner)
        _integer(seconds, minimum=1, maximum=120)
        with self._transaction() as db:
            meta, now = self._meta(db), self._now()
            if meta['lease_until'] > now:
                raise ExecutionError('paper_executor_already_leased')
            lease = Lease(owner, meta['fence'] + 1, uuid.uuid4().hex)
            db.execute('UPDATE paper_meta SET fence=?,lease_owner=?,lease_token=?,lease_until=? WHERE singleton=1',
                       (lease.fence, lease.owner, lease.token, now + seconds))
            # A new process cannot conclude that a previous dispatch never
            # reached the broker. It must reconcile the existing command ID.
            for row in db.execute("SELECT id FROM paper_orders WHERE state='sending'").fetchall():
                db.execute("UPDATE paper_orders SET state='unknown' WHERE id=?", (row['id'],))
                self._event(db, row['id'], 'dispatch_recovery_required', {'fence': lease.fence})
            self._event(db, None, 'lease_claimed', {'fence': lease.fence})
            return lease

    def renew(self, lease: Lease, *, seconds=60):
        _integer(seconds, minimum=1, maximum=120)
        with self._transaction() as db:
            self._lease(db, lease)
            db.execute('UPDATE paper_meta SET lease_until=? WHERE singleton=1', (self._now() + seconds,))
            self._event(db, None, 'lease_renewed', {'fence': lease.fence})

    def pause(self, paused: bool):
        if type(paused) is not bool:
            raise ExecutionError('paper_pause_boolean_required')
        with self._transaction() as db:
            self._meta(db)
            db.execute('UPDATE paper_meta SET paused=? WHERE singleton=1', (int(paused),))
            self._event(db, None, 'paused' if paused else 'resumed', {})

    def prepare(self, intent: OrderIntent) -> str:
        data = intent.validated()
        if intent.scope != self.scope:
            raise ExecutionError('paper_plan_scope_mismatch')
        encoded, digest = _json(data), _hash(data)
        with self._transaction() as db:
            self._meta(db)
            previous = db.execute('SELECT id,intent_hash FROM paper_orders WHERE request_key=?',
                                  (intent.idempotency_key,)).fetchone()
            if previous:
                if previous['intent_hash'] != digest:
                    raise ExecutionError('paper_idempotency_conflict')
                return previous['id']
            if self._meta(db)['paused']:
                raise ExecutionError('paper_new_orders_paused')
            snapshot = self._snapshot(db)
            if (intent.snapshot_revision != snapshot['revision']
                    or intent.strategy_revision != snapshot['strategy_revision']):
                raise ExecutionError('paper_plan_revision_stale')
            if intent.expires_at <= self._now():
                raise ExecutionError('paper_plan_expired')
            if db.execute('SELECT COUNT(*) FROM paper_orders').fetchone()[0] >= MAX_ORDERS:
                raise ExecutionError('paper_journal_capacity_reached')
            reserved, units = self._reserves(db)
            required = intent.fee_bound_nanorub
            if intent.side == 'buy':
                required += intent.lots * intent.lot_size * intent.limit_nanorub_per_unit
            elif snapshot['available_units'].get(intent.instrument, 0) - units.get(intent.instrument, 0) < intent.lots * intent.lot_size:
                raise ExecutionError('paper_available_position_insufficient')
            if snapshot['cash_nanorub'] - reserved < required:
                raise ExecutionError('paper_observed_cash_insufficient')
            order_id = str(uuid.uuid5(uuid.NAMESPACE_URL, 'analyst-paper:' + self.scope_key + ':' + intent.idempotency_key))
            db.execute("INSERT INTO paper_orders(id,request_key,intent_json,intent_hash,state,created_at) VALUES(?,?,?,?,'reserved',?)",
                       (order_id, intent.idempotency_key, encoded, digest, self._now()))
            self._event(db, order_id, 'reserved', {'intent_sha256': digest})
            return order_id

    def begin_send(self, order_id: str, lease: Lease) -> dict:
        with self._transaction() as db:
            meta = self._lease(db, lease)
            row = self._order(db, order_id)
            if row['state'] != 'reserved' or row['sends'] != 0:
                raise ExecutionError('paper_send_not_repeatable')
            if meta['paused']:
                raise ExecutionError('paper_new_orders_paused')
            if db.execute("SELECT 1 FROM paper_orders WHERE state IN ('sending','unknown','cancelling') LIMIT 1").fetchone():
                raise ExecutionError('paper_unknown_order_reconciliation_required')
            intent, snapshot = json.loads(row['intent_json']), self._snapshot(db)
            if (intent['snapshot_revision'] != snapshot['revision']
                    or intent['strategy_revision'] != snapshot['strategy_revision']):
                raise ExecutionError('paper_plan_revision_stale')
            if intent['expires_at'] <= self._now():
                raise ExecutionError('paper_plan_expired')
            cash, units = self._reserves(db)
            if (cash > snapshot['cash_nanorub'] or any(quantity > snapshot['available_units'].get(uid, 0)
                                                      for uid, quantity in units.items())):
                raise ExecutionError('paper_account_capacity_conflict')
            db.execute("UPDATE paper_orders SET state='sending',sends=1,sent_fence=? WHERE id=?", (lease.fence, order_id))
            command = {'mode': 'simulation', 'order_id': order_id, 'idempotency_key': intent['idempotency_key'],
                       'intent_sha256': row['intent_hash'], 'fence': lease.fence, 'intent': intent}
            self._event(db, order_id, 'send_intent_persisted', {'fence': lease.fence, 'intent_sha256': row['intent_hash']})
            return command

    def uncertain(self, order_id: str, lease: Lease):
        with self._transaction() as db:
            self._lease(db, lease)
            row = self._order(db, order_id)
            if row['state'] not in {'sending', 'unknown'}:
                raise ExecutionError('paper_unknown_transition_invalid')
            db.execute("UPDATE paper_orders SET state='unknown' WHERE id=?", (order_id,))
            self._event(db, order_id, 'send_outcome_unknown', {})

    def request_cancel(self, order_id: str, lease: Lease) -> dict:
        with self._transaction() as db:
            self._lease(db, lease)
            row = self._order(db, order_id)
            if row['state'] == 'reserved':
                db.execute("UPDATE paper_orders SET state='cancelled',terminal_state='cancelled' WHERE id=?", (order_id,))
                self._event(db, order_id, 'unsent_order_cancelled', {})
                return {'mode': 'simulation', 'dispatch_required': False, 'order_id': order_id}
            if row['state'] in TERMINAL or row['state'] == 'awaiting_reconciliation':
                return {'mode': 'simulation', 'dispatch_required': False, 'order_id': order_id}
            db.execute("UPDATE paper_orders SET state='cancelling' WHERE id=?", (order_id,))
            cancel_id = str(uuid.uuid5(uuid.NAMESPACE_URL, 'analyst-paper-cancel:' + order_id))
            self._event(db, order_id, 'cancel_intent_persisted', {'cancel_id': cancel_id})
            return {'mode': 'simulation', 'dispatch_required': True, 'order_id': order_id, 'cancel_id': cancel_id}

    def observe(self, order_id: str, lease: Lease, *, observation_id: str, sequence: int,
                state: str, filled_lots: int, executed_nanorub: int, fee_nanorub: int):
        _text(observation_id)
        for number in (sequence, filled_lots, executed_nanorub, fee_nanorub):
            _integer(number)
        if state not in {'active', 'partial', 'filled', 'cancelled', 'rejected'}:
            raise ExecutionError('paper_broker_state_invalid')
        payload = {'sequence': sequence, 'state': state, 'filled_lots': filled_lots,
                   'executed_nanorub': executed_nanorub, 'fee_nanorub': fee_nanorub}
        digest = _hash(payload)
        with self._transaction() as db:
            self._lease(db, lease)  # Reconciliation deliberately works while paused.
            row = self._order(db, order_id)
            previous = db.execute('SELECT digest FROM paper_observations WHERE order_id=? AND observation_id=?',
                                  (order_id, observation_id)).fetchone()
            if previous:
                if previous['digest'] != digest:
                    raise ExecutionError('paper_observation_identity_conflict')
                return
            if row['sends'] != 1:
                raise ExecutionError('paper_unsent_order_observation')
            if sequence <= row['observed_sequence']:
                raise ExecutionError('paper_observation_sequence_not_new')
            intent = json.loads(row['intent_json'])
            if not row['filled_lots'] <= filled_lots <= intent['lots']:
                raise ExecutionError('paper_cumulative_fill_invalid')
            if executed_nanorub < row['executed_nanorub'] or fee_nanorub < row['fee_nanorub']:
                raise ExecutionError('paper_cumulative_money_decreased')
            if fee_nanorub > intent['fee_bound_nanorub']:
                raise ExecutionError('paper_fee_bound_breached')
            units = filled_lots * intent['lot_size']
            delta_units = (filled_lots - row['filled_lots']) * intent['lot_size']
            delta_value = executed_nanorub - row['executed_nanorub']
            if delta_units == 0 and delta_value != 0:
                raise ExecutionError('paper_fill_value_changed_without_new_fill')
            if delta_units > 0 and (delta_value == 0 or intent['side'] == 'buy' and delta_value > delta_units * intent['limit_nanorub_per_unit']
                    or intent['side'] == 'sell' and delta_value < delta_units * intent['limit_nanorub_per_unit']):
                raise ExecutionError('paper_incremental_limit_price_breached')
            if (filled_lots == 0 and executed_nanorub != 0) or (filled_lots > 0 and executed_nanorub == 0):
                raise ExecutionError('paper_execution_amount_invalid')
            if (intent['side'] == 'buy' and executed_nanorub > units * intent['limit_nanorub_per_unit']
                    or intent['side'] == 'sell' and executed_nanorub < units * intent['limit_nanorub_per_unit']):
                raise ExecutionError('paper_limit_price_breached')
            if (state == 'filled' and filled_lots != intent['lots'] or state == 'rejected' and filled_lots != 0
                    or state == 'cancelled' and filled_lots == intent['lots']
                    or state == 'active' and filled_lots != 0 or state == 'partial' and not 0 < filled_lots < intent['lots']):
                raise ExecutionError('paper_broker_state_fill_conflict')
            terminal = state if state in {'filled', 'cancelled', 'rejected'} else None
            if row['terminal_state'] is not None and (terminal != row['terminal_state']
                    or filled_lots != row['filled_lots'] or executed_nanorub != row['executed_nanorub']
                    or fee_nanorub != row['fee_nanorub']):
                raise ExecutionError('paper_terminal_observation_conflict')
            next_state = 'awaiting_reconciliation' if terminal else state
            if row['state'] == 'cancelling' and terminal is None:
                next_state = 'cancelling'
            if row['state'] in TERMINAL:
                next_state = row['state']
            db.execute('INSERT INTO paper_observations VALUES(?,?,?,?,?)',
                       (order_id, observation_id, digest, _json(payload), self._now()))
            db.execute('''UPDATE paper_orders SET state=?,terminal_state=?,observed_sequence=?,filled_lots=?,
                          executed_nanorub=?,fee_nanorub=?,terminal_observed_at=? WHERE id=?''',
                       (next_state, terminal, sequence, filled_lots, executed_nanorub, fee_nanorub,
                        self._now() if terminal else None, order_id))
            self._event(db, order_id, 'broker_observation', {'observation_id': observation_id, **payload})

    def reconcile_account(self, snapshot: AccountSnapshot, lease: Lease, *, completed_order_ids: list[str]):
        data = snapshot.validated()
        if snapshot.scope != self.scope or snapshot.observed_at > self._now():
            raise ExecutionError('paper_snapshot_scope_or_time_invalid')
        if (not isinstance(completed_order_ids, list) or len(completed_order_ids) > MAX_ORDERS
                or len(set(completed_order_ids)) != len(completed_order_ids)):
            raise ExecutionError('paper_reconciliation_orders_invalid')
        with self._transaction() as db:
            self._lease(db, lease)
            previous = self._snapshot(db)
            if (snapshot.revision != previous['revision'] + 1 or snapshot.observed_at < previous['observed_at']
                    or snapshot.strategy_revision < previous['strategy_revision']):
                raise ExecutionError('paper_snapshot_revision_invalid')
            for order_id in completed_order_ids:
                row = self._order(db, order_id)
                if (row['state'] != 'awaiting_reconciliation' or row['terminal_state'] is None
                        or row['terminal_observed_at'] > snapshot.observed_at):
                    raise ExecutionError('paper_order_not_reconciliable')
                db.execute('UPDATE paper_orders SET state=terminal_state WHERE id=?', (order_id,))
                self._event(db, order_id, 'reservation_released_after_account_reconciliation',
                            {'snapshot_revision': snapshot.revision, 'evidence_sha256': snapshot.evidence_sha256})
            # Any independent account change, including a manual trade, makes
            # unsent plans stale. Already sent orders keep their reservations.
            for row in db.execute("SELECT id FROM paper_orders WHERE state='reserved'").fetchall():
                db.execute("UPDATE paper_orders SET state='invalidated',terminal_state='invalidated' WHERE id=?", (row['id'],))
                self._event(db, row['id'], 'unsent_plan_invalidated_by_account_revision', {'revision': snapshot.revision})
            db.execute('UPDATE paper_meta SET snapshot_json=? WHERE singleton=1', (_json(data),))
            self._event(db, None, 'independent_account_reconciled',
                        {'revision': snapshot.revision, 'evidence_sha256': snapshot.evidence_sha256})

    def status(self) -> dict:
        with self._connection() as db:
            db.execute('BEGIN')
            meta, snapshot = self._meta(db), self._snapshot(db)
            reserved, units = self._reserves(db)
            rows = db.execute('SELECT id,state,terminal_state,sends,filled_lots,observed_sequence FROM paper_orders ORDER BY created_at,id').fetchall()
            return {'mode': 'simulation', 'network_transport': False, 'real_orders_enabled': False,
                    'paused': bool(meta['paused']), 'snapshot_revision': snapshot['revision'],
                    'cash_nanorub': snapshot['cash_nanorub'], 'reserved_nanorub': reserved,
                    'unreserved_nanorub': snapshot['cash_nanorub'] - reserved,
                    'reserved_units': units, 'orders': [dict(row) for row in rows]}

    def verify_event_chain(self) -> bool:
        with self._connection() as db:
            previous = '0' * 64
            for row in db.execute('SELECT * FROM paper_events ORDER BY sequence'):
                if (row['previous_hash'] != previous or row['event_hash'] != _hash(
                        [previous, row['order_id'], row['kind'], row['payload_json'], row['at']])):
                    return False
                previous = row['event_hash']
            return True
