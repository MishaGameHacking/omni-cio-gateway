"""Read a complete bounded evidence history, not the last N imported facts.

Publication order is determined by the evidence selector. This layer preserves
all competing facts and additionally enforces when they became available to our
system. Exceeding a resource bound is an explicit failure, never a partial list.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json

MAX_RECORD_BYTES = 600_000
MAX_HISTORY_BYTES = 16 * 1024 * 1024
MAX_HISTORY_ROWS = 10_000


class HistoryUnavailable(ValueError):
    pass


def _instant(value: str) -> datetime:
    try:
        instant = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError('missing_timezone')
        return instant.astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError, OverflowError) as error:
        raise HistoryUnavailable('invalid_import_time') from error


def _object(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise HistoryUnavailable('duplicate_evidence_key')
        result[name] = value
    return result


def _nonfinite(_):
    raise HistoryUnavailable('nonfinite_evidence_json')


def _decode(kind, subject, digest, text):
    expected = hashlib.sha256((kind + ':' + subject + ':' + text).encode('utf-8')).hexdigest()
    if digest != expected:
        raise HistoryUnavailable('evidence_digest_mismatch')
    try:
        value = json.loads(text, object_pairs_hook=_object, parse_constant=_nonfinite)
    except (ValueError, TypeError, RecursionError) as error:
        raise HistoryUnavailable('invalid_evidence_json') from error
    if not isinstance(value, dict) or not isinstance(value.get('source'), dict):
        raise HistoryUnavailable('invalid_evidence_shape')
    return value


def read_history(db, kind: str, subject: str, *, at: datetime | None = None) -> list[dict]:
    if at is not None and (not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None):
        raise HistoryUnavailable('assessment_timezone_required')
    rows = db.execute('''SELECT digest,payload,imported_at FROM research_evidence_v1
        WHERE kind=? AND subject=? ORDER BY digest LIMIT ?''', (kind, subject, MAX_HISTORY_ROWS + 1))
    result, consumed = [], 0
    for index, (digest, text, imported) in enumerate(rows):
        if index == MAX_HISTORY_ROWS:
            raise HistoryUnavailable('evidence_history_row_limit')
        try:
            size = len(text.encode('utf-8'))
        except (AttributeError, UnicodeError) as error:
            raise HistoryUnavailable('invalid_evidence_encoding') from error
        consumed += size
        if size > MAX_RECORD_BYTES or consumed > MAX_HISTORY_BYTES:
            raise HistoryUnavailable('evidence_history_byte_limit')
        available = _instant(imported)
        if at is None or available <= at:
            result.append(_decode(kind, subject, digest, text))
    return result
