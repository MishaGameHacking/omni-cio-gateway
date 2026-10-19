"""Verify signed tokens using the actual validator without importing a live app."""
import ast
import json
from pathlib import Path
import secrets
import tempfile
import time
from types import SimpleNamespace
import unittest

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa


class TelegramNonceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.public_key = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(cls.private_key.public_key()))
        cls.public_key.update(kid="test-key", alg="RS256", use="sig")
        path = Path(__file__).resolve().parents[1] / "telegram_browser_app.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        names = {"TelegramTokenError", "TelegramKeyUnavailable", "_load_pinned_key",
                 "_nonce_matches", "verify_browser_id_token"}
        selected = [node for node in tree.body
                    if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names]
        cls.validator_code = compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec")

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "jwks.json"
        path.write_text(json.dumps({"keys": [self.public_key]}), encoding="utf-8")
        self.namespace = {
            "jwt": jwt, "json": json, "secrets": secrets, "TELEGRAM_JWKS_PATH": path,
            "legacy": SimpleNamespace(TELEGRAM_CLIENT_ID="test-client", TELEGRAM_ISSUER="https://example.invalid"),
        }
        exec(self.validator_code, self.namespace)
        self.verify = self.namespace["verify_browser_id_token"]
        self.invalid = self.namespace["TelegramTokenError"]
        self.expected = secrets.token_urlsafe(32)

    def token(self, nonce, *, changes=None, key=None):
        now = int(time.time())
        claims = {"iss": "https://example.invalid", "aud": "test-client", "sub": "test-owner",
                  "exp": now + 300, "iat": now, "nonce": nonce}
        claims.update(changes or {})
        return jwt.encode(claims, key or self.private_key, algorithm="RS256", headers={"kid": "test-key"})

    def test_exact_nonce_passes_with_real_signature(self):
        claims = self.verify(self.token(self.expected), self.expected)
        self.assertEqual(claims["sub"], "test-owner")

    def test_non_ascii_nonce_is_authentication_error_not_type_error(self):
        for nonce in ("чужой", "é", "🙂", "\ud800", self.expected + "é"):
            encoded = self.token(nonce)
            with self.subTest(nonce=ascii(nonce)), self.assertRaises(self.invalid):
                self.verify(encoded, self.expected)

    def test_bad_expected_nonce_cannot_escape_validation(self):
        encoded = self.token(self.expected)
        for expected in (None, 42, b"bytes", "é", "\ud800", ""):
            with self.subTest(expected=ascii(expected)), self.assertRaises(self.invalid):
                self.verify(encoded, expected)

    def test_matching_non_ascii_strings_are_not_generated_login_nonces(self):
        encoded = self.token("é")
        with self.assertRaises(self.invalid):
            self.verify(encoded, "é")

    def test_non_string_claims_are_not_coerced(self):
        for nonce in (12, True, [], {}, None):
            encoded = self.token(nonce)
            with self.subTest(nonce=nonce), self.assertRaises(self.invalid):
                self.verify(encoded, self.expected)

    def test_different_ascii_nonce_rejected(self):
        encoded = self.token("different-" + self.expected)
        with self.assertRaises(self.invalid):
            self.verify(encoded, self.expected)

    def test_nonce_is_case_sensitive(self):
        encoded = self.token("A" * 43)
        with self.assertRaises(self.invalid):
            self.verify(encoded, "a" * 43)

    def test_empty_nonces_cannot_authenticate(self):
        encoded = self.token("")
        with self.assertRaises(self.invalid):
            self.verify(encoded, "")

    def test_wrong_signature_still_rejected(self):
        encoded = self.token(self.expected, key=self.other_key)
        with self.assertRaises(self.invalid):
            self.verify(encoded, self.expected)

    def test_wrong_audience_still_rejected(self):
        encoded = self.token(self.expected, changes={"aud": "another-client"})
        with self.assertRaises(self.invalid):
            self.verify(encoded, self.expected)

    def test_wrong_issuer_still_rejected(self):
        encoded = self.token(self.expected, changes={"iss": "https://different.invalid"})
        with self.assertRaises(self.invalid):
            self.verify(encoded, self.expected)

    def test_expired_signed_token_still_rejected(self):
        encoded = self.token(self.expected, changes={"exp": int(time.time()) - 120})
        with self.assertRaises(self.invalid):
            self.verify(encoded, self.expected)


if __name__ == "__main__":
    unittest.main()
