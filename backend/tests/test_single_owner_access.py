"""Persisted owner-only policy: independent connections, concurrency and rollback."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from backend.owner_access import DENIED, OwnerConfigurationError, OwnerIdentity, bind_owner


class OwnerAccessTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "owner.db"
        self.identity = OwnerIdentity("confirmed-subject")
        with closing(self.connect()) as db:
            db.executescript("""
                CREATE TABLE users (id INTEGER PRIMARY KEY,telegram_sub TEXT UNIQUE NOT NULL,name TEXT);
                CREATE TABLE sessions (token TEXT PRIMARY KEY,user_id INTEGER);
                CREATE TABLE jobs (id INTEGER PRIMARY KEY,user_id INTEGER,payload TEXT);
                CREATE TABLE prices (id INTEGER PRIMARY KEY,value TEXT);
            """)

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def owner(self):
        with closing(self.connect()) as db:
            db.execute("INSERT INTO users VALUES (1,?,'Owner')", (self.identity.subject,))
            db.commit()

    def bind(self):
        bind_owner(self.connect, self.identity)

    def test_missing_configuration_does_not_choose_first_visitor(self):
        with self.assertRaises(OwnerConfigurationError):
            OwnerIdentity.from_environment({})

    def test_identity_validation(self):
        for subject in ("", " owner", "owner\n", "а", None, True, "a" * 257):
            with self.subTest(subject=subject), self.assertRaises(OwnerConfigurationError):
                OwnerIdentity(subject)

    def test_unknown_user_rejected_even_when_database_empty(self):
        self.bind()
        with closing(self.connect()) as db:
            with self.assertRaisesRegex(sqlite3.IntegrityError, DENIED):
                db.execute("INSERT INTO users VALUES (1,'visitor','Owner')")
            self.assertEqual(db.execute("SELECT count(*) FROM users").fetchone()[0], 0)

    def test_owner_allowed_with_multiple_sessions(self):
        self.bind()
        self.owner()
        with closing(self.connect()) as db:
            db.executemany("INSERT INTO sessions VALUES (?,1)", [("phone",), ("tablet",)])
            self.assertEqual(db.execute("SELECT count(*) FROM sessions").fetchone()[0], 2)

    def test_idempotent_binding(self):
        self.bind()
        self.owner()
        self.bind()
        self.bind()
        with closing(self.connect()) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM installation_owner").fetchone()[0], 1)

    def test_same_subject_cannot_replace_user_id(self):
        self.bind()
        self.owner()
        with closing(self.connect()) as db:
            with self.assertRaisesRegex(sqlite3.IntegrityError, DENIED):
                db.execute("INSERT OR REPLACE INTO users VALUES (2,?,'Owner')", (self.identity.subject,))
            self.assertEqual(db.execute("SELECT id FROM users").fetchone()[0], 1)

    def test_subject_and_primary_key_changes_rejected(self):
        self.bind()
        self.owner()
        with closing(self.connect()) as db:
            for query in ("UPDATE users SET telegram_sub='other'", "UPDATE users SET id=2"):
                with self.subTest(query=query), self.assertRaisesRegex(sqlite3.IntegrityError, DENIED):
                    db.execute(query)
            db.execute("UPDATE users SET name='Updated owner profile'")
            self.assertEqual(db.execute("SELECT name FROM users").fetchone()[0], "Updated owner profile")

    def test_all_owned_tables_reject_unknown_or_null_user(self):
        self.bind()
        self.owner()
        with closing(self.connect()) as db:
            for user in (None, 0, 2):
                with self.subTest(user=user), self.assertRaisesRegex(sqlite3.IntegrityError, DENIED):
                    db.execute("INSERT INTO jobs VALUES (1,?,'payload')", (user,))
            db.execute("INSERT INTO jobs VALUES (1,1,'payload')")
            with self.assertRaisesRegex(sqlite3.IntegrityError, DENIED):
                db.execute("UPDATE jobs SET user_id=2")

    def test_shared_market_data_remains_available(self):
        self.bind()
        with closing(self.connect()) as db:
            db.execute("INSERT INTO prices VALUES (1,'100.00')")
            self.assertEqual(db.execute("SELECT value FROM prices").fetchone()[0], "100.00")

    def test_does_not_delete_or_assign_existing_other_accounts(self):
        with closing(self.connect()) as db:
            db.execute("INSERT INTO users VALUES (8,'other','Other')")
            db.commit()
        with self.assertRaises(OwnerConfigurationError):
            self.bind()
        with closing(self.connect()) as db:
            self.assertEqual(db.execute("SELECT id,telegram_sub FROM users").fetchall(), [(8, "other")])
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='installation_owner'").fetchone())

    def test_existing_owner_can_be_preserved_without_rekeying(self):
        self.owner()
        self.bind()
        with closing(self.connect()) as db:
            self.assertEqual(db.execute("SELECT id FROM users").fetchone()[0], 1)

    def test_orphaned_legacy_records_abort_transaction(self):
        with closing(self.connect()) as db:
            db.execute("INSERT INTO sessions VALUES ('orphan',2)")
            db.commit()
        with self.assertRaises(OwnerConfigurationError):
            self.bind()
        with closing(self.connect()) as db:
            self.assertEqual(db.execute("SELECT user_id FROM sessions").fetchone()[0], 2)

    def test_owner_binding_cannot_be_changed_by_new_configuration(self):
        self.bind()
        other = OwnerIdentity("new-owner")
        with self.assertRaises(OwnerConfigurationError):
            bind_owner(self.connect, other)

    def test_binding_table_cannot_be_deleted_replaced_or_updated(self):
        self.bind()
        queries = ["DELETE FROM installation_owner", "UPDATE installation_owner SET telegram_sub='x'",
                   "INSERT OR REPLACE INTO installation_owner VALUES (1,'x','single-owner-0.11.0-v1')"]
        with closing(self.connect()) as db:
            for query in queries:
                with self.subTest(query=query), self.assertRaisesRegex(sqlite3.IntegrityError, DENIED):
                    db.execute(query)

    def test_new_user_table_protected_after_migration(self):
        self.bind()
        with closing(self.connect()) as db:
            db.execute('CREATE TABLE "new records" (user_id INTEGER,value TEXT)')
            db.commit()
        self.bind()
        with closing(self.connect()) as db:
            with self.assertRaisesRegex(sqlite3.IntegrityError, DENIED):
                db.execute('INSERT INTO "new records" VALUES (9,\'value\')')

    def test_simultaneous_logins_never_create_a_second_person(self):
        self.bind()
        def insert(subject):
            with closing(self.connect()) as db:
                try:
                    db.execute("INSERT INTO users(telegram_sub) VALUES (?)", (subject,))
                    db.commit()
                    return True
                except sqlite3.IntegrityError:
                    return False
        subjects = ["other-" + str(i) for i in range(20)] + [self.identity.subject] * 10
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(insert, subjects))
        self.assertEqual(sum(results), 1)
        with closing(self.connect()) as db:
            self.assertEqual(db.execute("SELECT telegram_sub FROM users").fetchall(), [(self.identity.subject,)])

    def test_owner_deletion_is_not_an_implicit_account_reset(self):
        self.bind()
        self.owner()
        with closing(self.connect()) as db:
            with self.assertRaisesRegex(sqlite3.IntegrityError, DENIED):
                db.execute("DELETE FROM users")


if __name__ == "__main__":
    unittest.main()
