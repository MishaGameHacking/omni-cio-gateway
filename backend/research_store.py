"""Versioned, operator-reviewed research imports; no client-writable truth endpoint."""
from __future__ import annotations
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json

try:
    from .credit_evidence import EvidenceError, Rating, Source, Statement, stamp
    from .risk_math import aligned_returns
except ImportError:
    from credit_evidence import EvidenceError, Rating, Source, Statement, stamp
    from risk_math import aligned_returns

KINDS = {'rating', 'statement', 'issuer_identity', 'total_returns'}


def initialize(db):
    db.execute('''CREATE TABLE IF NOT EXISTS research_evidence_v1 (
        digest TEXT PRIMARY KEY, kind TEXT NOT NULL, subject TEXT NOT NULL,
        payload TEXT NOT NULL, imported_at TEXT NOT NULL)''')
    db.execute('CREATE INDEX IF NOT EXISTS research_evidence_subject ON research_evidence_v1(kind,subject)')
    db.commit()


def import_record(connect, *, kind: str, subject: str, payload: dict, at: datetime | None = None) -> str:
    """Import already reviewed facts from a licensed/official source; does not verify truth.

    Called by an operator-side data connector, never by Android or a model. The
    review_id must identify that connector's audit record. Network source fetchers
    and agency subscriptions are separate; an empty store is not a good rating.
    """
    now = at or datetime.now(timezone.utc)
    if kind not in KINDS or not subject or len(subject) > 160:
        raise EvidenceError('invalid_record_key')
    source = Source(**payload.get('source', {}))
    if not source.valid(now):
        raise EvidenceError('unreviewed_or_stale_record')
    if kind == 'rating':
        rating = Rating(**{**payload, 'source': source})
        if rating.subject_id != subject or rating.subject_kind not in {'issuer', 'issue'}:
            raise EvidenceError('rating_subject_mismatch')
        if rating.status not in {'active', 'withdrawn', 'suspended'}:
            raise EvidenceError('invalid_rating_status')
        if rating.status == 'active' and rating.level() is None:
            raise EvidenceError('unsupported_rating_scale')
    if kind == 'statement':
        statement = Statement(**{**payload, 'source': source})
        if statement.issuer_id != subject:
            raise EvidenceError('statement_subject_mismatch')
    if kind == 'issuer_identity' and (not payload.get('issuer_id') or payload.get('instrument_uid') != subject):
        raise EvidenceError('identity_subject_mismatch')
    if kind == 'total_returns':
        if payload.get('basis') != 'total_return' or not payload.get('currency') or payload.get('instrument_uid') != subject:
            raise EvidenceError('return_basis_required')
        values = payload.get('values')
        if not isinstance(values, dict) or not 120 <= len(values) <= 10000:
            raise EvidenceError('invalid_return_history')
        _, days, _ = aligned_returns({subject: values})
        if days[-1] > stamp(source.published_at).date().isoformat():
            raise EvidenceError('history_after_publication')
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',', ':'))
    if len(serialized.encode()) > 600_000:
        raise EvidenceError('research_record_too_large')
    digest = hashlib.sha256((kind + ':' + subject + ':' + serialized).encode()).hexdigest()
    with closing(connect()) as db:
        initialize(db)
        db.execute('INSERT OR IGNORE INTO research_evidence_v1 VALUES (?,?,?,?,?)',
                   (digest, kind, subject, serialized, now.isoformat()))
        db.commit()
    return digest


def records(connect, kind: str, subject: str) -> list[dict]:
    with closing(connect()) as db:
        initialize(db)
        rows = db.execute('SELECT payload FROM research_evidence_v1 WHERE kind=? AND subject=? ORDER BY imported_at DESC LIMIT 100',
                          (kind, subject)).fetchall()
    return [json.loads(row[0]) for row in rows]


def latest_verified(connect, kind: str, subject: str, at: datetime) -> dict | None:
    candidates = [raw for raw in records(connect, kind, subject)
                  if stamp(raw['source']['published_at']) <= at and stamp(raw['source']['checked_at']) <= at]
    latest = max(candidates, key=lambda item: (stamp(item['source']['published_at']), stamp(item['source']['checked_at'])), default=None)
    return latest if latest and Source(**latest['source']).valid(at) else None
