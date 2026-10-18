"""Operator CLI for validated, already reviewed evidence on the existing DB.

It never fetches a source, fabricates a review, calls an AI, or changes secrets.
Validation is the default read-only operation; writing needs an explicit mode
and an existing database path. See RESEARCH_IMPORT.md for the bundle contract.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys

try:
    from . import research_store
    from .credit_evidence import EvidenceError
except ImportError:
    import research_store
    from credit_evidence import EvidenceError


MAX_BYTES = 8 * 1024 * 1024
MAX_RECORDS = 1000
# Deliberately not configurable through argv or the environment. An operator
# stages reviewed documents here; a generated CLI argument cannot choose a root.
REVIEWED_IMPORTS = Path(__file__).resolve().parent / 'reviewed_imports'
RESERVED_NAMES = {'CON', 'PRN', 'AUX', 'NUL'} | {f'{prefix}{number}' for prefix in ('COM', 'LPT') for number in range(1, 10)}


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceError('duplicate_import_json_key')
        result[key] = value
    return result


def _nonfinite(_):
    raise EvidenceError('nonfinite_import_json')


def _linked(entry: os.stat_result) -> bool:
    return stat.S_ISLNK(entry.st_mode) or bool(getattr(entry, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _reviewed_file(filename: str) -> tuple[Path, os.stat_result, os.stat_result]:
    # The same portable allowlist applies on Unix and Windows: no separators,
    # drive letters, device names, alternate streams, dot segments or escapes.
    if not isinstance(filename, str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,119}\.json', filename) is None:
        raise EvidenceError('research_import_filename_invalid')
    if filename[:-5].upper() in RESERVED_NAMES:
        raise EvidenceError('research_import_filename_invalid')
    root = REVIEWED_IMPORTS.lstat()
    if _linked(root) or not stat.S_ISDIR(root.st_mode):
        raise EvidenceError('research_import_directory_invalid')
    if os.name == 'posix' and (root.st_uid != os.geteuid() or root.st_mode & 0o077):
        raise EvidenceError('research_import_directory_not_private')
    path = REVIEWED_IMPORTS / filename
    entry = path.lstat()
    if _linked(entry) or not stat.S_ISREG(entry.st_mode) or entry.st_nlink != 1:
        raise EvidenceError('research_import_regular_file_required')
    if path.resolve(strict=True).parent != REVIEWED_IMPORTS.resolve(strict=True):
        raise EvidenceError('research_import_outside_directory')
    return path, root, entry


def _same_document(before: os.stat_result, opened: os.stat_result) -> bool:
    # Some filesystems reuse an unlinked inode immediately. Identity alone is
    # insufficient: also verify the captured type, links, length and timestamps.
    fields = ('st_mode', 'st_nlink', 'st_size', 'st_mtime_ns')
    # CPython #157671: Windows lstat ctime can mean creation while fstat ctime
    # means metadata change. Compare their explicit creation times instead;
    # retain change-time checking on POSIX and the legacy Windows fallback.
    if os.name == 'nt' and hasattr(before, 'st_birthtime_ns') and hasattr(opened, 'st_birthtime_ns'):
        fields += ('st_birthtime_ns',)
    else:
        fields += ('st_ctime_ns',)
    return os.path.samestat(before, opened) and all(getattr(before, key) == getattr(opened, key) for key in fields)


def read_bundle(filename: str) -> tuple[list[dict], str]:
    path, root, entry = _reviewed_file(filename)
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    with os.fdopen(os.open(path, flags), 'rb') as file:
        # Check the opened object before reading, also on platforms without
        # O_NOFOLLOW. A replaced file/directory must not turn validation into a
        # read of another object. NONBLOCK prevents a swapped FIFO from hanging.
        if not _same_document(entry, os.fstat(file.fileno())) or not os.path.samestat(root, REVIEWED_IMPORTS.lstat()):
            raise EvidenceError('research_import_file_replaced')
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


def run(filename: str, *, database: Path | None = None, apply: bool = False, expected_sha256: str | None = None) -> dict:
    records, file_digest = read_bundle(filename)
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
    parser.add_argument('--file', required=True, help='JSON basename in the fixed backend/reviewed_imports operator directory')
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
    except (OSError, sqlite3.Error, ValueError, TypeError, RecursionError):
        # Do not echo document contents, paths, SQL or installation settings.
        print(json.dumps({'ok': False, 'error': 'research_import_failed'}), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
