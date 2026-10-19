"""Exercise the guarded client's real HTTPX stream boundary without paid calls."""
import gzip
import unittest

import httpx

from backend.ai_guarded_client import GuardedAIClient, GuardError, Route

LIMIT = 512_000
ROUTE = Route('gateway', 'https://api.timeweb.ai/v1', 'test-only', 'model',
              1, 1, 0, 'max_tokens', 'RU', 1)


class Body(httpx.SyncByteStream):
    def __init__(self, chunks, failure=None):
        self.chunks = chunks
        self.failure = failure
        self.closed = False
        self.read_count = 0

    def __iter__(self):
        for chunk in self.chunks:
            self.read_count += 1
            yield chunk
        if self.failure is not None:
            raise self.failure

    def close(self):
        self.closed = True


class StreamingGuardTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.client = object.__new__(GuardedAIClient)
        self.body = None

    def stream(self, chunks, *, encoding=None, status=200, failure=None, extra_headers=None):
        self.body = Body(chunks, failure)
        headers = {} if encoding is None else {'Content-Encoding': encoding}
        headers.update(extra_headers or {})
        def transport(request):
            self.requests.append(request)
            return httpx.Response(status, stream=self.body, headers=headers)
        self.client.transport = httpx.MockTransport(transport)

    def send(self):
        return self.client._send(ROUTE, {'messages': [], 'stream': False})

    def rejected(self, code):
        with self.assertRaisesRegex(GuardError, '^' + code + '$') as raised:
            self.send()
        self.assertFalse(raised.exception.retryable)
        self.assertEqual(len(self.requests), 1)
        self.assertTrue(self.body.closed)

    def test_valid_identity_reply(self):
        self.stream([b'{"ok":true}'])
        self.assertEqual(self.send(), {'ok': True})
        self.assertEqual(self.requests[0].headers['Accept-Encoding'], 'gzip, identity')
        self.assertTrue(self.body.closed)

    def test_valid_gzip_reply(self):
        self.stream([gzip.compress(b'{"ok":true}', mtime=0)], encoding='gzip')
        self.assertEqual(self.send(), {'ok': True})
        self.assertTrue(self.body.closed)

    def test_concatenated_members_are_parsed_as_one_document(self):
        self.stream([gzip.compress(b'{"ok":', mtime=0), gzip.compress(b'true}', mtime=0)], encoding='gzip')
        self.assertEqual(self.send(), {'ok': True})

    def test_two_json_documents_cannot_hide_in_two_members(self):
        self.stream([gzip.compress(b'{}', mtime=0) + gzip.compress(b'{"hidden":true}', mtime=0)], encoding='gzip')
        self.rejected('ai_response_not_json')

    def test_gzip_without_integrity_trailer_is_rejected(self):
        self.stream([gzip.compress(b'{"ok":true}', mtime=0)[:-8]], encoding='gzip')
        self.rejected('ai_response_encoding_invalid')

    def test_expansion_limit_is_a_nonretryable_failure(self):
        self.stream([gzip.compress(b'x' * (LIMIT * 32), mtime=0)], encoding='gzip')
        self.rejected('ai_response_too_large')

    def test_false_content_length_does_not_override_actual_limit(self):
        self.stream([b'x' * (LIMIT + 1)], extra_headers={'Content-Length': '1'})
        self.rejected('ai_response_wire_too_large')

    def test_unnegotiated_encoding_is_rejected_before_body_read(self):
        self.stream([b'not a requested encoding'], encoding='br')
        self.rejected('ai_response_encoding_unsupported')
        self.assertEqual(self.body.read_count, 0)

    def test_redirect_is_not_followed_or_read(self):
        self.stream([b'not safe to consume'], status=302,
                    extra_headers={'Location': 'https://example.invalid/redirect'})
        self.rejected('ai_http_302')
        self.assertEqual(self.body.read_count, 0)

    def test_http_failure_does_not_read_error_body(self):
        self.stream([b'not safe to consume'], status=500)
        self.rejected('ai_http_500')
        self.assertEqual(self.body.read_count, 0)

    def test_read_error_remains_an_unknown_paid_outcome(self):
        self.stream([b'{'], failure=httpx.ReadError('do not expose transport details'))
        self.rejected('ai_transport_outcome_unknown')

    def test_strict_json_validation_still_runs_after_bounded_decompression(self):
        self.stream([gzip.compress(b'{"x":1,"x":2}', mtime=0)], encoding='gzip')
        self.rejected('ai_duplicate_json_field')


if __name__ == '__main__':
    unittest.main()
