"""Bounded publication byte-stream tests; synthetic bytes, no APK claims."""
from hashlib import sha256
from io import BytesIO
import unittest
from backend.release_bytes import ArtifactStreamError, copy_and_hash

DATA = b'synthetic bytes, not an APK'


class ByteStreamTests(unittest.TestCase):
    def test_copies_exact_bytes_and_digest(self):
        output = BytesIO()
        digest = copy_and_hash(BytesIO(DATA), len(DATA), output)
        self.assertEqual(output.getvalue(), DATA)
        self.assertEqual(digest, sha256(DATA).hexdigest())

    def test_hash_only_has_same_result(self):
        self.assertEqual(copy_and_hash(BytesIO(DATA), len(DATA)), sha256(DATA).hexdigest())

    def test_source_growth_is_bounded(self):
        class Growing:
            calls = []
            def read(self, size):
                self.calls.append(size)
                return b'x' * size
        source, output = Growing(), BytesIO()
        with self.assertRaisesRegex(ArtifactStreamError, 'size_changed'):
            copy_and_hash(source, 10, output)
        self.assertEqual(source.calls, [11])
        self.assertEqual(output.getvalue(), b'')

    def test_truncated_source_rejected(self):
        source, size = BytesIO(DATA[:-1]), len(DATA)
        with self.assertRaisesRegex(ArtifactStreamError, 'size_changed'):
            copy_and_hash(source, size)

    def test_changed_same_size_bytes_rejected(self):
        wrong = sha256(b'x' * len(DATA)).hexdigest()
        source, size = BytesIO(DATA), len(DATA)
        with self.assertRaisesRegex(ArtifactStreamError, 'checksum_changed'):
            copy_and_hash(source, size, expected_sha256=wrong)

    def test_short_writes_not_silently_successful(self):
        class ShortWriter:
            def write(self, chunk):
                return len(chunk) - 1
        source, size, output = BytesIO(DATA), len(DATA), ShortWriter()
        with self.assertRaisesRegex(ArtifactStreamError, 'short_write'):
            copy_and_hash(source, size, output)

    def test_invalid_bounds_rejected_before_read(self):
        for size in (0, -1, True, 10.0, 256 * 1024 * 1024 + 1):
            source = BytesIO(DATA)
            with self.subTest(size=size), self.assertRaises(ArtifactStreamError):
                copy_and_hash(source, size)
            self.assertEqual(source.tell(), 0)

    def test_invalid_digest_rejected_before_read(self):
        source = BytesIO(DATA)
        size = len(DATA)
        with self.assertRaises(ArtifactStreamError):
            copy_and_hash(source, size, expected_sha256='bad')
        self.assertEqual(source.tell(), 0)

    def test_io_exception_propagates(self):
        class Broken:
            def read(self, size):
                raise OSError('synthetic failure')
        source, size = Broken(), len(DATA)
        with self.assertRaises(OSError):
            copy_and_hash(source, size)

    def test_caller_owns_streams(self):
        source, output = BytesIO(DATA), BytesIO()
        copy_and_hash(source, len(DATA), output)
        self.assertFalse(source.closed)
        self.assertFalse(output.closed)

    def test_unexpected_read_type_not_eof(self):
        class NonBlocking:
            def read(self, size):
                return None
        source, size = NonBlocking(), len(DATA)
        with self.assertRaises(ArtifactStreamError):
            copy_and_hash(source, size)


if __name__ == '__main__':
    unittest.main()
