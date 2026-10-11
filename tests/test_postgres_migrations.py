from __future__ import annotations

import copy
import hashlib
import importlib
import json
import os
import re
import secrets
import subprocess
from contextlib import nullcontext
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from omnicio.db import Database
from omnicio.portfolio_store import PortfolioStore
from omnicio.schema import READINESS_QUERY

DATABASE_URL = os.environ.get("OMNICIO_TEST_DATABASE_URL", "")

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = tuple(sorted((ROOT / "migrations").glob("*.sql")))
ACCEPTED_MIGRATION_SHA256 = {
    "0001_phone_auth.sql": ("b92bc06b42cf837cf15d6688edd0ed6b32afabb6ef645b271ca5db6e4a766796"),
    "0002_tbank_connection.sql": (
        "bd48f5bd0ce75abf43606005e40d72869b2881d4c7519af1f2fe9f17fcfe89d8"
    ),
    "0003_vkid_owner_identity.sql": (
        "df8d27cd03820a0ef62dcf2008a12aa0443791161061532a1d0412961e46d710"
    ),
    "0004_user_role.sql": ("fa57fd62d166c31dc9076451a1a4207d2f4fe1be0fc8d4ac8134b0f9a92f6b12"),
    "0005_drop_phone_auth.sql": (
        "0476926a6588b9b3e0e3d80214e059c936568d1d7f2e565a47ec5a388c943a80"
    ),
    "0006_portfolio_observer.sql": (
        "c4b94e1ee1f9f087e60d8eed9f063edd601b4d53ad7b17005d82e4a17e50e256"
    ),
    "0007_portfolio_evidence.sql": (
        "9f2cb4effa5d6293ce4988b0b932241f7470d0eb8f3eeeb5223b8db61ca4b544"
    ),
    "0008_balancing_policy.sql": (
        "f169e65c4cd653da5dc9560acea9244daf2f697ea9da96e04e2a87d340cddda0"
    ),
    "0009_portfolio_proposals.sql": (
        "588c0f098e0341ef9931a9292ed167c9e9f5acd31300d0f83bb27b48ffded46c"
    ),
    "0010_portfolio_execution.sql": (
        "73f2d2d30caf5c4a1bc8364940e36c99991649bd389bdd61abcd81a5b3d687c4"
    ),
    "0011_portfolio_live_execution.sql": (
        "9ce5a36321cb88542b46cca33e6ebe5e1a65f4bf84e0bf00598af262a5550dc8"
    ),
    "0012_strategy_drafts.sql": "eb025bbd52f34398ed4d394b26639ffe82076f9a4b2826f56aa15fdff1df0dd5",
    "0013_strategy_assessment_admission.sql": (
        "66e6fa53c70377be00981278dea31361dbb780c632e3fbb40b92b20056ab6089"
    ),
    "0014_workspace.sql": "f2fd5b344f02b445d7f7abdc119b45c706fc49d83d66f7f01eee88a8992f1305",
    "0015_tid_identity.sql": "6721ea1377018a610f4441dc18956844847e69197983d334c2a002cc8498aff9",
    "0016_portfolio_refresh.sql": (
        "f18abf898992751060f3befff5bc946daa8192ba1c2827ea2671318342eca295"
    ),
    "0017_notifications.sql": (
        "fb6a54daa5ab934a643466bb9ef987c69b4d637ef90a79ceda680c1b79d8b971"
    ),
    "0018_strategy_research.sql": (
        "c0ba3797fc59024584b024f56eb39a4020699e959a3038ee5ac688ac92b6e780"
    ),
    "0019_session_security.sql": (
        "e4c0e3c6d01c810c86a26d5d1a01e7daa965a3e1e193861407de67b8df329dab"
    ),
    "0020_goal_plans.sql": (
        "664e0eaa545cc5c74696605de1772f72c3a3c88d774d9358daafa1a0131bb5d2"
    ),
    "0021_assistant_workspace.sql": (
        "e50b592b4f422c47a9c97b5c450cf407f45895f135b772aa01a1005f55910c06"
    ),
    "0022_billing.sql": (
        "8432fa5fa2776900b29165a23b868213b2388dad16bf1a782d154d76e9b8ba0e"
    ),
    "0023_strategy_execution_guards.sql": (
        "0c4a3f29bc370d424aef7959cbee569f10adc0ad836572d7dc6428071a4e0efb"
    ),
    "0024_background_reliability.sql": (
        "24ab7ef2a42b928d13e445517e6961293272a67b6557b4aa865a8158825867a9"
    ),
    "0025_billing_recovery.sql": (
        "5d6ac08ba7312d09aa85ee895f4d66b8bef7b08c1b8af3ce1d52e0457552d3b1"
    ),
    "0027_assistant_stream_memory.sql": (
        "90a733bcf4e9289eff6b14b9653f4a2344454a77b0b8bd76153accd042904419"
    ),
    "0028_notification_device_binding.sql": (
        "a8da904abff76418b04c7d02b1088e3cc48c0f15922562ec5c597b75feb4301f"
    ),
    "0026_strategy_research_capacity.sql": (
        "1cce5a0967c32a6ddd70c48986dd7dcf5074d23a1e8dfe60c7c5abbc72752288"
    ),
}
USER_ONE = UUID("00000000-0000-0000-0000-000000000101")
USER_TWO = UUID("00000000-0000-0000-0000-000000000102")
RUNTIME_PASSWORD = secrets.token_urlsafe(32)


def test_accepted_production_migrations_are_content_immutable() -> None:
    for name, expected_digest in ACCEPTED_MIGRATION_SHA256.items():
        content = (ROOT / "migrations" / name).read_text(encoding="utf-8")
        normalized = content.replace("\r\n", "\n").encode()
        assert hashlib.sha256(normalized).hexdigest() == expected_digest


@pytest.fixture
def inplace_database(monkeypatch):
    if not DATABASE_URL or not os.environ.get("OMNICIO_TEST_POSTGRES_BIN"):
        pytest.skip("disposable PostgreSQL CI launcher is required")
    options = conninfo_to_dict(DATABASE_URL)
    assert options["host"] == "127.0.0.1"
    assert options["dbname"] == "omnicio_test"
    monkeypatch.syspath_prepend(str(ROOT / ".github/scripts"))
    upgrade = importlib.import_module("inplace_upgrade")
    historical = json.loads((ROOT / "tests/fixtures/accepted_upgrade_1_3.json").read_text())
    plan = upgrade.validate_plan(historical["plan"])
    source_query = upgrade.schema_query(historical["source_schema"], plan["source_schema_sha256"])
    target_query = upgrade.schema_query(
        historical["target_schema"],
        "287e991cdb3e98879b4be876b7291bd2459c617cb93d8b45c9930a335863c2d2",
    )
    historical_migrations = tuple(path for path in MIGRATIONS if path.name[:4] <= "0028")
    assert [path.name for path in historical_migrations[-2:]] == [
        "0027_assistant_stream_memory.sql", "0028_notification_device_binding.sql",
    ]
    name = "omnicio_upgrade_" + secrets.token_hex(8)
    dsn = make_conninfo(DATABASE_URL, dbname=name)
    with psycopg.connect(DATABASE_URL, autocommit=True) as control:
        control.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(
            sql.Identifier(name),
        ))
        try:
            with psycopg.connect(dsn, autocommit=True) as connection:
                for path in historical_migrations[:-2]:
                    connection.execute(path.read_text(encoding="utf-8"))
                assert connection.execute(source_query).fetchone() == (True,)
                assert connection.execute(target_query).fetchone() == (False,)
                _seed_inplace_rows(connection)
                arguments = dict(
                    plan=plan,
                    statements=[path.read_text(encoding="utf-8")
                                for path in historical_migrations[-2:]],
                    source_query=source_query, target_query=target_query,
                    identity=upgrade.operation_identity(plan, {"database": name}),
                    release_sha="a" * 40, installed_release=plan["source_release"],
                )
                yield upgrade, connection, dsn, arguments
        finally:
            control.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.fixture
