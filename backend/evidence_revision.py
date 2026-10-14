"""Cache invalidation for reviewed evidence; not an attestation of source truth.

The generation distinguishes newly created stores. Revision changes in the same
SQLite transaction as evidence INSERT/UPDATE/DELETE. No payload or user secret
is included in the cache stamp. Restoring a backup still requires restarting
application processes to discard their pre-restore caches.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import sqlite3
import uuid

MAX_REVISION = 9_223_372_036_854_775_806


class RevisionUnavailable(ValueError):
    """Evidence cache coherence cannot be established."""


@dataclass(frozen=True)
class EvidenceRevision:
    generation: str
    sequence: int


def initialize_revision(db: sqlite3.Connection) -> None:
    """Called after research_evidence_v1 exists; the caller owns the transaction."""
    installed = db.execute("""SELECT COUNT(*) FROM sqlite_master WHERE
        (type = 'table' AND name = 'research_revision_v1') OR
        (type = 'trigger' AND name IN ('research_revision_insert_v1',
          'research_revision_update_v1', 'research_revision_delete_v1'))""").fetchone()[0]
    if installed == 4:
        return
    db.execute('''CREATE TABLE IF NOT EXISTS research_revision_v1 (
        singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
        generation TEXT NOT NULL,
        sequence INTEGER NOT NULL CHECK(typeof(sequence) = 'integer' AND sequence >= 0))''')
    db.execute('''INSERT OR IGNORE INTO research_revision_v1 VALUES (1, ?, 0)''',
               (uuid.uuid4().hex,))
    # All identifiers below are constants, not interpolated client input.
    for operation in ('INSERT', 'UPDATE', 'DELETE'):
        name = 'research_revision_' + operation.lower() + '_v1'
        db.execute(f'''CREATE TRIGGER IF NOT EXISTS {name}
            AFTER {operation} ON research_evidence_v1 BEGIN
                SELECT CASE WHEN (SELECT COUNT(*) FROM research_revision_v1) != 1
                    THEN RAISE(ABORT, 'research_revision_missing') END;
                SELECT CASE WHEN (SELECT sequence FROM research_revision_v1 WHERE singleton = 1) >= {MAX_REVISION}
                    THEN RAISE(ABORT, 'research_revision_exhausted') END;
                UPDATE research_revision_v1 SET sequence = sequence + 1 WHERE singleton = 1;
            END''')


def read_revision(db: sqlite3.Connection) -> EvidenceRevision:
    try:
        rows = db.execute('SELECT generation, sequence FROM research_revision_v1 WHERE singleton = 1').fetchall()
    except sqlite3.Error as error:
        raise RevisionUnavailable('research_revision_unavailable') from error
    if len(rows) != 1:
        raise RevisionUnavailable('research_revision_unavailable')
    generation, sequence = rows[0]
    if not isinstance(generation, str) or re.fullmatch(r'[a-f0-9]{32}', generation) is None:
        raise RevisionUnavailable('invalid_research_generation')
    if type(sequence) is not int or not 0 <= sequence <= MAX_REVISION:
        raise RevisionUnavailable('invalid_research_revision')
    return EvidenceRevision(generation, sequence)
