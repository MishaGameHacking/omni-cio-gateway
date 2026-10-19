"""Real HTTPX raw-stream tests, with no network, API keys or live accounts."""
import gzip
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import httpx

from backend.bounded_ai_response import (
    MAX_GZIP_MEMBERS, ResponseBodyError, read_bounded_body,
)

LIMIT = 512_000


class Chunks(httpx.SyncByteStream):
    def __init__(self, chunks):
        self.chunks = chunks
        self.read_count = 0
        self.closed = False

    def __iter__(self):
        for chunk in self.chunks:
            self.read_count += 1
            yield chunk

    def close(self):
        self.closed = True


def collect(chunks, encoding=None, limit=LIMIT, clock=None, deadline=None):
    stream = Chunks(chunks)
    headers = {} if encoding is None else {'Content-Encoding': encoding}
    response = httpx.Response(200, stream=stream, headers=headers)
    kwargs = {} if clock is None else {'clock': clock}
    try:
        result = read_bounded_body(response, limit=limit,
                                   deadline=time.monotonic() + 60 if deadline is None else deadline,
                                   **kwargs)
    finally:
        response.close()
    return result, stream


class BoundedResponseTests(unittest.TestCase):
    def test_identity_content_is_not_changed(self):
        data = '{"text":"Привет"}'.encode()
        value, stream = collect([data[:7], data[7:]])
        self.assertEqual(value, data)
        self.assertTrue(stream.closed)

    def test_exact_identity_limit_is_accepted(self):
        self.assertEqual(len(collect([b'x' * LIMIT])[0]), LIMIT)

    def test_wire_limit_is_checked_before_retaining_a_chunk(self):
        with self.assertRaisesRegex(ResponseBodyError, 'ai_response_wire_too_large'):
            collect([b'x' * (LIMIT + 1)])

    def test_cumulative_wire_limit_cannot_be_split_away(self):
        with self.assertRaisesRegex(ResponseBodyError, 'ai_response_wire_too_large'):
            collect([b'x' * 256_000, b'x' * 256_001])

    def test_gzip_content_survives_every_single_byte_boundary(self):
        data = '{"text":"проверка"}'.encode()
        packed = gzip.compress(data, mtime=0)
        self.assertEqual(collect([packed[i:i + 1] for i in range(len(packed))], 'gzip')[0], data)

    def test_exact_gzip_output_limit_is_accepted(self):
        self.assertEqual(len(collect([gzip.compress(b'x' * LIMIT, mtime=0)], 'gzip')[0]), LIMIT)

    def test_gzip_expansion_is_rejected_without_unbounded_decompress(self):
        packed = gzip.compress(b'x' * (LIMIT * 64), mtime=0)
        with self.assertRaisesRegex(ResponseBodyError, 'ai_response_too_large'):
            collect([packed], 'gzip')

    def test_decompress_never_uses_unbounded_max_length_or_flush(self):
        import backend.bounded_ai_response as module
        real = module.zlib.decompressobj
        budgets = []

        class ObservedDecoder:
            def __init__(self, *args):
                self.original = real(*args)

            def decompress(self, data, max_length):
                budgets.append(max_length)
                self.assert_positive_budget(max_length)
                return self.original.decompress(data, max_length)

            @staticmethod
            def assert_positive_budget(value):
                if not 0 < value <= LIMIT + 1:
                    raise AssertionError('unbounded decompression request')

            def __getattr__(self, key):
                if key == 'flush':
                    raise AssertionError('unbounded flush is forbidden')
                return getattr(self.original, key)

        packed = gzip.compress(b'x' * (LIMIT * 4), mtime=0)
        with patch.object(module.zlib, 'decompressobj', ObservedDecoder):
            with self.assertRaisesRegex(ResponseBodyError, 'ai_response_too_large'):
                collect([packed], 'gzip')
        self.assertTrue(budgets)

    def test_gzip_truncation_is_not_accepted_as_complete_json(self):
        packed = gzip.compress(b'{"ok":true}', mtime=0)
        for missing in (1, 4, 8):
            with self.subTest(missing=missing):
                with self.assertRaisesRegex(ResponseBodyError, 'ai_response_encoding_invalid'):
                    collect([packed[:-missing]], 'gzip')

    def test_gzip_checksum_failure_is_rejected(self):
        packed = bytearray(gzip.compress(b'{}', mtime=0))
        packed[-8] ^= 1
        corrupted = bytes(packed)
        with self.assertRaisesRegex(ResponseBodyError, 'ai_response_encoding_invalid'):
            collect([corrupted], 'gzip')

    def test_concatenated_members_are_not_silently_discarded(self):
        packed = gzip.compress(b'{"ok":', mtime=0) + gzip.compress(b'true}', mtime=0)
        self.assertEqual(collect([packed], 'gzip')[0], b'{"ok":true}')

    def test_separate_chunks_at_member_boundary_are_supported(self):
        chunks = [gzip.compress(b'{"ok":', mtime=0), gzip.compress(b'true}', mtime=0)]
        self.assertEqual(collect(chunks, 'gzip')[0], b'{"ok":true}')

    def test_later_member_is_subject_to_the_same_global_output_limit(self):
        chunks = [gzip.compress(b'x' * 300_000, mtime=0), gzip.compress(b'x' * 300_000, mtime=0)]
        with self.assertRaisesRegex(ResponseBodyError, 'ai_response_too_large'):
            collect(chunks, 'gzip')

    def test_trailing_garbage_is_rejected(self):
        packed = gzip.compress(b'{}', mtime=0) + b'not a gzip member'
        with self.assertRaisesRegex(ResponseBodyError, 'ai_response_encoding_invalid'):
            collect([packed], 'gzip')

    def test_empty_compressed_stream_is_invalid(self):
        with self.assertRaisesRegex(ResponseBodyError, 'ai_response_encoding_invalid'):
            collect([], 'gzip')

    def test_member_count_is_bounded_including_empty_members(self):
        packed = gzip.compress(b'', mtime=0) * (MAX_GZIP_MEMBERS + 1)
        with self.assertRaisesRegex(ResponseBodyError, 'ai_response_gzip_members_exceeded'):
            collect([packed], 'gzip')

    def test_exact_member_limit_is_accepted(self):
        packed = gzip.compress(b'x', mtime=0) * MAX_GZIP_MEMBERS
        self.assertEqual(collect([packed], 'gzip')[0], b'x' * MAX_GZIP_MEMBERS)

    def test_unadvertised_or_stacked_encoding_is_rejected(self):
        for encoding in ('br', 'deflate', 'zstd', 'gzip, gzip', ''):
            with self.subTest(encoding=encoding):
                with self.assertRaisesRegex(ResponseBodyError, 'ai_response_encoding_unsupported'):
                    collect([b'{}'], encoding)

    def test_case_insensitive_gzip_token(self):
        self.assertEqual(collect([gzip.compress(b'{}', mtime=0)], ' GZIP ')[0], b'{}')

    def test_pre_read_identity_response_is_bounded(self):
        response = httpx.Response(200, content=b'{}')
        self.assertEqual(read_bounded_body(response, limit=2, deadline=time.monotonic() + 60), b'{}')
        deadline = time.monotonic() + 60
        with self.assertRaisesRegex(ResponseBodyError, 'ai_response_too_large'):
            read_bounded_body(response, limit=1, deadline=deadline)

    def test_predecoded_gzip_cannot_claim_bounded_decompression(self):
        response = httpx.Response(200, content=gzip.compress(b'{}'), headers={'Content-Encoding': 'gzip'})
        deadline = time.monotonic() + 60
        with self.assertRaisesRegex(ResponseBodyError, 'ai_response_encoded_body_already_read'):
            read_bounded_body(response, limit=1000, deadline=deadline)

    def test_expired_deadline_prevents_reading(self):
        with self.assertRaisesRegex(ResponseBodyError, 'ai_response_deadline'):
            collect([b'{}'], deadline=10, clock=lambda: 10)

    def test_deadline_is_checked_at_eof_even_without_output(self):
        clock = iter((0, 11))
        with self.assertRaisesRegex(ResponseBodyError, 'ai_response_deadline'):
            collect([], deadline=10, clock=clock.__next__)

    def test_deadline_is_checked_on_raw_header_only_chunks(self):
        clock = iter((0, 1, 11))
        packed = gzip.compress(b'{}', mtime=0)
        with self.assertRaisesRegex(ResponseBodyError, 'ai_response_deadline'):
            collect([packed[:1], packed[1:2], packed[2:]], 'gzip', deadline=10, clock=clock.__next__)

    def test_later_chunks_are_not_read_after_a_rejection(self):
        stream = Chunks([b'x' * 10, b'never read'])
        response = httpx.Response(200, stream=stream)
        deadline = time.monotonic() + 60
        with self.assertRaisesRegex(ResponseBodyError, 'ai_response_wire_too_large'):
            read_bounded_body(response, limit=1, deadline=deadline)
        response.close()
        self.assertEqual(stream.read_count, 1)
        self.assertTrue(stream.closed)

    def test_limits_are_explicitly_validated(self):
        for limit in (True, 0, -1, 2.0, 2 * 1024 * 1024 + 1):
            with self.subTest(limit=limit), self.assertRaisesRegex(ValueError, 'ai_response_limit_invalid'):
                collect([], limit=limit)

    def test_invalid_deadlines_are_rejected(self):
        for deadline in (True, float('nan'), float('inf'), '10'):
            with self.subTest(deadline=deadline), self.assertRaisesRegex(ValueError, 'ai_response_deadline_invalid'):
                collect([], deadline=deadline)

    def test_parallel_responses_do_not_share_decoder_or_limits(self):
        def exercise(index):
            data = ('{"id":%d}' % index).encode()
            packed = gzip.compress(data, mtime=0)
            return collect([packed], 'gzip')[0] == data
        with ThreadPoolExecutor(max_workers=4) as executor:
            self.assertTrue(all(executor.map(exercise, range(64))))


if __name__ == '__main__':
    unittest.main()
