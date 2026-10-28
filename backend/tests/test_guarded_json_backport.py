"""Regression contracts for both model content and the paid response envelope."""
import json
import math
import unittest

import httpx

from backend.ai_guarded_client import GuardError, GuardedAIClient, Route, _result_content


def content(value):
    return {"choices": [{"message": {"content": value}}]}


def send(body):
    # Exercise the real HTTP response parser without starting workers, a ledger,
    # or an external paid request. _send only needs an HTTP transport.
    client = object.__new__(GuardedAIClient)
    client.transport = httpx.MockTransport(lambda request: httpx.Response(200, content=body))
    route = Route("gateway", "https://api.timeweb.ai/v1", "test-only", "model", 1, 1, 0,
                  "max_tokens", "RU", 1)
    return client._send(route, {"messages": [], "stream": False})


class GuardedJsonBackportTests(unittest.TestCase):
    def test_duplicate_fields_are_rejected_at_every_object_depth(self):
        examples = ('{"x":1,"x":2}', '{"a":{"x":1,"x":2}}',
                    '{"a":[{"x":1,"x":2}]}', '{"x":1,"\\u0078":2}')
        for raw in examples:
            response = content(raw)
            with self.subTest(raw=raw), self.assertRaisesRegex(GuardError, "ai_duplicate_json_field"):
                _result_content(response)

    def test_large_exponents_do_not_become_infinity(self):
        for number in ("1e309", "-1e309", "1e9999"):
            response = content('{"value":' + number + '}')
            with self.subTest(number=number), self.assertRaisesRegex(GuardError, "ai_nonfinite_json"):
                _result_content(response)

    def test_nonzero_numbers_do_not_silently_become_zero(self):
        for number in ("1e-9999", "-1e-9999", "0.001e-9999"):
            response = content('{"value":' + number + '}')
            with self.subTest(number=number), self.assertRaisesRegex(GuardError, "ai_numeric_underflow"):
                _result_content(response)

    def test_nonstandard_constants_are_still_rejected(self):
        for number in ("NaN", "Infinity", "-Infinity"):
            response = content('{"value":' + number + '}')
            with self.subTest(number=number), self.assertRaisesRegex(GuardError, "ai_nonfinite_json"):
                _result_content(response)

    def test_finite_numbers_true_zero_and_exact_integers_are_preserved(self):
        parsed = _result_content(content('{"large":1e30,"zero":0e-9999,"negative":-0.0,"integer":9007199254740993}'))
        self.assertTrue(math.isfinite(parsed["large"]))
        self.assertEqual(parsed["zero"], 0)
        self.assertEqual(math.copysign(1, parsed["negative"]), -1)
        self.assertEqual(parsed["integer"], 9007199254740993)

    def test_sibling_objects_can_have_the_same_field(self):
        result = _result_content(content('{"items":[{"x":1},{"x":2}]}'))
        self.assertEqual(result["items"], [{"x": 1}, {"x": 2}])

    def test_strings_do_not_count_as_nested_containers(self):
        value = '{["\\' * 100
        self.assertEqual(_result_content(content(json.dumps({"text": value}))), {"text": value})

    def test_depth_limit_applies_before_python_decoder_recursion(self):
        response = content('{"a":' + '[' * 64 + '0' + ']' * 64 + '}')
        with self.assertRaisesRegex(GuardError, "ai_json_nesting_exceeded"):
            _result_content(response)

    def test_depth_boundary_is_accepted(self):
        response = content('{"a":' + '[' * 63 + '0' + ']' * 63 + '}')
        self.assertIn("a", _result_content(response))

    def test_content_byte_limit_counts_utf8_not_characters(self):
        response = content(json.dumps({"text": "я" * 256000}, ensure_ascii=False))
        with self.assertRaisesRegex(GuardError, "ai_response_too_large"):
            _result_content(response)

    def test_bad_grammar_is_a_safe_non_retryable_content_error(self):
        for raw in ('{"x":[}', '{"x":"unfinished}', '[]', '{"x":01}'):
            response = content(raw)
            with self.subTest(raw=raw), self.assertRaises(GuardError) as caught:
                _result_content(response)
            self.assertFalse(caught.exception.retryable)

    def test_response_usage_fields_cannot_be_overwritten_by_duplicates(self):
        body = b'{"usage":{"prompt_tokens":999,"prompt_tokens":1}}'
        with self.assertRaisesRegex(GuardError, "ai_duplicate_json_field"):
            send(body)

    def test_response_depth_limit_is_shared_with_content(self):
        body = ('{"a":' + '[' * 64 + '0' + ']' * 64 + '}').encode()
        with self.assertRaisesRegex(GuardError, "ai_json_nesting_exceeded"):
            send(body)

    def test_envelope_nonfinite_number_is_rejected(self):
        body = b'{"extra":1e9999}'
        with self.assertRaisesRegex(GuardError, "ai_nonfinite_json"):
            send(body)

    def test_valid_envelope_and_invalid_utf8(self):
        self.assertEqual(send(b'{"usage":{"prompt_tokens":1}}'), {"usage": {"prompt_tokens": 1}})
        with self.assertRaisesRegex(GuardError, "ai_response_not_json"):
            send(b'\xff')


if __name__ == "__main__":
    unittest.main()
