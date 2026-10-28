"""Synthetic source contracts; tests never access a real provider or account."""
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import hashlib
import json
import sqlite3

import pytest

from backend import public_sources as sources

NOW = datetime(2026, 10, 27, 9, 0, tzinfo=timezone.utc)
ISIN = "US0378331005"
LEI = "HWUPKR0MPOU8FGXBT394"


def document(*, total=1):
    row = {"type": "lei-records", "id": LEI, "attributes": {"lei": LEI,
        "entity": {"legalName": {"name": "Synthetic issuer"}, "jurisdiction": "US-CA",
            "registeredAs": "SYNTHETIC-123", "registeredAt": {"id": "RA000598"}, "status": "ACTIVE"},
        "registration": {"lastUpdateDate": "2026-01-01T00:00:00Z", "status": "ISSUED",
            "nextRenewalDate": "2027-01-01T00:00:00Z"}}}
    return {"meta": {"goldenCopy": {"publishDate": "2026-10-27T02:00:00Z"},
        "pagination": {"total": total, "currentPage": 1}}, "data": [deepcopy(row) for _ in range(min(total, 2))]}


def encoded(value):
    return json.dumps(value, sort_keys=True).encode()


@pytest.fixture
def connect(tmp_path):
    path = tmp_path / "source.sqlite3"
    return lambda: sqlite3.connect(path, timeout=5)


def good_fetch(url, headers):
    assert url.startswith(sources.BASE_URL + "?")
    assert set(headers) <= {"If-None-Match", "If-Modified-Since"}
    return 200, {"etag": '"synthetic-version-1"'}, encoded(document())


