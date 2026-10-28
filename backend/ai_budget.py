"""Atomic RUB estimates and durable reservations; never a provider billing receipt.

Money is integer micro-RUB. Uncertain calls retain their full reservation across
midnight. Missing prices/zero caps disable paid calls. No network under a DB lock.
"""
from __future__ import annotations

from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Context, Decimal, InvalidOperation, ROUND_CEILING
import sqlite3
import time
from typing import Callable, Iterator

try:
    from .schema_migrations import execute_schema
except ImportError:
    from schema_migrations import execute_schema

Connect = Callable[[], sqlite3.Connection]
MOSCOW = timezone(timedelta(hours=3))
SCALE = 1_000_000
MAX_MONEY = 10**12


class BudgetDenied(RuntimeError):
    pass


def micro_rub(value: str) -> int:
    try:
        amount = Decimal(value)
        if not amount.is_finite() or amount < 0 or amount > MAX_MONEY // SCALE:
            raise ValueError
        # Quantize before scaling: a default-context multiplication can erase
        # a positive fractional micro-RUB before the final upward rounding.
        # The validated maximum has 13 micro-RUB digits; precision 20 suffices
        # for the quantized amount and its exact integer product independently
        # of a caller's decimal precision, exponent limits or rounding mode.
        context = Context(prec=20)
        rounded = amount.quantize(Decimal("0.000001"), rounding=ROUND_CEILING, context=context)
        return int(context.multiply(rounded, SCALE))
    except (InvalidOperation, ValueError, TypeError):
        raise BudgetDenied('ai_budget_invalid_money') from None


def token_cost(input_tokens: int, output_tokens: int, input_rate: int, output_rate: int) -> int:
    """Rates are micro-RUB per million tokens; round the total upwards once."""
    values = (input_tokens, output_tokens, input_rate, output_rate)
    if any(type(v) is not int or v < 0 or v > MAX_MONEY for v in values):
        raise BudgetDenied('ai_budget_invalid_usage')
    numerator = input_tokens * input_rate + output_tokens * output_rate
    result = (numerator + SCALE - 1) // SCALE
    if result > MAX_MONEY:
        raise BudgetDenied('ai_budget_cost_too_large')
    return result


def day_key(at: int) -> str:
    return datetime.fromtimestamp(at, MOSCOW).date().isoformat()


@contextmanager
def transaction(connect: Connect) -> Iterator[sqlite3.Connection]:
    # SQLite commits on normal exit and rolls back even BaseException or a
    # failed commit. closing() then releases the connection on every path.
    with closing(connect()) as db, db:
        db.execute('BEGIN IMMEDIATE')
        yield db


