"""Real SQLite rows with synthetic session hashes; no credentials or APKs."""
import sqlite3
import unittest
from unittest.mock import Mock

from backend.client_compatibility import has_current_session

PREVIEW = 'ru.omnicio.app.debug'
RELEASE = 'ru.omnicio.app'
PACKAGES = (PREVIEW, RELEASE)
CURRENT = (23, 'a' * 64)


class ClientCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.execute('CREATE TABLE sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER,expires_at INTEGER)')
        self.db.execute('''CREATE TABLE client_versions(session_hash TEXT PRIMARY KEY,user_id INTEGER,
            package_name TEXT,version_code INTEGER,release_sha256 TEXT,observed_at INTEGER)''')
        self.reader = Mock(return_value=CURRENT)
        self.clock = Mock(return_value=100.0)

    def add(self, name='session', *, user=1, session_user=None, package=PREVIEW,
            version=23, digest='a' * 64, expiry=200):
        self.db.execute('INSERT INTO sessions VALUES(?,?,?)', (name, user if session_user is None else session_user, expiry))
        self.db.execute('INSERT INTO client_versions VALUES(?,?,?,?,?,?)', (name, user, package, version, digest, 90))

    def check(self, user=1, packages=PACKAGES):
        return has_current_session(self.db, user, packages=packages, verified_release=self.reader, clock=self.clock)

    def test_no_observation_makes_no_artifact_read(self):
        self.assertFalse(self.check())
        self.reader.assert_not_called()

    def test_current_unexpired_session(self):
        self.add()
        self.assertTrue(self.check())
        self.reader.assert_called_once_with(PREVIEW)

    def test_many_old_sessions_hash_one_artifact_not_one_hundred(self):
        for index in range(120):
            self.add(str(index), version=22)
        self.assertFalse(self.check())
        self.reader.assert_called_once_with(PREVIEW)

    def test_valid_session_not_hidden_by_many_old_sessions(self):
        for index in range(120):
            self.add(str(index), version=22)
        self.add('current')
        self.assertTrue(self.check())
        self.reader.assert_called_once_with(PREVIEW)

    def test_at_most_one_read_for_each_supported_package(self):
        for index in range(60):
            self.add('p' + str(index), version=22)
            self.add('r' + str(index), package=RELEASE, version=22)
        self.assertFalse(self.check())
        self.assertEqual(self.reader.call_count, 2)
        self.assertEqual({call.args[0] for call in self.reader.call_args_list}, set(PACKAGES))

    def test_duplicate_package_configuration_does_not_repeat_artifact_read(self):
        self.add(version=22)
        self.assertFalse(self.check(packages=(PREVIEW, PREVIEW)))
        self.reader.assert_called_once_with(PREVIEW)

    def test_different_user_not_resumed(self):
        self.add(user=2)
        self.assertFalse(self.check())
        self.reader.assert_not_called()

    def test_cross_user_join_does_not_authorize(self):
        self.add(user=1, session_user=2)
        self.assertFalse(self.check())
        self.reader.assert_not_called()

    def test_deleted_session_does_not_authorize(self):
        self.add()
        self.db.execute('DELETE FROM sessions')
        self.assertFalse(self.check())
        self.reader.assert_not_called()

    def test_expired_session_does_not_trigger_artifact_read(self):
        self.add(expiry=100)
        self.assertFalse(self.check())
        self.reader.assert_not_called()

    def test_expiry_during_verification_does_not_authorize(self):
        self.add(expiry=101)
        self.clock.side_effect = [100.0, 100.0, 102.0]
        self.assertFalse(self.check())

    def test_revocation_during_verification_does_not_authorize(self):
        self.add()
        def revoke(_):
            self.db.execute('DELETE FROM sessions')
            return CURRENT
        self.reader.side_effect = revoke
        self.assertFalse(self.check())

    def test_foreign_package_ignored(self):
        self.add(package='another.app')
        self.assertFalse(self.check())
        self.reader.assert_not_called()

    def test_matching_version_with_wrong_digest_not_current(self):
        self.add(digest='b' * 64)
        self.assertFalse(self.check())

    def test_missing_release_does_not_allow_work(self):
        self.add()
        self.reader.return_value = None
        self.assertFalse(self.check())

    def test_other_supported_channel_can_allow_work(self):
        self.add('release', package=RELEASE, version=22)
        self.add('preview', package=PREVIEW)
        self.reader.side_effect = lambda package: CURRENT if package == PREVIEW else None
        self.assertTrue(self.check())
        self.assertEqual(self.reader.call_count, 2)

    def test_next_check_verifies_again_even_if_rows_unchanged(self):
        self.add()
        self.assertTrue(self.check())
        self.reader.return_value = (24, 'b' * 64)
        self.assertFalse(self.check())
        self.assertEqual(self.reader.call_count, 2)

    def test_future_version_not_current(self):
        self.add(version=24)
        self.assertFalse(self.check())

    def test_invalid_identity_never_authorizes(self):
        self.add()
        for identity in ((True, 'a' * 64), (0, 'a' * 64), (23, 'invalid'), (23, 'A' * 64)):
            self.reader.return_value = identity
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                self.check()

    def test_invalid_user_rejected(self):
        for user in (True, 0, -1, '1'):
            with self.subTest(user=user), self.assertRaises(ValueError):
                self.check(user)
        self.reader.assert_not_called()


if __name__ == '__main__':
    unittest.main()
