"""Tenant-scoped workspace persistence; no provider writes or network access.

Goals and preferences survive disconnecting a broker. Their account bindings do
not silently switch to another account, and incomplete evidence stays unavailable.
"""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID
from zoneinfo import ZoneInfo

from .db import Database, live_execution_lock_key
from .goal_planning import goal_forecast, normalize_goal_plan
from .portfolio_store import SettingsVersionConflict
from .workspace import (
    CATEGORIES,
    GOAL_FIELDS,
    amount,
    cashflow_summary,
    decimal_text,
    default_preferences,
    event_digest,
    event_id,
    goal_progress,
    normalize_goal,
    normalize_preferences,
    portfolio_performance,
    quiet_now,
    timestamp,
)

_MAX_GOALS = 50
_MAX_OPERATIONS = 50_000
_MAX_HISTORY_POINTS = 366
_HISTORY_PERIOD_DAYS = {"1d": 1, "1w": 7, "1m": 31, "3m": 93, "1y": 365}
_FINANCIAL_AGE = timedelta(hours=36)
_EVENT_ID_PATTERN = r"[0-9a-f]{64}"
_ACTIVITY = {
    "account_created": "Аккаунт создан",
    "login_succeeded": "Выполнен вход в аккаунт",
    "tbank_connected": "Брокерский счёт подключён",
    "tbank_disconnected": "Брокерский счёт отключён",
    "investment_profile_saved": "Инвестиционные условия сохранены",
    "balancing_policy_saved": "Ограничения портфеля сохранены",
    "support_sessions_revoked": "Сессии аккаунта отозваны",
    "session_revoked": "Выбранная сессия завершена",
    "other_sessions_revoked": "Другие сессии аккаунта завершены",
    "identity_unlinked": "Способ входа отвязан",
}
_RISK_LABELS = {
    "normal": "обычная оценка по доступным данным",
    "data_missing": "недостаточно данных для оценки риска",
    "watch": "требует наблюдения",
    "elevated": "повышенный риск",
    "critical": "критический риск",
    "confirmed_default": "подтверждённый дефолт",
}


class WorkspaceNotFound(LookupError):
    """The requested owner-bound object does not exist."""


@dataclass(frozen=True, slots=True)
class _Basis:
    connection: dict[str, Any] | None
    latest: dict[str, Any] | None
    operations: list[dict[str, Any]]
    watermark: datetime | None
    complete: bool


@dataclass(frozen=True, slots=True)
class _History:
    snapshots: list[dict[str, Any]]
    performance_snapshots: list[dict[str, Any]]
    coverage: dict[str, Any]


def _version(expected: int, actual: int) -> None:
    if type(expected) is not int or expected < 0:
        raise ValueError("workspace_version_invalid")
    if expected != actual:
        raise SettingsVersionConflict("settings_version_conflict")


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def _event_cursor(value: str | None) -> tuple[datetime | None, str | None, int | None]:
    if value is None:
        return None, None, None
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,512}", value):
        raise ValueError("workspace_event_cursor_invalid")
    try:
        decoded = json.loads(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))
        if not isinstance(decoded, list) or len(decoded) != 3:
            raise ValueError("workspace_event_cursor_invalid")
        at, ident, ceiling = decoded
        parsed = timestamp(at)
        if (parsed is None or not isinstance(ident, str)
                or re.fullmatch(_EVENT_ID_PATTERN, ident) is None
                or type(ceiling) is not int or not 0 <= ceiling < 2**63):
            raise ValueError("workspace_event_cursor_invalid")
        return parsed, ident, ceiling
    except (ValueError, TypeError) as exc:
        raise ValueError("workspace_event_cursor_invalid") from exc


