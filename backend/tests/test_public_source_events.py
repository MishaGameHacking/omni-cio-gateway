"""Public evidence runs through the durable event job without changing price truth."""
from contextlib import closing
from datetime import datetime, timedelta, timezone

from backend import app as backend, public_sources
from backend import background_dispatch as dispatch, volume_jobs as jobs
from backend import volume_state as state, volume_workspace as workspace
from backend.tests.test_background_dispatch import stored, event_sources, forbidden
from backend.tests.test_public_sources import ISIN, document, encoded
from backend.tests.test_volume_workspace import fixture


def prepared(fixture):
    snapshot = stored(fixture)
    snapshot["positions"][0]["metadata"]["isin"] = ISIN
    workspace.persist(fixture["user"], snapshot)
    event_sources(fixture)
    fixture["patch"].setattr(workspace.details, "load_dashboard", forbidden)
    return state.saved_snapshot(fixture["user"])


def public_document(url, headers):
    value = document()
    now = datetime.now(timezone.utc)
    value["meta"]["goldenCopy"]["publishDate"] = (now - timedelta(minutes=1)).isoformat()
    return 200, {"etag": '"event-fixture"'}, encoded(value)


def test_event_job_persists_public_document_without_promoting_rating_or_revaluing(fixture):
    old = prepared(fixture)
    fixture["patch"].setattr(public_sources, "fetch_document", public_document)
    job = dispatch.enqueue_events(fixture["user"])
    jobs.run_job(job["job_id"])
    assert jobs.get_job(int(fixture["user"]["id"]), job["job_id"])["state"] == "completed"
    current = state.saved_snapshot(fixture["user"])
    assert current["public_sources"]["mapped_identifiers"] == 1
    assert current["public_sources"]["rating_sources_fetched"] is False
    assert current["event_monitor"]["new_rating_sources_fetched"] is False
    for name in ("positions", "capital", "accounts", "as_of", "collection", "attribution"):
        assert current[name] == old[name]
    with closing(backend.connect()) as db:
        assert db.execute("SELECT COUNT(*) FROM public_source_documents_v1").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM research_evidence_v1").fetchone()[0] == 0


def test_public_outage_does_not_fail_successful_broker_event_collection(fixture):
    prepared(fixture)
    fixture["patch"].setattr(public_sources, "fetch_document", lambda *args: (503, {}, b""))
    job = dispatch.enqueue_events(fixture["user"])
    jobs.run_job(job["job_id"])
    assert jobs.get_job(int(fixture["user"]["id"]), job["job_id"])["state"] == "completed"
    current = state.saved_snapshot(fixture["user"])
    assert current["public_sources"]["state"] == "partial"
    assert current["public_sources"]["items"][0]["reason"] == "source_http_503"
    assert current["events"]["items"][0]["id"] == "new-synthetic-news"
    assert current["event_monitor"]["complete"] is True


def test_public_source_status_read_never_refreshes_provider(fixture):
    prepared(fixture)
    fixture["patch"].setattr(public_sources, "fetch_document", public_document)
    job = dispatch.enqueue_events(fixture["user"])
    jobs.run_job(job["job_id"])
    fixture["patch"].setattr(public_sources, "fetch_document", forbidden)
    first = fixture["client"].get("/workspace/public-sources")
    second = fixture["client"].get("/workspace/public-sources")
    assert first.status_code == second.status_code == 200
    assert first.json()["items"] == second.json()["items"]
    assert first.json()["rating_sources_fetched"] is False


def test_public_source_status_requires_owner_session(fixture):
    backend.app.dependency_overrides.pop(backend.current_user, None)
    response = fixture["client"].get("/workspace/public-sources")
    assert response.status_code == 401
