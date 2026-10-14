"""Local manifest writer tests; synthetic metadata, no deployment or APK install."""
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest

from backend.client_updates import AndroidRelease, PREVIEW_PACKAGE, ReleaseUnavailable
from backend.release_publication import _manifest


class PublicationJsonTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.target = self.root / 'retained.json'
        self.release = AndroidRelease(PREVIEW_PACKAGE, 24, '0.6.1-preview', 'a' * 64,
                                      100, 'b' * 64, 33, 1)
        self.raw = {'schema_version': 1, **asdict(self.release)}

    def write(self, raw):
        self.target.write_bytes(raw)

    def check_existing(self):
        _manifest(self.root, self.target, self.release, immutable=True)

    def test_canonical_metadata_can_be_retained(self):
        _manifest(self.root, self.target, self.release, immutable=True)
        before = self.target.read_bytes()
        self.check_existing()
        self.assertEqual(self.target.read_bytes(), before)

    def test_conflicting_duplicate_cannot_be_accepted_as_unchanged(self):
        raw = b'{"version_code":23,' + json.dumps(self.raw).encode()[1:]
        self.write(raw)
        with self.assertRaisesRegex(ReleaseUnavailable, 'immutable_manifest_invalid'):
            self.check_existing()
        self.assertEqual(self.target.read_bytes(), raw)

    def test_identical_duplicate_is_also_ambiguous(self):
        raw = b'{"version_code":24,' + json.dumps(self.raw).encode()[1:]
        self.write(raw)
        with self.assertRaisesRegex(ReleaseUnavailable, 'immutable_manifest_invalid'):
            self.check_existing()

    def test_unambiguous_different_version_is_still_immutable(self):
        self.write(json.dumps({**self.raw, 'version_code': 25}).encode())
        with self.assertRaisesRegex(ReleaseUnavailable, 'immutable_manifest_conflict'):
            self.check_existing()

    def test_bad_encoding_is_a_domain_error(self):
        self.write(b'{"notes":"\xff"}')
        with self.assertRaises(ReleaseUnavailable):
            self.check_existing()

    def test_recursive_metadata_does_not_escape_as_recursion_error(self):
        raw = b'{"extra":' + b'[' * 80 + b'0' + b']' * 80 + b'}'
        self.write(raw)
        with self.assertRaises(ReleaseUnavailable):
            self.check_existing()

    def test_trailing_document_does_not_overwrite_existing_metadata(self):
        raw = json.dumps(self.raw).encode() + b'{}'
        self.write(raw)
        with self.assertRaises(ReleaseUnavailable):
            self.check_existing()
        self.assertEqual(self.target.read_bytes(), raw)
        self.assertEqual(list(self.root.iterdir()), [self.target])


if __name__ == '__main__':
    unittest.main()