def remote_inplace_database(inplace_database, monkeypatch):
    """Run the Linux entry point against native CI PostgreSQL, with no production files."""
    upgrade, connection, dsn, arguments = inplace_database
    deployer = importlib.import_module("timeweb_auth_app")
    options = conninfo_to_dict(dsn)
    expected = {
        "host": options["host"], "port": int(options["port"]),
        "database": options["dbname"], "user": options["user"], "cluster_id": 42,
    }
    password = secrets.token_urlsafe(32)
    keys = {
        "CLIENT_IP_KEY": "synthetic-native-ip",
        "BROKER_TOKEN_CRYPTO_KEY": "synthetic-native-broker",
        "VKID_FLOW_CRYPTO_KEY": "synthetic-native-flow",
    }
    runtime = {"DATABASE_URL": make_conninfo(dsn, password=password), **keys}
    files = {
        "runtime.env": runtime,
        "auth-secrets.env": {"OMNICIO_DB_ADMIN_PASSWORD": password, **keys},
    }

    def private_file(path: Path, _maximum: int) -> str:
        return "\n".join(f"{name}={deployer._environment_value(value)}"
                         for name, value in files[path.name].items())

    receipts = []
    # Windows runs the actual PostgreSQL server. Only Linux/filesystem ownership
    # boundaries are fixtures; connection, identity SQL and both migrations remain real.
    monkeypatch.setattr(upgrade, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(upgrade, "_operation_lock", nullcontext)
    monkeypatch.setattr(upgrade, "_private_file", private_file)
    monkeypatch.setattr(upgrade, "_read_receipt",
                        lambda: copy.deepcopy(receipts[-1]) if receipts else None)
    monkeypatch.setattr(upgrade, "_write_receipt",
                        lambda value: receipts.append(copy.deepcopy(value)))
    monkeypatch.setattr(
        upgrade, "_existing_installation", lambda _plan, _receipt, _release, _verified:
        (arguments["source_query"], arguments["installed_release"]),
    )
    payload = {
        "plan": arguments["plan"], "statements": arguments["statements"],
        "target_query": arguments["target_query"], "release_sha": arguments["release_sha"],
        "database": expected, "application_version": arguments["plan"]["target_version"],
    }
    return upgrade, connection, payload, receipts, runtime


def test_remote_upgrade_accepts_native_endpoint_and_preserves_rows(
    remote_inplace_database, capsys,
):
    upgrade, connection, payload, receipts, _runtime = remote_inplace_database
    before = _inplace_rows(connection, exclude_changes=True)
    expected_output = {
        "cluster_id": payload["database"]["cluster_id"],
        "release_sha": payload["release_sha"], "new_database_copies": 0,
    }
    # A real IPv4 session catches inet::text returning a /32 suffix. Mocking
    # the observed SELECT tuple would miss the production failure again.
    upgrade.remote_main(payload)
    output = capsys.readouterr()
    assert json.loads(output.out) == {**expected_output, "status": "applied"}
    assert output.err == ""
    assert [item["phase"] for item in receipts] == ["pending", "completed"]
    assert receipts[-1]["identity"]["database"] == payload["database"]
    assert connection.execute(payload["target_query"]).fetchone() == (True,)
    assert _inplace_rows(connection, exclude_changes=True) == before

    after = _inplace_rows(connection)
    upgrade.remote_main(payload)
    output = capsys.readouterr()
    assert json.loads(output.out) == {**expected_output, "status": "already_applied"}
    assert output.err == ""
    assert [item["phase"] for item in receipts] == ["pending", "completed", "completed"]
    assert _inplace_rows(connection) == after


def test_remote_upgrade_rejects_wrong_native_server_before_receipt_or_migration(
    remote_inplace_database, capsys,
):
    upgrade, connection, payload, receipts, runtime = remote_inplace_database
    before = _inplace_rows(connection)
    actual_host = payload["database"]["host"]
    payload["database"]["host"] = "127.0.0.2"
    # Both addresses are loopback. libpq's explicit hostaddr reaches the actual
    # disposable server while the declared target passes the runtime-file check.
    # The server-side observation must still reject this different endpoint.
    runtime["DATABASE_URL"] = make_conninfo(
        runtime["DATABASE_URL"], host=payload["database"]["host"], hostaddr=actual_host,
    )
    with pytest.raises(upgrade.UpgradeBlocked, match="^connected_database_address_mismatch$"):
        upgrade.remote_main(payload)
    assert receipts == []
    assert connection.execute(upgrade.NEW_SCHEMA_ABSENT).fetchone() == (True,)
    assert connection.execute(payload["target_query"]).fetchone() == (False,)
    assert _inplace_rows(connection) == before
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == ""


def _seed_inplace_rows(connection):
    for owner in (USER_ONE, USER_TWO):
        connection.execute("INSERT INTO users (id) VALUES (%s)", (owner,))
        connection.execute(
            "INSERT INTO sessions (user_id, token_digest, client_ip_hash, expires_at) "
            "VALUES (%s, %s, %s, now() + interval '1 day')", (owner, owner.bytes, b"synthetic-ip"),
        )
        connection.execute(
            "INSERT INTO workspace_preferences (user_id, version, document) "
            "VALUES (%s, 7, '{\"selected_strategy\":\"custom\"}')", (owner,),
        )
        connection.execute(
            "INSERT INTO investment_goals (user_id, version, title, kind, target_amount_rub, "
            "start_date, progress_source, manual_amount_rub, status) "
            "VALUES (%s, 3, 'Synthetic goal', 'capital', 1000000.00000001, "
            "current_date, 'manual', 1234.56789012, 'active')", (owner,),
        )
        conversation, request = uuid4(), uuid4()
        connection.execute(
            "INSERT INTO assistant_conversations (user_id, id, title) VALUES (%s, %s, 'Synthetic')",
            (owner, conversation),
        )
        connection.execute(
            "INSERT INTO assistant_requests (user_id, id, conversation_id, input_hash, "
            "connection_version, conversation_version, status, context_used, model) "
            "VALUES (%s, %s, %s, %s, 1, 1, 'completed', false, 'synthetic-model')",
            (owner, request, conversation, "a" * 64),
        )
        connection.execute(
            "INSERT INTO assistant_messages (user_id, conversation_id, position, request_id, "
            "role, content) VALUES (%s, %s, 1, %s, 'user', 'Preserved synthetic message')",
            (owner, conversation, request),
        )
        channel = connection.execute(
            "INSERT INTO notification_channels (user_id, kind, destination_hash, "
            "destination_ciphertext, label, status) "
            "VALUES (%s, 'push', %s, %s, 'Legacy device', 'active') RETURNING id",
            (owner, "b" * 64, b"encrypted-synthetic-subscription"),
        ).fetchone()[0]
        for status in ("queued", "accepted"):
            connection.execute(
                "INSERT INTO notification_outbox (user_id, channel_id, message_key, "
                "kind, payload_ciphertext, status) VALUES (%s, %s, %s, 'event', %s, %s)",
                (owner, channel, status, b"encrypted-synthetic-payload", status),
            )


def _inplace_rows(connection, *, exclude_changes=False):
    exclusions = {
        "users": [], "sessions": [], "workspace_preferences": [], "investment_goals": [],
        "assistant_conversations": [], "assistant_messages": [],
        "assistant_requests": ["reply_prefix", "stream_sequence", "source_refs", "updated_at"],
        "notification_channels": ["session_id", "binding_id", "status", "updated_at"],
        "notification_outbox": ["binding_id", "status", "last_error", "updated_at"],
    }
    return {table: connection.execute(sql.SQL(
        "SELECT (to_jsonb(record) - %s::text[])::text AS document "
        "FROM {} AS record ORDER BY document",
    ).format(sql.Identifier(table)), (columns if exclude_changes else [],)).fetchall()
        for table, columns in exclusions.items()}


def test_inplace_transaction_preserves_tenants_and_expires_only_unbound_delivery(inplace_database):
    upgrade, connection, _dsn, arguments = inplace_database
    before = _inplace_rows(connection, exclude_changes=True)
    accepted_query = ("SELECT (to_jsonb(record) - 'binding_id')::text AS document "
                      "FROM notification_outbox AS record "
                      "WHERE status = 'accepted' ORDER BY document")
    accepted = connection.execute(accepted_query).fetchall()
    receipts = []
    assert upgrade.apply_upgrade(connection, **arguments, receipt=None,
                                 save_receipt=receipts.append) == "applied"
    assert [item["phase"] for item in receipts] == ["pending", "completed"]
    assert connection.execute(arguments["target_query"]).fetchone() == (True,)
    assert _inplace_rows(connection, exclude_changes=True) == before
    assert connection.execute(accepted_query).fetchall() == accepted
    for owner in (USER_ONE, USER_TWO):
        assert connection.execute(
            "SELECT status FROM notification_channels WHERE user_id = %s", (owner,),
        ).fetchall() == [("expired",)]
        assert connection.execute(
            "SELECT status, last_error FROM notification_outbox WHERE user_id = %s ORDER BY status",
            (owner,),
        ).fetchall() == [("accepted", None), ("cancelled", "push_binding_expired")]
        assert connection.execute(
            "SELECT reply_prefix, stream_sequence, source_refs, updated_at IS NOT NULL "
            "FROM assistant_requests WHERE user_id = %s", (owner,),
        ).fetchone() == ("", 0, [], True)


def test_inplace_failure_in_second_migration_rolls_back_both_and_can_resume(inplace_database):
    upgrade, connection, _dsn, arguments = inplace_database
    before = _inplace_rows(connection)
    connection.execute("""
        CREATE FUNCTION synthetic_upgrade28_fault() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF to_regclass('public.assistant_memory') IS NULL THEN
                RAISE EXCEPTION 'synthetic_migration27_was_not_applied';
            END IF;
            RAISE EXCEPTION 'synthetic_upgrade28_failure';
        END;
        $$;
        CREATE TRIGGER synthetic_upgrade28_fault BEFORE UPDATE ON notification_channels
            FOR EACH ROW EXECUTE FUNCTION synthetic_upgrade28_fault();
    """)
    receipts = []
    with pytest.raises(psycopg.errors.RaiseException, match="synthetic_upgrade28_failure"):
        upgrade.apply_upgrade(connection, **arguments, receipt=None, save_receipt=receipts.append)
    assert [item["phase"] for item in receipts] == ["pending"]
    assert connection.execute(arguments["source_query"]).fetchone() == (True,)
    assert connection.execute(upgrade.NEW_SCHEMA_ABSENT).fetchone() == (True,)
    assert _inplace_rows(connection) == before
    connection.execute("DROP TRIGGER synthetic_upgrade28_fault ON notification_channels")
    connection.execute("DROP FUNCTION synthetic_upgrade28_fault()")
    with pytest.raises(upgrade.UpgradeBlocked, match="completed_upgrade_schema_changed"):
        upgrade.apply_upgrade(connection, **arguments,
                              receipt=receipts[-1] | {"phase": "completed"},
                              save_receipt=receipts.append)
    with pytest.raises(upgrade.UpgradeBlocked, match="target_schema_not_ready"):
        upgrade.apply_upgrade(connection, **dict(arguments, target_query="SELECT false"),
                              receipt=receipts[-1], save_receipt=receipts.append)
    assert connection.execute(upgrade.NEW_SCHEMA_ABSENT).fetchone() == (True,)
    assert _inplace_rows(connection) == before
    assert upgrade.apply_upgrade(connection, **arguments, receipt=receipts[-1],
                                 save_receipt=receipts.append) == "applied"
    assert connection.execute(arguments["target_query"]).fetchone() == (True,)


def test_inplace_lost_commit_confirmation_never_repeats_migration_sql(inplace_database):
    upgrade, connection, _dsn, arguments = inplace_database
    receipts = []

    def interrupted_write(value):
        if value["phase"] == "completed":
            raise OSError("synthetic receipt write failed after commit")
        receipts.append(copy.deepcopy(value))

    with pytest.raises(OSError, match="after commit"):
        upgrade.apply_upgrade(connection, **arguments, receipt=None, save_receipt=interrupted_write)
    assert [item["phase"] for item in receipts] == ["pending"]
    assert connection.info.transaction_status == psycopg.pq.TransactionStatus.IDLE
    assert connection.execute(arguments["target_query"]).fetchone() == (True,)
    with pytest.raises(upgrade.UpgradeBlocked, match="target_schema_has_no_operation_receipt"):
        upgrade.apply_upgrade(connection, **arguments, receipt=None, save_receipt=receipts.append)
    connection.execute("""
        CREATE FUNCTION synthetic_repeated_ddl() RETURNS event_trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'synthetic_migration_was_repeated'; END; $$;
        CREATE EVENT TRIGGER synthetic_repeated_ddl ON ddl_command_start
            EXECUTE FUNCTION synthetic_repeated_ddl();
    """)
    assert upgrade.apply_upgrade(connection, **arguments, receipt=receipts[-1],
                                 save_receipt=receipts.append) == "already_applied"
    assert receipts[-1]["phase"] == "completed"
    # Keep the actually running A installation trusted if B deployment fails.
    next_release = dict(arguments, release_sha="b" * 40, installed_release="a" * 40)
    for _ in range(2):
        assert upgrade.apply_upgrade(connection, **next_release, receipt=receipts[-1],
                                     save_receipt=receipts.append) == "already_applied"
        assert receipts[-1]["installed_release"] == "a" * 40


def test_inplace_requires_top_level_transaction_and_exclusive_operation(inplace_database):
    upgrade, connection, dsn, arguments = inplace_database
    receipts = []
    with pytest.raises(upgrade.UpgradeBlocked, match="initial_upgrade_requires_source_"):
        upgrade.apply_upgrade(connection, **dict(arguments, installed_release="a" * 40),
                              receipt=None, save_receipt=receipts.append)
    connection.autocommit = False
    with pytest.raises(upgrade.UpgradeBlocked, match="idle_autocommit"):
        upgrade.apply_upgrade(connection, **arguments, receipt=None, save_receipt=receipts.append)
    assert connection.info.transaction_status == psycopg.pq.TransactionStatus.IDLE
    connection.autocommit = True
    connection.execute("BEGIN")
    try:
        with pytest.raises(upgrade.UpgradeBlocked, match="idle_autocommit"):
            upgrade.apply_upgrade(connection, **arguments, receipt=None,
                                  save_receipt=receipts.append)
        assert connection.info.transaction_status == psycopg.pq.TransactionStatus.INTRANS
    finally:
        connection.rollback()
    with psycopg.connect(dsn) as other:
        other.execute("SELECT pg_advisory_xact_lock(4215095001300)")
        with pytest.raises(upgrade.UpgradeBlocked, match="another_upgrade_is_running"):
            upgrade.apply_upgrade(connection, **arguments, receipt=None,
                                  save_receipt=receipts.append)
    assert receipts == []
    assert connection.execute(arguments["source_query"]).fetchone() == (True,)
    assert connection.execute(upgrade.NEW_SCHEMA_ABSENT).fetchone() == (True,)


def test_inplace_table_lock_timeout_keeps_the_old_schema_and_rows(inplace_database):
    upgrade, connection, dsn, arguments = inplace_database
    before, receipts = _inplace_rows(connection), []
    with psycopg.connect(dsn) as other:
        other.execute("LOCK TABLE notification_channels IN ACCESS EXCLUSIVE MODE")
        with pytest.raises(psycopg.errors.LockNotAvailable):
            upgrade.apply_upgrade(connection, **arguments, receipt=None,
                                  save_receipt=receipts.append)
    assert [item["phase"] for item in receipts] == ["pending"]
    assert connection.execute(arguments["source_query"]).fetchone() == (True,)
    assert connection.execute(upgrade.NEW_SCHEMA_ABSENT).fetchone() == (True,)
    assert _inplace_rows(connection) == before


@pytest.fixture
def email_upgrade_database(monkeypatch):
    """Upgrade a disposable 1.3 database as its real, non-bypassing table owner."""
    if not DATABASE_URL or not os.environ.get("OMNICIO_TEST_POSTGRES_BIN"):
        pytest.skip("disposable PostgreSQL CI launcher is required")
    options = conninfo_to_dict(DATABASE_URL)
    assert options["host"] == "127.0.0.1"
    assert options["dbname"] == "omnicio_test"
    monkeypatch.syspath_prepend(str(ROOT / ".github/scripts"))
    upgrade = importlib.import_module("inplace_upgrade")
    plan = upgrade.load_plan()
    assert (plan["source_version"], plan["target_version"]) == ("1.3.0", "1.5.0")
    historical = json.loads((ROOT / "tests/fixtures/accepted_upgrade_1_3.json").read_text())
    source_query = upgrade.schema_query(historical["target_schema"], plan["source_schema_sha256"])
    name = "omnicio_email_upgrade_" + secrets.token_hex(8)
    role = "email_owner_" + secrets.token_hex(8)
    dsn = make_conninfo(DATABASE_URL, dbname=name, user=role, password=secrets.token_urlsafe(32))
    with psycopg.connect(DATABASE_URL, autocommit=True) as control:
        control.execute(sql.SQL(
            "CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOBYPASSRLS "
            "NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT",
        ).format(sql.Identifier(role), sql.Literal(conninfo_to_dict(dsn)["password"])))
        try:
            control.execute(sql.SQL("CREATE DATABASE {} OWNER {} TEMPLATE template0").format(
                sql.Identifier(name), sql.Identifier(role),
            ))
            with psycopg.connect(dsn, autocommit=True) as connection:
                for path in MIGRATIONS:
                    if path.name[:4] <= "0028":
                        connection.execute(path.read_text(encoding="utf-8"))
                assert connection.execute(source_query).fetchone() == (True,)
                assert connection.execute(upgrade.source_absence_query(plan)).fetchone() == (
                    True,
                ), _email_check_expressions(connection)
                assert connection.execute(READINESS_QUERY).fetchone() == (False,)
                _seed_email_upgrade_rows(connection)
                arguments = dict(
                    plan=plan,
                    statements=[path.read_text(encoding="utf-8") for path in MIGRATIONS[-3:]],
                    source_query=source_query, target_query=READINESS_QUERY,
                    identity=upgrade.operation_identity(plan, {"database": name}),
                    release_sha="a" * 40, installed_release=plan["source_release"],
                    # Only this disposable synthetic database has a test-only recovery callback.
                    # Production remote_main must obtain its own verified recovery evidence.
                    require_recovery=lambda: None,
                )
                yield upgrade, connection, dsn, arguments
        finally:
            control.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(name),
            ))
            control.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


