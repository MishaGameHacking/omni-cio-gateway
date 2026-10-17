"""Actual operator entry point with isolated files/SQLite, no external calls."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from backend import research_import as cli, research_store as store
from backend.credit_evidence import EvidenceError


def source(identifier, host="issuer.example.invalid"):
    now = datetime.now(timezone.utc)
    return {"id": identifier, "url": "https://" + host + "/reviewed-document",
            "published_at": (now - timedelta(days=2)).isoformat(), "checked_at": (now - timedelta(hours=1)).isoformat(),
            "expires_at": (now + timedelta(days=2)).isoformat(), "review_id": "synthetic-operator-review"}


def records():
    primary = source("primary-proof")
    return [
        {"kind": "issuer_identity", "subject": "fixture-instrument", "payload": {
            "instrument_uid": "fixture-instrument", "issuer_id": "fixture-issuer", "issuer_name": "Synthetic issuer",
            "group_id": "fixture-group", "group_name": "Synthetic group", "source": source("identity-proof")}},
        {"kind": "rating", "subject": "fixture-issuer", "payload": {
            "agency": "ACRA", "scale": "RU_NATIONAL_LONG_TERM", "grade": "AAA(RU)", "subject_kind": "issuer",
            "subject_id": "fixture-issuer", "status": "active", "outlook": "stable", "source": source("rating-proof", "acra-ratings.ru")}},
        {"kind": "statement", "subject": "fixture-issuer", "payload": {
            "issuer_id": "fixture-issuer", "sector": "industry", "standard": "IFRS", "currency": "RUB",
            "period_start": "2025-01-01T00:00:00Z", "period_end": "2025-12-31T00:00:00Z",
            "values": {"net_debt": "100", "ebitda": "20"}, "audited": True, "source": source("statement-proof")}},
        {"kind": "news_event", "subject": "77", "payload": {
            "broker_news_id": "77", "event_id": "fixture-event", "news_sha256": "a" * 64,
            "publication_role": "primary", "source": {**primary, "id": "publication-proof"}, "primary_source": primary}},
    ]


def bundle(tmp_path, value=None):
    path = tmp_path / "reviewed-fixture.json"
    path.write_text(json.dumps({"schema_version": 1, "records": records() if value is None else value}), encoding="utf-8")
    return path


def database(tmp_path):
    path = tmp_path / "existing-backend.sqlite"
    with closing(sqlite3.connect(path)) as db:
        db.execute("CREATE TABLE users(id INTEGER PRIMARY KEY,marker TEXT NOT NULL)")
        db.execute("INSERT INTO users VALUES (1,'preserve-existing-user')")
        db.commit()
    return path


def test_operator_validation_does_not_open_database_or_require_authentication_settings(tmp_path):
    path = bundle(tmp_path)
    candidate = tmp_path / "must-not-be-created.sqlite"
    result = cli.run(path, database=candidate)
    assert result["mode"] == "validate"
    assert result["record_count"] == 4
    assert result["source_truth_attested_by_cli"] is False
    assert not candidate.exists()
    command = [sys.executable, "-m", "backend.research_import", "--file", str(path)]
    settings = {key: value for key, value in os.environ.items()
                if key not in {'TELEGRAM_CLIENT_ID', 'TELEGRAM_CLIENT_SECRET', 'FERNET_KEY', 'BACKEND_PUBLIC_URL'}}
    completed = subprocess.run(command, cwd=Path(__file__).resolve().parents[2], env=settings,
                               capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["file_sha256"] == result["file_sha256"]


def test_operator_import_is_atomic_idempotent_and_preserves_users_and_first_availability(tmp_path):
    path, db_path = bundle(tmp_path), database(tmp_path)
    verified = cli.run(path)
    result = cli.run(path, database=db_path, apply=True, expected_sha256=verified["file_sha256"])
    assert result["inserted_count"] == 4
    connect = lambda: sqlite3.connect(db_path)
    revision = store.revision(connect)
    with closing(connect()) as db:
        times = dict(db.execute("SELECT digest,imported_at FROM research_evidence_v1"))
    duplicate = cli.run(path, database=db_path, apply=True)
    assert duplicate["inserted_count"] == 0
    assert duplicate["unchanged_count"] == 4
    assert store.revision(connect) == revision
    with closing(connect()) as db:
        assert dict(db.execute("SELECT digest,imported_at FROM research_evidence_v1")) == times
        assert db.execute("SELECT marker FROM users WHERE id=1").fetchone()[0] == "preserve-existing-user"
    now = datetime.now(timezone.utc)
    assert store.latest_verified(connect, "issuer_identity", "fixture-instrument", now)["issuer_id"] == "fixture-issuer"
    assert store.latest_verified(connect, "news_event", "77", now)["publication_role"] == "primary"


@pytest.mark.parametrize("invalid", ["expired", "no_review", "wrong_issuer", "missing_primary", "wrong_digest",
                                     "statement_period", "statement_publication", "statement_value", "statement_basis"])
def test_import_rejects_invalid_bundle_before_any_fact_is_written(tmp_path, invalid):
    rows, db_path = records(), database(tmp_path)
    if invalid == "expired":
        rows[-1]["payload"]["source"]["expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    elif invalid == "no_review":
        rows[-1]["payload"]["source"]["review_id"] = ""
    elif invalid == "wrong_issuer":
        rows[1]["payload"]["subject_id"] = "different-issuer"
    elif invalid == "missing_primary":
        rows[-1]["payload"]["primary_source"] = None
    elif invalid == "statement_period":
        rows[2]["payload"]["period_start"] = rows[2]["payload"]["period_end"]
    elif invalid == "statement_publication":
        rows[2]["payload"]["period_end"] = datetime.now(timezone.utc).isoformat()
    elif invalid == "statement_value":
        rows[2]["payload"]["values"]["ebitda"] = "Infinity"
    elif invalid == "statement_basis":
        rows[2]["payload"]["currency"] = "million rubles"
    path = bundle(tmp_path, rows)
    expected = "0" * 64 if invalid == "wrong_digest" else None
    with pytest.raises(EvidenceError):
        cli.run(path, database=db_path, apply=True, expected_sha256=expected)
    with closing(sqlite3.connect(db_path)) as db:
        assert db.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='research_evidence_v1'").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


@pytest.mark.parametrize("invalid_json", ['{"schema_version":1,"schema_version":1,"records":[]}',
                                         '{"schema_version":1,"records":[NaN]}',
                                         '{"schema_version":true,"records":[]}'])
def test_operator_parser_rejects_ambiguous_json(tmp_path, invalid_json):
    path = tmp_path / "invalid.json"
    path.write_text(invalid_json, encoding="utf-8")
    with pytest.raises(EvidenceError):
        cli.run(path)


def test_transaction_failure_rolls_back_entire_evidence_batch(tmp_path):
    db_path = database(tmp_path)
    connect = lambda: sqlite3.connect(db_path)
    with closing(connect()) as db:
        store.initialize(db)
        db.execute("""CREATE TRIGGER fixture_reject_news BEFORE INSERT ON research_evidence_v1
            WHEN NEW.kind='news_event' BEGIN SELECT RAISE(ABORT,'synthetic-storage-failure'); END""")
        db.commit()
    revision = store.revision(connect)
    with pytest.raises(sqlite3.IntegrityError):
        cli.run(bundle(tmp_path), database=db_path, apply=True)
    with closing(connect()) as db:
        assert db.execute("SELECT COUNT(*) FROM research_evidence_v1").fetchone()[0] == 0
    assert store.revision(connect) == revision


def test_apply_requires_explicit_existing_backend_database(tmp_path):
    path = bundle(tmp_path)
    with pytest.raises(EvidenceError):
        cli.run(path, apply=True)
    missing = tmp_path / "missing.sqlite"
    with pytest.raises(EvidenceError):
        cli.run(path, database=missing, apply=True)
    assert not missing.exists()
