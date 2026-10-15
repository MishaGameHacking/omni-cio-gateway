"""Cross-runtime release text/JSON limits; no network, APK install or deployment."""
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from backend.client_updates import AndroidRelease, ReleaseUnavailable
from backend.release_json import (
    MAX_RELEASE_JSON_BYTES,
    ReleaseJsonError,
    decode_release_json,
    encode_release_json,
    utf16_units,
)
from backend.release_publication import _manifest


class ReleaseMetadataContractTests(unittest.TestCase):
    def release(self, **changes):
        raw = {
            'schema_version': 1,
            'package_name': 'ru.omnicio.app.debug',
            'version_code': 24,
            'version_name': '0.6.1-preview',
            'apk_sha256': 'a' * 64,
            'apk_bytes': 4_000_000,
            'certificate_sha256': 'b' * 64,
            'min_sdk': 36,
            'published_at': 1,
            'notes': '',
        }
        raw.update(changes)
        return AndroidRelease.parse(raw)

    def test_python_matches_android_utf16_limits(self):
        self.assertEqual(utf16_units('😀'), 2)
        self.assertEqual(self.release(version_name='😀' * 32).version_name, '😀' * 32)
        self.assertEqual(self.release(notes='😀' * 2000).notes, '😀' * 2000)
        for field, value in (
            ('version_name', '😀' * 33),
            ('notes', '😀' * 2001),
            ('version_name', chr(0xD800)),
            ('notes', chr(0xDC00)),
        ):
            with self.subTest(field=field), self.assertRaises(ReleaseUnavailable):
                self.release(**{field: value})

    def test_blank_names_and_unsafe_controls_are_rejected(self):
        self.assertEqual(self.release(notes='строка 1\nстрока 2\tготово\r').version_code, 24)
        for field, value in (('version_name', '   '), ('version_name', 'x\n'), ('notes', 'x\x01')):
            with self.subTest(field=field), self.assertRaises(ReleaseUnavailable):
                self.release(**{field: value})

    def test_writer_enforces_the_same_bounded_utf8_document(self):
        release = self.release(notes='Д' * 4000)
        document = encode_release_json({'schema_version': 1, **release.__dict__})
        self.assertLessEqual(len(document), MAX_RELEASE_JSON_BYTES)
        self.assertEqual(decode_release_json(document)['notes'], release.notes)
        with self.assertRaises(ReleaseJsonError):
            encode_release_json({'notes': 'x' * (MAX_RELEASE_JSON_BYTES + 1)})
        with self.assertRaises(ReleaseJsonError):
            decode_release_json(b'{"notes":"\\ud800"}')

    def test_failed_manifest_serialization_cannot_replace_current(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            destination = directory / 'current.json'
            destination.write_bytes(b'known-good')
            invalid = replace(self.release(), notes='x' * (MAX_RELEASE_JSON_BYTES + 1))
            with self.assertRaises(ReleaseUnavailable):
                _manifest(directory, destination, invalid, immutable=False)
            self.assertEqual(destination.read_bytes(), b'known-good')
            self.assertEqual(list(directory.glob('*.part')), [])


if __name__ == '__main__':
    unittest.main()