def _seed_email_upgrade_rows(connection):
    for owner in (USER_ONE, USER_TWO):
        connection.execute("SELECT set_config('omnicio.user_id', %s, false)", (str(owner),))
        connection.execute("INSERT INTO users (id) VALUES (%s)", (owner,))
        connection.execute("INSERT INTO vkid_identities (user_id, vk_user_id) VALUES (%s, %s)",
                           (owner, str(owner.int)))
        connection.execute("INSERT INTO tid_identities (user_id, tid_subject) VALUES (%s, %s)",
                           (owner, "synthetic-" + str(owner.int)))
        for provider in (None, "vkid", "tid"):
            connection.execute(
                "INSERT INTO sessions (user_id, token_digest, client_ip_hash, expires_at, "
                "authenticated_provider, authenticated_at) VALUES (%s, %s, %s, "
                "now() + interval '1 day', %s, "
                "CASE WHEN %s::text IS NULL THEN NULL ELSE now() END)",
                (owner, owner.bytes + (provider or "legacy").encode().ljust(16, b"x"),
                 b"synthetic-ip", provider, provider),
            )
        connection.execute(
            "INSERT INTO legal_acceptances (user_id, document_type, document_version, "
            "client_ip_hash) VALUES (%s, 'terms', 'before-1.4', %s)", (owner, b"synthetic-ip"),
        )
        connection.execute(
            "INSERT INTO tbank_connection (user_id, environment, account_id, token_ciphertext) "
            "VALUES (%s, 'prod', 'synthetic-account', %s)", (owner, b"synthetic-" + owner.bytes),
        )
        connection.execute(
            "INSERT INTO workspace_preferences (user_id, version, document) "
            "VALUES (%s, 7, '{\"theme\":\"dark\"}')", (owner,),
        )
        connection.execute(
            "INSERT INTO strategy_drafts (user_id, version, document, fingerprint) "
            "VALUES (%s, 3, '{\"name\":\"Preserved synthetic strategy\"}', %s)",
            (owner, "a" * 64),
        )
        snapshot = connection.execute(
            "INSERT INTO portfolio_snapshots (user_id, account_id, environment, captured_at, "
            "analysis_status, nav_rub, rub_cash_total, rub_cash_blocked, "
            "limits_loading_in_progress, evidence) VALUES (%s, 'synthetic-account', 'prod', "
            "now(), 'observed', 1234.56789012, 123.45678901, 12.34567890, false, "
            "'{\"source\":\"preserved synthetic evidence\"}') RETURNING id", (owner,),
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO portfolio_snapshot_positions (snapshot_id, user_id, instrument_uid, "
            "instrument_type, quantity, blocked, blocked_lots) "
            "VALUES (%s, %s, 'synthetic-instrument', 'share', 1.123456789, false, 0)",
            (snapshot, owner),
        )
    connection.execute("SELECT set_config('omnicio.user_id', '', false)")


def _email_upgrade_rows(connection):
    result = {"users": connection.execute(
        "SELECT to_jsonb(record)::text AS document FROM users AS record ORDER BY document",
    ).fetchall()}
    tables = ("vkid_identities", "tid_identities", "sessions", "legal_acceptances",
              "tbank_connection", "workspace_preferences", "strategy_drafts",
              "portfolio_snapshots", "portfolio_snapshot_positions")
    for owner in (USER_ONE, USER_TWO):
        connection.execute("SELECT set_config('omnicio.user_id', %s, false)", (str(owner),))
        result[str(owner)] = {
            table: connection.execute(sql.SQL(
                "SELECT to_jsonb(record)::text AS document FROM {} AS record "
                "WHERE user_id = %s ORDER BY document",
            ).format(sql.Identifier(table)), (owner,)).fetchall() for table in tables
        }
    connection.execute("SELECT set_config('omnicio.user_id', '', false)")
    return result


def _email_check_expressions(connection):
    """Expose only catalog definitions if PostgreSQL's canonical expression contract drifts."""
    return connection.execute(
        "SELECT conrelid::regclass::text, conname, pg_get_expr(conbin, conrelid) "
        "FROM pg_constraint WHERE contype = 'c' AND conrelid IN ("
        "to_regclass('public.email_identities'), to_regclass('public.email_auth_challenges'), "
        "to_regclass('public.email_auth_rate_limits'), to_regclass('public.sessions')) "
        "ORDER BY conrelid::regclass::text, conname",
    ).fetchall()


def _assert_email_readiness(connection):
    """Keep full synthetic catalog evidence in CI when a strict predicate differs."""
    ready = connection.execute(READINESS_QUERY).fetchone()
    if ready != (True,):
        predicates = READINESS_QUERY.strip().removeprefix("SELECT").removesuffix("AS ready")
        failed_predicates = []
        for position, predicate in enumerate(predicates.split("\n    AND "), start=1):
            result = connection.execute("SELECT " + predicate).fetchone()
            if result != (True,):
                failed_predicates.append({"position": position, "result": result,
                                          "expression": predicate.strip()})
        columns = connection.execute("""
            SELECT relation.relname, attribute.attname,
                   format_type(attribute.atttypid, attribute.atttypmod), attribute.attnotnull,
                   pg_get_expr(defaults.adbin, defaults.adrelid),
                   relation.relrowsecurity, relation.relforcerowsecurity, relation.relacl::text
            FROM pg_class AS relation
            JOIN pg_attribute AS attribute ON attribute.attrelid = relation.oid
                AND attribute.attnum > 0 AND NOT attribute.attisdropped
            LEFT JOIN pg_attrdef AS defaults ON defaults.adrelid = relation.oid
                AND defaults.adnum = attribute.attnum
            WHERE relation.oid IN (to_regclass('public.email_identities'),
                to_regclass('public.email_auth_challenges'),
                to_regclass('public.email_auth_rate_limits'))
            ORDER BY relation.relname, attribute.attnum
        """).fetchall()
        constraints = connection.execute("""
            SELECT conrelid::regclass::text, conname, contype, convalidated, conenforced,
                   condeferrable, pg_get_constraintdef(oid)
            FROM pg_constraint WHERE conrelid IN (to_regclass('public.email_identities'),
                to_regclass('public.email_auth_challenges'),
                to_regclass('public.email_auth_rate_limits'), to_regclass('public.sessions'))
            ORDER BY conrelid::regclass::text, conname
        """).fetchall()
        indexes = connection.execute("""
            SELECT indexrelid::regclass::text, pg_get_indexdef(indexrelid),
                   indisvalid, indisready, pg_get_expr(indpred, indrelid)
            FROM pg_index WHERE indrelid IN (to_regclass('public.email_identities'),
                to_regclass('public.email_auth_challenges'),
                to_regclass('public.email_auth_rate_limits'))
            ORDER BY indexrelid::regclass::text
        """).fetchall()
        print(json.dumps({"failed_readiness_predicates": failed_predicates,
                          "columns": columns, "constraints": constraints, "indexes": indexes,
                          "check_expressions": _email_check_expressions(connection)}, indent=2))
    assert ready == (True,)


def test_email_upgrade_preserves_rows_and_nullable_snapshots_under_force_rls(
    email_upgrade_database,
):
    upgrade, connection, _dsn, arguments = email_upgrade_database
    before, receipts = _email_upgrade_rows(connection), []
    assert connection.execute(
        "SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolreplication "
        "FROM pg_roles WHERE rolname = current_user",
    ).fetchone() == (False, False, False, False, False)
    assert upgrade.apply_upgrade(connection, **arguments, receipt=None,
                                 save_receipt=receipts.append) == "applied"
    assert [item["phase"] for item in receipts] == ["pending", "completed"]
    assert _email_upgrade_rows(connection) == before
    assert connection.execute(READINESS_QUERY).fetchone() == (True,)
    assert connection.execute(upgrade.source_absence_query(
        arguments["plan"],
    )).fetchone() == (False,)
    # FORCE RLS remains effective even for the table-owning production-shaped role.
    assert connection.execute("SELECT user_id FROM portfolio_snapshots").fetchall() == []
    connection.execute("SELECT set_config('omnicio.user_id', %s, false)", (str(USER_ONE),))
    assert connection.execute("SELECT user_id FROM portfolio_snapshots").fetchall() == [(USER_ONE,)]
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        connection.execute(
            "UPDATE portfolio_snapshots SET user_id = %s WHERE user_id = %s", (USER_TWO, USER_ONE),
        )
    values = connection.execute(
        "INSERT INTO portfolio_snapshots (user_id, account_id, environment, captured_at, "
        "analysis_status, nav_rub, rub_cash_total, rub_cash_blocked, "
        "limits_loading_in_progress, evidence) VALUES (%s, 'synthetic-account', 'prod', now(), "
        "'partial', NULL, NULL, NULL, false, '{}') "
        "RETURNING nav_rub, rub_cash_total, rub_cash_blocked", (USER_ONE,),
    ).fetchone()
    assert values == (None, None, None)


def test_email_upgrade_requires_recovery_before_receipt_or_ddl(email_upgrade_database):
    upgrade, connection, _dsn, arguments = email_upgrade_database
    before, receipts = _email_upgrade_rows(connection), []
    without_recovery = {key: value for key, value in arguments.items() if key != "require_recovery"}
    with pytest.raises(upgrade.UpgradeBlocked, match="^upgrade_recovery_required$"):
        upgrade.apply_upgrade(connection, **without_recovery, receipt=None,
                              save_receipt=receipts.append)

    def unavailable_recovery():
        raise upgrade.UpgradeBlocked("synthetic_recovery_unavailable")

    with pytest.raises(upgrade.UpgradeBlocked, match="^synthetic_recovery_unavailable$"):
        upgrade.apply_upgrade(connection, **{**arguments, "require_recovery": unavailable_recovery},
                              receipt=None, save_receipt=receipts.append)
    assert receipts == []
    assert _email_upgrade_rows(connection) == before
    assert connection.execute(upgrade.source_absence_query(arguments["plan"])).fetchone() == (True,)


@pytest.mark.parametrize("drift", [
    "CREATE TABLE email_auth_challenges (id uuid)",
    "ALTER TABLE portfolio_snapshots ALTER COLUMN nav_rub DROP NOT NULL",
    "ALTER TABLE sessions DROP CONSTRAINT sessions_authentication_evidence; "
    "ALTER TABLE sessions ADD CONSTRAINT sessions_authentication_evidence CHECK (true)",
])
def test_email_upgrade_rejects_partial_or_weakened_source(email_upgrade_database, drift):
    upgrade, connection, _dsn, arguments = email_upgrade_database
    before, receipts = _email_upgrade_rows(connection), []
    connection.execute(drift)
    with pytest.raises(upgrade.UpgradeBlocked, match="^source_schema_is_not_reviewed_baseline$"):
        upgrade.apply_upgrade(connection, **arguments, receipt=None, save_receipt=receipts.append)
    assert receipts == []
    assert _email_upgrade_rows(connection) == before


def test_email_upgrade_uses_public_schema_despite_a_shadow_search_path(email_upgrade_database):
    upgrade, connection, _dsn, arguments = email_upgrade_database
    connection.execute("CREATE SCHEMA synthetic_shadow")
    connection.execute("CREATE TABLE synthetic_shadow.sessions (untouched text)")
    connection.execute("CREATE TABLE synthetic_shadow.portfolio_snapshots (untouched text)")
    connection.execute("SET search_path TO synthetic_shadow, public")
    receipts = []
    assert upgrade.apply_upgrade(connection, **arguments, receipt=None,
                                 save_receipt=receipts.append) == "applied"
    assert connection.execute(READINESS_QUERY).fetchone() == (True,)
    assert connection.execute(
        "SELECT to_regclass('synthetic_shadow.email_identities') IS NULL",
    ).fetchone() == (True,)
    assert connection.execute(
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE table_schema = 'synthetic_shadow' ORDER BY table_name",
    ).fetchall() == [("portfolio_snapshots", "untouched"), ("sessions", "untouched")]


def test_email_upgrade_second_migration_lock_failure_rolls_back_both_and_retries(
    email_upgrade_database,
):
    upgrade, connection, dsn, arguments = email_upgrade_database
    before, receipts = _email_upgrade_rows(connection), []
    with psycopg.connect(dsn) as other:
        other.execute("LOCK TABLE portfolio_snapshots IN ACCESS EXCLUSIVE MODE")
        with pytest.raises(psycopg.errors.LockNotAvailable):
            upgrade.apply_upgrade(connection, **arguments, receipt=None,
                                  save_receipt=receipts.append)
    assert [item["phase"] for item in receipts] == ["pending"]
    assert connection.execute(arguments["source_query"]).fetchone() == (True,)
    assert connection.execute(upgrade.source_absence_query(arguments["plan"])).fetchone() == (True,)
    assert _email_upgrade_rows(connection) == before
    assert upgrade.apply_upgrade(connection, **arguments, receipt=receipts[-1],
                                 save_receipt=receipts.append) == "applied"
    assert _email_upgrade_rows(connection) == before


def test_email_upgrade_lost_commit_receipt_reconciles_without_repeating_ddl(email_upgrade_database):
    upgrade, connection, dsn, arguments = email_upgrade_database
    before, receipts = _email_upgrade_rows(connection), []

    def lost_confirmation(value):
        if value["phase"] == "completed":
            raise OSError("synthetic lost receipt after commit")
        receipts.append(copy.deepcopy(value))

    with pytest.raises(OSError, match="after commit"):
        upgrade.apply_upgrade(connection, **arguments, receipt=None, save_receipt=lost_confirmation)
    assert [item["phase"] for item in receipts] == ["pending"]
    assert connection.execute(READINESS_QUERY).fetchone() == (True,)
    assert _email_upgrade_rows(connection) == before
    with pytest.raises(upgrade.UpgradeBlocked, match="^target_schema_has_no_operation_receipt$"):
        upgrade.apply_upgrade(connection, **arguments, receipt=None, save_receipt=receipts.append)
    admin_dsn = make_conninfo(DATABASE_URL, dbname=conninfo_to_dict(dsn)["dbname"])
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute("""
            CREATE FUNCTION synthetic_repeated_email_ddl() RETURNS event_trigger
            LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'synthetic_migration_was_repeated'; END; $$;
            CREATE EVENT TRIGGER synthetic_repeated_email_ddl ON ddl_command_start
                EXECUTE FUNCTION synthetic_repeated_email_ddl();
        """)
    # Reconciliation of the committed transaction needs its matching receipt;
    # it must not repeat either DDL or a now-unavailable pre-mutation recovery check.
    without_recovery = {key: value for key, value in arguments.items() if key != "require_recovery"}
    for _ in range(2):
        assert upgrade.apply_upgrade(connection, **without_recovery, receipt=receipts[-1],
                                     save_receipt=receipts.append) == "already_applied"
    assert [item["phase"] for item in receipts] == ["pending", "completed", "completed"]
    assert _email_upgrade_rows(connection) == before


def test_email_readiness_survives_reparsed_check_definitions(email_upgrade_database):
    upgrade, connection, _dsn, arguments = email_upgrade_database
    receipts = []
    upgrade.apply_upgrade(connection, **arguments, receipt=None, save_receipt=receipts.append)
    _assert_email_readiness(connection)
    definitions = connection.execute("""
        SELECT relation.relname, constraint_definition.conname,
               pg_get_constraintdef(constraint_definition.oid)
        FROM pg_constraint AS constraint_definition
        JOIN pg_class AS relation ON relation.oid = constraint_definition.conrelid
        WHERE constraint_definition.contype = 'c' AND constraint_definition.conrelid IN (
            to_regclass('public.email_identities'), to_regclass('public.email_auth_challenges'),
            to_regclass('public.email_auth_rate_limits'), to_regclass('public.sessions'))
        ORDER BY relation.relname, constraint_definition.conname
    """).fetchall()
    # pg_dump restores these deparsed CHECK definitions. BETWEEN's inner AND becomes
    # part of its parent AND when parsed again; its enforced conditions must survive.
    with connection.transaction():
        for table, name, definition in definitions:
            connection.execute(sql.SQL("ALTER TABLE {} DROP CONSTRAINT {}").format(
                sql.Identifier("public", table), sql.Identifier(name),
            ))
            connection.execute(sql.SQL("ALTER TABLE {} ADD CONSTRAINT {} {}").format(
                sql.Identifier("public", table), sql.Identifier(name), sql.SQL(definition),
            ))
        _assert_email_readiness(connection)
    assert upgrade.apply_upgrade(connection, **arguments, receipt=receipts[-1],
                                 save_receipt=receipts.append) == "already_applied"


def test_email_readiness_rejects_malformed_auth_contracts(email_upgrade_database):
    upgrade, connection, _dsn, arguments = email_upgrade_database
    receipts = []
    upgrade.apply_upgrade(connection, **arguments, receipt=None, save_receipt=receipts.append)
    _assert_email_readiness(connection)
    drifts = (
        "ALTER TABLE email_auth_challenges DROP COLUMN delivery_ciphertext",
        "ALTER TABLE email_auth_challenges ALTER COLUMN delivery_attempts TYPE integer",
        "ALTER TABLE email_identities ALTER COLUMN password_hash DROP NOT NULL",
        "ALTER TABLE email_identities ALTER COLUMN password_version DROP DEFAULT",
        "ALTER TABLE email_identities DROP CONSTRAINT email_identities_email_key",
        "ALTER TABLE email_auth_challenges DROP CONSTRAINT email_auth_challenges_user_id_fkey",
        "ALTER TABLE email_auth_challenges DROP CONSTRAINT email_auth_challenges_user_id_fkey; "
        "ALTER TABLE email_auth_challenges ADD CONSTRAINT email_auth_challenges_user_id_fkey "
        "FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL",
        "ALTER TABLE email_identities DROP CONSTRAINT email_identity_hash_valid; "
        "ALTER TABLE email_identities ADD CONSTRAINT email_identity_hash_valid CHECK (true)",
        "ALTER TABLE email_identities DROP CONSTRAINT email_identity_address_valid; "
        "ALTER TABLE email_identities ADD CONSTRAINT email_identity_address_valid CHECK ("
        "(char_length(email) >= 3 AND char_length(email) <= 254) "
        "OR split_part(email, '@', 2) IN ('gmail.com', 'mail.ru', 'xmail.ru'))",
        "ALTER TABLE email_auth_challenges DROP CONSTRAINT email_challenge_enrollment",
        "ALTER TABLE sessions DROP CONSTRAINT sessions_authentication_evidence; "
        "ALTER TABLE sessions ADD CONSTRAINT sessions_authentication_evidence CHECK (true)",
        "ALTER TABLE email_auth_challenges DROP CONSTRAINT email_challenge_expiry; "
        "ALTER TABLE email_auth_challenges ADD CONSTRAINT email_challenge_expiry "
        "CHECK (expires_at > created_at) NOT VALID",
        "ALTER TABLE email_auth_challenges DROP CONSTRAINT email_challenge_expiry; "
        "ALTER TABLE email_auth_challenges ADD CONSTRAINT email_challenge_expiry "
        "CHECK (expires_at > created_at) NOT ENFORCED",
        "DROP INDEX email_auth_challenges_delivery_idx",
        "DROP INDEX email_auth_challenges_delivery_idx; "
        "CREATE INDEX email_auth_challenges_delivery_idx ON email_auth_challenges (created_at)",
        "ALTER TABLE email_auth_challenges ENABLE ROW LEVEL SECURITY",
        "GRANT SELECT ON email_auth_challenges TO PUBLIC",
        "ALTER TABLE portfolio_snapshots ALTER COLUMN nav_rub TYPE numeric(16, 2)",
        "ALTER TABLE portfolio_snapshots ALTER COLUMN nav_rub SET NOT NULL",
        "ALTER TABLE portfolio_snapshots NO FORCE ROW LEVEL SECURITY",
    )
    for drift in drifts:
        with connection.transaction(force_rollback=True):
            connection.execute(drift)
            assert connection.execute(READINESS_QUERY).fetchone() == (False,), drift
        assert connection.execute(READINESS_QUERY).fetchone() == (True,)
    connection.execute("ALTER TABLE email_identities DROP CONSTRAINT email_identities_email_key")
    with pytest.raises(upgrade.UpgradeBlocked, match="^completed_upgrade_schema_changed$"):
        upgrade.apply_upgrade(connection, **arguments, receipt=receipts[-1],
                              save_receipt=receipts.append)


@pytest.mark.skipif(not DATABASE_URL, reason="ephemeral PostgreSQL is required")
def test_device_binding_migration_expires_all_legacy_owners_without_erasing_receipts() -> None:
    name = "push_migration_" + secrets.token_hex(6)
    owners = [uuid4(), uuid4()]
    migration = ROOT / "migrations" / "0028_notification_device_binding.sql"
    with psycopg.connect(DATABASE_URL, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(name)))
        try:
            admin.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(name)))
            for path in MIGRATIONS:
                if path != migration:
                    admin.execute(path.read_text(encoding="utf-8"))
            for owner in owners:
                admin.execute("INSERT INTO users (id) VALUES (%s)", (owner,))
                admin.execute("SELECT set_config('omnicio.user_id', %s, false)", (str(owner),))
                channel = admin.execute(
                    "INSERT INTO notification_channels (user_id, kind, destination_hash, "
                    "destination_ciphertext, label, status) "
                    "VALUES (%s, 'push', %s, %s, 'Legacy device', 'active') RETURNING id",
                    (owner, "b" * 64, b"encrypted-synthetic-subscription"),
                ).fetchone()[0]
                for status in ("queued", "accepted"):
                    admin.execute(
                        "INSERT INTO notification_outbox (user_id, channel_id, message_key, "
                        "kind, payload_ciphertext, status) VALUES (%s, %s, %s, 'event', %s, %s)",
                        (owner, channel, status, b"encrypted-synthetic-payload", status),
                    )
            content = migration.read_text(encoding="utf-8")
            admin.execute(content)
            admin.execute(content)
            for owner in owners:
                admin.execute("SELECT set_config('omnicio.user_id', %s, false)", (str(owner),))
                assert admin.execute(
                    "SELECT status FROM notification_channels WHERE user_id = %s", (owner,),
                ).fetchone()[0] == "expired"
                assert admin.execute(
                    "SELECT status, last_error FROM notification_outbox WHERE user_id = %s "
                    "ORDER BY status", (owner,),
                ).fetchall() == [("accepted", None), ("cancelled", "push_binding_expired")]
            index = admin.execute(
                "SELECT indisunique, indisvalid FROM pg_index "
                "WHERE indexrelid = 'notification_push_active_destination_key'::regclass",
            ).fetchone()
            assert index == (True, True)
            assert admin.execute(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                "WHERE oid = 'notification_channels'::regclass",
            ).fetchone() == (True, True)
        finally:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(name)))


