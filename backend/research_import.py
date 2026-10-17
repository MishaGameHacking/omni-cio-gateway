"""Operator CLI for validated, already reviewed evidence on the existing DB.

It never fetches a source, fabricates a review, calls an AI, or changes secrets.
Validation is the default read-only operation; writing needs an explicit mode
and an existing database path. See RESEARCH_IMPORT.md for the bundle contract.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

try:
    from . import research_store
    from .credit_evidence import EvidenceError
except ImportError:
    import research_store
    from credit_evidence import EvidenceError


MAX_BYTES = 8 * 1024 * 1024
MAX_RECORDS = 1000


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceError('duplicate_import_json_key')
        result[key] = value
    return result


def _nonfinite(_):
    raise EvidenceError('nonfinite_import_json')


def read_bundle(path: Path) -> tuple[list[dict], str]:
    with path.open('rb') as file:
        raw = file.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise EvidenceError('research_import_byte_limit')
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=_object, parse_constant=_nonfinite)
    if not isinstance(value, dict) or set(value) != {'schema_version', 'records'} or type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise EvidenceError('research_import_schema_invalid')
    records = value['records']
    if not isinstance(records, list) or not 1 <= len(records) <= MAX_RECORDS:
        raise EvidenceError('research_import_record_limit')
    if any(not isinstance(row, dict) or set(row) != {'kind', 'subject', 'payload'} for row in records):
        raise EvidenceError('research_import_record_shape_invalid')
    return records, hashlib.sha256(raw).hexdigest()


def _database(path: Path):
    # mode=rw must not accidentally create a second empty production database.
    if not path.is_file():
        raise EvidenceError('existing_database_required')
    db = sqlite3.connect(path.resolve().as_uri() + '?mode=rw', uri=True, timeout=30)
    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'").fetchone() is None:
        db.close()
        raise EvidenceError('analyst_database_required')
    return db


def run(path: Path, *, database: Path | None = None, apply: bool = False, expected_sha256: str | None = None) -> dict:
    records, file_digest = read_bundle(path)
    if expected_sha256 is not None and file_digest != expected_sha256:
        raise EvidenceError('research_import_file_changed')
    now = datetime.now(timezone.utc)
    prepared = [research_store.prepare_record(**record, at=now) for record in records]
    summary = {'ok': True, 'mode': 'apply' if apply else 'validate', 'file_sha256': file_digest,
               'record_count': len(records), 'kinds': sorted({row['kind'] for row in records}),
               'digests': [row[0] for row in prepared], 'source_truth_attested_by_cli': False}
    if not apply:
        return summary
    if database is None:
        raise EvidenceError('explicit_database_required')
    summary.update(research_store.import_batch(lambda: _database(database), records, at=now))
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Validate or atomically import already reviewed Analyst AI evidence.')
    parser.add_argument('--file', type=Path, required=True, help='UTF-8 schema_version=1 reviewed evidence bundle')
    parser.add_argument('--apply', action='store_true', help='Write validated records; otherwise validation only')
    parser.add_argument('--database', type=Path, help='Existing Analyst AI SQLite database; required with --apply')
    parser.add_argument('--expected-sha256', help='Optional exact hash from the prior validation receipt')
    arguments = parser.parse_args(argv)
    try:
        result = run(arguments.file, database=arguments.database, apply=arguments.apply,
                     expected_sha256=arguments.expected_sha256)
    except EvidenceError as error:
        print(json.dumps({'ok': False, 'error': str(error)}), file=sys.stderr)
        return 2
    except (OSError, sqlite3.Error, UnicodeError, ValueError, TypeError, RecursionError):
        # Do not echo document contents, paths, SQL or installation settings.
        print(json.dumps({'ok': False, 'error': 'research_import_failed'}), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
