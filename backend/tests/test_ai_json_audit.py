"""Reject ambiguous/nonrepresentable model numbers at both JSON boundaries."""
import unittest

import httpx

from backend.ai_guarded_client import GuardedAIClient, GuardError, Route, _result_content


class ModelJsonAuditTests(unittest.TestCase):
    @staticmethod
    def content(text):
        return _result_content({'choices': [{'message': {'content': text}}]})

    @staticmethod
    def outer(text):
        # Bypass only initialization (which creates a ledger). _send is the real
        # bounded transport/JSON parser, with no external requests or model calls.
        client = object.__new__(GuardedAIClient)
        client.transport = httpx.MockTransport(lambda request: httpx.Response(200, content=text))
        route = Route('gateway', 'https://api.timeweb.ai/v1', 'synthetic-test-token',
                      'audit-model', 1, 1, 0, 'max_tokens', 'RU', 1)
        return client._send(route, {})

    def test_underflow_is_not_accepted_as_zero(self):
        for number in ('1e-999', '-1e-999', '1e-324', '0.0001e-999'):
            text = '{"risk":' + number + '}'
            for parse in (self.content, self.outer):
                with self.subTest(number=number, boundary=parse.__name__):
                    with self.assertRaisesRegex(GuardError, 'ai_numeric_underflow'):
                        parse(text)

    def test_real_zero_and_representable_small_number_remain_valid(self):
        for number, expected in [('0e-999', 0.0), ('-0.0e+999', -0.0), ('5e-324', 5e-324), ('1e-300', 1e-300)]:
            text = '{"value":' + number + '}'
            for parse in (self.content, self.outer):
                with self.subTest(number=number, boundary=parse.__name__):
                    self.assertEqual(parse(text)['value'], expected)

    def test_duplicate_fields_cannot_overwrite_decisions(self):
        for text in ('{"risk":1,"risk":0}', '{"nested":{"a":1,"a":2}}', '{"a":1,"\\u0061":2}'):
            for parse in (self.content, self.outer):
                with self.subTest(text=text, boundary=parse.__name__):
                    with self.assertRaisesRegex(GuardError, 'ai_duplicate_json_field'):
                        parse(text)

    def test_overflow_and_nonfinite_numbers_are_rejected(self):
        for number in ('1e999', '-1e999', 'NaN', 'Infinity', '-Infinity'):
            text = '{"value":' + number + '}'
            for parse in (self.content, self.outer):
                with self.subTest(number=number, boundary=parse.__name__):
                    with self.assertRaisesRegex(GuardError, 'ai_nonfinite_json'):
                        parse(text)

    def test_excessive_nesting_is_a_controlled_error(self):
        text = '{"nested":' + '[' * 10000 + '0' + ']' * 10000 + '}'
        for parse in (self.content, self.outer):
            with self.subTest(boundary=parse.__name__):
                with self.assertRaisesRegex(GuardError, 'ai_json_nesting_exceeded'):
                    parse(text)

    def test_valid_nested_objects_are_unchanged(self):
        text = '{"decision":"wait","details":[{"risk":0.125,"lots":0}]}'
        expected = {'decision': 'wait', 'details': [{'risk': 0.125, 'lots': 0}]}
        self.assertEqual(self.content(text), expected)
        self.assertEqual(self.outer(text), expected)


if __name__ == '__main__':
    unittest.main()
