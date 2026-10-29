"""Original report bytes survive refreshes and respect the corpus retention boundary."""
from contextlib import closing
import pytest
from backend import osint_store as store, osint_read as read, osint_catalogue as catalogue
from backend.osint_retention import cleanup
from backend.tests.test_investment_osint import corpus, item, save, NOW


def report(raw=b"%PDF-1.7\nsynthetic original", url="https://www.moex.com/report.pdf"):
    return {**item(url=url), "kind": "report", "original_pdf": raw, "raw_sha": store.sha(raw)}


def test_original_is_deduplicated_and_missing_legacy_original_is_backfilled(corpus):
    value = report()
    legacy = {key: val for key, val in value.items() if key != "original_pdf"}
    assert save(corpus, legacy)
    assert not store.has_original(corpus, value["raw_sha"])
    assert save(corpus, value, NOW + 1) is False
    assert save(corpus, value, NOW + 2) is False
    with closing(corpus()) as db:
        rows = db.execute("SELECT * FROM osint_originals_v1").fetchall()
        assert len(rows) == 1
        assert rows[0]["body"] == value["original_pdf"]
        identifier = db.execute("SELECT id FROM osint_publications_v1").fetchone()[0]
    result = read.document(corpus, identifier, now=NOW + 2)
    assert result["original"]["available"] is True
    assert result["original"]["bytes"] == len(value["original_pdf"])
    assert "original_pdf" not in result
    assert read.status(corpus, NOW + 2)["storage"]["originals"] == 1


@pytest.mark.parametrize("change", [
    {"original_pdf": b"not a pdf"}, {"raw_sha": "wrong"}, {"primary": False}, {"kind": "news"},
])
def test_invalid_original_never_commits(corpus, change):
    value = {**report(), **change}
    with pytest.raises(catalogue.IntakeError, match="original_invalid"):
        save(corpus, value)
    with closing(corpus()) as db:
        assert db.execute("SELECT COUNT(*) FROM osint_originals_v1").fetchone()[0] == 0


def test_capacity_failure_is_explicit_without_replacing_previous_version(corpus, monkeypatch):
    value = report()
    save(corpus, value)
    monkeypatch.setattr(store, "MAX_ORIGINAL_BYTES", len(value["original_pdf"]))
    second = report(b"%PDF-1.7\nsecond revision")
    with pytest.raises(catalogue.IntakeError, match="original_capacity"):
        save(corpus, second, NOW + 1)
    with closing(corpus()) as db:
        assert db.execute("SELECT raw_sha FROM osint_publications_v1").fetchone()[0] == value["raw_sha"]


def test_old_original_is_retained_while_referenced_by_history(corpus):
    first, second = report(), report(b"%PDF-1.7\nsecond revision")
    save(corpus, first)
    save(corpus, second, NOW + 1)
    cleanup(corpus, NOW + 31 * 86400)
    assert store.has_original(corpus, first["raw_sha"])
    assert store.has_original(corpus, second["raw_sha"])
    cleanup(corpus, NOW + 367 * 86400)
    assert not store.has_original(corpus, first["raw_sha"])
    assert store.has_original(corpus, second["raw_sha"])


def test_initialization_only_queues_legacy_successful_reports(corpus):
    with closing(corpus()) as db:
        store.add_target(db, "moex_reports", {"kind": "pdf", "url": "https://www.moex.com/report.pdf", "title": "Report"}, NOW)
        db.execute("UPDATE osint_targets_v1 SET status='ready',next_at=?,body_sha='legacy' WHERE kind='pdf'", (NOW + 86400,))
        db.commit()
    store.initialize(corpus)
    with closing(corpus()) as db:
        assert db.execute("SELECT next_at FROM osint_targets_v1 WHERE kind='pdf'").fetchone()[0] == 0
