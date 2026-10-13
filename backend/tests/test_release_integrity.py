"""Byte-level integrity regressions; fixtures are NOT installable APKs."""
import hashlib
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from backend.client_updates import AndroidRelease, ReleaseChannel, ReleaseUnavailable, MAX_APK_BYTES, _file_digest


class ReleaseIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        data = b'original synthetic bytes'
        digest = hashlib.sha256(data).hexdigest()
        self.release = AndroidRelease('ru.omnicio.app.debug', 23, 'test', digest, len(data),
                                      'c' * 64, 33, int(time.time()))
        self.path = self.root / self.release.package_name / self.release.filename
        self.path.parent.mkdir()
        self.path.write_bytes(data)
        self.channel = ReleaseChannel(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_content_is_rehashed_even_with_identical_stat(self):
        original_stat = self.path.stat()
        real_stat = Path.stat
        def frozen_stat(path, *args, **kwargs):
            return original_stat if path == self.path else real_stat(path, *args, **kwargs)
        with patch.object(Path, 'stat', frozen_stat):
            self.assertEqual(self.channel.verified_file(self.release), self.path)
            self.path.write_bytes(b'x' * self.release.apk_bytes)
            self.assertEqual(self.path.stat(), original_stat)
            with self.assertRaisesRegex(ReleaseUnavailable, 'checksum_invalid'):
                self.channel.verified_file(self.release)

    def test_direct_hash_is_not_cached_by_path_and_size(self):
        old = _file_digest(str(self.path), self.release.apk_bytes)
        self.path.write_bytes(b'x' * self.release.apk_bytes)
        self.assertNotEqual(_file_digest(str(self.path), self.release.apk_bytes), old)

    def test_shrinking_during_verification_is_rejected(self):
        self.path.write_bytes(b'one')
        with self.assertRaisesRegex(ReleaseUnavailable, 'size_changed'):
            _file_digest(str(self.path), 4)

    def test_growing_during_verification_is_rejected(self):
        self.path.write_bytes(b'four')
        with self.assertRaisesRegex(ReleaseUnavailable, 'size_changed'):
            _file_digest(str(self.path), 3)

    def test_invalid_read_bounds_are_rejected(self):
        for size in (True, 0, -1, MAX_APK_BYTES + 1):
            with self.subTest(size=size), self.assertRaises(ReleaseUnavailable):
                _file_digest(str(self.path), size)

    def test_unchanged_bytes_match_expected_sha256(self):
        for _ in range(3):
            self.assertEqual(_file_digest(str(self.path), self.release.apk_bytes), self.release.apk_sha256)

if __name__ == '__main__':
    unittest.main()
