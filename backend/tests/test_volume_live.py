"""Real SQLite transactions and authenticated long polls; no external services."""
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
import time
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend import app as backend, autonomous_ai, volume_live as live


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(backend, "DATABASE_PATH", tmp_path / "live.sqlite3")
    monkeypatch.setenv("ANALYSIS_SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("ANDROID_UPDATES_ENABLED", "false")
    backend.init_db()
    autonomous_ai.init_autonomous_db()
    with closing(backend.connect()) as db:
        for user in (1, 2):
            db.execute("INSERT INTO users(id,telegram_sub,created_at,updated_at) VALUES (?,?,1,1)", (user, "live-fixture-" + str(user)))
            db.execute("INSERT INTO sessions VALUES (?,?,?)", (backend.hash_token("synthetic-" + str(user)), user, int(time.time()) + 120))
        db.commit()
    live.initialize()
    with TestClient(backend.app) as client:
        yield client


def headers(user=1):
    return {"Authorization": "Bearer synthetic-" + str(user)}


def current(user=1):
    return live.snapshot(user, backend.hash_token("synthetic-" + str(user)))


def record(user=1, value="first", commit=True):
    with closing(backend.connect()) as db:
        db.execute("""INSERT INTO workspace_records VALUES (?,'note','item',?,1,1,1)
            ON CONFLICT(user_id,kind,id) DO UPDATE SET payload_json=excluded.payload_json""", (user, value))
        if commit:
            db.commit()


def test_scope_rollback_and_unchanged_updates(setup):
    before, other = current(), current(2)
    record(commit=False)
    assert current() == before
    record(2)
    assert current() == before
    assert current(2)["revision"] != other["revision"]
    record()
    changed = current()
    assert changed["revision"] != before["revision"]
    record()
    assert current() == changed
    assert changed["broker_revision"] == before["broker_revision"]


def test_reassigning_and_deleting_rows_invalidate_both_owners(setup):
    record()
    before, other = current(), current(2)
    with closing(backend.connect()) as db:
        db.execute("UPDATE workspace_records SET user_id=2 WHERE user_id=1")
        db.commit()
    assert current()["revision"] != before["revision"]
    assert current(2)["revision"] != other["revision"]
    other = current(2)
    with closing(backend.connect()) as db:
        db.execute("DELETE FROM workspace_records WHERE user_id=2")
        db.commit()
    assert current(2)["revision"] != other["revision"]


def test_public_evidence_invalidates_both_scopes(setup):
    before, other = current(), current(2)
    with closing(backend.connect()) as db:
        db.execute("INSERT INTO market_facts VALUES ('fixture','fixture',NULL,'synthetic','{}','2026-01-01',NULL,1)")
        db.commit()
    assert current()["revision"] != before["revision"]
    assert current(2)["revision"] != other["revision"]


def test_poll_is_authenticated_bounded_and_never_returns_credentials(setup):
    assert setup.get("/workspace/live?wait=0").status_code == 401
    assert setup.get("/workspace/live?wait=0", headers=headers(3)).status_code == 401
    response = setup.get("/workspace/live?wait=0&user_id=2", headers=headers())
    assert response.status_code == 200
    assert response.json()["revision"] == current()["revision"]
    assert response.json()["revision"] != current(2)["revision"]
    assert response.headers["cache-control"] == "no-store"
    assert len(response.content) < 1000
    assert set(response.json()) == {"revision", "changed", "broker_revision", "broker_connected", "server_time"}
    for query in ("wait=21", "wait=-1", "after=not-a-revision"):
        assert setup.get("/workspace/live?" + query, headers=headers()).status_code == 422


def test_heartbeat_does_not_change_the_stamp_or_create_jobs(setup):
    before = current()
    with closing(backend.connect()) as db:
        counts = [db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
                  for table in ("workspace_jobs", "ai_work_jobs", "ai_money_reservations")]
    response = setup.get("/workspace/live?wait=0&after=" + before["revision"], headers=headers())
    assert response.json()["changed"] is False
    assert current() == before
    with closing(backend.connect()) as db:
        assert counts == [db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
                          for table in ("workspace_jobs", "ai_work_jobs", "ai_money_reservations")]


def test_commit_wakes_a_waiting_client(setup, monkeypatch):
    monkeypatch.setattr(live, "POLL_INTERVAL", .02)
    revision = current()["revision"]
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(setup.get, "/workspace/live?wait=2&after=" + revision, headers=headers())
        time.sleep(.08)
        record(value="arrived while waiting")
        response = pending.result(timeout=2)
    assert response.status_code == 200 and response.json()["changed"] is True


def test_session_revocation_interrupts_wait(setup, monkeypatch):
    monkeypatch.setattr(live, "POLL_INTERVAL", .02)
    revision = current()["revision"]
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(setup.get, "/workspace/live?wait=2&after=" + revision, headers=headers())
        time.sleep(.08)
        with closing(backend.connect()) as db:
            db.execute("DELETE FROM sessions WHERE user_id=1")
            db.commit()
        assert pending.result(timeout=2).status_code == 401


def test_broker_change_has_its_own_stamp_without_revealing_the_token(setup):
    before = current()
    with closing(backend.connect()) as db:
        db.execute("UPDATE users SET tinvest_token_encrypted=? WHERE id=1", ("synthetic-private-token",))
        db.commit()
    response = setup.get("/workspace/live?wait=0", headers=headers())
    assert response.json()["broker_connected"] is True
    assert response.json()["broker_revision"] != before["broker_revision"]
    assert "synthetic-private-token" not in response.text


def test_initialize_is_idempotent_and_deployment_changes_invalidate(setup, monkeypatch):
    before = current()
    live.initialize()
    assert current() == before
    monkeypatch.setattr(live, "DEPLOYMENT", "next-verified-server-release")
    assert current()["revision"] != before["revision"]


def test_waiter_limits_release_after_failures(setup):
    with live.watcher(1), live.watcher(1), live.watcher(1):
        with pytest.raises(HTTPException) as error:
            with live.watcher(1):
                pass
        assert error.value.status_code == 429
        with live.watcher(2):
            pass
    assert not live._waiters
    with pytest.raises(RuntimeError):
        with live.watcher(1):
            raise RuntimeError("cancelled")
    assert not live._waiters


def test_server_version_is_authenticated_uncached_and_does_not_create_jobs(setup):
    assert setup.get("/workspace/version").status_code == 401
    with closing(backend.connect()) as db:
        before = [db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
                  for table in ("workspace_jobs", "ai_work_jobs", "ai_money_reservations")]
    response = setup.get("/workspace/version", headers=headers())
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, private"
    assert response.json() == live.server_version.current()
    assert set(response.json()) == {"schema_version", "version", "source_revision"}
    with closing(backend.connect()) as db:
        assert before == [db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
                          for table in ("workspace_jobs", "ai_work_jobs", "ai_money_reservations")]


def test_source_release_changes_live_revision_for_the_same_client(setup, monkeypatch):
    before = current()
    monkeypatch.setattr(live.server_version, "SOURCE_REVISION", "a" * 64)
    monkeypatch.setattr(live, "DEPLOYMENT", live.deployment_signature())
    after = current()
    assert after["revision"] != before["revision"]
    assert after["broker_revision"] == before["broker_revision"]
    assert setup.get("/workspace/version", headers=headers()).json()["version"] == "srv-" + "a" * 12
