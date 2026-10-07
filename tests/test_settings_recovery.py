"""Settings concurrency and real backup recovery on disposable, synthetic PostgreSQL.

The CI launcher owns the loopback cluster and its binaries. No production URL,
customer dump or provider credential is consumed by this drill.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import UUID, uuid4

import psycopg
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from omnicio.db import Database, UserRecord
from omnicio.main import app
from omnicio.portfolio_store import PortfolioStore, SettingsVersionConflict
from omnicio.recovery import database_guards, table_fingerprints
from omnicio.schema import READINESS_QUERY
from omnicio.security import decrypt_secret, encrypt_secret
from omnicio.strategy import preset_document
from omnicio.workspace import default_preferences

ROOT = Path(__file__).resolve().parents[1]
A, B = UUID(int=901), UUID(int=902)
PROFILE = dict(
    reserve_rub=Decimal("12345.67"),
    planned_withdrawal_rub=Decimal("1000.01"),
    horizon_months=60,
    max_drawdown_percent=Decimal("15"),
    liquidity_horizon_days=30,
    allow_below_investment_grade=False,
)
POLICY = dict(
    max_instrument_percent=Decimal("20"),
    max_sector_percent=Decimal("30"),
    max_issuer_percent=Decimal("20"),
    max_group_percent=Decimal("25"),
    max_share_percent=Decimal("70"),
    max_bond_percent=Decimal("80"),
    max_etf_percent=Decimal("70"),
    max_below_grade_percent=Decimal("5"),
    max_unknown_percent=Decimal("0"),
    max_term_months=120,
    turnover_budget_percent=Decimal("25"),
    max_daily_turnover_participation_percent=Decimal("5"),
    securities_tax_rate_percent=Decimal("15"),
    uncertainty_haircut_percent=Decimal("3"),
    credit_loss_haircut_percent=Decimal("2"),
    no_trade_band_percent=Decimal("1"),
    min_replace_benefit_rub=Decimal("500"),
)




@contextmanager
def database_store(dsn: str):
    db = Database(dsn)
    db.open()
    try:
        yield db, PortfolioStore(db)
    finally:
        db.close()


def _insert_historical_setting(
    db: Database, table: str, owner: UUID, version: int, values: dict[str, object],
) -> None:
    """Only synthetic recovery data may seed the retired confirmed-settings tables."""
    columns = ("user_id", "version", *values)
    with db.pool.connection() as conn, conn.transaction():
        conn.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(owner),))
        conn.execute(
            sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                sql.Identifier(table),
                sql.SQL(", ").join(map(sql.Identifier, columns)),
                sql.SQL(", ").join(sql.Placeholder() for _ in columns),
            ),
            (owner, version, *values.values()),
        )


def _seed_historical_settings(db: Database) -> None:
    for owner, version, reserve in ((A, 1, "12345.67"), (A, 2, "20000"), (B, 1, "7.25")):
        _insert_historical_setting(
            db, "investment_profile_versions", owner, version,
            {**PROFILE, "reserve_rub": Decimal(reserve)},
        )
    for version, instrument_limit in ((1, "20"), (2, "15")):
        _insert_historical_setting(
            db, "balancing_policy_versions", A, version,
            {**POLICY, "max_instrument_percent": Decimal(instrument_limit)},
        )
    with db.pool.connection() as conn:
        for owner, event in (
            (A, "investment_profile_saved"), (A, "investment_profile_saved"),
            (A, "balancing_policy_saved"), (A, "balancing_policy_saved"),
            (B, "investment_profile_saved"),
        ):
            conn.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(owner),))
            conn.execute(
                "INSERT INTO audit_events (user_id, event_type) VALUES (%s, %s)", (owner, event),
            )


def _verify_restored(dsn: str, role: str, password: str, key: str, expected, guards) -> None:
    with psycopg.connect(dsn, autocommit=True) as admin:
        assert table_fingerprints(admin) == expected
        assert database_guards(admin) == guards
        encrypted = admin.execute("SELECT token_ciphertext FROM tbank_connection").fetchone()[0]
        assert decrypt_secret(bytes(encrypted), key) == "synthetic-broker-token"
        assert admin.execute(READINESS_QUERY).fetchone()[0]
        for incomplete_schema in (
            "ALTER TABLE portfolio_execution_legs DISABLE TRIGGER strategy_submission_authority",
            "ALTER TABLE billing_payments RENAME cancel_attempted_at TO missing_cancel_receipt",
        ):
            with admin.transaction(force_rollback=True):
                admin.execute(incomplete_schema)
                assert admin.execute(READINESS_QUERY).fetchone()[0] is False
        assert admin.execute(READINESS_QUERY).fetchone()[0]
        admin.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
        assert admin.execute("SELECT * FROM investment_profile_versions").fetchall() == []
        assert admin.execute("SELECT * FROM strategy_drafts").fetchall() == []
        with admin.transaction():
            admin.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(A),))
            assert {
                r[0]
                for r in admin.execute("SELECT user_id FROM investment_profile_versions").fetchall()
            } == {A}
            assert {r[0] for r in admin.execute("SELECT user_id FROM "
                "strategy_drafts").fetchall()} == {A}
            assert admin.execute("UPDATE strategy_drafts SET version=99 WHERE "
                "user_id=%s", (B,)).rowcount == 0
            updated = admin.execute(
                "UPDATE investment_profile_versions SET reserve_rub = 0 WHERE user_id = %s",
                (B,),
            )
            assert updated.rowcount == 0
        with admin.transaction():
            admin.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(A),))
            with pytest.raises(psycopg.errors.InsufficientPrivilege), admin.transaction():
                admin.execute(
                    "INSERT INTO investment_profile_versions "
                    "(user_id,version,reserve_rub,planned_withdrawal_rub,horizon_months,"
                    "max_drawdown_percent,liquidity_horizon_days,allow_below_investment_grade) "
                    "VALUES (%s,99,0,0,12,10,7,false)",
                    (B,),
                )
    runtime_dsn = make_conninfo(dsn, user=role, password=password)
    with database_store(runtime_dsn) as (db, store):
        assert db.healthcheck()
        assert store.current_profile(B).reserve_rub == Decimal("7.25")
        assert store.current_profile(A).version == 2
        assert store.current_strategy_draft(A)["version"] == 4
        assert store.current_strategy_draft(B)["document"]["profile"]["reserve_rub"] == "7.01"
        # Current working-copy writes survive restore; confirmed history stays
        # unchanged. Sequences are independently checked with synthetic SQL.
        previous = store.current_profile(A)
        revised = store.save_strategy_draft(A, preset_document("balanced"), expected_version=4)
        assert revised["version"] == 5
        assert store.current_profile(A) == previous
        _insert_historical_setting(db, "investment_profile_versions", A, 3, PROFILE)
        assert store.current_profile(A).id > previous.id
        assert store.current_profile(A).version == 3
        assert store.current_profile(B).version == 1


@pytest.mark.skipif(
    not os.environ.get("OMNICIO_TEST_POSTGRES_BIN"),
    reason="the disposable PostgreSQL CI launcher supplies dump/restore binaries",
)
def test_dump_restore_preserves_settings_and_tenant_isolation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    base = os.environ["OMNICIO_TEST_DATABASE_URL"]
    options = conninfo_to_dict(base)
    assert options["host"] == "127.0.0.1"
    assert options["dbname"] == "omnicio_test"
    binary = Path(os.environ["OMNICIO_TEST_POSTGRES_BIN"])
    identity = uuid4().hex
    source, target, role = (
        f"omnicio_recovery_{identity}_{suffix}" for suffix in ("src", "dst", "role")
    )
    password = uuid4().hex
    key = Fernet.generate_key().decode("ascii")
    created = []
    with psycopg.connect(base, autocommit=True) as control:
        assert int(control.execute("SHOW server_version_num").fetchone()[0]) // 10000 == 18
        control.execute(
            sql.SQL(
                "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                "NOREPLICATION NOBYPASSRLS PASSWORD {}"
            ).format(sql.Identifier(role), sql.Literal(password))
        )
        try:
            for name in (source, target):
                control.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
                created.append(name)
            source_dsn = make_conninfo(base, dbname=source)
            target_dsn = make_conninfo(base, dbname=target)
            with psycopg.connect(source_dsn, autocommit=True) as admin:
                for migration in sorted((ROOT / "migrations").glob("*.sql")):
                    admin.execute(migration.read_text(encoding="utf-8"))
                admin.execute("INSERT INTO users (id) VALUES (%s), (%s)", (A, B))
                admin.execute(
                    "INSERT INTO vkid_identities (user_id,vk_user_id,verified_at) "
                    "VALUES (%s,'synthetic-a',now()),(%s,'synthetic-b',now())",
                    (A, B),
                )
                admin.execute(
                    "INSERT INTO tbank_connection "
                    "(user_id,environment,account_id,token_ciphertext) "
                    "VALUES (%s,'sandbox','synthetic-account',%s)",
                    (A, encrypt_secret("synthetic-broker-token", key)),
                )
                admin.execute(
                    sql.SQL(
                        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}"
                    ).format(sql.Identifier(role))
                )
                admin.execute(
                    sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(
                        sql.Identifier(role)
                    )
                )
            with database_store(make_conninfo(source_dsn, user=role, password=password)) as (
                db,
                store,
            ):
                _seed_historical_settings(db)
                _exercise_strategy_drafts(store, db)
                _exercise_strategy_admission(store, db)
            with psycopg.connect(source_dsn, autocommit=True) as admin:
                admin.execute(
                    sql.SQL(
                        "ALTER TABLE strategy_drafts ADD CONSTRAINT synthetic_draft_failure "
                        "CHECK (user_id <> {} OR version < 2) NOT VALID"
                    ).format(sql.Literal(B))
                )
            with database_store(make_conninfo(source_dsn, user=role, password=password)) as (
                db,
                store,
            ):
                before = store.current_strategy_draft(B)
                changed = copy.deepcopy(before["document"])
                changed["profile"]["reserve_rub"] = "99"
                with pytest.raises(psycopg.errors.CheckViolation):
                    store.save_strategy_draft(B, changed, expected_version=1)
                assert store.current_strategy_draft(B) == before
                assert store.current_profile(B).version == 1
                assert len(db.recent_activity(B)) == 1
            with psycopg.connect(source_dsn, autocommit=True) as admin:
                admin.execute("ALTER TABLE strategy_drafts DROP CONSTRAINT synthetic_draft_failure")
                expected, guards = table_fingerprints(admin), database_guards(admin)
            archive = tmp_path / "synthetic.dump"
            started = time.monotonic()
            subprocess.run(
                [
                    str(binary / "pg_dump.exe"),
                    "--format=custom",
                    "--no-password",
                    "--file",
                    str(archive),
                    source_dsn,
                ],
                check=True,
                capture_output=True,
                timeout=90,
            )
            # Encryption key is separate from the backup file, and no customer data is involved.
            ciphertext = Fernet(key).encrypt(archive.read_bytes())
            archive.unlink()
            (tmp_path / "synthetic.dump.encrypted").write_bytes(ciphertext)
            archive.write_bytes(Fernet(key).decrypt(ciphertext))
            restore = [
                str(binary / "pg_restore.exe"),
                "--exit-on-error",
                "--single-transaction",
                "--no-password",
                "--dbname",
                target_dsn,
            ]
            broken = tmp_path / "truncated.dump"
            broken.write_bytes(archive.read_bytes()[: archive.stat().st_size // 2])
            failed = subprocess.run([*restore, str(broken)], capture_output=True, timeout=90)
            assert failed.returncode != 0
            with psycopg.connect(target_dsn) as restored:
                assert table_fingerprints(restored) == {}
            subprocess.run([*restore, str(archive)], check=True, capture_output=True, timeout=90)
            _verify_restored(target_dsn, role, password, key, expected, guards)
            duration = round(time.monotonic() - started, 2)
            report = (
                f"Synthetic PostgreSQL 18 recovery: {len(expected)} tables, two isolated users, "
                f"encrypted archive, truncated-restore rollback, {duration}s. "
                "This is not a production-backup recovery proof."
            )
            with capsys.disabled():
                print(report)
            summary = os.environ.get("GITHUB_STEP_SUMMARY")
            if summary:
                with Path(summary).open("a", encoding="utf-8") as output:
                    output.write(f"\n- {report}\n")

        finally:
            for name in reversed(created):
                control.execute(
                    sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
                )
            control.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


@pytest.mark.skipif(
    not os.environ.get("OMNICIO_TEST_POSTGRES_BIN"),
    reason="the disposable PostgreSQL CI launcher supplies isolated cluster binaries",
)
def test_operator_logical_restore_tool_uses_distinct_cluster_and_authenticated_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise the actual operator commands on two synthetic disposable clusters."""
    from omnicio.recovery import verified_recovery_evidence

    script = ROOT / ".github/scripts/timeweb_recovery.py"
    monkeypatch.syspath_prepend(str(script.parent))
    runner = importlib.import_module("run_recovery_drill")
    spec = importlib.util.spec_from_file_location("synthetic_operator_restore", script)
    assert spec is not None
    assert spec.loader is not None
    recovery = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, recovery)
    spec.loader.exec_module(recovery)
    monkeypatch.setattr(recovery, "RESTORE_ROOT", tmp_path)
    binary = Path(os.environ["OMNICIO_TEST_POSTGRES_BIN"])
    suffix = ".exe" if os.name == "nt" else ""
    base = os.environ["OMNICIO_TEST_DATABASE_URL"]
    options = conninfo_to_dict(base)
    assert options["host"] == "127.0.0.1"
    assert options["dbname"] == "omnicio_test"
    source_name = "omnicio_export_" + uuid4().hex
    target_data = tmp_path / "target"
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    signing_key = "synthetic-operator-receipt-" + uuid4().hex
    archive_key = Fernet.generate_key().decode()
    release_sha = "a" * 40
    try:
        runner.native(
            [str(binary / f"initdb{suffix}"), "-D", str(target_data),
             "-U", "postgres", "-A", "trust"], timeout=90,
        )
        runner.native(
            [str(binary / f"pg_ctl{suffix}"), "-D", str(target_data),
             "-l", str(tmp_path / "pg.log"), "-o", f"-h 127.0.0.1 -p {port} -F",
             "-w", "-t", "30", "start"], timeout=45,
        )
        with psycopg.connect(base, autocommit=True) as control:
            control.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(source_name)))
            try:
                source_dsn = make_conninfo(base, dbname=source_name)
                with psycopg.connect(source_dsn, autocommit=True) as source:
                    for migration in sorted((ROOT / "migrations").glob("*.sql")):
                        source.execute(migration.read_text(encoding="utf-8"))
                    source.execute("INSERT INTO users (id) VALUES (%s), (%s)", (A, B))
                    for owner in (A, B):
                        source.execute(
                            "INSERT INTO workspace_preferences (user_id, version, document) "
                            "VALUES (%s, 1, %s::jsonb)",
                            (owner, json.dumps(default_preferences())),
                        )
                manifest = recovery.export_logical_archive(
                    source_dsn, binary, cluster_id=recovery.load_policy().cluster_id,
                    release_sha=release_sha, signing_key=signing_key, archive_key=archive_key,
                )
                archive = recovery.restore_artifact_path("database.dump.encrypted")
                assert not archive.read_bytes().startswith(b"PGDMP")
                with pytest.raises(recovery.RecoveryBlocked, match="same PostgreSQL cluster"):
                    recovery.verify_logical_archive(
                        base, binary, manifest, release_sha=release_sha,
                        signing_key=signing_key, archive_key=archive_key,
                    )
                isolated = f"postgresql://postgres@127.0.0.1:{port}/postgres"
                receipt = recovery.verify_logical_archive(
                    isolated, binary, manifest, release_sha=release_sha,
                    signing_key=signing_key, archive_key=archive_key,
                )
                proof = verified_recovery_evidence(receipt, signing_key)
                assert proof is not None
                assert all(proof["checks"].values())
                assert proof["source_system_id"] != proof["target_system_id"]
                with psycopg.connect(isolated) as target:
                    assert target.execute(
                        "SELECT count(*) FROM pg_database WHERE datname LIKE 'omnicio_restore_%%'",
                    ).fetchone()[0] == 0
                    assert target.execute(
                        "SELECT count(*) FROM pg_roles WHERE rolname LIKE 'omnicio_restore_%%'",
                    ).fetchone()[0] == 0
            finally:
                control.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                    sql.Identifier(source_name),
                ))
    finally:
        if (target_data / "postmaster.pid").exists():
            runner.native(
                [str(binary / f"pg_ctl{suffix}"), "-D", str(target_data),
                 "-m", "fast", "-w", "-t", "30", "stop"], timeout=45,
            )