@pytest.mark.skipif(
    not DATABASE_URL or not os.environ.get("OMNICIO_TEST_POSTGRES_BIN"),
    reason="disposable PostgreSQL client and database are required",
)
def test_native_psql_reports_only_sqlstate_and_stdin_line() -> None:
    binary = Path(os.environ["OMNICIO_TEST_POSTGRES_BIN"])
    executable = binary / ("psql.exe" if os.name == "nt" else "psql")
    result = subprocess.run(
        [
            str(executable),
            "-X",
            "-d",
            DATABASE_URL,
            "-q",
            "-f",
            "-",
            "-v",
            "ON_ERROR_STOP=1",
            "-v",
            "VERBOSITY=sqlstate",
            "-v",
            "SHOW_CONTEXT=never",
        ],
        input="-- Input values must not appear in diagnostics.\n"
        "SELECT 'omnicio-private-error-canary'::integer;\n",
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 3
    assert re.fullmatch(r"psql:<stdin>:2: ERROR:\s+22P02", result.stderr.strip())
    assert result.stdout == ""


def _runtime_url() -> str:
    values = conninfo_to_dict(DATABASE_URL)
    values["user"] = "omnicio_runtime_test"
    values["password"] = RUNTIME_PASSWORD
    return make_conninfo(**values)


def _apply_all_migrations() -> None:
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        for migration in MIGRATIONS:
            conn.execute(migration.read_text(encoding="utf-8"))


def _seed_legacy_policy(runtime, version: int) -> None:
    """Existing financial settings are fixtures, not a current write API."""
    runtime.execute(
        "INSERT INTO balancing_policy_versions (user_id, version, max_instrument_percent, "
        "max_sector_percent, max_issuer_percent, max_group_percent, max_share_percent, "
        "max_bond_percent, max_etf_percent, max_below_grade_percent, max_unknown_percent, "
        "max_term_months, turnover_budget_percent, max_daily_turnover_participation_percent, "
        "securities_tax_rate_percent, uncertainty_haircut_percent, credit_loss_haircut_percent, "
        "no_trade_band_percent, min_replace_benefit_rub) "
        "VALUES (%s, %s, 20, 30, 20, 25, 70, 80, 70, 5, 0, 120, 25, 5, 15, 3, 2, 1, 500)",
        (USER_ONE, version),
    )


def _seed_legacy_proposal(runtime, snapshot_id: UUID, version: int) -> tuple[UUID, int]:
    """Persist synthetic old history through the actual immutable schema guards."""
    proposal_id = runtime.execute(
        "INSERT INTO portfolio_proposals (user_id, version, source_snapshot_id, account_id, "
        "profile_version, policy_version, scenario_kind, target_instrument_uid, proposal_hash, "
        "created_session_digest, payload, expires_at) "
        "VALUES (%s, %s, %s, 'account-1', 1, 1, 'deploy_cash', 'provider-bond-uid', %s, %s, "
        '\'{"schema":"omnicio.portfolio.proposal.v1","execution_enabled":false}\'::jsonb, '
        "now() + interval '30 minutes') RETURNING id",
        (USER_ONE, version, snapshot_id, b"p" * 32, b"s" * 32),
    ).fetchone()[0]
    action_id = runtime.execute(
        "INSERT INTO portfolio_proposal_actions (proposal_id, user_id, action, proposal_version, "
        "proposal_hash, session_digest) VALUES (%s, %s, 'confirmed', %s, %s, %s) RETURNING id",
        (proposal_id, USER_ONE, version, b"p" * 32, b"d" * 32),
    ).fetchone()[0]
    return proposal_id, action_id


def _seed_legacy_run(
    runtime, proposal_id: UUID, action_id: int, mode: str, mandate_id: UUID | None = None
) -> UUID:
    environment = {"shadow": None, "sandbox": "sandbox", "live": "prod"}[mode]
    return runtime.execute(
        "INSERT INTO portfolio_execution_runs (user_id, proposal_id, confirmed_action_id, "
        "proposal_version, proposal_hash, account_id, mode, provider_environment, "
        "live_mandate_id, created_session_digest) "
        "SELECT user_id, id, %s, version, proposal_hash, account_id, %s, %s, %s, %s "
        "FROM portfolio_proposals WHERE id = %s RETURNING id",
        (action_id, mode, environment, mandate_id, b"e" * 32, proposal_id),
    ).fetchone()[0]


def _seed_legacy_leg(runtime, run_id: UUID, state: str) -> UUID:
    return runtime.execute(
        "INSERT INTO portfolio_execution_legs (run_id, user_id, leg_index, action, "
        "instrument_uid, lots_requested, limit_price, limit_price_type, max_spend_rub, "
        "request_id, status) VALUES (%s, %s, 0, 'buy', 'provider-bond-uid', 2, 101.25, "
        "'point', 2500, gen_random_uuid(), %s) RETURNING id",
        (run_id, USER_ONE, state),
    ).fetchone()[0]


def _assert_legacy_source_guards(runtime, runs: dict[str, UUID], legs: dict[str, UUID]) -> None:
    with pytest.raises(
        psycopg.errors.RaiseException,
        match="execution source fields are immutable",
    ):
        runtime.execute(
            "UPDATE portfolio_execution_runs SET account_id = 'other' WHERE id = %s",
            (runs["live"],),
        )
    with pytest.raises(psycopg.errors.RaiseException, match="execution leg source fields"):
        runtime.execute(
            "UPDATE portfolio_execution_legs SET request_id = gen_random_uuid() WHERE id = %s",
            (legs["live"],),
        )
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        runtime.execute(
            "INSERT INTO portfolio_execution_events (run_id, leg_id, user_id, event_type) "
            "VALUES (%s, %s, %s, 'invalid_lineage')",
            (runs["live"], legs["sandbox"], USER_ONE),
        )


def _seed_and_check_legacy_records(runtime, snapshot_id: UUID) -> tuple[UUID, int]:
    """Retained historical rows stay immutable and tenant-bound after API retirement."""
    _seed_legacy_policy(runtime, 1)
    proposal_id, action_id = _seed_legacy_proposal(runtime, snapshot_id, 1)
    mandate_id = runtime.execute(
        "INSERT INTO portfolio_live_execution_mandates (user_id, account_id, "
        "max_order_notional_rub, max_daily_notional_rub, created_session_digest, expires_at) "
        "VALUES (%s, 'account-1', 3000, 5000, %s, now() + interval '30 minutes') RETURNING id",
        (USER_ONE, b"m" * 32),
    ).fetchone()[0]
    runs = {mode: _seed_legacy_run(runtime, proposal_id, action_id, mode,
                                 mandate_id if mode == "live" else None)
            for mode in ("shadow", "sandbox", "live")}
    legs = {mode: _seed_legacy_leg(runtime, run, "submitted" if mode == "sandbox" else "pending")
            for mode, run in runs.items()}
    _assert_legacy_source_guards(runtime, runs, legs)
    competing_id, competing_action = _seed_legacy_proposal(runtime, snapshot_id, 2)
    with pytest.raises(psycopg.errors.UniqueViolation, match="one_active_live"):
        _seed_legacy_run(runtime, competing_id, competing_action, "live", mandate_id)
    _seed_legacy_policy(runtime, 2)
    with pytest.raises(psycopg.errors.RaiseException, match="not an exact confirmed proposal"):
        _seed_legacy_run(runtime, competing_id, competing_action, "shadow")
    return proposal_id, action_id









def test_r6_execution_migration_has_valid_guards_and_event_lineage() -> None:
    migration = (ROOT / "migrations" / "0010_portfolio_execution.sql").read_text(encoding="utf-8")

    assert "omnicio_validate_execution_run_source" in migration
    assert "AS $omnicio$" in migration
    assert "execution leg source fields are immutable" in migration
    assert "portfolio_execution_legs_source_guard" in migration
    assert "UNIQUE (id, run_id, user_id)" in migration
    assert "FOREIGN KEY (leg_id, run_id, user_id)" in migration
    assert "REFERENCES portfolio_execution_legs(id, run_id, user_id)" in migration
    assert "TG_OP = 'INSERT' AND NOT EXISTS" in migration
    assert "p.expires_at > now()" in migration
    assert "p.source_snapshot_id, p.account_id" in migration
    assert "omnicio.financial_cleanup" in migration
    assert "'account_delete'" in migration
    assert "'broker_disconnect'" in migration
    assert "portfolio_proposals_source_snapshot_tenant_fkey" in migration
    assert "AS $omnicio_cleanup$" in migration
    assert "\nAS $\n" not in migration
    database_source = (ROOT / "src" / "omnicio" / "db.py").read_text(encoding="utf-8")
    assert "set_config('omnicio.financial_cleanup', 'account_delete', true)" in database_source
    assert "set_config('omnicio.financial_cleanup', 'broker_disconnect', true)" in database_source


def test_r7_live_execution_migration_requires_exact_mandate_and_fail_closed_mode() -> None:
    migration = (ROOT / "migrations" / "0011_portfolio_live_execution.sql").read_text(
        encoding="utf-8"
    )

    assert "portfolio_live_execution_mandates" in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "live_mandate_id" in migration
    assert "mode IN ('shadow', 'sandbox', 'live')" in migration
    assert "mode = 'live'" in migration
    assert "provider_environment = 'prod'" in migration
    assert "live execution requires an active exact-account mandate" in migration
    assert "portfolio_execution_runs_one_active_live_idx" in migration
    assert "portfolio_live_execution_mandates_active_idx" in migration
    assert "portfolio_live_execution_mandates_expiry_window" in migration
    assert "expires_at <= created_at + interval '24 hours'" in migration
    assert "omnicio_validate_live_submission_authority" in migration
    assert "portfolio_execution_legs_live_submission_guard" in migration
    assert "FOR SHARE OF m" in migration
    assert "live execution mandate is inactive before submission" in migration


@pytest.mark.skipif(
    not DATABASE_URL,
    reason="ephemeral PostgreSQL is required for migration integration coverage",
)
def test_migrations_apply_reapply_and_enforce_observer_rls() -> None:
    assert [item.name for item in MIGRATIONS][-3:] == [
        "0029_email_auth.sql", "0030_portfolio_read_only.sql", "0031_social_auth.sql",
    ]
    _apply_all_migrations()
    with psycopg.connect(DATABASE_URL, autocommit=True) as readiness:
        _assert_email_readiness(readiness)

    with psycopg.connect(DATABASE_URL, autocommit=True) as admin:
        # The additive latest migration is safe to retry before release. Once
        # accepted on main it becomes immutable migration history.
        admin.execute(
            (ROOT / "migrations" / "0011_portfolio_live_execution.sql").read_text(encoding="utf-8")
        )

        admin.execute(
            (ROOT / "migrations" / "0012_strategy_drafts.sql").read_text(encoding="utf-8")
        )

        admin.execute(
            (ROOT / "migrations" / "0013_strategy_assessment_admission.sql").read_text(
                encoding="utf-8"
            )
        )

        table_names = {
            row[0]
            for row in admin.execute(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                """
            ).fetchall()
        }
        assert {
            "instrument_catalog",
            "account_instrument_access",
            "investment_profile_versions",
            "job_runs",
            "portfolio_snapshots",
            "portfolio_snapshot_positions",
            "operation_observations",
            "broker_sync_state",
            "source_documents",
            "source_retrievals",
            "source_facts",
            "payout_events",
            "portfolio_risk_assessments",
            "balancing_policy_versions",
            "portfolio_proposals",
            "portfolio_proposal_actions",
            "portfolio_execution_runs",
            "portfolio_execution_legs",
            "portfolio_execution_events",
            "portfolio_live_execution_mandates",
            "strategy_drafts",
        } <= table_names

        protected = {
            row[0]: (row[1], row[2])
            for row in admin.execute(
                """
                SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
                FROM pg_class AS c
                JOIN pg_namespace AS n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relname = ANY (
                      ARRAY[
                          'account_instrument_access',
                          'investment_profile_versions',
                          'job_runs',
                          'portfolio_snapshots',
                          'portfolio_snapshot_positions',
                          'operation_observations',
                          'broker_sync_state',
                          'portfolio_risk_assessments',
                          'balancing_policy_versions',
                          'portfolio_proposals',
                          'portfolio_proposal_actions',
                          'portfolio_execution_runs',
                          'portfolio_execution_legs',
                          'portfolio_execution_events',
                          'portfolio_live_execution_mandates',
                          'strategy_drafts'
                      ]
                  )
                """
            ).fetchall()
        }
        assert len(protected) == 16
        assert all(rls and forced for rls, forced in protected.values())

        catalog_columns = {
            row[0]
            for row in admin.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'instrument_catalog'
                """
            ).fetchall()
        }
        assert "required_tests" not in catalog_columns
        assert {
            "nominal_value",
            "nominal_currency",
            "maturity_date",
            "floating_coupon",
            "perpetual",
            "amortization",
            "subordinated",
            "liquidity",
        } <= catalog_columns

        proposal_columns = {
            row[0]
            for row in admin.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'portfolio_proposals'
                """
            ).fetchall()
        }
        assert {
            "account_id",
            "created_session_digest",
            "proposal_hash",
            "payload",
            "expires_at",
        } <= proposal_columns

        proposal_action_columns = {
            row[0]
            for row in admin.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'portfolio_proposal_actions'
                """
            ).fetchall()
        }
        assert {
            "session_digest",
            "user_reason",
            "deferred_until",
            "proposal_hash",
        } <= proposal_action_columns

        semantic_indexes = {
            row[0]
            for row in admin.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = 'operation_observations'
                """
            ).fetchall()
        }
        assert "operation_observations_semantic_unique_idx" in semantic_indexes

        admin.execute(
            """
            INSERT INTO users (id)
            VALUES (%s), (%s)
            """,
            (USER_ONE, USER_TWO),
        )
        admin.execute(
            """
            INSERT INTO tbank_connection (user_id, account_id, environment, token_ciphertext)
            VALUES (%s, 'account-1', 'prod', %s), (%s, 'account-1', 'prod', %s)
            """,
            (USER_ONE, b"synthetic-one", USER_TWO, b"synthetic-two"),
        )
        admin.execute(
            """
            INSERT INTO instrument_catalog (
                provider,
                instrument_uid,
                instrument_type,
                provider_retrieved_at
            )
            VALUES ('tbank', 'instrument-1', 'share', now())
            """
        )

        admin.execute("DROP ROLE IF EXISTS omnicio_runtime_test")
        admin.execute(
            sql.SQL(
                """
                CREATE ROLE {}
                LOGIN
                PASSWORD {}
                NOSUPERUSER
                NOCREATEDB
                NOCREATEROLE
                NOINHERIT
                NOREPLICATION
                """
            ).format(
                sql.Identifier("omnicio_runtime_test"),
                sql.Literal(RUNTIME_PASSWORD),
            )
        )
        admin.execute("GRANT CONNECT ON DATABASE omnicio_test TO omnicio_runtime_test")
        admin.execute("GRANT USAGE ON SCHEMA public TO omnicio_runtime_test")
        admin.execute(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public "
            "TO omnicio_runtime_test"
        )
        admin.execute(
            "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO omnicio_runtime_test"
        )

    with psycopg.connect(_runtime_url(), autocommit=True) as runtime:
        runtime.execute(
            "SELECT set_config('omnicio.user_id', %s, false)",
            (str(USER_ONE),),
        )
        runtime.execute(
            """
            INSERT INTO investment_profile_versions (
                user_id,
                version,
                reserve_rub,
                planned_withdrawal_rub,
                horizon_months,
                max_drawdown_percent,
                liquidity_horizon_days,
                allow_below_investment_grade
            )
            VALUES (%s, 1, 100000, 0, 60, 20, 30, false)
            """,
            (USER_ONE,),
        )
        runtime.execute(
            """
            INSERT INTO account_instrument_access (
                user_id,
                account_id,
                provider,
                instrument_uid,
                required_tests,
                observed_at
            )
            VALUES (%s, 'account-1', 'tbank', 'instrument-1', '["test-one"]'::jsonb, now())
            """,
            (USER_ONE,),
        )
        runtime.execute(
            "SELECT set_config('omnicio.user_id', %s, false)",
            (str(USER_TWO),),
        )
        assert (
            runtime.execute("SELECT count(*) FROM investment_profile_versions").fetchone()[0] == 0
        )
        assert runtime.execute("SELECT count(*) FROM account_instrument_access").fetchone()[0] == 0

        runtime.execute(
            "SELECT set_config('omnicio.user_id', %s, false)",
            (str(USER_ONE),),
        )
        job_id = runtime.execute(
            """
            INSERT INTO job_runs (
                user_id,
                job_type,
                scheduled_for,
                status,
                attempt,
                started_at
            )
            VALUES (%s, 'portfolio_daily', current_date, 'running', 1, now())
            RETURNING id
            """,
            (USER_ONE,),
        ).fetchone()[0]
        snapshot_id = runtime.execute(
            """
            INSERT INTO portfolio_snapshots (
                user_id,
                job_run_id,
                account_id,
                environment,
                captured_at,
                analysis_status,
                nav_rub,
                rub_cash_total,
                rub_cash_blocked,
                rub_cash_unblocked,
                limits_loading_in_progress,
                evidence
            )
            VALUES (
                %s, %s, 'account-1', 'prod', now(), 'observed',
                1000, 100, 0, 100, false, '{}'::jsonb
            )
            RETURNING id
            """,
            (USER_ONE, job_id),
        ).fetchone()[0]
        runtime.execute(
            """
            INSERT INTO portfolio_risk_assessments (
                user_id,
                snapshot_id,
                instrument_uid,
                state,
                rating_status,
                fundamental_status,
                source_status,
                reasons,
                evidence,
                assessed_at
            )
            VALUES (
                %s, %s, 'instrument-1', 'data_missing', 'data_missing',
                'received', 'received', '[]'::jsonb, '{}'::jsonb, now()
            )
            """,
            (USER_ONE, snapshot_id),
        )

        source_id = runtime.execute(
            """
            INSERT INTO source_documents (
                provider,
                document_type,
                subject_uid,
                provider_key,
                source_url,
                first_retrieved_at,
                content_hash,
                payload
            )
            VALUES (
                'test', 'fundamental', 'asset-1', 'v1',
                'https://example.invalid/evidence', now(),
                decode(repeat('00', 32), 'hex'), '{"value": 1}'::jsonb
            )
            RETURNING id
            """
        ).fetchone()[0]
        with pytest.raises(psycopg.errors.RaiseException, match="immutable evidence"):
            runtime.execute(
                "UPDATE source_documents SET provider_key = 'changed' WHERE id = %s",
                (source_id,),
            )

        runtime.execute(
            """
            INSERT INTO instrument_catalog (
                provider,
                instrument_uid,
                figi,
                asset_uid,
                instrument_type,
                provider_retrieved_at
            )
            VALUES (
                'tbank',
                'provider-bond-uid',
                'FIGI-ONLY',
                'asset-fallback',
                'bond',
                now()
            )
            """
        )
        runtime.execute(
            """
            INSERT INTO portfolio_snapshot_positions (
                snapshot_id,
                user_id,
                instrument_uid,
                figi,
                ticker,
                instrument_type,
                quantity,
                blocked,
                blocked_lots,
                sector,
                country_of_risk
            )
            VALUES (
                %s,
                %s,
                'FIGI-ONLY',
                'FIGI-ONLY',
                'TESTBOND',
                'bond',
                1,
                false,
                0,
                'finance',
                'RU'
            )
            """,
            (snapshot_id, USER_ONE),
        )
        payout_source_id = runtime.execute(
            """
            INSERT INTO source_documents (
                provider,
                document_type,
                subject_uid,
                provider_key,
                source_url,
                first_retrieved_at,
                content_hash,
                payload
            )
            VALUES (
                'tbank',
                'bond_coupon',
                'provider-bond-uid',
                'coupon-1',
                'https://developer.tbank.ru/invest/services/instruments/methods',
                now(),
                decode(repeat('11', 32), 'hex'),
                '{"coupon": 1}'::jsonb
            )
            RETURNING id
            """
        ).fetchone()[0]
        runtime.execute(
            """
            INSERT INTO source_retrievals (source_document_id, retrieved_at)
            VALUES (%s, now())
            """,
            (payout_source_id,),
        )
        runtime.execute(
            """
            INSERT INTO payout_events (
                source_document_id,
                provider,
                instrument_uid,
                event_type,
                provider_key,
                expected_at,
                amount,
                currency,
                status,
                payload,
                semantic_hash
            )
            VALUES (
                %s,
                'tbank',
                'provider-bond-uid',
                'coupon',
                'coupon-1',
                now() + interval '30 days',
                42,
                'RUB',
                'scheduled',
                '{"coupon": 1}'::jsonb,
                decode(repeat('22', 32), 'hex')
            )
            """,
            (payout_source_id,),
        )

        database = Database(_runtime_url())
        database.open()
        try:
            store = PortfolioStore(database)

            visualization = store.portfolio_visualization(
                USER_ONE,
                history_limit=30,
            )
            assert visualization["status"] == "observed"
            latest_visualization = visualization["latest"]
            assert isinstance(latest_visualization, dict)
            assert latest_visualization["account_id"] == "account-1"
            assert latest_visualization["environment"] == "prod"
            assert latest_visualization["nav_rub"] == Decimal("1000")
            assert len(visualization["history"]) == 1
            positions = latest_visualization["positions"]
            assert isinstance(positions, list)
            assert any(
                item["instrument_uid"] == "FIGI-ONLY"
                and item["catalog_instrument_uid"] == "provider-bond-uid"
                for item in positions
            )

            other_tenant_visualization = store.portfolio_visualization(
                USER_TWO,
                history_limit=30,
            )
            assert other_tenant_visualization == {
                "status": "pending",
                "history": [],
                "latest": None,
            }

            instrument_visualization = store.instrument_visualization(
                USER_ONE,
                "FIGI-ONLY",
                history_limit=30,
            )
            assert instrument_visualization is not None
            assert instrument_visualization["account_id"] == "account-1"
            assert len(instrument_visualization["history"]) == 1
            assert instrument_visualization["latest"]["ticker"] == "TESTBOND"
            assert any(
                item["instrument_uid"] == "provider-bond-uid" and item["event_type"] == "coupon"
                for item in instrument_visualization["payouts"]
            )
            assert any(
                item["subject_uid"] == "provider-bond-uid"
                and item["document_type"] == "bond_coupon"
                for item in instrument_visualization["sources"]
            )
            assert (
                store.instrument_visualization(
                    USER_TWO,
                    "FIGI-ONLY",
                    history_limit=30,
                )
                is None
            )

            proposal_id, action_id = _seed_and_check_legacy_records(runtime, snapshot_id)
            current_policy = store.current_balancing_policy(USER_ONE)
            assert current_policy is not None
            assert current_policy.version == 2
            assert current_policy.max_instrument_percent == Decimal("20")
            assert runtime.execute("SELECT count(*) FROM portfolio_proposals").fetchone()[0] == 2


            # The user-facing journal filters both owner and event type, and
            # never serializes audit metadata (which is for server use only).
            with psycopg.connect(DATABASE_URL, autocommit=True) as audit_admin:
                audit_admin.execute(
                    "INSERT INTO audit_events (user_id, event_type, metadata) "
                    "VALUES (%s, 'login_succeeded', %s::jsonb), "
                    "(%s, 'internal_test_event', '{}'::jsonb)",
                    (USER_TWO, '{"private_marker": "not-for-the-journal"}', USER_ONE),
                )
            own_activity = database.recent_activity(USER_ONE)
            other_activity = database.recent_activity(USER_TWO)
            assert own_activity == []
            assert [item["event_type"] for item in other_activity] == ["login_succeeded"]
            assert all(set(item) == {"event_type", "created_at"} for item in other_activity)
            assert len(database.recent_activity(USER_TWO, limit=1)) == 1
        finally:
            database.close()
        with pytest.raises(
            psycopg.errors.RaiseException,
            match="immutable proposal",
        ):
            runtime.execute(
                "UPDATE portfolio_proposals SET version = version + 1 WHERE id = %s",
                (proposal_id,),
            )
        with pytest.raises(
            psycopg.errors.RaiseException,
            match="immutable proposal",
        ):
            runtime.execute(
                "DELETE FROM portfolio_proposal_actions WHERE id = %s",
                (action_id,),
            )

        runtime.execute(
            "SELECT set_config('omnicio.user_id', %s, false)",
            (str(USER_TWO),),
        )
        assert runtime.execute("SELECT count(*) FROM portfolio_risk_assessments").fetchone()[0] == 0
        assert runtime.execute("SELECT count(*) FROM balancing_policy_versions").fetchone()[0] == 0
        assert runtime.execute("SELECT count(*) FROM portfolio_proposals").fetchone()[0] == 0
        assert runtime.execute("SELECT count(*) FROM portfolio_proposal_actions").fetchone()[0] == 0
        assert runtime.execute("SELECT count(*) FROM portfolio_execution_runs").fetchone()[0] == 0
        assert runtime.execute("SELECT count(*) FROM portfolio_execution_legs").fetchone()[0] == 0
        assert runtime.execute("SELECT count(*) FROM portfolio_execution_events").fetchone()[0] == 0

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            runtime.execute(
                """
                INSERT INTO balancing_policy_versions (
                    user_id,
                    version,
                    max_instrument_percent,
                    max_sector_percent,
                    max_issuer_percent,
                    max_group_percent,
                    max_share_percent,
                    max_bond_percent,
                    max_etf_percent,
                    max_below_grade_percent,
                    max_unknown_percent,
                    max_term_months,
                    turnover_budget_percent,
                    max_daily_turnover_participation_percent,
                    securities_tax_rate_percent,
                    uncertainty_haircut_percent,
                    credit_loss_haircut_percent,
                    no_trade_band_percent,
                    min_replace_benefit_rub
                )
                VALUES (
                    %s, 3, 10, 20, 10, 15, 60, 80, 60, 0, 0, 120,
                    20, 5, 15, 3, 2, 1, 500
                )
                """,
                (USER_ONE,),
            )

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            runtime.execute(
                """
                INSERT INTO investment_profile_versions (
                    user_id,
                    version,
                    reserve_rub,
                    planned_withdrawal_rub,
                    horizon_months,
                    max_drawdown_percent,
                    liquidity_horizon_days,
                    allow_below_investment_grade
                )
                VALUES (%s, 2, 100000, 0, 60, 20, 30, false)
                """,
                (USER_ONE,),
            )

    with psycopg.connect(DATABASE_URL, autocommit=True) as admin:
        admin.execute(
            """
            INSERT INTO vkid_identities (user_id, vk_user_id, verified_at)
            VALUES (%s, 'r6-delete-regression', now())
            """,
            (USER_ONE,),
        )

    database = Database(DATABASE_URL)
    database.open()
    try:
        assert database.delete_user_account(USER_ONE) is True
    finally:
        database.close()

    with psycopg.connect(DATABASE_URL, autocommit=True) as admin:
        assert (
            admin.execute(
                "SELECT count(*) FROM users WHERE id = %s",
                (USER_ONE,),
            ).fetchone()[0]
            == 0
        )
        for table in (
            "portfolio_proposals",
            "portfolio_proposal_actions",
            "portfolio_execution_runs",
            "portfolio_execution_legs",
            "portfolio_execution_events",
        ):
            assert (
                admin.execute(
                    sql.SQL("SELECT count(*) FROM {} WHERE user_id = %s").format(
                        sql.Identifier(table)
                    ),
                    (USER_ONE,),
                ).fetchone()[0]
                == 0
            )
