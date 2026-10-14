"""Synthetic release JSON and local bytes, never an installable/signed APK."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from backend.client_updates import AndroidRelease, ReleaseChannel, ReleaseUnavailable, _client_code, _integer, valid_apk_filename
from backend.release_json import decode_release_json, ReleaseJsonError, MAX_RELEASE_JSON_BYTES


class ReleaseJsonTests(unittest.TestCase):
    def test_utf8_and_types_preserved(self):
        raw = '{"notes":"Обновление","code":23,"flag":true,"absent":null}'.encode()
        self.assertEqual(decode_release_json(raw), {'notes': 'Обновление', 'code': 23, 'flag': True, 'absent': None})

    def test_duplicate_version_rejected(self):
        raw = b'{"version_code":22,"version_code":23}'
        with self.assertRaises(ReleaseJsonError):
            decode_release_json(raw)

    def test_identical_duplicate_is_also_ambiguous(self):
        with self.assertRaises(ReleaseJsonError):
            decode_release_json(b'{"code":23,"code":23}')

    def test_escaped_duplicate_rejected(self):
        raw = b'{"version_code":22,"\\u0076ersion_code":23}'
        with self.assertRaises(ReleaseJsonError):
            decode_release_json(raw)

    def test_duplicate_null_not_missed(self):
        with self.assertRaises(ReleaseJsonError):
            decode_release_json(b'{"x":null,"x":1}')

    def test_nested_duplicate_rejected(self):
        with self.assertRaises(ReleaseJsonError):
            decode_release_json(b'{"extra":{"x":1,"x":2}}')

    def test_separate_object_members_do_not_conflict(self):
        result = decode_release_json(b'{"extra":[{"x":1},{"x":2}]}')
        self.assertEqual(result['extra'][1]['x'], 2)

    def test_nonfinite_rejected(self):
        for number in (b'NaN', b'Infinity', b'-Infinity', b'1e9999'):
            raw = b'{"extra":' + number + b'}'
            with self.subTest(number=number), self.assertRaises(ReleaseJsonError):
                decode_release_json(raw)

    def test_finite_fraction_is_not_coerced_to_integer(self):
        self.assertIs(type(decode_release_json(b'{"code":23.0}')['code']), float)

    def test_nonstandard_syntax_and_trailing_documents_rejected(self):
        for raw in (b"{'x':1}", b'{x:1}', b'{"x":1,}', b'{}{}', b'{/*comment*/"x":1}', b'{"x":01}'):
            with self.subTest(raw=raw), self.assertRaises(ReleaseJsonError):
                decode_release_json(raw)

    def test_only_object_root_allowed(self):
        for raw in (b'[]', b'null', b'1', b'"object"', b'true'):
            with self.subTest(raw=raw), self.assertRaises(ReleaseJsonError):
                decode_release_json(raw)

    def test_malformed_utf8_and_other_encodings_rejected(self):
        for raw in (b'{"x":"\xff"}', b'\xef\xbb\xbf{}', '{}'.encode('utf-16')):
            with self.subTest(raw=raw), self.assertRaises(ReleaseJsonError):
                decode_release_json(raw)

    def test_size_bound_includes_utf8_bytes(self):
        raw = ('{"x":"' + 'я' * MAX_RELEASE_JSON_BYTES + '"}').encode()
        with self.assertRaises(ReleaseJsonError):
            decode_release_json(raw)

    def test_limit_is_inclusive(self):
        raw = b'{}' + b' ' * (MAX_RELEASE_JSON_BYTES - 2)
        self.assertEqual(decode_release_json(raw), {})

    def test_empty_or_nonbytes_rejected(self):
        for raw in (b'', None, {}, '{}'):
            with self.subTest(raw=raw), self.assertRaises(ReleaseJsonError):
                decode_release_json(raw)

    def test_deep_nesting_is_domain_failure_not_recursion_crash(self):
        raw = b'{"extra":' + b'[' * 2000 + b'0' + b']' * 2000 + b'}'
        with self.assertRaises(ReleaseJsonError):
            decode_release_json(raw)

    def test_long_integer_bounds(self):
        raw = b'{"x":9223372036854775807,"y":-9223372036854775808}'
        self.assertEqual(decode_release_json(raw)['x'], 2**63 - 1)
        for raw in (b'{"x":9223372036854775808}', b'{"x":-9223372036854775809}'):
            with self.subTest(raw=raw), self.assertRaises(ReleaseJsonError):
                decode_release_json(raw)

    def test_value_budget_rejected(self):
        raw = b'{"x":[' + b','.join([b'0'] * 1024) + b']}'
        with self.assertRaises(ReleaseJsonError):
            decode_release_json(raw)

    def test_unpaired_surrogates_rejected(self):
        for raw in (b'{"x":"\\ud800"}', b'{"\\udfff":0}'):
            with self.subTest(raw=raw), self.assertRaises(ReleaseJsonError):
                decode_release_json(raw)

    def test_code_header_stays_ascii_and_bounded(self):
        self.assertEqual(_client_code('23'), 23)
        for value in ('2٣', '２3', '23\n', '023', '2100000001', True, None):
            self.assertEqual(_client_code(value), 0)

    def test_filename_stays_ascii(self):
        self.assertTrue(valid_apk_filename('Analyst-AI-23-' + 'a' * 64 + '.apk'))
        self.assertFalse(valid_apk_filename('Analyst-AI-2٣-' + 'a' * 64 + '.apk'))

    def test_integer_type_and_limits_are_not_weakened(self):
        for value in (True, '23', 23.0, None, 0, 24):
            with self.subTest(value=value), self.assertRaises(ReleaseUnavailable):
                _integer(value, 1, 23)
        self.assertEqual(_integer(23, 1, 23), 23)


class ReleaseChannelJsonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.channel = ReleaseChannel(Path(self.temp.name))
        data = b'synthetic-file-not-an-apk'
        self.release = AndroidRelease('ru.omnicio.app.debug', 23, '0.6.0-preview',
            hashlib.sha256(data).hexdigest(), len(data), 'b' * 64, 33, int(time.time()) - 10)
        self.directory = self.channel.directory(self.release.package_name)
        self.directory.mkdir()
        (self.directory / self.release.filename).write_bytes(data)
        self.raw = json.dumps({'schema_version': 1, **asdict(self.release)}).encode()
        self.current = self.directory / 'current.json'

    def test_canonical_manifest_still_checks_actual_bytes(self):
        self.current.write_bytes(self.raw)
        self.assertEqual(self.channel.current(self.release.package_name), self.release)
        (self.directory / self.release.filename).write_bytes(b'changed')
        with self.assertRaises(ReleaseUnavailable):
            self.channel.current(self.release.package_name)

    def test_duplicate_manifest_stops_before_apk_verification(self):
        self.current.write_bytes(self.raw.replace(b'{', b'{"version_code":22,', 1))
        with patch.object(self.channel, 'verified_file') as verify:
            with self.assertRaises(ReleaseUnavailable):
                self.channel.current(self.release.package_name)
        verify.assert_not_called()

    def test_retained_manifest_uses_same_decoder(self):
        path = self.directory / (self.release.filename[:-4] + '.json')
        path.write_bytes(self.raw.replace(b'{', b'{"version_code":22,', 1))
        self.current.write_bytes(self.raw)
        with self.assertRaises(ReleaseUnavailable):
            self.channel.published(self.release.package_name, self.release.filename)

    def test_recursive_input_is_release_unavailable(self):
        self.current.write_bytes(b'{"x":' + b'[' * 2000 + b'0' + b']' * 2000 + b'}')
        with self.assertRaises(ReleaseUnavailable):
            self.channel.current(self.release.package_name)


if __name__ == '__main__':
    unittest.main()
