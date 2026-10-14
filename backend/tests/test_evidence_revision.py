"""Real SQLite transactions with synthetic records; no broker/model/network I/O."""
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from backend.evidence_revision import (EvidenceRevision, MAX_REVISION, RevisionUnavailable,
                                       initialize_revision, read_revision)


def create_store(db):
    db.execute('''CREATE TABLE IF NOT EXISTS research_evidence_v1 (
        digest TEXT PRIMARY KEY, kind TEXT, subject TEXT, payload TEXT, imported_at TEXT)''')
    initialize_revision(db)
    db.commit()


def insert(db, digest='synthetic-1', payload='{}'):
    db.execute('INSERT INTO research_evidence_v1 VALUES (?, ?, ?, ?, ?)',
               (digest, 'rating', 'synthetic-issuer', payload, '2026-10-14T00:00:00+00:00'))


class EvidenceRevisionTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        create_store(self.db)
        self.initial = read_revision(self.db)

    def test_initial_sequence_zero(self):
        self.assertEqual(self.initial.sequence, 0)
        self.assertEqual(len(self.initial.generation), 32)

    def test_initialization_is_idempotent_and_does_not_rewrite_records(self):
        insert(self.db)
        self.db.commit()
        old = read_revision(self.db)
        create_store(self.db)
        self.assertEqual(read_revision(self.db), old)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM research_evidence_v1').fetchone()[0], 1)

    def test_existing_schema_check_does_not_take_a_write_transaction(self):
        changes = self.db.total_changes
        initialize_revision(self.db)
        self.assertFalse(self.db.in_transaction)
        self.assertEqual(self.db.total_changes, changes)

    def test_insert_changes_revision(self):
        insert(self.db)
        self.assertEqual(read_revision(self.db), EvidenceRevision(self.initial.generation, 1))

    def test_correction_with_same_count_changes_revision(self):
        insert(self.db)
        old = read_revision(self.db)
        self.db.execute("UPDATE research_evidence_v1 SET payload = ?", ('{"status":"withdrawn"}',))
        self.assertEqual(read_revision(self.db).sequence, old.sequence + 1)

    def test_delete_changes_revision(self):
        insert(self.db)
        old = read_revision(self.db)
        self.db.execute('DELETE FROM research_evidence_v1')
        self.assertEqual(read_revision(self.db).sequence, old.sequence + 1)

    def test_delete_reinsert_same_count_cannot_reuse_old_stamp(self):
        insert(self.db)
        old = read_revision(self.db)
        self.db.execute('DELETE FROM research_evidence_v1')
        insert(self.db)
        self.assertNotEqual(read_revision(self.db), old)

    def test_duplicate_ignored_does_not_invalidate(self):
        insert(self.db)
        old = read_revision(self.db)
        self.db.execute('INSERT OR IGNORE INTO research_evidence_v1 SELECT * FROM research_evidence_v1')
        self.assertEqual(read_revision(self.db), old)

    def test_rolled_back_insert_keeps_old_stamp(self):
        insert(self.db)
        self.db.rollback()
        self.assertEqual(read_revision(self.db), self.initial)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM research_evidence_v1').fetchone()[0], 0)

    def test_rolled_back_correction_keeps_record_and_stamp(self):
        insert(self.db)
        self.db.commit()
        old = read_revision(self.db)
        self.db.execute("UPDATE research_evidence_v1 SET payload = 'changed'")
        self.db.rollback()
        self.assertEqual(read_revision(self.db), old)
        self.assertEqual(self.db.execute('SELECT payload FROM research_evidence_v1').fetchone()[0], '{}')

    def test_savepoint_rollback_restores_revision(self):
        self.db.execute('SAVEPOINT changes')
        insert(self.db)
        self.db.execute('ROLLBACK TO changes')
        self.db.execute('RELEASE changes')
        self.assertEqual(read_revision(self.db), self.initial)

    def test_recreated_store_uses_different_generation(self):
        with closing(sqlite3.connect(':memory:')) as other:
            create_store(other)
            self.assertNotEqual(read_revision(other).generation, self.initial.generation)

    def test_missing_revision_rejected(self):
        self.db.execute('DELETE FROM research_revision_v1')
        with self.assertRaises(RevisionUnavailable):
            read_revision(self.db)

    def test_bad_generation_rejected(self):
        self.db.execute("UPDATE research_revision_v1 SET generation = 'broken'")
        with self.assertRaises(RevisionUnavailable):
            read_revision(self.db)

    def test_schema_corruption_rejected(self):
        self.db.execute('DROP TABLE research_revision_v1')
        with self.assertRaises(RevisionUnavailable):
            read_revision(self.db)

    def test_overflow_stops_evidence_mutation(self):
        self.db.execute('UPDATE research_revision_v1 SET sequence = ?', (MAX_REVISION,))
        with self.assertRaises(sqlite3.IntegrityError):
            insert(self.db)
        self.assertEqual(read_revision(self.db).sequence, MAX_REVISION)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM research_evidence_v1').fetchone()[0], 0)

    def test_migration_preserves_existing_evidence(self):
        with closing(sqlite3.connect(':memory:')) as legacy:
            legacy.execute('CREATE TABLE research_evidence_v1 (payload TEXT)')
            legacy.execute("INSERT INTO research_evidence_v1 VALUES ('legacy')")
            initialize_revision(legacy)
            self.assertEqual(legacy.execute('SELECT payload FROM research_evidence_v1').fetchone()[0], 'legacy')
            old = read_revision(legacy)
            legacy.execute("UPDATE research_evidence_v1 SET payload = 'corrected'")
            self.assertNotEqual(read_revision(legacy), old)

    def test_other_connection_sees_only_committed_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic.sqlite'
            with closing(sqlite3.connect(path)) as writer, closing(sqlite3.connect(path)) as reader:
                create_store(writer)
                initial = read_revision(reader)
                insert(writer)
                self.assertEqual(read_revision(reader), initial)
                writer.commit()
                self.assertEqual(read_revision(reader).sequence, initial.sequence + 1)


if __name__ == '__main__':
    unittest.main()
