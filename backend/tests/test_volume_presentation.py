"""Authenticated server persistence, conflicts and live invalidation."""
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor

import pytest
from backend import app as backend, volume_live, volume_presentation
from backend.tests.test_volume_live import setup, headers, current


def write(client, version=0, user=1, **changes):
    return client.put("/workspace/presentation", headers=headers(user),
                      json={"expected_version": version, "changes": changes})


def read(client, user=1):
    return client.get("/workspace/presentation", headers=headers(user))


def test_read_is_authenticated_and_has_no_write_side_effect(setup):
    assert setup.get("/workspace/presentation").status_code == 401
    before = current()
    reply = read(setup)
    assert reply.status_code == 200
    assert reply.headers["cache-control"] == "no-store, private"
    assert reply.json() == {"schema_version": 1, "version": 0, "settings": volume_presentation.DEFAULTS}
    assert current() == before
    with closing(backend.connect()) as db:
        assert db.execute("SELECT COUNT(*) FROM workspace_presentation_preferences").fetchone()[0] == 0


def test_update_survives_reinitialization_and_invalidates_only_owner(setup):
    before, other = current(), current(2)
    reply = write(setup, haptics=False, screenshots_blocked=True)
    assert reply.status_code == 200
    assert reply.json()["version"] == 1
    assert current()["revision"] != before["revision"]
    assert current()["broker_revision"] == before["broker_revision"]
    assert current(2) == other
    volume_live.initialize()
    assert read(setup).json() == reply.json()
    assert read(setup, 2).json()["settings"]["haptics"] is True


def test_conflict_and_retry_preserve_other_fields_and_newer_server_values(setup):
    assert write(setup, motion="OFF").status_code == 200
    assert write(setup, haptics=False).status_code == 409
    assert write(setup, version=1, haptics=False).status_code == 200
    result = read(setup).json()
    assert result["settings"]["motion"] == "OFF"
    assert result["settings"]["haptics"] is False
    assert result["version"] == 2


def test_noop_does_not_advance_version_or_live_stamp(setup):
    reply = write(setup, haptics=False)
    before = current()
    repeated = write(setup, version=reply.json()["version"], haptics=False)
    assert repeated.json() == reply.json()
    assert current() == before


@pytest.mark.parametrize("changes", [{"haptics": 1}, {"haptics": "false"}, {"motion": "unknown"},
                                    {"screenshots_blocked": None}, {"user_id": 2}, {}])
def test_invalid_changes_are_rejected_without_write(setup, changes):
    assert write(setup, **changes).status_code == 422
    assert read(setup).json()["version"] == 0


def test_parallel_writers_cannot_overwrite_each_other_at_one_version(setup):
    with ThreadPoolExecutor(max_workers=2) as pool:
        calls = [pool.submit(write, setup, motion="OFF"), pool.submit(write, setup, haptics=False)]
        assert sorted(call.result().status_code for call in calls) == [200, 409]
    assert read(setup).json()["version"] == 1
