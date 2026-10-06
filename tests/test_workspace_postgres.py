"""Workspace contracts exercised with an isolated schema and a non-bypass role."""

from __future__ import annotations

import os
import secrets
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from omnicio.db import Database
from omnicio.portfolio_store import SettingsVersionConflict
from omnicio.workspace import default_preferences
from omnicio.workspace_store import WorkspaceNotFound, WorkspaceStore

DATABASE_URL = os.environ.get("OMNICIO_TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="ephemeral PostgreSQL is required")
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def workspace_database() -> Iterator[tuple[Database, str, str]]:
    config = conninfo_to_dict(DATABASE_URL)
    assert config.get("host") in {"127.0.0.1", "localhost", "::1"}
    assert config.get("dbname", "").endswith("_test")
    name = "workspace_test_" + secrets.token_hex(6)
    role = name + "_role"
    password = secrets.token_urlsafe(32)
    with psycopg.connect(DATABASE_URL, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(name)))
        admin.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(name)))
        for path in sorted((ROOT / "migrations").glob("*.sql")):
            admin.execute(path.read_text(encoding="utf-8"))
        # The unreleased additive migration has a deterministic retry contract.
        admin.execute((ROOT / "migrations" / "0014_workspace.sql").read_text(encoding="utf-8"))
        admin.execute(
            sql.SQL(
                "CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB "
                "NOCREATEROLE NOREPLICATION NOBYPASSRLS"
            ).format(
                sql.Identifier(role),
                sql.Literal(password),
            )
        )
        admin.execute(
            sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                sql.Identifier(name),
                sql.Identifier(role),
            )
        )
        admin.execute(
            sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {} TO {}").format(
                sql.Identifier(name), sql.Identifier(role)
            )
        )
        admin.execute(
            sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {} TO {}").format(
                sql.Identifier(name),
                sql.Identifier(role),
            )
        )
    config.update(user=role, password=password, options=f"-c search_path={name},public")
    database = Database(make_conninfo(**config))
    database.open()
    try:
        yield database, DATABASE_URL, name
    finally:
        database.close()
        with psycopg.connect(DATABASE_URL, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(name)))
            admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


def user(database: Database, *, account: bool = False) -> UUID:
    ident = uuid4()
    with database.pool.connection() as conn:
        conn.execute("INSERT INTO users (id) VALUES (%s)", (ident,))
        if account:
            conn.execute(
                "INSERT INTO tbank_connection (user_id, environment, account_id, account_name, "
                "token_ciphertext) VALUES (%s, 'prod', %s, 'Test account', %s)",
                (ident, str(ident), b"test-only-encrypted-placeholder"),
            )
    return ident


def goal_document(**changes: Any) -> dict[str, Any]:
    return {
        "title": "Цель пользователя",
        "kind": "capital",
        "target_amount_rub": "100000",
        "start_date": "2026-01-01",
        "target_date": None,
        "progress_source": "manual",
        "allocation_percent": None,
        "manual_amount_rub": "15000",
        "status": "active",
        **changes,
    }


