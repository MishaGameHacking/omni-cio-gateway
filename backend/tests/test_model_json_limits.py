"""Bounded model JSON: parse the exact transport and inner-content boundaries."""
import json
import unittest
from unittest.mock import patch

import httpx

from backend.ai_guarded_client import GuardedAIClient, GuardError, Route, _result_content
from backend.model_json_limits import (
    MAX_MODEL_JSON_BYTES, MAX_MODEL_JSON_DEPTH, checked_model_json_text,
)


def _document(depth, kind):
    left, right = ('[', ']') if kind == 'array' else ('{"child":', '}')
    return '{"data":' + left * (depth - 1) + '0' + right * (depth - 1) + '}'


def _inner(text):
    return _result_content({'choices': [{'message': {'content': text}}]})


def _outer(text):
    client = object.__new__(GuardedAIClient)
    client.transport = httpx.MockTransport(lambda request: httpx.Response(200, content=text))
    route = Route('gateway', 'https://api.timeweb.ai/v1', 'synthetic-test-token',
                  'audit-model', 1, 1, 0, 'max_tokens', 'RU', 1)
    return client._send(route, {})


class ModelJsonLimitsTests(unittest.TestCase):
    def test_depth_limit_has_no_off_by_one(self):
        for kind in ('array', 'object'):
            accepted = _document(MAX_MODEL_JSON_DEPTH, kind)
            rejected = _document(MAX_MODEL_JSON_DEPTH + 1, kind)
            for parser in (_inner, _outer):
                with self.subTest(kind=kind, boundary=parser.__name__):
                    self.assertEqual(parser(accepted), json.loads(accepted))
                    with self.assertRaisesRegex(GuardError, 'ai_json_nesting_exceeded'):
                        parser(rejected)

    def test_rejection_happens_before_json_decoder(self):
        text = _document(10001, 'array')
        # This succeeds even with an iterative decoder that never raises
        # RecursionError. Do not adjust sys.setrecursionlimit in tests/runtime.
        with patch('backend.ai_guarded_client.json.loads') as decoder:
            with self.assertRaisesRegex(GuardError, 'ai_json_nesting_exceeded'):
                _inner(text)
        decoder.assert_not_called()

    def test_quotes_and_escaped_backslashes_are_not_depth(self):
        values = ['[' * 10000, '{' * 10000, '"[{}]"', '\\"[', '\\\\', '\\']
        for value in values:
            text = json.dumps({'text': value})
            for parser in (_inner, _outer):
                with self.subTest(value_length=len(value), boundary=parser.__name__):
                    self.assertEqual(parser(text), {'text': value})

    def test_utf8_byte_limit_applies_to_inner_content(self):
        text = json.dumps({'text': 'я' * (MAX_MODEL_JSON_BYTES // 2)}, ensure_ascii=False)
        with self.assertRaisesRegex(GuardError, 'ai_response_too_large'):
            _inner(text)

    def test_exact_byte_boundary_is_accepted(self):
        text = '"' + 'x' * (MAX_MODEL_JSON_BYTES - 2) + '"'
        self.assertEqual(checked_model_json_text(text), text)
        self.assertEqual(checked_model_json_text(text.encode()), text)
        self.assertEqual(checked_model_json_text(bytearray(text.encode())), text)

    def test_one_byte_over_budget_is_rejected_at_both_boundaries(self):
        text = '{"x":"' + 'a' * MAX_MODEL_JSON_BYTES + '"}'
        for parser in (_inner, _outer):
            with self.subTest(boundary=parser.__name__):
                with self.assertRaisesRegex(GuardError, 'ai_response_too_large'):
                    parser(text)

    def test_unbalanced_and_invalid_grammar_remain_controlled(self):
        for text in ('{"x": [}', '{"x": ]}', '{"x": [1}', '{"x": "unterminated',
                     '{"x": "tail\\', '{"x": 1,}', '{"x": "\\q"}', '{"x": "a\nb"}'):
            for parser in (_inner, _outer):
                with self.subTest(document=text, boundary=parser.__name__):
                    with self.assertRaises(GuardError):
                        parser(text)

    def test_unicode_decode_and_surrogates_are_controlled(self):
        with self.assertRaisesRegex(GuardError, 'ai_response_not_json'):
            _outer(b'{"x":"\xff"}')
        with self.assertRaisesRegex(GuardError, 'ai_content_not_json'):
            _inner('{"x":"\ud800"}')

    def test_duplicate_nested_keys_are_not_last_value_wins(self):
        text = '{"nested":{"risk":1,"risk":0}}'
        for parser in (_inner, _outer):
            with self.subTest(boundary=parser.__name__):
                with self.assertRaisesRegex(GuardError, 'ai_duplicate_json_field'):
                    parser(text)

    def test_nonfinite_and_underflow_cannot_become_decisions(self):
        for number in ('1e999', 'NaN', 'Infinity', '1e-999', '-1e-999'):
            text = '{"value":' + number + '}'
            for parser in (_inner, _outer):
                with self.subTest(number=number, boundary=parser.__name__):
                    with self.assertRaises(GuardError):
                        parser(text)

    def test_valid_decision_and_numbers_are_unchanged(self):
        text = '{"decision":"wait","lots":0,"zero":0e-999,"risk":0.125}'
        expected = {'decision': 'wait', 'lots': 0, 'zero': 0.0, 'risk': 0.125}
        self.assertEqual(_inner(text), expected)
        self.assertEqual(_outer(text), expected)

    def test_nontext_preflight_input_rejected(self):
        for value in (None, {}, [], 123):
            with self.subTest(type_name=type(value).__name__):
                with self.assertRaises(TypeError):
                    checked_model_json_text(value)


if __name__ == '__main__':
    unittest.main()