class MoneyLedger:
    def __init__(self, connect: Connect):
        self.connect = connect

    def initialize(self) -> None:
        with transaction(self.connect) as db:
            execute_schema(db, '''
                CREATE TABLE IF NOT EXISTS ai_money_reservations (
                    request_key TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    day_key TEXT NOT NULL,
                    route_id TEXT NOT NULL,
                    model TEXT NOT NULL,
                    ceiling INTEGER NOT NULL CHECK (ceiling >= 0),
                    charge INTEGER NOT NULL CHECK (charge >= 0),
                    state TEXT NOT NULL CHECK (state IN ('reserved','settled','uncertain')),
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ai_money_user_day
                    ON ai_money_reservations(user_id, day_key);
                CREATE INDEX IF NOT EXISTS ai_money_unresolved
                    ON ai_money_reservations(state, day_key);
                CREATE TABLE IF NOT EXISTS ai_route_cooldown (route_id TEXT PRIMARY KEY, until_at INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS ai_money_control (
                    name TEXT PRIMARY KEY,
                    reason TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                );
            ''')

    @staticmethod
    def _spent(db: sqlite3.Connection, day: str, user_id: int | None) -> int:
        clause = '' if user_id is None else ' AND user_id = ?'
        params = (day,) if user_id is None else (day, user_id)
        row = db.execute(
            "SELECT COALESCE(SUM(charge),0) FROM ai_money_reservations "
            "WHERE (day_key = ? OR state IN ('reserved','uncertain'))" + clause, params,
        ).fetchone()
        return int(row[0])

    @staticmethod
    def _monthly_spent(db: sqlite3.Connection, day: str, user_id: int | None) -> int:
        clause = "" if user_id is None else " AND user_id = ?"
        params = (day[:7] + "%",) if user_id is None else (day[:7] + "%", user_id)
        return int(db.execute("SELECT COALESCE(SUM(charge),0) FROM ai_money_reservations "
            "WHERE (day_key LIKE ? OR state IN ('reserved','uncertain'))" + clause, params).fetchone()[0])

    def reserve(self, *, user_id: int, key: str, route: str, model: str,
                ceiling: int, user_cap: int, project_cap: int, at: int | None = None, job: tuple[str, str] | None = None, guard=None,
                user_month_cap: int | None = None, project_month_cap: int | None = None) -> None:
        _validate_reservation(user_id, key, route, model, ceiling, user_cap, project_cap)
        for cap in (user_month_cap, project_month_cap):
            if cap is not None and (type(cap) is not int or not 0 < cap <= MAX_MONEY):
                raise BudgetDenied("ai_monthly_budget_disabled_or_invalid")
        now = int(time.time()) if at is None else at
        day = day_key(now)
        with transaction(self.connect) as db:
            if guard is not None:
                guard(db)
            if job and not db.execute("SELECT 1 FROM ai_work_jobs WHERE id=? AND owner=? AND user_id=? AND status='running' AND cancel_requested_at IS NULL AND expires_at>?", (*job, user_id, now)).fetchone():
                raise BudgetDenied('ai_worker_lease_lost')
            if db.execute("SELECT 1 FROM ai_money_control WHERE name='paused'").fetchone():
                raise BudgetDenied('ai_budget_reconciliation_required')
            if db.execute('SELECT 1 FROM ai_route_cooldown WHERE route_id=? AND until_at>?', (route, now)).fetchone():
                raise BudgetDenied('ai_route_cooling_down')
            if db.execute("SELECT 1 FROM ai_money_reservations WHERE route_id=? AND state='reserved' AND created_at>? LIMIT 1", (route, now - 120)).fetchone():
                raise BudgetDenied('ai_route_in_flight')
            if db.execute('SELECT 1 FROM ai_money_reservations WHERE request_key=?', (key,)).fetchone():
                raise BudgetDenied('ai_budget_duplicate_attempt')
            if self._spent(db, day, user_id) + ceiling > user_cap:
                raise BudgetDenied('ai_user_budget_exhausted')
            if self._spent(db, day, None) + ceiling > project_cap:
                raise BudgetDenied('ai_project_budget_exhausted')
            if user_month_cap is not None and self._monthly_spent(db, day, user_id) + ceiling > user_month_cap:
                raise BudgetDenied('ai_user_monthly_budget_exhausted')
            if project_month_cap is not None and self._monthly_spent(db, day, None) + ceiling > project_month_cap:
                raise BudgetDenied('ai_project_monthly_budget_exhausted')
            db.execute('''INSERT INTO ai_money_reservations
                (request_key,user_id,day_key,route_id,model,ceiling,charge,state,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,'reserved',?,?)''',
                (key, user_id, day, route, model, ceiling, ceiling, now, now))

    def uncertain(self, key: str, *, pause_reason: str | None = None,
                  observed_cost: int | None = None) -> None:
        # This is a conservative priced observation, never a provider invoice.
        # Validate before writing: invalid evidence cannot partially change state.
        if observed_cost is not None and (type(observed_cost) is not int or not 0 <= observed_cost <= MAX_MONEY):
            raise BudgetDenied('ai_budget_invalid_usage')
        if pause_reason and pause_reason not in {'model_mismatch', 'usage_over_ceiling', 'unexpected_usage'}:
            raise BudgetDenied('ai_budget_invalid_pause')
        now = int(time.time())
        with transaction(self.connect) as db:
            # Concurrent/late observations can only increase an unresolved amount.
            # Cleanup after settle must not reopen a completed reservation.
            db.execute("UPDATE ai_money_reservations SET state='uncertain',"
                       "charge=MAX(charge,COALESCE(?,charge)),updated_at=? "
                       "WHERE request_key=? AND state IN ('reserved','uncertain')",
                       (observed_cost, now, key))
            if pause_reason:
                db.execute("INSERT OR IGNORE INTO ai_money_control VALUES ('paused',?,?)", (pause_reason, now))

    def settle(self, key: str, *, model: str, cost: int, input_tokens: int,
               output_tokens: int) -> bool:
        if any(type(v) is not int or v < 0 or v > MAX_MONEY for v in (cost, input_tokens, output_tokens)):
            self.uncertain(key, pause_reason='unexpected_usage')
            return False
        now = int(time.time())
        with transaction(self.connect) as db:
            row = db.execute('SELECT model,ceiling,state FROM ai_money_reservations WHERE request_key=?', (key,)).fetchone()
            if row is None:
                raise BudgetDenied('ai_budget_reservation_missing')
            if row[2] != 'reserved':
                return False
            if model != row[0] or cost > row[1]:
                reason = 'model_mismatch' if model != row[0] else 'usage_over_ceiling'
                # If the server reports a greater cost, never conceal the overrun.
                db.execute("UPDATE ai_money_reservations SET state='uncertain',charge=?,updated_at=? WHERE request_key=?",
                           (max(cost, row[1]), now, key))
                db.execute("INSERT OR IGNORE INTO ai_money_control VALUES ('paused',?,?)", (reason, now))
                return False
            db.execute("UPDATE ai_money_reservations SET state='settled',charge=?,input_tokens=?,output_tokens=?,updated_at=? WHERE request_key=?",
                       (cost, input_tokens, output_tokens, now, key))
        return True

    def cool_down(self, route: str, *, at: int | None = None) -> None:
        now = int(time.time()) if at is None else at
        with transaction(self.connect) as db:
            db.execute("INSERT INTO ai_route_cooldown VALUES (?,?) ON CONFLICT(route_id) DO UPDATE SET until_at=MAX(until_at,excluded.until_at)", (route, now + 300))

    def user_summary(self, user_id: int, *, at: int | None = None) -> dict:
        day = day_key(int(time.time()) if at is None else at)
        with closing(self.connect()) as db:
            spent = self._spent(db, day, user_id)
            monthly = self._monthly_spent(db, day, user_id)
            unresolved = db.execute("SELECT COUNT(*) FROM ai_money_reservations WHERE user_id=? AND state IN ('reserved','uncertain')", (user_id,)).fetchone()[0]
            paused = bool(db.execute("SELECT 1 FROM ai_money_control WHERE name='paused'").fetchone())
        return {'day': day, 'timezone': 'Europe/Moscow', 'estimated_and_reserved_rub': _rub_text(spent),
                'month': day[:7], 'monthly_estimated_and_reserved_rub': _rub_text(monthly),
                'unresolved_attempts': unresolved, 'paid_calls_paused': paused, 'provider_invoice_reconciled': False}


def _validate_reservation(user_id, key, route, model, ceiling, user_cap, project_cap):
    values = (ceiling, user_cap, project_cap)
    if any(type(v) is not int or not 0 < v <= MAX_MONEY for v in values):
        raise BudgetDenied('ai_budget_disabled_or_invalid')
    if type(user_id) is not int or user_id <= 0 or not _bounded_label(key, 180):
        raise BudgetDenied('ai_budget_invalid_identity')
    if not _bounded_label(route, 200) or not _bounded_label(model, 200):
        raise BudgetDenied('ai_budget_invalid_route')


def _rub_text(value: int) -> str:
    """Format integer micro-RUB exactly, independent of caller Decimal settings."""
    whole, fraction = divmod(value, SCALE)
    if fraction == 0:
        return str(whole)
    return f"{whole}.{fraction:06d}".rstrip('0')


def _bounded_label(value, limit: int) -> bool:
    return isinstance(value, str) and 0 < len(value) <= limit
