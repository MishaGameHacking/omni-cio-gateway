"""Settings concurrency and real backup recovery on disposable, synthetic PostgreSQL.

The CI launcher owns the loopback cluster and its binaries. No production URL,
customer dump or provider credential is consumed by this drill.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import asdict
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
from omnicio.portfolio_store import (
    BalancingPolicyInput,
    BalancingPolicyRecord,
    InvestmentProfileRecord,
    PortfolioStore,
    SettingsVersionConflict,
)
from omnicio.security import decrypt_secret, encrypt_secret

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
POLICY = BalancingPolicyInput(
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


@pytest.mark.parametrize("kind", ["investment", "balancing"])
def test_settings_writes_require_version_and_session_owner(kind: str) -> None:
    values = PROFILE if kind == "investment" else asdict(POLICY)
    payload = {
        key: str(value) if isinstance(value, Decimal) else value for key, value in values.items()
    }
    payload["expected_public_id"] = "000000901"
    path = f"/api/profile/{kind}"
    database = Mock(spec=Database)
    database.has_legal_versions.return_value = True
    store = Mock(spec=PortfolioStore)
    writer = store.save_profile if kind == "investment" else store.save_balancing_policy
    writer.side_effect = SettingsVersionConflict("settings_version_conflict")
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
        headers = {"Origin": "https://omnicio.ru", "X-Omnicio-Profile": "000000901"}
        missing = client.put(path, json=payload, headers=headers)
        assert missing.status_code == 422
        for bad in (-1, True, "1", 1.2):
            invalid = client.put(path, json={**payload, "expected_version": bad}, headers=headers)
            assert invalid.status_code == 422
        writer.assert_not_called()
        for token, owner in (("a", A), ("b", B)):
            signed_in = TestClient(app, cookies={"omnicio_session": token})
            conflict = signed_in.put(
                path + f"?user_id={B}",
                json={**payload, "expected_version": 2, "expected_public_id": f"{owner.int:09d}"},
                headers={**headers, "X-Omnicio-Profile": f"{owner.int:09d}"},
            )
            assert conflict.status_code == 409
            assert conflict.json()["detail"] == "settings_version_conflict"
            assert conflict.headers["cache-control"] == "private, no-store"
            assert writer.call_args.args[0] == owner
            assert writer.call_args.kwargs["expected_version"] == 2
        calls = writer.call_count
        switched = TestClient(app, cookies={"omnicio_session": "b"}).put(
            path,
            json={**payload, "expected_version": 2},
            headers={**headers, "X-Omnicio-Profile": "000000902"},
        )
        assert switched.status_code == 409
        assert switched.json()["detail"] == "settings_owner_conflict"
        assert writer.call_count == calls
        anonymous = TestClient(app).put(
            path,
            json={**payload, "expected_version": 2},
            headers=headers,
        )
        assert anonymous.status_code == 401
        assert writer.call_count == calls
        writer.side_effect = None
        record_type = InvestmentProfileRecord if kind == "investment" else BalancingPolicyRecord
        writer.return_value = record_type(
            id=1,
            user_id=A,
            version=3,
            created_at=datetime.now(UTC),
            **values,
        )
        saved = client.put(path, json={**payload, "expected_version": 2}, headers=headers)
        assert saved.status_code == 200
        key = "profile" if kind == "investment" else "policy"
        assert saved.json()[key]["version"] == 3
        assert saved.headers["cache-control"] == "private, no-store"


@contextmanager
def database_store(dsn: str):
    db = Database(dsn)
    db.open()
    try:
        yield db, PortfolioStore(db)
    finally:
        db.close()


def table_fingerprints(conn):
    tables = conn.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
    ).fetchall()
    result = {}
    for (name,) in tables:
        rows = conn.execute(
            sql.SQL(
                "SELECT row_to_json(t)::text FROM {} AS t ORDER BY row_to_json(t)::text"
            ).format(sql.Identifier("public", name))
        ).fetchall()
        result[name] = (
            len(rows),
            hashlib.sha256("\n".join(r[0] for r in rows).encode()).hexdigest(),
        )
    return result


def database_guards(conn):
    return conn.execute("""
        SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
               p.policyname, p.qual, p.with_check
        FROM pg_class c JOIN pg_namespace n ON c.relnamespace = n.oid
        LEFT JOIN pg_policies p ON p.schemaname = n.nspname AND p.tablename = c.relname
        WHERE n.nspname = 'public' AND c.relkind = 'r'
        ORDER BY c.relname, p.policyname
    """).fetchall()


def _exercise_settings(store: PortfolioStore, db: Database) -> None:
    first = store.save_profile(A, expected_version=0, **PROFILE)
    repeated = store.save_profile(A, expected_version=0, **PROFILE)
    assert repeated.id == first.id

    # Two clients both loaded v1; exactly one differing write can win.
    def save(reserve: str) -> str:
        try:
            store.save_profile(
                A, expected_version=1, **{**PROFILE, "reserve_rub": Decimal(reserve)}
            )
            return "saved"
        except SettingsVersionConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as threads:
        assert sorted(threads.map(save, ("20000", "30000"))) == ["conflict", "saved"]
    store.save_profile(B, expected_version=0, **{**PROFILE, "reserve_rub": Decimal("7.25")})
    first_policy = store.save_balancing_policy(A, POLICY, expected_version=0)
    assert store.save_balancing_policy(A, POLICY, expected_version=0).id == first_policy.id
    changed = BalancingPolicyInput(**{**asdict(POLICY), "max_instrument_percent": Decimal("15")})
    store.save_balancing_policy(A, changed, expected_version=1)
    with pytest.raises(SettingsVersionConflict):
        store.save_balancing_policy(A, POLICY, expected_version=1)
    with pytest.raises(SettingsVersionConflict):
        store.save_balancing_policy(B, POLICY, expected_version=2)
    assert store.current_balancing_policy(B) is None
    assert len(db.recent_activity(A)) == 4
    assert len(db.recent_activity(B)) == 1


def _verify_restored(dsn: str, role: str, password: str, key: str, expected, guards) -> None:
    with psycopg.connect(dsn, autocommit=True) as admin:
        assert table_fingerprints(admin) == expected
        assert database_guards(admin) == guards
        encrypted = admin.execute("SELECT token_ciphertext FROM tbank_connection").fetchone()[0]
        assert decrypt_secret(bytes(encrypted), key) == "synthetic-broker-token"
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
        # Restored sequences and transactional writes must work too.
        revised = store.save_profile(A, expected_version=2, **PROFILE)
        assert revised.version == 3
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
                _exercise_settings(store, db)
                _exercise_strategy_drafts(store, db)
            with psycopg.connect(source_dsn, autocommit=True) as admin:
                admin.execute(
                    sql.SQL(
                        "ALTER TABLE audit_events ADD CONSTRAINT synthetic_audit_failure "
                        "CHECK (user_id <> {}) NOT VALID"
                    ).format(sql.Literal(B))
                )
            with database_store(make_conninfo(source_dsn, user=role, password=password)) as (
                db,
                store,
            ):
                with pytest.raises(psycopg.errors.CheckViolation):
                    store.save_profile(B, expected_version=1, **PROFILE)
                assert store.current_profile(B).version == 1
                assert len(db.recent_activity(B)) == 1
            with psycopg.connect(source_dsn, autocommit=True) as admin:
                admin.execute("ALTER TABLE audit_events DROP CONSTRAINT synthetic_audit_failure")
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


def test_strategy_draft_api_requires_owner_origin_version_and_keeps_authority_separate() -> None:
    from omnicio.strategy import preset_document

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
        store.save_profile.assert_not_called()
        store.save_balancing_policy.assert_not_called()
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
    from omnicio.strategy import preset_document

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


def test_strategy_diagnostic_is_versioned_read_only_and_owner_bound(monkeypatch) -> None:
    from omnicio import main
    from omnicio.strategy import preset_document

    client, user = _strategy_api(monkeypatch)
    document = preset_document("income")
    calls = []

    class Store:
        def current_strategy_draft(self, user_id):
            calls.append(user_id)
            return {"version": 4, "document": document}

    monkeypatch.setattr(main, "portfolio_store", lambda request: Store())
    body = {
        "expected_public_id": "000000123", "expected_version": 4,
        "nav_rub": "20000", "lot_cost_rub": "1000.01",
    }
    response = client.post(
        "/api/profile/strategy/feasibility", headers={"Origin": "https://omnicio.ru"},
        json=body,
    )
    assert response.status_code == 200
    assert response.json()["public_id"] == "000000123"
    assert response.json()["strategy_version"] == 4
    assert response.json()["lots_per_issuer"] == 0
    assert response.json()["stress"]["probability_of_profit"] is None
    assert response.headers["Cache-Control"] == "private, no-store"
    assert calls == [user.id]
    before = copy.deepcopy(document)
    response = client.post(
        "/api/profile/strategy/feasibility", headers={"Origin": "https://omnicio.ru"},
        json={**body, "expected_version": 3},
    )
    assert response.status_code == 409
    assert document == before
    for headers, payload, expected_status in (
        ({"Origin": "https://evil.example"}, body, 403),
        ({"Origin": "https://omnicio.ru"}, {**body, "expected_public_id": "000000999"}, 409),
        ({"Origin": "https://omnicio.ru"}, {**body, "user_id": str(B)}, 422),
        ({"Origin": "https://omnicio.ru"}, {**body, "nav_rub": "NaN"}, 422),
    ):
        count = len(calls)
        rejected = client.post("/api/profile/strategy/feasibility", headers=headers, json=payload)
        assert rejected.status_code == expected_status
        assert len(calls) == count
