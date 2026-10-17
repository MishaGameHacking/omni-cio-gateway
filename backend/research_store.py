"""Versioned, operator-reviewed research imports; no client-writable truth endpoint."""
from __future__ import annotations
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import re
import sqlite3

try:
    from .credit_evidence import EvidenceError, Rating, Source, Statement, stamp
    from .risk_math import aligned_returns
    from .evidence_order import latest_unambiguous
    from .evidence_history import HistoryUnavailable, read_history
    from .evidence_revision import initialize_revision, read_revision, RevisionUnavailable
except ImportError:
    from credit_evidence import EvidenceError, Rating, Source, Statement, stamp
    from risk_math import aligned_returns
    from evidence_order import latest_unambiguous
    from evidence_history import HistoryUnavailable, read_history
    from evidence_revision import initialize_revision, read_revision, RevisionUnavailable

KINDS = {'rating', 'statement', 'issuer_identity', 'total_returns', 'news_event'}


def initialize(db):
    db.execute('''CREATE TABLE IF NOT EXISTS research_evidence_v1 (
        digest TEXT PRIMARY KEY, kind TEXT NOT NULL, subject TEXT NOT NULL,
        payload TEXT NOT NULL, imported_at TEXT NOT NULL)''')
    db.execute('CREATE INDEX IF NOT EXISTS research_evidence_subject ON research_evidence_v1(kind,subject)')
    initialize_revision(db)
    db.commit()


def revision(connect):
    try:
        with closing(connect()) as db:
            initialize(db)
            return read_revision(db)
    except (sqlite3.Error, RevisionUnavailable) as error:
        raise EvidenceError('research_revision_unavailable') from error


def _key(kind, subject):
    if not isinstance(kind, str) or kind not in KINDS:
        raise EvidenceError('invalid_record_key')
    if not isinstance(subject, str) or not subject.strip() or len(subject) > 160:
        raise EvidenceError('invalid_record_key')


def _rating(subject, payload, source):
    rating = Rating(**{**payload, 'source': source})
    if rating.subject_id != subject or rating.subject_kind not in {'issuer', 'issue'}:
        raise EvidenceError('rating_subject_mismatch')
    if rating.status not in {'active', 'withdrawn', 'suspended'}:
        raise EvidenceError('invalid_rating_status')
    if not isinstance(rating.outlook, str):
        raise EvidenceError('invalid_rating_outlook')
    if rating.status == 'active' and rating.level() is None:
        raise EvidenceError('unsupported_rating_scale')


def _statement(subject, payload, source):
    statement = Statement(**{**payload, 'source': source})
    if statement.issuer_id != subject:
        raise EvidenceError('statement_subject_mismatch')
    if type(statement.audited) is not bool or not isinstance(statement.values, dict):
        raise EvidenceError('invalid_statement_shape')


def _identity(subject, payload, _source):
    issuer = payload.get('issuer_id')
    if not isinstance(issuer, str) or not issuer.strip() or len(issuer) > 160 or payload.get('instrument_uid') != subject:
        raise EvidenceError('identity_subject_mismatch')
    for key in ('issuer_name', 'group_id', 'group_name'):
        value = payload.get(key)
        if value is not None and (not isinstance(value, str) or not value.strip() or len(value) > 240 or any(ord(char) < 32 for char in value)):
            raise EvidenceError('identity_optional_field_invalid')
    if payload.get('group_name') and not payload.get('group_id'):
        raise EvidenceError('verified_group_identity_required')


def _returns(subject, payload, source):
    if payload.get('basis') != 'total_return' or not payload.get('currency') or payload.get('instrument_uid') != subject:
        raise EvidenceError('return_basis_required')
    values = payload.get('values')
    if not isinstance(values, dict) or not 120 <= len(values) <= 10000:
        raise EvidenceError('invalid_return_history')
    _, days, _ = aligned_returns({subject: values})
    if days[-1] > stamp(source.published_at).date().isoformat():
        raise EvidenceError('history_after_publication')


def _news_event(subject, payload, source):
    if payload.get('broker_news_id') != subject or not re.fullmatch(r'\d{1,20}', subject):
        raise EvidenceError('news_subject_mismatch')
    if not re.fullmatch(r'[A-Za-z0-9_.:\-]{1,160}', str(payload.get('event_id', ''))):
        raise EvidenceError('news_event_identity_required')
    if not re.fullmatch(r'[0-9a-f]{64}', str(payload.get('news_sha256', ''))):
        raise EvidenceError('news_observation_fingerprint_required')
    role = payload.get('publication_role')
    if role not in {'primary', 'repost', 'independent_report'}:
        raise EvidenceError('news_publication_role_invalid')
    primary = payload.get('primary_source')
    if primary is None:
        if role in {'primary', 'repost'}:
            raise EvidenceError('news_primary_source_required')
        return
    if not isinstance(primary, dict):
        raise EvidenceError('news_primary_source_invalid')
    if not Source(**primary).valid(stamp(source.checked_at)):
        raise EvidenceError('news_primary_source_not_verified')
    if role == 'primary' and primary['url'] != source.url:
        raise EvidenceError('news_primary_source_does_not_match_publication')


VALIDATORS = {'rating': _rating, 'statement': _statement, 'issuer_identity': _identity, 'total_returns': _returns,
              'news_event': _news_event}


def import_record(connect, *, kind: str, subject: str, payload: dict, at: datetime | None = None) -> str:
    """Import reviewed facts from an operator-side connector, never from Android.

    Source timestamps are source claims. imported_at additionally records when
    this installation first received the fact, for point-in-time replay.
    """
    now = at if at is not None else datetime.now(timezone.utc)
    _key(kind, subject)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise EvidenceError('import_timezone_required')
    if not isinstance(payload, dict) or not isinstance(payload.get('source'), dict):
        raise EvidenceError('invalid_record_shape')
    try:
        source = Source(**payload['source'])
        if not source.valid(now):
            raise EvidenceError('unreviewed_or_stale_record')
        VALIDATORS[kind](subject, payload, source)
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',', ':'))
        encoded = serialized.encode('utf-8')
    except (TypeError, UnicodeError, RecursionError) as error:
        raise EvidenceError('invalid_record_shape') from error
    except ValueError as error:
        if isinstance(error, EvidenceError):
            raise
        raise EvidenceError('invalid_record_value') from error
    if len(encoded) > 600_000:
        raise EvidenceError('research_record_too_large')
    digest = hashlib.sha256((kind + ':' + subject + ':' + serialized).encode()).hexdigest()
    with closing(connect()) as db:
        initialize(db)
        db.execute('INSERT OR IGNORE INTO research_evidence_v1 VALUES (?,?,?,?,?)',
                   (digest, kind, subject, serialized, now.astimezone(timezone.utc).isoformat()))
        db.commit()
    return digest


def records(connect, kind: str, subject: str, *, at: datetime | None = None) -> list[dict]:
    _key(kind, subject)
    try:
        with closing(connect()) as db:
            initialize(db)
            return read_history(db, kind, subject, at=at)
    except HistoryUnavailable as error:
        raise EvidenceError('research_history_unavailable') from error


def latest_verified(connect, kind: str, subject: str, at: datetime) -> dict | None:
    # Do not hide simultaneous contradictions behind a SQL LIMIT or backfill
    # facts into an assessment made before this system received them.
    return latest_unambiguous(records(connect, kind, subject, at=at), at=at,
                              valid_source=lambda source: Source(**source).valid(at))