def test_strategy_draft_api_requires_owner_origin_version_and_keeps_authority_separate() -> None:
    database = Mock(spec=Database)
    database.has_legal_versions.return_value = True
    store = Mock(spec=PortfolioStore)
    document = preset_document("balanced")
    request_body = {"expected_public_id": "000000901", "expected_version": 0,
                    "intent": "select", "document": document}
    headers = {"Origin": "https://omnicio.ru", "X-Omnicio-Profile": "000000901"}
    with (
        patch("omnicio.main.service") as auth,
        patch("omnicio.main.portfolio_store", return_value=store),
        patch.object(app.state, "database", database, create=True),
    ):
        auth.return_value.refresh_session.side_effect = lambda token: {
            "a": UserRecord(A, 901, "active", "user"),
            "b": UserRecord(B, 902, "active", "user"),
        }.get(token)
        client = TestClient(app, cookies={"omnicio_session": "a"})
        catalog = client.get("/api/strategy/catalog")
        assert catalog.status_code == 200
        assert len(catalog.json()["presets"]) == 10
        store.current_strategy_draft.return_value = None
        loaded = client.get("/api/profile/strategy", headers=headers)
        assert loaded.status_code == 200
        assert loaded.json() == {"public_id": "000000901", "selection": None}
        store.save_strategy_draft.assert_not_called()
        for bad in (-1, True, "0", 1.2):
            response = client.put("/api/profile/strategy", headers=headers,
                                  json={**request_body, "expected_version": bad})
            assert response.status_code == 422
        hostile = client.put("/api/profile/strategy", json=request_body,
                             headers={**headers, "Origin": "https://other.invalid"})
        assert hostile.status_code == 403
        other = TestClient(app, cookies={"omnicio_session": "b"}).put(
            "/api/profile/strategy", json=request_body,
            headers={**headers, "X-Omnicio-Profile": "000000902"},
        )
        assert other.status_code == 409
        anonymous = TestClient(app).put("/api/profile/strategy", headers=headers, json=request_body)
        assert anonymous.status_code == 401
        store.save_strategy_draft.assert_not_called()
        saved = {"version": 1, "document": document, "custom_document": None,
                 "updated_at": datetime.now(UTC), "fingerprint": "a" * 64}
        store.save_strategy_draft.return_value = saved
        response = client.put("/api/profile/strategy?user_id=" + str(B),
                              headers=headers, json=request_body)
        assert response.status_code == 200
        assert response.json()["public_id"] == "000000901"
        assert response.json()["applied_to_confirmed_policy"] is False
        assert response.json()["broker_execution_enabled"] is False
        assert response.headers["cache-control"] == "private, no-store"
        assert store.save_strategy_draft.call_args.args[0] == A
        assert store.save_strategy_draft.call_args.kwargs["expected_version"] == 0
        assert {call[0] for call in store.mock_calls} == {
            "current_strategy_draft", "save_strategy_draft",
        }
        edited = preset_document("balanced")
        edited["policy"]["max_issuer_percent"] = "4.1234"
        response = client.put("/api/profile/strategy", headers=headers,
                              json={**request_body, "intent": "edit", "document": edited})
        assert response.status_code == 200
        assert store.save_strategy_draft.call_args.args[1]["customized"] is True
        before = store.save_strategy_draft.call_count
        response = client.put("/api/profile/strategy", headers=headers,
                              json={**request_body, "document": edited})
        assert response.status_code == 422
        assert store.save_strategy_draft.call_count == before
        store.save_strategy_draft.side_effect = SettingsVersionConflict("settings_version_conflict")
        response = client.put("/api/profile/strategy", headers=headers, json=request_body)
        assert response.status_code == 409
        assert response.headers["cache-control"] == "private, no-store"


