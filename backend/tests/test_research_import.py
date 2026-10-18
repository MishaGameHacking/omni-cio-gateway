"""Actual operator entry point with isolated files/SQLite, no external calls."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

import pytest

from backend import research_import as cli, research_store as store
from backend.credit_evidence import EvidenceError


@pytest.fixture(autouse=True)
def reviewed_directory(tmp_path, monkeypatch):
    directory = tmp_path / 'operator-install' / 'reviewed_imports'
    directory.mkdir(mode=0o700, parents=True)
    monkeypatch.setattr(cli, 'REVIEWED_IMPORTS', directory)
    return directory


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


def bundle(value=None):
    path = cli.REVIEWED_IMPORTS / "reviewed-fixture.json"
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
    path = bundle()
    candidate = tmp_path / "must-not-be-created.sqlite"
    result = cli.run(path.name, database=candidate)
    assert result["mode"] == "validate"
    assert result["record_count"] == 4
    assert result["source_truth_attested_by_cli"] is False
    assert not candidate.exists()
    completed = isolated_cli('--file', path.name)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["file_sha256"] == result["file_sha256"]


def test_operator_import_is_atomic_idempotent_and_preserves_users_and_first_availability(tmp_path):
    path, db_path = bundle(), database(tmp_path)
    verified = cli.run(path.name)
    result = cli.run(path.name, database=db_path, apply=True, expected_sha256=verified["file_sha256"])
    assert result["inserted_count"] == 4
    connect = lambda: sqlite3.connect(db_path)
    revision = store.revision(connect)
    with closing(connect()) as db:
        times = dict(db.execute("SELECT digest,imported_at FROM research_evidence_v1"))
    duplicate = cli.run(path.name, database=db_path, apply=True)
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
    path = bundle(rows)
    expected = "0" * 64 if invalid == "wrong_digest" else None
    with pytest.raises(EvidenceError):
        cli.run(path.name, database=db_path, apply=True, expected_sha256=expected)
    with closing(sqlite3.connect(db_path)) as db:
        assert db.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='research_evidence_v1'").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


@pytest.mark.parametrize("invalid_json", ['{"schema_version":1,"schema_version":1,"records":[]}',
                                         '{"schema_version":1,"records":[NaN]}',
                                         '{"schema_version":true,"records":[]}'])
def test_operator_parser_rejects_ambiguous_json(tmp_path, invalid_json):
    path = cli.REVIEWED_IMPORTS / "invalid.json"
    path.write_text(invalid_json, encoding="utf-8")
    with pytest.raises(EvidenceError):
        cli.run(path.name)


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
        cli.run(bundle().name, database=db_path, apply=True)
    with closing(connect()) as db:
        assert db.execute("SELECT COUNT(*) FROM research_evidence_v1").fetchone()[0] == 0
    assert store.revision(connect) == revision


def test_apply_requires_explicit_existing_backend_database(tmp_path):
    path = bundle()
    with pytest.raises(EvidenceError):
        cli.run(path.name, apply=True)
    missing = tmp_path / "missing.sqlite"
    with pytest.raises(EvidenceError):
        cli.run(path.name, database=missing, apply=True)
    assert not missing.exists()


def isolated_cli(*arguments):
    # Copy only the actual entry point into a temporary operator installation;
    # the fixed directory is still derived from __file__, never a CLI override.
    original = Path(cli.__file__).resolve()
    entry = cli.REVIEWED_IMPORTS.parent / original.name
    shutil.copyfile(original, entry)
    settings = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR', 'PATH') if key in os.environ}
    settings['PYTHONPATH'] = str(original.parent)
    return subprocess.run([sys.executable, str(entry), *arguments], cwd=entry.parent,
                          env=settings, capture_output=True, text=True, check=False, timeout=30)


@pytest.mark.parametrize('filename', [
    '../outside.json', '..\\outside.json', '/outside.json', 'C:\\outside.json', 'C:outside.json',
    '\\\\server\\share\\outside.json', 'folder/inside.json', 'folder\\inside.json',
    'inside.json:secret', 'CON.json', 'nul.json', 'COM1.json', 'LPT9.json', '.', '..',
    'reviewed.json ', 'reviewed.json\n', '%2e%2e%2foutside.json', 'a' * 121 + '.json',
])
def test_file_argument_cannot_escape_fixed_reviewed_directory_or_open_a_device(tmp_path, monkeypatch, filename):
    db_path = database(tmp_path)
    opened = []
    monkeypatch.setattr(cli.os, 'open', lambda *args, **kwargs: opened.append(args))
    with pytest.raises(EvidenceError, match='research_import_filename_invalid'):
        cli.run(filename, database=db_path, apply=True)
    assert opened == []
    with closing(sqlite3.connect(db_path)) as db:
        assert db.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='research_evidence_v1'").fetchone()[0] == 0


def test_cli_rejects_an_existing_absolute_path_without_disclosing_contents_or_opening_database(tmp_path):
    outside = tmp_path / 'outside.json'
    outside.write_text('synthetic-private-marker', encoding='utf-8')
    candidate = tmp_path / 'must-not-be-created.sqlite'
    completed = isolated_cli('--file', str(outside), '--apply', '--database', str(candidate))
    assert completed.returncode == 2
    assert json.loads(completed.stderr) == {'ok': False, 'error': 'research_import_filename_invalid'}
    assert completed.stdout == ''
    assert str(outside) not in completed.stderr
    assert 'synthetic-private-marker' not in completed.stderr
    assert not candidate.exists()


@pytest.mark.parametrize('kind', ['file', 'directory', 'self_loop'])
def test_symlinks_never_grant_import_access_to_an_external_document(tmp_path, kind):
    outside = tmp_path / 'outside'
    outside.mkdir()
    source_path = outside / 'reviewed-fixture.json'
    source_path.write_text(json.dumps({'schema_version': 1, 'records': records()}), encoding='utf-8')
    link = cli.REVIEWED_IMPORTS if kind == 'directory' else cli.REVIEWED_IMPORTS / source_path.name
    target = link if kind == 'self_loop' else outside if kind == 'directory' else source_path
    if kind == 'directory':
        link.rmdir()
    try:
        link.symlink_to(target, target_is_directory=kind == 'directory')
    except (OSError, NotImplementedError) as error:
        pytest.skip(f'Local symlink creation unavailable: {type(error).__name__}')
    with pytest.raises(EvidenceError, match='research_import_(regular_file_required|directory_invalid)'):
        cli.run(source_path.name)


def test_non_regular_and_hardlinked_documents_are_rejected_before_read(tmp_path):
    name = 'reviewed-fixture.json'
    directory = cli.REVIEWED_IMPORTS / name
    directory.mkdir()
    with pytest.raises(EvidenceError, match='research_import_regular_file_required'):
        cli.run(name)
    directory.rmdir()
    outside = tmp_path / 'outside.json'
    outside.write_text('synthetic-outside-document', encoding='utf-8')
    try:
        directory.hardlink_to(outside)
    except (OSError, NotImplementedError) as error:
        pytest.skip(f'Local hardlink creation unavailable: {type(error).__name__}')
    with pytest.raises(EvidenceError, match='research_import_regular_file_required'):
        cli.run(name)


@pytest.mark.skipif(os.name != 'posix', reason='POSIX mode bits; Windows uses the operator directory ACL')
def test_operator_directory_must_be_private():
    path = bundle()
    cli.REVIEWED_IMPORTS.chmod(0o755)
    with pytest.raises(EvidenceError, match='research_import_directory_not_private'):
        cli.run(path.name)


def test_document_replaced_between_validation_and_open_is_never_read(tmp_path, monkeypatch):
    path = bundle()
    replacement = tmp_path / 'outside.json'
    replacement.write_text('synthetic-private-marker', encoding='utf-8')
    original_open = cli.os.open
    read_started = []

    def replaced_open(filename, flags):
        path.unlink()
        shutil.copyfile(replacement, path)
        return original_open(filename, flags)

    original_fdopen = cli.os.fdopen

    class ObservedFile:
        def __init__(self, file):
            self.file = file

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.file.close()

        def fileno(self):
            return self.file.fileno()

        def read(self, size):
            read_started.append(True)
            return self.file.read(size)

    monkeypatch.setattr(cli.os, 'open', replaced_open)
    monkeypatch.setattr(cli.os, 'fdopen', lambda *args: ObservedFile(original_fdopen(*args)))
    with pytest.raises(EvidenceError, match='research_import_file_replaced'):
        cli.run(path.name)
    assert read_started == []


def test_bounded_reader_accepts_exact_limit_and_rejects_next_byte_before_database(tmp_path):
    path = bundle()
    raw = path.read_bytes()
    path.write_bytes(raw + b' ' * (cli.MAX_BYTES - len(raw)))
    assert cli.run(path.name)['record_count'] == 4
    with path.open('ab') as output:
        output.write(b' ')
    candidate = tmp_path / 'must-not-be-created.sqlite'
    with pytest.raises(EvidenceError, match='research_import_byte_limit'):
        cli.run(path.name, database=candidate, apply=True)
    assert not candidate.exists()