def test_preference_versions_and_goal_crud_are_tenant_isolated(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    store = WorkspaceStore(database)
    owner, other = user(database), user(database)
    initial = store.preferences(owner)
    assert initial == {"version": 0, "document": default_preferences()}
    edited = {**initial["document"], "display_name": "Имя владельца", "mask_balances": True}
    saved = store.save_preferences(owner, edited, expected_version=0)
    assert saved["version"] == 1
    assert store.save_preferences(owner, edited, expected_version=1) == saved
    with pytest.raises(SettingsVersionConflict):
        store.save_preferences(owner, initial["document"], expected_version=0)
    assert store.preferences(other)["version"] == 0

    created = store.create_goal(owner, goal_document())
    ident = UUID(created["id"])
    assert created["progress"]["amount_rub"] == "15000.00000000"
    assert store.goals(other)["items"] == []
    with pytest.raises(WorkspaceNotFound):
        store.update_goal(other, ident, goal_document(), expected_version=1)
    with pytest.raises(SettingsVersionConflict):
        store.update_goal(owner, ident, goal_document(), expected_version=0)
    updated = store.update_goal(owner, ident, goal_document(title="Изменено"), expected_version=1)
    assert updated["version"] == 2
    with pytest.raises(SettingsVersionConflict):
        store.delete_goal(owner, ident, expected_version=1)
    assert store.delete_goal(owner, ident, expected_version=2)
    assert store.goals(owner)["items"] == []


def test_allocation_cannot_double_count_even_under_concurrent_writes(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    store = WorkspaceStore(database)
    owner = user(database, account=True)
    linked = goal_document(
        progress_source="portfolio", allocation_percent="60", manual_amount_rub=None
    )

    def save(index: int) -> dict[str, Any] | str:
        try:
            return store.create_goal(owner, {**linked, "title": f"Цель {index}"})
        except ValueError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(save, (1, 2)))
    assert sum(isinstance(item, dict) for item in results) == 1
    assert "workspace_goal_allocation_exceeds_available" in results
    goal = store.goals(owner)["items"][0]
    assert goal["progress"]["amount_rub"] is None
    assert goal["account_id"] == str(owner)
    with database.pool.connection() as conn:
        conn.execute(
            "UPDATE tbank_connection SET account_id = 'replacement' WHERE user_id = %s", (owner,)
        )
    # An unrelated edit cannot assign the stored capital to a different account.
    edited = store.update_goal(
        owner, UUID(goal["id"]), {**linked, "title": "Новое название"}, expected_version=1
    )
    assert edited["account_id"] == str(owner)
    assert edited["progress"]["reason"] == "linked_account_unavailable"


def test_events_deduplicate_and_read_state_survives_refresh_and_cross_tenant_attempts(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    store = WorkspaceStore(database)
    owner, other = user(database), user(database)
    store.create_goal(owner, goal_document(manual_amount_rub="100000"))
    with database.pool.connection() as conn:
        conn.execute(
            "INSERT INTO audit_events (user_id, event_type) VALUES (%s, 'login_succeeded')",
            (owner,),
        )
    first = store.events(owner)
    second = store.events(owner)
    assert first["unread_count"] == second["unread_count"] == 2
    assert {row["id"] for row in first["items"]} == {row["id"] for row in second["items"]}
    ids = [item["id"] for item in first["items"]]
    with pytest.raises(WorkspaceNotFound):
        store.mark_events_read(other, ids)
    marked = store.mark_events_read(owner, ids)
    assert marked["unread_count"] == 0
    assert store.events(owner, unread_only=True)["items"] == []
    assert store.mark_events_read(owner, ids, read=False)["unread_count"] == 2
    preferences = default_preferences()
    preferences["notifications"]["system"] = False
    store.save_preferences(owner, preferences, expected_version=0)
    filtered = store.events(owner)
    assert filtered["unread_count"] == 1
    assert all(item["category"] == "goals" for item in filtered["items"])
    assert store.dashboard(other)["overview"]["nav_rub"] is None


def test_workspace_database_rls_and_user_cascade_are_enforced(
    workspace_database: tuple[Database, str, str],
) -> None:
    database, admin_url, schema = workspace_database
    owner, other = user(database), user(database)
    store = WorkspaceStore(database)
    store.save_preferences(owner, default_preferences(), expected_version=0)
    store.create_goal(owner, goal_document(manual_amount_rub="100000"))
    store.events(owner)
    with database.pool.connection() as conn:
        for table in ("workspace_preferences", "investment_goals", "workspace_events"):
            assert (
                conn.execute(
                    sql.SQL("SELECT count(*) FROM {} WHERE user_id = %s").format(
                        sql.Identifier(table),
                    ),
                    (owner,),
                ).fetchone()["count"]
                == 0
            )
    with pytest.raises(psycopg.errors.InsufficientPrivilege), database.pool.connection() as conn:
        conn.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(other),))
        conn.execute(
            "INSERT INTO workspace_preferences (user_id, version, document) "
            "VALUES (%s, 1, '{}'::jsonb)",
            (owner,),
        )
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema)))
        enforced = admin.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE relnamespace = %s::regnamespace AND relname = ANY (%s)",
            (schema, ["workspace_preferences", "investment_goals", "workspace_events"]),
        ).fetchall()
        assert len(enforced) == 3 and all(enabled and forced for enabled, forced in enforced)
        admin.execute("DELETE FROM users WHERE id = %s", (owner,))
        for table in ("workspace_preferences", "investment_goals", "workspace_events"):
            assert (
                admin.execute(
                    sql.SQL("SELECT count(*) FROM {} WHERE user_id = %s").format(
                        sql.Identifier(table),
                    ),
                    (owner,),
                ).fetchone()[0]
                == 0
            )


