"""Transaction exit must preserve atomicity and release the SQLite connection."""
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from backend.ai_budget import transaction

INSERT_PARENT = "INSERT INTO parent VALUES (1)"


class TransactionExitTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "ledger.sqlite3"
        with closing(self.connect()) as db:
            db.executescript("""
                CREATE TABLE parent (id INTEGER PRIMARY KEY);
                CREATE TABLE child (id INTEGER REFERENCES parent(id)
                    DEFERRABLE INITIALLY DEFERRED);
            """)

    def connect(self):
        db = sqlite3.connect(self.path)
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def count(self):
        with closing(self.connect()) as db:
            return db.execute("SELECT COUNT(*) FROM parent").fetchone()[0]

    def assert_closed(self, db):
        with self.assertRaises(sqlite3.ProgrammingError):
            db.execute("SELECT 1")

    def test_return_commits_and_closes(self):
        def early_return():
            with transaction(self.connect) as db:
                db.execute(INSERT_PARENT)
                return db

        db = early_return()
        self.assertEqual(self.count(), 1)
        self.assert_closed(db)

    def test_base_exception_rolls_back_and_closes(self):
        def interrupted():
            with transaction(self.connect) as db:
                self.interrupted_db = db
                db.execute(INSERT_PARENT)
                raise KeyboardInterrupt

        with self.assertRaises(KeyboardInterrupt):
            interrupted()
        self.assertEqual(self.count(), 0)
        self.assert_closed(self.interrupted_db)

    def test_failed_commit_rolls_back_and_closes(self):
        def invalid_transaction():
            with transaction(self.connect) as db:
                self.failed_db = db
                db.execute(INSERT_PARENT)
                db.execute("INSERT INTO child VALUES (2)")

        with self.assertRaises(sqlite3.IntegrityError):
            invalid_transaction()
        self.assertEqual(self.count(), 0)
        self.assert_closed(self.failed_db)