def test_exact_identity_keeps_document_and_dataset_times_separate():
    raw = encoded(document())
    result = sources.parse_gleif(raw, ISIN, NOW)
    assert result["state"] == "available"
    assert result["identity"]["lei"] == LEI
    assert result["entity_updated_at"] == "2026-01-01T00:00:00+00:00"
    assert result["dataset_published_at"] == "2026-10-27T02:00:00+00:00"
    assert result["checked_at"] == NOW.isoformat()
    assert result["document_sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["rating_verified"] is result["trade_permission"] is False


@pytest.mark.parametrize("value", ["RU0009029541", "RU0009029540&token=private", "http://localhost", None, 123])
def test_invalid_identifier_never_reaches_network(connect, value):
    calls = []
    with pytest.raises(sources.SourceError):
        sources.refresh_isin(connect, value, at=NOW, fetch=lambda *args: calls.append(args))
    assert calls == []


def test_known_missing_mapping_is_distinct_from_unavailable_and_ambiguous():
    missing = sources.parse_gleif(encoded(document(total=0)), ISIN, NOW)
    ambiguous = sources.parse_gleif(encoded(document(total=2)), ISIN, NOW)
    assert missing["state"] == "missing"
    assert missing["identity"] is None
    assert ambiguous["state"] == "ambiguous"
    assert ambiguous["identity"] is None


@pytest.mark.parametrize("published", ["2026-10-28T02:00:00Z", "2026-10-23T02:00:00Z"])
def test_download_today_cannot_refresh_old_or_future_dataset(published):
    value = document()
    value["meta"]["goldenCopy"]["publishDate"] = published
    result = sources.parse_gleif(encoded(value), ISIN, NOW)
    assert result["state"] == "stale"
    assert result["identity"] is None


@pytest.mark.parametrize("change", ["bad_lei", "mismatch", "future_update", "bad_name", "pagination", "duplicate_keys"])
def test_invalid_schema_and_identity_are_not_accepted(change):
    value = document()
    attributes = value["data"][0]["attributes"]
    if change == "bad_lei":
        attributes["lei"] = "A" * 20
    elif change == "mismatch":
        value["data"][0]["id"] = "wrong"
    elif change == "future_update":
        attributes["registration"]["lastUpdateDate"] = "2026-10-28T02:00:00Z"
    elif change == "bad_name":
        attributes["entity"]["legalName"]["name"] = "unsafe\ntext"
    elif change == "pagination":
        value["meta"]["pagination"]["total"] = 10
    raw = b'{"data":[],"data":[]}' if change == "duplicate_keys" else encoded(value)
    with pytest.raises(sources.SourceError):
        sources.parse_gleif(raw, ISIN, NOW)


@pytest.mark.parametrize("key,value", [("status", "LAPSED"), ("nextRenewalDate", "2026-10-26T00:00:00Z")])
def test_lapsed_registration_does_not_become_fresh_issuer(key, value):
    payload = document()
    payload["data"][0]["attributes"]["registration"][key] = value
    result = sources.parse_gleif(encoded(payload), ISIN, NOW)
    assert result["state"] == "inactive"
    assert result["identity"] is None


def test_cache_and_immutable_history_do_not_import_reviewed_facts(connect):
    first = sources.refresh_isin(connect, ISIN, at=NOW, fetch=good_fetch)
    second = sources.refresh_isin(connect, ISIN, at=NOW + timedelta(minutes=1),
        fetch=lambda *args: pytest.fail("fresh cache must not perform network"))
    assert second == first
    with closing(connect()) as db:
        assert db.execute("SELECT COUNT(*) FROM public_source_documents_v1").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM public_source_observations_v1").fetchone()[0] == 1
        assert not db.execute("SELECT name FROM sqlite_master WHERE name='research_evidence_v1'").fetchone()
        assert db.execute("SELECT first_received_at FROM public_source_documents_v1").fetchone()[0] == NOW.isoformat()


def test_304_keeps_original_bytes_and_publication_but_records_new_observation(connect):
    first = sources.refresh_isin(connect, ISIN, at=NOW, fetch=good_fetch)
    def unchanged(url, headers):
        assert headers == {"If-None-Match": '"synthetic-version-1"'}
        return 304, {"etag": '"synthetic-version-1"'}, b""
    second = sources.refresh_isin(connect, ISIN, at=NOW + timedelta(hours=6), fetch=unchanged)
    assert second["state"] == "available"
    assert second["document_sha256"] == first["document_sha256"]
    assert second["dataset_published_at"] == first["dataset_published_at"]
    with closing(connect()) as db:
        assert db.execute("SELECT COUNT(*) FROM public_source_documents_v1").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM public_source_observations_v1").fetchone()[0] == 2
        assert db.execute("SELECT first_received_at FROM public_source_documents_v1").fetchone()[0] == NOW.isoformat()


def test_304_does_not_resurrect_expired_dataset(connect):
    sources.refresh_isin(connect, ISIN, at=NOW, fetch=good_fetch)
    later = sources.refresh_isin(connect, ISIN, at=NOW + timedelta(days=3), fetch=lambda *args: (304, {}, b""))
    assert later["state"] == "stale"
    assert later["identity"] is None


def test_429_retry_after_persists_and_failed_source_has_no_old_identity(connect):
    sources.refresh_isin(connect, ISIN, at=NOW, fetch=good_fetch)
    failure = sources.refresh_isin(connect, ISIN, at=NOW + timedelta(hours=6),
        fetch=lambda *args: (429, {"retry-after": "7200"}, b"sensitive external error"))
    assert failure["state"] == "unavailable"
    assert failure["identity"] is None
    assert failure["reason"] == "source_http_429"
    assert failure["next_check_at"] == (NOW + timedelta(hours=8)).isoformat()
    again = sources.refresh_isin(connect, ISIN, at=NOW + timedelta(hours=7),
        fetch=lambda *args: pytest.fail("Retry-After not respected"))
    assert again == failure


def test_304_without_cached_document_and_body_limit_are_explicit(connect):
    first = sources.refresh_isin(connect, ISIN, at=NOW, fetch=lambda *args: (304, {}, b""))
    assert first["reason"] == "source_304_without_document"
    second = sources.refresh_isin(connect, ISIN, at=NOW + timedelta(minutes=2),
        fetch=lambda *args: (200, {}, b"x" * (sources.MAX_BYTES + 1)))
    assert second["reason"] == "source_response_limit"


def test_source_lease_prevents_reentry_and_stale_writer(connect):
    calls = []
    def racing(url, headers):
        calls.append(url)
        # A reentrant job sees the lease and performs no second request.
        nested = sources.refresh_isin(connect, ISIN, at=NOW,
            fetch=lambda *args: pytest.fail("lease allowed duplicate source request"))
        assert nested["state"] == "pending"
        with closing(connect()) as db:
            db.execute("UPDATE public_source_cache_v1 SET lease_token='new-owner'")
            db.commit()
        return good_fetch(url, headers)
    with pytest.raises(sources.SourceError, match="source_lease_lost"):
        sources.refresh_isin(connect, ISIN, at=NOW, fetch=racing)
    assert len(calls) == 1
    with closing(connect()) as db:
        assert db.execute("SELECT COUNT(*) FROM public_source_documents_v1").fetchone()[0] == 0


def test_snapshot_lane_deduplicates_identifiers_without_mutating_financial_state(connect):
    snapshot = {"as_of": "2026-10-01T00:00:00Z", "capital": {"value": "123"}, "positions": [
        {"instrument_uid": "a", "instrument_type": "share", "metadata": {"isin": ISIN},
            "verified_identity": {"issuer_id": "existing-reviewed"}, "account_id": "private-account"},
        {"instrument_uid": "b", "instrument_type": "bond", "metadata": {"isin": ISIN}},
        {"instrument_uid": "c", "instrument_type": "bond", "metadata": {}},
        {"instrument_uid": "cash", "instrument_type": "cash", "metadata": {}}]}
    original, calls, checkpoints = deepcopy(snapshot), [], []
    def fetch(url, headers):
        calls.append(url)
        assert "private-account" not in url
        assert "existing-reviewed" not in url
        return good_fetch(url, headers)
    checkpoint = {}
    result = sources.collect_snapshot_sources(connect, snapshot, checkpoint,
        lambda stage, state: checkpoints.append(deepcopy(state)), at=NOW, fetch=fetch)
    assert snapshot == original
    assert len(calls) == 1
    assert result["eligible_identifiers"] == result["mapped_identifiers"] == 1
    assert result["missing_identifiers"] == 1
    assert result["state"] == "partial"
    assert result["items"][0]["instrument_uids"] == ["a", "b"]
    assert checkpoint["public_source_cursor"] == ISIN
    assert result["rating_sources_fetched"] is result["reviewed_issuer_identity_replaced"] is False


def test_snapshot_lane_network_failure_does_not_raise_or_block_other_sources(connect):
    snapshot = {"positions": [{"instrument_uid": "a", "instrument_type": "share", "metadata": {"isin": ISIN}}]}
    def failed(*args):
        raise OSError("sensitive path must not be logged")
    result = sources.collect_snapshot_sources(connect, snapshot, {}, lambda *args: None, at=NOW, fetch=failed)
    assert result["state"] == "partial"
    assert result["items"][0]["reason"] == "source_transport_unavailable"


def test_cached_identity_expiration_is_checked_without_network(connect):
    sources.refresh_isin(connect, ISIN, at=NOW, fetch=good_fetch)
    result = sources.cached_result(connect, ISIN, at=NOW + timedelta(hours=7))
    assert result["state"] == "stale"
    assert result["identity"] is None


def test_source_transport_rejects_redirects_and_uses_no_environment_auth(monkeypatch):
    seen = {}
    class Response:
        status_code = 302
        headers = {"location": "http://127.0.0.1/private"}
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
    class Client:
        def __init__(self, **kwargs):
            seen.update(kwargs)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def stream(self, method, url, headers):
            assert method == "GET"
            assert url == sources.request_url(ISIN)
            assert headers == {}
            return Response()
    monkeypatch.setattr(sources.httpx, "Client", Client)
    assert sources.fetch_document(sources.request_url(ISIN), {}) == (302, {}, b"")
    assert seen["follow_redirects"] is seen["trust_env"] is False
    assert "Authorization" not in seen["headers"]


@pytest.mark.parametrize("preserve_snapshot_sources", [True, False])
def test_successive_jobs_do_not_starve_tail_when_full_collection_replaces_snapshot(connect, preserve_snapshot_sources):
    identifiers = [ISIN, "US5949181045", "US0231351067", "US88160R1014"]
    snapshot = {"positions": [{"instrument_uid": value, "instrument_type": "share",
        "metadata": {"isin": value}} for value in identifiers]}
    calls = []
    def fetch(url, headers):
        calls.append(url)
        return good_fetch(url, headers)
    first = sources.collect_snapshot_sources(connect, snapshot, {}, lambda *args: None, at=NOW, fetch=fetch)
    assert first["identifiers_visited"] == 3
    assert len(calls) == 3
    assert sum(item["state"] == "pending" for item in first["items"]) == 1
    if preserve_snapshot_sources:
        snapshot["public_sources"] = first
    second_checkpoint = {}
    second = sources.collect_snapshot_sources(connect, snapshot, second_checkpoint,
        lambda *args: None, at=NOW + timedelta(minutes=10), fetch=fetch)
    assert second["mapped_identifiers"] == 4
    assert len(set(calls)) == 4
    assert len(calls) == 4
    assert second["identifiers_visited"] == 1


def test_due_source_priority_uses_oldest_persisted_deadline_and_skips_fresh(connect):
    identifiers = [ISIN, "US5949181045", "US0231351067", "US88160R1014"]
    for index, value in enumerate(identifiers):
        sources.refresh_isin(connect, value, at=NOW + timedelta(minutes=index), fetch=good_fetch)
    snapshot = {"positions": [{"instrument_uid": value, "instrument_type": "share",
        "metadata": {"isin": value}} for value in identifiers]}
    calls = []
    def fetch(url, headers):
        calls.append(url)
        return good_fetch(url, headers)
    # All entries expired, but identifier order differs from freshness order.
    first = sources.collect_snapshot_sources(connect, snapshot, {}, lambda *args: None,
        at=NOW + timedelta(hours=7), fetch=fetch)
    assert calls == [sources.request_url(value) for value in identifiers[:3]]
    assert first["identifiers_visited"] == 3
    second = sources.collect_snapshot_sources(connect, snapshot, {}, lambda *args: None,
        at=NOW + timedelta(hours=7, minutes=10), fetch=fetch)
    assert calls[-1] == sources.request_url(identifiers[3])
    assert len(calls) == 4
    assert second["identifiers_visited"] == 1


def test_corrupt_cached_json_is_explicit_without_breaking_event_lane(connect):
    sources.refresh_isin(connect, ISIN, at=NOW, fetch=good_fetch)
    with closing(connect()) as db:
        db.execute("UPDATE public_source_cache_v1 SET result='['")
        db.commit()
    snapshot = {"positions": [{"instrument_uid": "a", "instrument_type": "share", "metadata": {"isin": ISIN}}]}
    result = sources.collect_snapshot_sources(connect, snapshot, {}, lambda *args: None, at=NOW, fetch=good_fetch)
    assert result["state"] == "partial"
    assert result["items"][0]["reason"] == "source_store_unavailable"


@pytest.mark.parametrize("stamp", ["0001-01-01T00:00:00+01:00", "9999-12-31T23:59:59-01:00"])
def test_provider_timestamp_overflow_is_quarantined_without_aborting_lane(connect, stamp):
    payload = document()
    payload["meta"]["goldenCopy"]["publishDate"] = stamp
    result = sources.refresh_isin(connect, ISIN, at=NOW, fetch=lambda *args: (200, {}, encoded(payload)))
    assert result["state"] == "unavailable"
    assert result["identity"] is None
    assert result["reason"] == "source_timestamp_invalid"


def test_http_date_retry_after_and_renewal_deadline_are_respected(connect):
    retry_at = NOW + timedelta(hours=2)
    failure = sources.refresh_isin(connect, ISIN, at=NOW,
        fetch=lambda *args: (429, {"retry-after": format_datetime(retry_at, usegmt=True)}, b""))
    assert failure["next_check_at"] == retry_at.isoformat()
    payload = document()
    payload["data"][0]["attributes"]["registration"]["nextRenewalDate"] = (retry_at + timedelta(minutes=30)).isoformat()
    success = sources.refresh_isin(connect, ISIN, at=retry_at, fetch=lambda *args: (200, {}, encoded(payload)))
    assert success["state"] == "available"
    assert success["next_check_at"] == success["fresh_until"] == (retry_at + timedelta(minutes=30)).isoformat()


def test_snapshot_view_expires_identity_and_limits_results_to_current_holdings(connect):
    result = sources.refresh_isin(connect, ISIN, at=NOW, fetch=good_fetch)
    snapshot = {"positions": [{"instrument_uid": "current", "instrument_type": "share",
        "metadata": {"isin": ISIN}}], "public_sources": {"checked_at": NOW.isoformat(),
            "items": [{**result, "instrument_uids": ["sold-position"]}]}}
    original = deepcopy(snapshot)
    view = sources.snapshot_status(snapshot, at=NOW + timedelta(hours=7))
    assert view["state"] == "partial"
    assert view["mapped_identifiers"] == 0
    assert view["items"][0]["state"] == "stale"
    assert view["items"][0]["identity"] is None
    assert view["items"][0]["instrument_uids"] == ["current"]
    assert snapshot == original


@pytest.mark.parametrize("as_http_date", [False, True])
def test_long_retry_after_never_polls_before_provider_deadline(connect, as_http_date):
    retry_at = NOW + timedelta(days=2)
    header = format_datetime(retry_at, usegmt=True) if as_http_date else "172800"
    result = sources.refresh_isin(connect, ISIN, at=NOW,
        fetch=lambda *args: (429, {"retry-after": header}, b""))
    assert result["next_check_at"] == retry_at.isoformat()
    sources.refresh_isin(connect, ISIN, at=NOW + timedelta(days=1),
        fetch=lambda *args: pytest.fail("long provider retry deadline ignored"))
