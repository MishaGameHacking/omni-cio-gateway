from __future__ import annotations

import unittest

from scripts.v10_jsonc import loads_jsonc


class JsoncTests(unittest.TestCase):
    def test_comments_and_trailing_commas_are_supported(self) -> None:
        payload = loads_jsonc(
            """
            {
              // Wrangler-style line comment
              "name": "omni//cio",
              "nested": {
                /* block comment */
                "value": "literal /* text */",
              },
              "items": [1, 2,],
            }
            """
        )
        self.assertEqual(payload["name"], "omni//cio")
        self.assertEqual(payload["nested"]["value"], "literal /* text */")
        self.assertEqual(payload["items"], [1, 2])

    def test_unterminated_block_comment_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "unterminated JSONC block comment"):
            loads_jsonc('{"value": 1 /*')

    def test_escaped_string_content_is_preserved(self) -> None:
        payload = loads_jsonc(r'{"value": "quote: \" // not a comment",}')
        self.assertEqual(payload["value"], 'quote: " // not a comment')


if __name__ == "__main__":
    unittest.main()