def _exercise_strategy_drafts(store: PortfolioStore, db: Database) -> None:
    a_profile = store.current_profile(A)
    a_policy = store.current_balancing_policy(A)
    activity = db.recent_activity(A)
    assert store.current_strategy_draft(A) is None
    document = preset_document("income")
    first = store.save_strategy_draft(A, document, expected_version=0)
    assert first["version"] == 1
    assert store.save_strategy_draft(A, document, expected_version=0) == first
    document["customized"] = True
    document["profile"]["reserve_rub"] = "100.12345678"
    personal = store.save_strategy_draft(A, document, expected_version=1)
    assert personal["version"] == 2
    assert personal["custom_document"] == personal["document"]
    b_document = preset_document("balanced")
    b_document["customized"] = True
    b_document["profile"]["reserve_rub"] = "7.01"
    store.save_strategy_draft(B, b_document, expected_version=0)
    preset = store.save_strategy_draft(A, preset_document("bogle"), expected_version=2)
    assert preset["version"] == 3
    assert preset["custom_document"] == personal["document"]

    def concurrent_write(amount: str) -> str:
        candidate = preset_document("bogle")
        candidate["customized"] = True
        candidate["profile"]["reserve_rub"] = amount
        try:
            store.save_strategy_draft(A, candidate, expected_version=3)
            return "saved"
        except SettingsVersionConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as threads:
        assert sorted(threads.map(concurrent_write, ("1000", "2000"))) == ["conflict", "saved"]
    assert store.current_strategy_draft(A)["version"] == 4
    assert store.current_strategy_draft(B)["document"]["profile"]["reserve_rub"] == "7.01"
    assert store.current_profile(A) == a_profile
    assert store.current_balancing_policy(A) == a_policy
    assert db.recent_activity(A) == activity