def _event_record(row: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(row)
    source = result["source"]
    destination: dict[str, str] = {
        "view": {"overview": "home", "income": "analytics"}.get(
            result["target"], result["target"],
        ),
    }
    uid = source.get("instrument_uid")
    if isinstance(uid, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", uid):
        destination = {"view": "asset", "uid": uid}
    elif source.get("goal_id"):
        try:
            goal = str(UUID(str(source["goal_id"])))
            destination = {"view": "goals", "goal_id": goal}
        except ValueError:
            pass
    result["destination"] = destination
    return result


class WorkspaceStore:
    def __init__(self, database: Database) -> None:
        self.database = database

    @contextmanager
    def _transaction(self, user_id: UUID) -> Iterator[Any]:
        with self.database.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            # Same short transaction lock as broker replacement/deletion. No I/O
            # outside PostgreSQL is held under it, including for dashboard reads.
            cur.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (live_execution_lock_key(user_id),),
            )
            cur.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(user_id),))
            cur.execute(
                "SELECT id FROM users WHERE id = %s AND status = 'active' FOR SHARE", (user_id,)
            )
            if cur.fetchone() is None:
                raise WorkspaceNotFound("workspace_user_unavailable")
            yield cur

    @staticmethod
    def _preferences(cur: Any, user_id: UUID) -> dict[str, Any]:
        cur.execute(
            "SELECT version, document FROM workspace_preferences WHERE user_id = %s", (user_id,)
        )
        row = cur.fetchone()
        if row is None:
            return {"version": 0, "document": default_preferences()}
        return {"version": row["version"], "document": normalize_preferences(row["document"])}

    def preferences(self, user_id: UUID) -> dict[str, Any]:
        with self._transaction(user_id) as cur:
            return self._preferences(cur, user_id)

    def save_preferences(
        self,
        user_id: UUID,
        document: object,
        *,
        expected_version: int,
    ) -> dict[str, Any]:
        validated = normalize_preferences(document)
        with self._transaction(user_id) as cur:
            existing = self._preferences(cur, user_id)
            _version(expected_version, existing["version"])
            if existing["version"] and existing["document"] == validated:
                return existing
            version = existing["version"] + 1
            cur.execute(
                "INSERT INTO workspace_preferences (user_id, version, document) "
                "VALUES (%s, %s, %s::jsonb) ON CONFLICT (user_id) DO UPDATE SET "
                "version = EXCLUDED.version, document = EXCLUDED.document, updated_at = now()",
                (user_id, version, _json(validated)),
            )
            return {"version": version, "document": validated}

    @staticmethod
    def _connection(cur: Any, user_id: UUID) -> dict[str, Any] | None:
        cur.execute(
            "SELECT account_id, account_name, environment, verified_at "
            "FROM tbank_connection WHERE user_id = %s",
            (user_id,),
        )
        row = cur.fetchone()
        return dict(row) if row is not None else None

    def _basis(self, cur: Any, user_id: UUID) -> _Basis:
        connection = self._connection(cur, user_id)
        if connection is None:
            return _Basis(None, None, [], None, False)
        account_id, environment = connection["account_id"], connection["environment"]
        cur.execute(
            "SELECT id, captured_at, analysis_status, nav_rub, rub_cash_total, "
            "rub_cash_blocked, rub_cash_unblocked, evidence FROM portfolio_snapshots "
            "WHERE user_id = %s AND account_id = %s AND environment = %s "
            "ORDER BY captured_at DESC, created_at DESC, id DESC LIMIT 1",
            (user_id, account_id, environment),
        )
        snapshot = cur.fetchone()
        cur.execute(
            "SELECT last_complete_watermark, pending_cursor FROM broker_sync_state "
            "WHERE user_id = %s AND account_id = %s",
            (user_id, account_id),
        )
        state = cur.fetchone()
        watermark = timestamp(state["last_complete_watermark"]) if state is not None else None
        cur.execute(
            "SELECT * FROM (SELECT DISTINCT ON (CASE WHEN provider_operation_id <> '' "
            "THEN provider_operation_id ELSE encode(semantic_hash, 'hex') END) "
            "id, provider_operation_id, operation_date, operation_type, operation_state, "
            "instrument_uid, payment_value, payment_currency, observed_at "
            "FROM operation_observations WHERE user_id = %s AND account_id = %s "
            "ORDER BY CASE WHEN provider_operation_id <> '' THEN provider_operation_id "
            "ELSE encode(semantic_hash, 'hex') END, observed_at DESC, id DESC) AS latest "
            "ORDER BY operation_date DESC, id DESC LIMIT %s",
            (user_id, account_id, _MAX_OPERATIONS + 1),
        )
        operations = [dict(row) for row in cur.fetchall()]
        complete = bool(
            state is not None
            and watermark is not None
            and not state["pending_cursor"]
            and len(operations) <= _MAX_OPERATIONS
        )
        return _Basis(connection, dict(snapshot) if snapshot is not None else None,
                      operations[:_MAX_OPERATIONS], watermark, complete)

    @staticmethod
    def _history(
        cur: Any, user_id: UUID, basis: _Basis, *, period: str,
        from_at: datetime | None, now: datetime,
    ) -> _History:
        coverage: dict[str, Any] = {
            "status": "empty", "period": period,
            "requested_from": from_at.isoformat() if from_at is not None else None,
            "requested_to": now.isoformat(),
            "available_from": None, "available_to": None,
            "total_stored_observations": 0, "total_observations": 0,
            "returned_observations": 0, "returned_from": None, "returned_to": None,
            "sampling": "all_observations", "max_points": _MAX_HISTORY_POINTS,
        }
        if basis.connection is None:
            return _History([], [], coverage)
        # One materialized source, one MVCC statement snapshot for chart points,
        # exact financial endpoints and coverage. Only bounded minimal rows leave
        # PostgreSQL; a long account history never loads full evidence documents.
        cur.execute(
            "WITH source AS MATERIALIZED ("
            "SELECT id, captured_at, created_at, analysis_status, nav_rub::text AS nav_rub "
            "FROM portfolio_snapshots "
            "WHERE user_id = %(user)s AND account_id = %(account)s "
            "AND environment = %(environment)s), "
            "selected AS MATERIALIZED (SELECT * FROM source WHERE captured_at <= %(to)s "
            "AND (%(from)s::timestamptz IS NULL OR captured_at >= %(from)s::timestamptz)), "
            "ranked AS (SELECT selected.*, "
            "row_number() OVER (ORDER BY captured_at, created_at, id) AS ordinal, "
            "count(*) OVER () AS total, min(captured_at) OVER () AS first_at, "
            "max(captured_at) OVER () AS last_at FROM selected), "
            "bucketed AS (SELECT ranked.*, CASE WHEN total <= %(limit)s THEN ordinal "
            "ELSE COALESCE(floor(extract(epoch FROM (captured_at - first_at)) / "
            "NULLIF(extract(epoch FROM (last_at - first_at)), 0) * (%(limit)s - 2))::bigint, 0) "
            "END AS bucket FROM ranked), "
            "sample AS ((SELECT id, captured_at, created_at, analysis_status, nav_rub "
            "FROM bucketed WHERE ordinal = 1) UNION "
            "(SELECT DISTINCT ON (bucket) id, captured_at, created_at, analysis_status, nav_rub "
            "FROM bucketed ORDER BY bucket, captured_at DESC, created_at DESC, id DESC)), "
            "covered AS MATERIALIZED (SELECT * FROM selected "
            "WHERE analysis_status = 'observed' AND captured_at <= %(watermark)s), "
            "endpoints AS ((SELECT * FROM covered ORDER BY captured_at, created_at, id LIMIT 1) "
            "UNION (SELECT * FROM covered "
            "ORDER BY captured_at DESC, created_at DESC, id DESC LIMIT 1)) "
            "SELECT (SELECT jsonb_agg(to_jsonb(sample) - 'created_at' "
            "ORDER BY captured_at, created_at, id) FROM sample) AS snapshots, "
            "(SELECT jsonb_agg(to_jsonb(endpoints) - 'created_at' "
            "ORDER BY captured_at, created_at, id) FROM endpoints) AS performance_snapshots, "
            "(SELECT count(*) FROM source) AS stored_total, "
            "(SELECT min(captured_at) FROM source) AS available_from, "
            "(SELECT max(captured_at) FROM source) AS available_to, "
            "(SELECT count(*) FROM selected) AS total",
            {"user": user_id, "account": basis.connection["account_id"],
             "environment": basis.connection["environment"], "from": from_at,
             "to": now, "watermark": basis.watermark, "limit": _MAX_HISTORY_POINTS},
        )
        row = cur.fetchone()
        snapshots = row["snapshots"] or []
        sampled = row["total"] > _MAX_HISTORY_POINTS
        coverage_status = "empty"
        if snapshots:
            coverage_status = "sampled" if sampled else "complete"
        coverage.update(
            status=coverage_status,
            available_from=(row["available_from"].isoformat()
                            if row["available_from"] is not None else None),
            available_to=(row["available_to"].isoformat()
                          if row["available_to"] is not None else None),
            total_stored_observations=row["stored_total"], total_observations=row["total"],
            returned_observations=len(snapshots),
            returned_from=snapshots[0]["captured_at"] if snapshots else None,
            returned_to=snapshots[-1]["captured_at"] if snapshots else None,
            sampling="time_bucket_last" if sampled else "all_observations",
        )
        return _History(snapshots, row["performance_snapshots"] or [], coverage)

    @staticmethod
    def _goal_rows(cur: Any, user_id: UUID) -> list[dict[str, Any]]:
        cur.execute(
            "SELECT * FROM investment_goals WHERE user_id = %s "
            "ORDER BY CASE status WHEN 'active' THEN 0 WHEN 'completed' THEN 1 ELSE 2 END, "
            "target_date NULLS LAST, created_at, id",
            (user_id,),
        )
        return [dict(row) for row in cur.fetchall()]

    @staticmethod
    def _goal(row: Mapping[str, Any], basis: _Basis, now: datetime) -> dict[str, Any]:
        result = dict(row)
        result.pop("user_id", None)
        for key in ("target_amount_rub", "allocation_percent", "manual_amount_rub"):
            result[key] = decimal_text(amount(result[key])) if result[key] is not None else None
        for key in ("target_date", "start_date", "created_at", "updated_at"):
            result[key] = result[key].isoformat() if result[key] is not None else None
        result["id"] = str(result["id"])
        result["progress"] = goal_progress(
            result,
            connection=basis.connection,
            snapshot=basis.latest,
            operations=basis.operations,
            watermark=basis.watermark,
            history_complete=basis.complete,
            now=now,
        )
        return result

    def goals(self, user_id: UUID) -> dict[str, Any]:
        now = datetime.now(UTC)
        with self._transaction(user_id) as cur:
            basis = self._basis(cur, user_id)
            return {"items": [self._goal(row, basis, now) for row in self._goal_rows(cur, user_id)]}

    def goal_plan(self, user_id: UUID, goal_id: UUID) -> dict[str, Any]:
        now = datetime.now(UTC)
        with self._transaction(user_id) as cur:
            cur.execute("SELECT * FROM investment_goals WHERE user_id = %s AND id = %s",
                        (user_id, goal_id))
            row = cur.fetchone()
            if row is None:
                raise WorkspaceNotFound("workspace_goal_not_found")
            goal = self._goal(row, self._basis(cur, user_id), now)
            cur.execute("SELECT version, document, updated_at FROM goal_plans "
                        "WHERE user_id = %s AND goal_id = %s", (user_id, goal_id))
            plan = cur.fetchone()
            saved = dict(plan) if plan else {"version": 0, "document": None, "updated_at": None}
        return {**saved, "goal_id": str(goal_id), "goal_version": goal["version"],
                "forecast": goal_forecast(
                    goal, saved["document"], today=now.astimezone(ZoneInfo("Europe/Moscow")).date(),
                )
                if saved["document"] else None}

    def save_goal_plan(
        self, user_id: UUID, goal_id: UUID, document: object, *,
        expected_version: int, expected_goal_version: int,
    ) -> dict[str, Any]:
        normalized = normalize_goal_plan(document)
        with self._transaction(user_id) as cur:
            cur.execute("SELECT version FROM investment_goals WHERE user_id = %s "
                        "AND id = %s FOR UPDATE", (user_id, goal_id))
            row = cur.fetchone()
            if row is None:
                raise WorkspaceNotFound("workspace_goal_not_found")
            _version(expected_goal_version, row["version"])
            cur.execute("SELECT version FROM goal_plans WHERE user_id = %s AND goal_id = %s",
                        (user_id, goal_id))
            existing = cur.fetchone()
            _version(expected_version, existing["version"] if existing else 0)
            cur.execute("INSERT INTO goal_plans (user_id, goal_id, version, document) "
                        "VALUES (%s, %s, 1, %s::jsonb) ON CONFLICT (user_id, goal_id) "
                        "DO UPDATE SET version = goal_plans.version + 1, "
                        "document = EXCLUDED.document, updated_at = now()",
                        (user_id, goal_id, _json(normalized)))
        return self.goal_plan(user_id, goal_id)

    def _goal_binding(
        self,
        cur: Any,
        user_id: UUID,
        goal: Mapping[str, Any],
        *,
        exclude: UUID | None = None,
        previous: Mapping[str, Any] | None = None,
    ) -> tuple[str | None, str | None]:
        if goal["progress_source"] == "manual":
            return None, None
        connection = (
            previous
            if previous is not None and previous["progress_source"] == goal["progress_source"]
            else self._connection(cur, user_id)
        )
        if connection is None:
            raise ValueError("workspace_goal_broker_required")
        account_id, environment = str(connection["account_id"]), str(connection["environment"])
        if goal["status"] == "active":
            cur.execute(
                "SELECT COALESCE(sum(allocation_percent), 0) AS allocated "
                "FROM investment_goals WHERE user_id = %s AND status = 'active' "
                "AND progress_source = %s AND account_id = %s AND environment = %s "
                "AND (%s::uuid IS NULL OR id <> %s::uuid)",
                (user_id, goal["progress_source"], account_id, environment, exclude, exclude),
            )
            allocated = amount(cur.fetchone()["allocated"])
            if allocated + amount(goal["allocation_percent"]) > 100:
                raise ValueError("workspace_goal_allocation_exceeds_available")
        return account_id, environment

    def create_goal(self, user_id: UUID, document: object) -> dict[str, Any]:
        goal = normalize_goal(document)
        now = datetime.now(UTC)
        with self._transaction(user_id) as cur:
            cur.execute(
                "SELECT count(*) AS total FROM investment_goals WHERE user_id = %s", (user_id,)
            )
            if cur.fetchone()["total"] >= _MAX_GOALS:
                raise ValueError("workspace_goal_limit")
            account_id, environment = self._goal_binding(cur, user_id, goal)
            cur.execute(
                "INSERT INTO investment_goals (user_id, version, title, kind, target_amount_rub, "
                "target_date, start_date, progress_source, allocation_percent, manual_amount_rub, "
                "status, account_id, environment) "
                "VALUES (%s, 1, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
                (user_id, *(goal[key] for key in GOAL_FIELDS), account_id, environment),
            )
            row = dict(cur.fetchone())
            return self._goal(row, self._basis(cur, user_id), now)

    def update_goal(
        self,
        user_id: UUID,
        goal_id: UUID,
        document: object,
        *,
        expected_version: int,
    ) -> dict[str, Any]:
        goal = normalize_goal(document)
        now = datetime.now(UTC)
        with self._transaction(user_id) as cur:
            cur.execute(
                "SELECT * FROM investment_goals WHERE user_id = %s AND id = %s FOR UPDATE",
                (user_id, goal_id),
            )
            existing = cur.fetchone()
            if existing is None:
                raise WorkspaceNotFound("workspace_goal_not_found")
            _version(expected_version, existing["version"])
            account_id, environment = self._goal_binding(
                cur,
                user_id,
                goal,
                exclude=goal_id,
                previous=existing,
            )
            cur.execute(
                "UPDATE investment_goals SET version = version + 1, title = %s, kind = %s, "
                "target_amount_rub = %s, target_date = %s, start_date = %s, progress_source = %s, "
                "allocation_percent = %s, manual_amount_rub = %s, status = %s, account_id = %s, "
                "environment = %s, updated_at = now() WHERE user_id = %s AND id = %s RETURNING *",
                (*(goal[key] for key in GOAL_FIELDS), account_id, environment, user_id, goal_id),
            )
            row = dict(cur.fetchone())
            return self._goal(row, self._basis(cur, user_id), now)

    def delete_goal(self, user_id: UUID, goal_id: UUID, *, expected_version: int) -> bool:
        with self._transaction(user_id) as cur:
            cur.execute(
                "SELECT version FROM investment_goals WHERE user_id = %s AND id = %s",
                (user_id, goal_id),
            )
            row = cur.fetchone()
            if row is None:
                raise WorkspaceNotFound("workspace_goal_not_found")
            _version(expected_version, row["version"])
            cur.execute(
                "DELETE FROM workspace_events WHERE user_id = %s AND source ->> 'goal_id' = %s",
                (user_id, str(goal_id)),
            )
            cur.execute(
                "DELETE FROM investment_goals WHERE user_id = %s AND id = %s", (user_id, goal_id)
            )
            return True

    @staticmethod
    def _overview(basis: _Basis, history: _History, now: datetime) -> dict[str, Any]:
        latest = basis.latest
        result: dict[str, Any] = {
            "status": "pending" if basis.connection else "not_connected",
            "nav_rub": None,
            "cash_rub": None,
            "blocked_cash_rub": None,
            "free_cash_rub": None,
            "observed_at": None,
            "history": [
                {"captured_at": row["captured_at"], "nav_rub": row["nav_rub"],
                 "status": row["analysis_status"]}
                for row in history.snapshots
            ],
            "history_coverage": history.coverage,
            "basis": "latest_observation",
            "allocations": [],
        }
        if latest is None:
            return result
        captured_at = timestamp(latest["captured_at"])
        state = "observed" if latest["analysis_status"] == "observed" else "partial"
        if captured_at is None or captured_at > now:
            state = "partial"
        elif now - captured_at > _FINANCIAL_AGE:
            state = "stale"
        analysis = latest["evidence"].get("analysis", {})
        return {
            **result,
            "status": state,
            "nav_rub": decimal_text(amount(latest["nav_rub"])),
            "cash_rub": decimal_text(amount(latest["rub_cash_total"])),
            "blocked_cash_rub": decimal_text(amount(latest["rub_cash_blocked"])),
            "free_cash_rub": decimal_text(amount(latest["rub_cash_unblocked"]))
            if latest["rub_cash_unblocked"] is not None
            else None,
            "observed_at": captured_at.isoformat() if captured_at is not None else None,
            "allocations": analysis.get("classes", []),
        }

    @staticmethod
    def _income(
        basis: _Basis, now: datetime, *, from_at: datetime | None = None,
    ) -> dict[str, Any]:
        latest = basis.latest
        opened_at = (
            timestamp(latest["evidence"].get("account", {}).get("opened_at"))
            if latest is not None
            else None
        )
        if opened_at is None or basis.watermark is None:
            return {
                "status": "unavailable",
                "reason": "history_incomplete",
                "from": None,
                "to": None,
                "coupons_rub": None,
                "dividends_rub": None,
                "other_income_rub": None,
                "total_rub": None,
                "redemptions_rub": None,
                "by_month": [],
            }
        end = min(basis.watermark, now)
        start = max(opened_at - timedelta(microseconds=1), from_at) if from_at else (
            opened_at - timedelta(microseconds=1)
        )
        return cast(
            dict[str, Any],
            cashflow_summary(
                basis.operations,
                from_at=start,
                to_at=end,
                complete=basis.complete and start <= end,
            )["income"],
        )

    @staticmethod
    def _insert_event(
        cur: Any,
        user_id: UUID,
        *,
        identity: object,
        category: str,
        kind: str,
        title: str,
        occurred_at: object,
        detail: str = "",
        severity: str = "info",
        target: str = "overview",
        source: Mapping[str, object],
    ) -> None:
        at = timestamp(occurred_at)
        if at is None:
            return
        cur.execute(
            "INSERT INTO workspace_events (user_id, id, category, kind, severity, title, detail, "
            "occurred_at, target, source) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb) "
            "ON CONFLICT (user_id, id) DO UPDATE SET title = EXCLUDED.title, "
            "detail = EXCLUDED.detail, severity = EXCLUDED.severity, source = EXCLUDED.source, "
            "revision = CASE WHEN workspace_events.source IS DISTINCT FROM EXCLUDED.source "
            "THEN nextval(pg_get_serial_sequence('workspace_events', 'revision')) "
            "ELSE workspace_events.revision END, "
            "updated_at = CASE WHEN workspace_events.source IS DISTINCT FROM EXCLUDED.source "
            "THEN now() ELSE workspace_events.updated_at END, "
            "read_at = CASE WHEN workspace_events.source IS DISTINCT FROM EXCLUDED.source "
            "THEN NULL ELSE workspace_events.read_at END, "
            "occurred_at = CASE WHEN workspace_events.source IS DISTINCT FROM EXCLUDED.source "
            "THEN EXCLUDED.occurred_at ELSE workspace_events.occurred_at END",
            (
                user_id,
                event_id(kind, identity),
                category,
                kind,
                severity,
                title[:200],
                detail[:1000],
                at,
                target,
                _json(dict(source)),
            ),
        )

    def _sync_events(
        self,
        cur: Any,
        user_id: UUID,
        basis: _Basis,
        goals: Sequence[Mapping[str, Any]],
        now: datetime,
    ) -> None:
        self._activity_events(cur, user_id)
        self._job_events(cur, user_id, now)
        self._goal_events(cur, user_id, goals, now)
        if basis.latest is None:
            return
        snapshot_id = basis.latest["id"]
        self._risk_events(cur, user_id, snapshot_id, basis.connection)
        self._payout_events(cur, user_id, snapshot_id, now)
        account_id = basis.connection["account_id"] if basis.connection else None
        self._payment_events(cur, user_id, basis.operations, account_id, now)

    def _activity_events(self, cur: Any, user_id: UUID) -> None:
        cur.execute(
            "SELECT id, event_type, created_at FROM audit_events WHERE user_id = %s "
            "AND event_type = ANY (%s) ORDER BY created_at DESC, id DESC LIMIT 100",
            (user_id, list(_ACTIVITY)),
        )
        for row in cur.fetchall():
            self._insert_event(
                cur,
                user_id,
                identity=row["id"],
                category="system",
                kind="account_activity",
                title=_ACTIVITY[row["event_type"]],
                occurred_at=row["created_at"],
                target="settings",
                source={"type": "audit", "id": str(row["id"]), "event_type": row["event_type"]},
            )

    def _job_events(self, cur: Any, user_id: UUID, now: datetime) -> None:
        cur.execute(
            "SELECT id, status, scheduled_for, requested_at, finished_at "
            "FROM job_runs WHERE user_id = %s "
            "AND status IN ('degraded', 'failed') AND finished_at >= %s "
            "ORDER BY finished_at DESC, id DESC LIMIT 20",
            (user_id, now - timedelta(days=7)),
        )
        for row in cur.fetchall():
            self._insert_event(
                cur,
                user_id,
                identity=[str(row["id"]), row["status"]],
                category="system",
                kind="synchronization",
                title="Не все данные обновлены"
                if row["status"] == "degraded"
                else "Обновление данных прервано",
                occurred_at=row["finished_at"],
                detail="Проверьте состояние подключения. Неполные данные отмечены в расчётах.",
                severity="warning",
                target="settings",
                source={
                    "type": "job",
                    "id": str(row["id"]),
                    "status": row["status"],
                    "scheduled_for": row["scheduled_for"].isoformat()
                    if row["scheduled_for"] is not None else None,
                    "requested_at": row["requested_at"].isoformat(),
                },
            )

    def _goal_events(
        self, cur: Any, user_id: UUID, goals: Sequence[Mapping[str, Any]], now: datetime,
    ) -> None:
        for goal in goals:
            if goal["status"] != "active":
                continue
            progress = goal["progress"]
            if progress["status"] == "available" and amount(progress["percent"]) >= 100:
                self._insert_event(
                    cur,
                    user_id,
                    identity=[goal["id"], goal["version"]],
                    category="goals",
                    kind="goal_reached",
                    title=f"Цель «{goal['title']}» достигнута",
                    occurred_at=progress["as_of"],
                    target="goals",
                    source={"type": "goal", "goal_id": goal["id"], "version": goal["version"]},
                )
            elif goal["target_date"] is not None:
                due = datetime.fromisoformat(goal["target_date"]).replace(tzinfo=UTC)
                if due <= now + timedelta(days=7):
                    self._insert_event(
                        cur,
                        user_id,
                        identity=[goal["id"], goal["version"], goal["target_date"]],
                        category="goals",
                        kind="goal_due",
                        title=f"Срок цели «{goal['title']}»",
                        detail=f"Плановая дата: {goal['target_date']}",
                        occurred_at=min(now, due),
                        target="goals",
                        source={
                            "type": "goal",
                            "goal_id": goal["id"],
                            "due_date": goal["target_date"],
                        },
                    )

    def _risk_events(
        self, cur: Any, user_id: UUID, snapshot_id: UUID,
        connection: Mapping[str, Any] | None,
    ) -> None:
        account_id = connection["account_id"] if connection else None
        environment = connection["environment"] if connection else None
        cur.execute(
            "SELECT r.instrument_uid, r.state, r.assessed_at, "
            "COALESCE(NULLIF(p.ticker, ''), r.instrument_uid) AS ticker "
            "FROM portfolio_risk_assessments r JOIN portfolio_snapshot_positions p "
            "ON p.snapshot_id = r.snapshot_id AND p.user_id = r.user_id "
            "AND p.instrument_uid = r.instrument_uid "
            "WHERE r.user_id = %s AND r.snapshot_id = %s "
            "AND (r.state IN ('watch', 'elevated', 'critical', 'confirmed_default') "
            "OR EXISTS (SELECT 1 FROM workspace_events e WHERE e.user_id = r.user_id "
            "AND e.kind = 'instrument_risk' AND e.source ->> 'account_id' = %s "
            "AND e.source ->> 'environment' = %s "
            "AND e.source ->> 'instrument_uid' = r.instrument_uid)) "
            "ORDER BY r.assessed_at DESC, r.instrument_uid LIMIT 100",
            (user_id, snapshot_id, account_id, environment),
        )
        for row in cur.fetchall():
            severity = "warning"
            if row["state"] in {"critical", "confirmed_default"}:
                severity = "critical"
            elif row["state"] == "normal":
                severity = "info"
            self._insert_event(
                cur,
                user_id,
                # A new observation of the same risk must not notify again.
                # Changes, including a return to normal, update this alert and
                # clear read_at through the existing source-change contract.
                identity=[account_id, environment, row["instrument_uid"]],
                category="portfolio",
                kind="instrument_risk",
                title="Оценка риска обновлена",
                detail=f"{row['ticker']}: {_RISK_LABELS[row['state']]}",
                occurred_at=row["assessed_at"],
                target="portfolio",
                severity=severity,
                source={
                    "type": "risk",
                    "account_id": account_id,
                    "environment": environment,
                    "instrument_uid": row["instrument_uid"],
                    "state": row["state"],
                },
            )

    def _payment_events(
        self, cur: Any, user_id: UUID, operations: Sequence[Mapping[str, Any]],
        account_id: str | None, now: datetime,
    ) -> None:
        payment_operations = [
            item
            for item in operations
            if item["operation_type"] in {"OPERATION_TYPE_COUPON", "OPERATION_TYPE_DIVIDEND"}
        ]
        for operation in payment_operations[:200]:
            at = timestamp(operation["operation_date"])
            if at is None or at < now - timedelta(days=90):
                continue
            received = operation["operation_state"] == "OPERATION_STATE_EXECUTED"
            title = "Статус выплаты изменён"
            if received:
                title = (
                    "Купон получен"
                    if operation["operation_type"] == "OPERATION_TYPE_COUPON"
                    else "Дивиденды получены"
                )
            self._insert_event(
                cur,
                user_id,
                identity=[
                    account_id,
                    operation["provider_operation_id"] or operation["id"],
                ],
                category="payments",
                kind="payment_operation",
                title=title,
                occurred_at=at,
                detail="Поступление подтверждено исполненной операцией брокера."
                if received
                else "Брокер не подтверждает исполнение этой операции выплаты.",
                target="income",
                source={
                    "type": "operation",
                    "id": str(operation["id"]),
                    "amount": str(operation["payment_value"]),
                    "currency": operation["payment_currency"],
                    "instrument_uid": operation["instrument_uid"],
                    "state": operation["operation_state"],
                },
            )

    def _payout_events(self, cur: Any, user_id: UUID, snapshot_id: UUID, now: datetime) -> None:
        cur.execute(
            "SELECT * FROM (SELECT DISTINCT ON (pe.provider, pe.instrument_uid, pe.event_type, "
            "pe.provider_key) pe.id, pe.instrument_uid, pe.event_type, pe.provider_key, pe.status, "
            "pe.expected_at, pe.amount, pe.currency, sd.source_url, sd.first_retrieved_at "
            "FROM payout_events pe JOIN source_documents sd ON sd.id = pe.source_document_id "
            "WHERE EXISTS (SELECT 1 FROM portfolio_snapshot_positions p WHERE p.user_id = %s "
            "AND p.snapshot_id = %s AND p.instrument_uid = pe.instrument_uid) "
            "ORDER BY pe.provider, pe.instrument_uid, pe.event_type, pe.provider_key, "
            "sd.first_retrieved_at DESC, pe.id DESC) AS current_events "
            "WHERE expected_at >= %s ORDER BY expected_at, id LIMIT 200",
            (user_id, snapshot_id, now - timedelta(days=7)),
        )
        labels = {
            "coupon": "Купон по расписанию",
            "dividend": "Объявлены дивиденды",
            "bond_event": "Событие облигации",
        }
        for row in cur.fetchall():
            self._insert_event(
                cur,
                user_id,
                identity=[row["instrument_uid"], row["event_type"], row["provider_key"]],
                category="payments",
                kind="payout_calendar",
                title=labels[row["event_type"]],
                occurred_at=row["first_retrieved_at"],
                detail="Событие эмитента. Факт зачисления на ваш счёт проверяется по операциям.",
                target="income",
                source={
                    "type": "payout",
                    "id": str(row["id"]),
                    "instrument_uid": row["instrument_uid"],
                    "expected_at": row["expected_at"],
                    "amount_per_security": str(row["amount"])
                    if row["amount"] is not None
                    else None,
                    "currency": row["currency"],
                    "status": row["status"],
                    "url": row["source_url"],
                },
            )

    @staticmethod
    def _events_payload(
        cur: Any,
        user_id: UUID,
        preferences: Mapping[str, Any],
        now: datetime,
        *,
        limit: int = 50,
        unread_only: bool = False,
        category: str = "all",
        cursor: str | None = None,
        query: str = "",
    ) -> dict[str, Any]:
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("workspace_event_limit")
        if category not in (*CATEGORIES, "all") or type(unread_only) is not bool:
            raise ValueError("workspace_event_filter")
        if (not isinstance(query, str) or len(query) > 200
                or any(ord(char) < 32 for char in query)):
            raise ValueError("workspace_event_query_invalid")
        before, before_id, ceiling = _event_cursor(cursor)
        cur.execute(
            "SELECT COALESCE(max(revision), 0) AS revision FROM workspace_events "
            "WHERE user_id = %s", (user_id,),
        )
        current_revision = int(cur.fetchone()["revision"])
        if ceiling is not None and ceiling > current_revision:
            raise ValueError("workspace_event_cursor_invalid")
        ceiling = current_revision if ceiling is None else ceiling
        enabled = [
            key
            for key in CATEGORIES
            if preferences["notifications"][key] and category in {"all", key}
        ]
        cur.execute(
            "SELECT id, category, kind, severity, title, detail, occurred_at, read_at, "
            "target, source, revision "
            "FROM workspace_events WHERE user_id = %s AND category = ANY (%s) "
            "AND (NOT %s OR read_at IS NULL) AND revision <= %s "
            "AND (%s::timestamptz IS NULL OR (occurred_at, id) < (%s, %s)) "
            "AND (%s = '' OR position(lower(%s) IN lower(title || ' ' || detail "
            "|| ' ' || source::text)) > 0) "
            "ORDER BY occurred_at DESC, id DESC LIMIT %s",
            (user_id, enabled, unread_only, ceiling, before, before, before_id,
             query.strip(), query.strip(), limit + 1),
        )
        rows = cur.fetchall()
        items = [_event_record(row) for row in rows[:limit]]
        next_cursor = None
        if len(rows) > limit:
            last = items[-1]
            next_cursor = base64.urlsafe_b64encode(_json([
                last["occurred_at"], last["id"], ceiling,
            ]).encode()).decode().rstrip("=")
        cur.execute(
            "SELECT count(*) AS total FROM workspace_events WHERE user_id = %s "
            "AND category = ANY (%s) AND read_at IS NULL",
            (user_id, enabled),
        )
        unread = int(cur.fetchone()["total"])
        digest = event_digest([], preferences, now)
        if digest["frequency"] != "off":
            cur.execute(
                "SELECT category, count(*) AS total FROM workspace_events WHERE user_id = %s "
                "AND category = ANY (%s) AND read_at IS NULL AND occurred_at >= %s "
                "AND occurred_at <= %s GROUP BY category",
                (user_id, enabled, digest["from"], now),
            )
            for row in cur.fetchall():
                digest["by_category"][row["category"]] = int(row["total"])
            digest["count"] = sum(digest["by_category"].values())
        return {
            "items": items,
            "unread_count": unread,
            "alerts_suppressed": quiet_now(preferences, now),
            "digest": digest,
            "next_cursor": next_cursor,
            "read_all_before": ceiling,
        }

    def events(
        self,
        user_id: UUID,
        *,
        limit: int = 50,
        unread_only: bool = False,
        category: str = "all",
        cursor: str | None = None,
        query: str = "",
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        with self._transaction(user_id) as cur:
            basis = self._basis(cur, user_id)
            goals = [self._goal(row, basis, now) for row in self._goal_rows(cur, user_id)]
            self._sync_events(cur, user_id, basis, goals, now)
            return self._events_payload(
                cur,
                user_id,
                self._preferences(cur, user_id)["document"],
                now,
                limit=limit,
                unread_only=unread_only,
                category=category,
                cursor=cursor,
                query=query,
            )

    def synchronize_events(self, user_id: UUID) -> None:
        """Collect persisted facts even while the owner's browser is closed."""
        now = datetime.now(UTC)
        with self._transaction(user_id) as cur:
            basis = self._basis(cur, user_id)
            goals = [self._goal(row, basis, now) for row in self._goal_rows(cur, user_id)]
            self._sync_events(cur, user_id, basis, goals, now)

    def get_event(self, user_id: UUID, ident: str) -> dict[str, Any]:
        if not isinstance(ident, str) or re.fullmatch(_EVENT_ID_PATTERN, ident) is None:
            raise ValueError("workspace_event_ids_invalid")
        with self._transaction(user_id) as cur:
            cur.execute(
                "SELECT id, category, kind, severity, title, detail, occurred_at, read_at, "
                "target, source, revision FROM workspace_events WHERE user_id = %s AND id = %s",
                (user_id, ident),
            )
            row = cur.fetchone()
            if row is None:
                raise WorkspaceNotFound("workspace_event_not_found")
            return _event_record(row)

    def mark_all_events_read(
        self, user_id: UUID, *, through_revision: int, category: str = "all",
    ) -> dict[str, Any]:
        if (type(through_revision) is not int or not 0 <= through_revision < 2**63
                or category not in (*CATEGORIES, "all")):
            raise ValueError("workspace_event_cutoff_invalid")
        now = datetime.now(UTC)
        with self._transaction(user_id) as cur:
            preferences = self._preferences(cur, user_id)["document"]
            cur.execute(
                "SELECT COALESCE(max(revision), 0) AS revision FROM workspace_events "
                "WHERE user_id = %s", (user_id,),
            )
            if through_revision > int(cur.fetchone()["revision"]):
                raise ValueError("workspace_event_cutoff_invalid")
            enabled = [key for key in CATEGORIES
                       if preferences["notifications"][key] and category in {"all", key}]
            cur.execute(
                "UPDATE workspace_events SET read_at = %s WHERE user_id = %s "
                "AND category = ANY (%s) AND read_at IS NULL AND revision <= %s",
                (now, user_id, enabled, through_revision),
            )
            return self._events_payload(cur, user_id, preferences, now, category=category)

    def mark_events_read(
        self,
        user_id: UUID,
        ids: Sequence[str],
        *,
        read: bool = True,
    ) -> dict[str, Any]:
        if (
            isinstance(ids, (str, bytes))
            or not 1 <= len(ids) <= 200
            or type(read) is not bool
            or any(
                not isinstance(value, str) or re.fullmatch(_EVENT_ID_PATTERN, value) is None
                for value in ids
            )
            or len(set(ids)) != len(ids)
        ):
            raise ValueError("workspace_event_ids_invalid")
        now = datetime.now(UTC)
        with self._transaction(user_id) as cur:
            cur.execute(
                "SELECT count(*) AS total FROM workspace_events "
                "WHERE user_id = %s AND id = ANY (%s)",
                (user_id, list(ids)),
            )
            if cur.fetchone()["total"] != len(ids):
                raise WorkspaceNotFound("workspace_event_not_found")
            cur.execute(
                "UPDATE workspace_events SET read_at = CASE WHEN %s THEN COALESCE(read_at, %s) "
                "ELSE NULL END WHERE user_id = %s AND id = ANY (%s)",
                (read, now, user_id, list(ids)),
            )
            return self._events_payload(
                cur, user_id, self._preferences(cur, user_id)["document"], now
            )

    def dashboard(self, user_id: UUID, *, history_period: str = "all") -> dict[str, Any]:
        if history_period != "all" and history_period not in _HISTORY_PERIOD_DAYS:
            raise ValueError("workspace_history_period_invalid")
        now = datetime.now(UTC)
        from_at = (now - timedelta(days=_HISTORY_PERIOD_DAYS[history_period])
                   if history_period != "all" else None)
        with self._transaction(user_id) as cur:
            basis = self._basis(cur, user_id)
            history = self._history(
                cur, user_id, basis, period=history_period, from_at=from_at, now=now,
            )
            preferences = self._preferences(cur, user_id)
            goals = [self._goal(row, basis, now) for row in self._goal_rows(cur, user_id)]
            self._sync_events(cur, user_id, basis, goals, now)
            return {
                "generated_at": now.isoformat(),
                "connection": {
                    "connected": basis.connection is not None,
                    **(
                        basis.connection
                        or {
                            "account_id": None,
                            "account_name": None,
                            "environment": None,
                        }
                    ),
                },
                "overview": self._overview(basis, history, now),
                "performance": {
                    **portfolio_performance(
                        history.performance_snapshots, basis.operations,
                        watermark=basis.watermark, history_complete=basis.complete,
                    ),
                    "period": history_period,
                    "requested_from": history.coverage["requested_from"],
                    "requested_to": history.coverage["requested_to"],
                },
                "income": {**self._income(basis, now, from_at=from_at), "period": history_period},
                "goals": {"items": goals},
                "preferences": preferences,
                "events": self._events_payload(cur, user_id, preferences["document"], now),
            }