def test_dashboard_uses_latest_operation_correction_and_complete_ledger(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner = user(database, account=True)
    now = datetime.now(UTC)
    begin, end = now - timedelta(days=3), now - timedelta(days=1)
    with database.pool.connection() as conn:
        conn.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(owner),))
        for at, nav in ((begin, "10000"), (end, "10500")):
            conn.execute(
                "INSERT INTO portfolio_snapshots (user_id, account_id, environment, captured_at, "
                "analysis_status, nav_rub, rub_cash_total, rub_cash_blocked, rub_cash_unblocked, "
                "limits_loading_in_progress, evidence) "
                "VALUES (%s, %s, 'prod', %s, 'observed', %s, %s, 0, %s, false, "
                "jsonb_build_object('analysis', '{}'::jsonb, 'account', "
                "jsonb_build_object('opened_at', %s::text)))",
                (owner, str(owner), at, nav, nav, nav, (begin - timedelta(days=10)).isoformat()),
            )
        conn.execute(
            "INSERT INTO broker_sync_state (user_id, account_id, last_complete_watermark) "
            "VALUES (%s, %s, %s)",
            (owner, str(owner), now),
        )
        for index, state in enumerate(("OPERATION_STATE_EXECUTED", "OPERATION_STATE_CANCELED")):
            conn.execute(
                "INSERT INTO operation_observations (user_id, account_id, observation_hash, "
                "semantic_hash, provider_operation_id, operation_date, operation_type, "
                "operation_state, payment_value, payment_currency, normalized, observed_at) "
                "VALUES (%s, %s, %s, %s, 'same-provider-id', %s, 'OPERATION_TYPE_INPUT', %s, "
                "1000, 'RUB', '{}'::jsonb, %s)",
                (
                    owner,
                    str(owner),
                    bytes([index + 1]) * 32,
                    bytes([index + 1]) * 32,
                    begin + timedelta(days=1),
                    state,
                    end + timedelta(minutes=index),
                ),
            )
    dashboard = WorkspaceStore(database).dashboard(owner)
    assert dashboard["performance"]["status"] == "available"
    assert dashboard["performance"]["net_contributions_rub"] == "0"
    assert Decimal(dashboard["performance"]["investment_result_rub"]) == 500
    assert dashboard["performance"]["return_percent"] is None
    assert dashboard["income"]["total_rub"] == "0"

    def insert_coupon(state: str, byte: int) -> None:
        with database.pool.connection() as conn:
            conn.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(owner),))
            conn.execute(
                "INSERT INTO operation_observations (user_id, account_id, observation_hash, "
                "semantic_hash, provider_operation_id, operation_date, operation_type, "
                "operation_state, payment_value, payment_currency, normalized, observed_at) "
                "VALUES (%s, %s, %s, %s, 'corrected-coupon', %s, 'OPERATION_TYPE_COUPON', %s, "
                "300, 'RUB', '{}'::jsonb, %s)",
                (
                    owner,
                    str(owner),
                    bytes([byte]) * 32,
                    bytes([byte]) * 32,
                    begin + timedelta(days=1),
                    state,
                    now - timedelta(minutes=10 - byte),
                ),
            )

    store = WorkspaceStore(database)
    insert_coupon("OPERATION_STATE_EXECUTED", 3)
    paid = next(
        item for item in store.events(owner)["items"] if item["kind"] == "payment_operation"
    )
    store.mark_events_read(owner, [paid["id"]])
    insert_coupon("OPERATION_STATE_CANCELED", 4)
    corrected = [
        item for item in store.events(owner)["items"] if item["kind"] == "payment_operation"
    ]
    assert len(corrected) == 1
    assert corrected[0]["id"] == paid["id"]
    assert corrected[0]["read_at"] is None
    assert corrected[0]["source"]["state"] == "OPERATION_STATE_CANCELED"
    assert store.dashboard(owner)["income"]["total_rub"] == "0"


def test_risk_alerts_survive_unchanged_snapshots_and_notify_actual_state_changes(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner = user(database, account=True)
    store = WorkspaceStore(database)
    start = datetime.now(UTC) - timedelta(days=1)

    def observe(state: str, minute: int) -> list[dict[str, Any]]:
        snapshot_id = uuid4()
        at = start + timedelta(minutes=minute)
        with database.pool.connection() as conn:
            conn.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(owner),))
            conn.execute(
                "INSERT INTO portfolio_snapshots (id, user_id, account_id, environment, "
                "captured_at, analysis_status, nav_rub, rub_cash_total, rub_cash_blocked, "
                "rub_cash_unblocked, limits_loading_in_progress, evidence) "
                "VALUES (%s, %s, %s, 'prod', %s, 'observed', 1000, 0, 0, 0, false, '{}'::jsonb)",
                (snapshot_id, owner, str(owner), at),
            )
            conn.execute(
                "INSERT INTO portfolio_snapshot_positions (snapshot_id, user_id, instrument_uid, "
                "ticker, instrument_type, quantity, blocked, blocked_lots) "
                "VALUES (%s, %s, 'risk-instrument', 'TEST', 'bond', 1, false, 0)",
                (snapshot_id, owner),
            )
            conn.execute(
                "INSERT INTO portfolio_risk_assessments (user_id, snapshot_id, instrument_uid, "
                "state, rating_status, fundamental_status, source_status, reasons, evidence, "
                "assessed_at) VALUES (%s, %s, 'risk-instrument', %s, 'received', "
                "'not_applicable', 'received', '[]'::jsonb, '{}'::jsonb, %s)",
                (owner, snapshot_id, state, at),
            )
        return [item for item in store.events(owner)["items"] if item["kind"] == "instrument_risk"]

    assert observe("normal", 0) == []
    first = observe("watch", 1)[0]
    store.mark_events_read(owner, [first["id"]])
    unchanged = observe("watch", 2)
    assert len(unchanged) == 1 and unchanged[0]["id"] == first["id"]
    assert unchanged[0]["read_at"] is not None
    assert unchanged[0]["occurred_at"] == first["occurred_at"]
    for index, state in enumerate(("critical", "normal", "critical"), start=3):
        changed = observe(state, index)
        assert len(changed) == 1 and changed[0]["id"] == first["id"]
        assert changed[0]["read_at"] is None
        assert changed[0]["source"]["state"] == state
        store.mark_events_read(owner, [first["id"]])