def test_strategy_research_is_versioned_read_only_and_owner_bound(monkeypatch) -> None:
    from test_backtest import END, START, prices, research_document

    from omnicio import main
    from omnicio.broker import BrokerConnectionStatus, BrokerService
    from omnicio.research_store import ResearchStore

    user = UserRecord(A, 123, "active", "user")
    database = Mock(spec=Database)
    database.has_legal_versions.return_value = True
    auth = Mock()
    auth.refresh_session.return_value = user
    monkeypatch.setattr(main, "service", lambda request: auth)
    monkeypatch.setattr(app.state, "database", database, raising=False)
    client = TestClient(
        app, cookies={"omnicio_session": "synthetic-session"},
        headers={"X-Omnicio-Profile": "000000123"},
    )
    document = research_document()
    before = copy.deepcopy(document)
    store = Mock(spec=PortfolioStore)
    store.current_strategy_draft.return_value = {"version": 4, "document": document}
    store.latest_balancing_context.return_value = {
        "account_id": "synthetic-a", "holdings": [],
        "candidates": [{
            "instrument_uid": "a", "ticker": "TEST", "instrument_type": "share",
            "currency": "RUB", "lot": 1, "sector": "synthetic",
            "provider_retrieved_at": START, "asset_uid": "asset-a",
        }],
    }
    broker = Mock(spec=BrokerService)
    broker.status.return_value = BrokerConnectionStatus(
        connected=True, environment="prod", account_id="synthetic-a", verified_at=START,
    )
    broker.candidate_fundamentals.return_value = ()
    broker.candidate_daily_exchange_candles.return_value = prices("a").candles
    research = Mock(wraps=main.strategy_research)
    archive = Mock(spec=ResearchStore)
    archive.evidence.return_value = {"version": 0, "document": {"assets": []}, "received_at": None}
    archive.save_run.return_value = {"id": str(UUID(int=900)), "replay_available": True}
    monkeypatch.setattr(app.state, "research_store", archive, raising=False)
    monkeypatch.setattr(main, "market_service", lambda request: Mock(cbr=None))
    monkeypatch.setattr(main, "portfolio_store", lambda request: store)
    monkeypatch.setattr(main, "broker_service", lambda request: broker)
    monkeypatch.setattr(main, "strategy_research", research)
    body = {
        "expected_public_id": "000000123", "expected_version": 4,
        "from_at": START.isoformat(), "to_at": END.isoformat(),
        "commission_bps": "10", "slippage_bps": "5", "initial_capital_rub": "20000",
    }
    response = client.post(
        "/api/profile/strategy/research", headers={"Origin": "https://omnicio.ru"},
        json=body,
    )
    assert response.status_code == 200
    assert response.json()["public_id"] == "000000123"
    assert response.json()["strategy_version"] == 4
    assert response.json()["status"] == "computed"
    assert response.json()["probability_of_profit"] is None
    assert response.json()["execution_enabled"] is False
    assert response.headers["Cache-Control"] == "private, no-store"
    research.assert_called_once_with(
        user_id=user.id, expected_version=4, store=store, broker=broker,
        from_at=START, to_at=END, commission_bps=Decimal("10"),
        slippage_bps=Decimal("5"), initial_capital_rub=Decimal("20000"),
        research_store=archive, cbr=None,
    )
    broker.candidate_daily_exchange_candles.assert_called_once_with(
        user.id, "a", from_at=START, to_at=END,
    )
    response = client.post(
        "/api/profile/strategy/research", headers={"Origin": "https://omnicio.ru"},
        json={**body, "expected_version": 3},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "settings_version_conflict"
    assert broker.candidate_daily_exchange_candles.call_count == 1
    assert document == before
    for headers, payload, expected_status in (
        ({"Origin": "https://evil.example"}, body, 403),
        ({"Origin": "https://omnicio.ru"}, {**body, "expected_public_id": "000000999"}, 409),
        ({"Origin": "https://omnicio.ru"}, {**body, "user_id": str(B)}, 422),
        ({"Origin": "https://omnicio.ru"}, {**body, "initial_capital_rub": "NaN"}, 422),
        ({"Origin": "https://omnicio.ru"}, {**body, "commission_bps": "-1"}, 422),
        ({"Origin": "https://omnicio.ru"}, {**body, "from_at": END.isoformat()}, 422),
    ):
        rejected = client.post("/api/profile/strategy/research", headers=headers, json=payload)
        assert rejected.status_code == expected_status
        assert broker.candidate_daily_exchange_candles.call_count == 1

    auth.refresh_session.return_value = UserRecord(B, 999, "active", "user")
    switched = client.post(
        "/api/profile/strategy/research", headers={"Origin": "https://omnicio.ru"}, json=body,
    )
    assert switched.status_code == 409
    assert broker.candidate_daily_exchange_candles.call_count == 1

    for revoked_context, expected_status in (("session", 401), ("consent", 409)):
        auth.refresh_session.return_value = user
        database.has_legal_versions.return_value = True

        def provider_read(owner, uid, *, context=revoked_context, **kwargs):
            if context == "session":
                auth.refresh_session.return_value = None
            else:
                database.has_legal_versions.return_value = False
            return prices(uid).candles

        broker.candidate_daily_exchange_candles.side_effect = provider_read
        count = broker.candidate_daily_exchange_candles.call_count
        revoked = client.post(
            "/api/profile/strategy/research", headers={"Origin": "https://omnicio.ru"}, json=body,
        )
        assert revoked.status_code == expected_status
        assert broker.candidate_daily_exchange_candles.call_count == count + 1
        assert "equity_curve" not in revoked.json()
        assert "metrics" not in revoked.json()

    assert document == before
    assert {call[0] for call in store.mock_calls} == {
        "current_strategy_draft", "latest_balancing_context",
    }
    assert {call[0] for call in broker.mock_calls} == {
        "status", "candidate_fundamentals", "candidate_daily_exchange_candles",
    }



def _exercise_strategy_admission(store: PortfolioStore, db: Database) -> None:
    """Distinct worker processes share admission; cooldown survives pool restart."""
    before = store.current_strategy_draft(A)
    child = (
        "import os; from uuid import UUID; from omnicio.db import Database; "
        "db=Database(os.environ['SYNTHETIC_SLOT_DSN']); db.open(); "
        "slot=db.strategy_assessment_slot(UUID(os.environ['SYNTHETIC_SLOT_OWNER'])); "
        "print(slot.__enter__()); slot.__exit__(None,None,None); db.close()"
    )
    def another_worker(owner):
        result = subprocess.run(
            [sys.executable, "-c", child], check=True, capture_output=True, text=True, timeout=20,
            env={**os.environ, "SYNTHETIC_SLOT_DSN": db.pool.conninfo,
                 "SYNTHETIC_SLOT_OWNER": str(owner)},
        )
        return result.stdout.strip() == "True"

    def expire(owner):
        with db.pool.connection() as conn, conn.transaction():
            conn.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(owner),))
            conn.execute("UPDATE strategy_drafts SET next_assessment_at = "
                         "clock_timestamp() - interval '1 second' WHERE user_id=%s", (owner,))

    with db.strategy_assessment_slot(A) as admitted:
        assert admitted is True
        expire(A)  # Even after cooldown expires, the in-flight session still excludes A.
        assert another_worker(A) is False
        assert another_worker(B) is True
    assert another_worker(A) is True
    assert another_worker(A) is False  # Previous process exited; cooldown persists in the database.
    expire(A)
    with (pytest.raises(RuntimeError, match="synthetic cancellation"),
          db.strategy_assessment_slot(A) as admitted):
        assert admitted is True
        raise RuntimeError("synthetic cancellation")
    expire(A)
    assert another_worker(A) is True  # Failure released the session lock.
    assert store.current_strategy_draft(A) == before  # No strategy version/amount changes.
    with db.pool.connection() as conn, conn.transaction():
        conn.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(B),))
        assert conn.execute("UPDATE strategy_drafts SET next_assessment_at='-infinity' "
                            "WHERE user_id=%s RETURNING user_id", (A,)).fetchone() is None
