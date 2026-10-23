"""Verify signed tokens using the actual validator without importing a live app."""
import json
import secrets
import time
import unittest

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from backend.telegram_oidc import TelegramKeyUnavailable, TelegramTokenError, verify_id_token


class TelegramNonceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.public_key = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(cls.private_key.public_key()))
        cls.public_key.update(kid="test-key", alg="RS256", use="sig")
        cls.other_public_key = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(cls.other_key.public_key()))
        cls.other_public_key.update(kid="rotated-key", alg="RS256", use="sig")

    def setUp(self):
        self.invalid = TelegramTokenError
        self.verify = lambda token, nonce: verify_id_token(
            token, nonce, client_id="test-client", issuer="https://example.invalid",
            jwks={"keys": [self.public_key]})
        self.expected = secrets.token_urlsafe(32)

    def token(self, nonce, *, changes=None, key=None, headers=None, algorithm="RS256"):
        now = int(time.time())
        claims = {"iss": "https://example.invalid", "aud": "test-client", "sub": "test-owner",
                  "exp": now + 300, "iat": now, "nonce": nonce}
        claims.update(changes or {})
        signing_key = self.private_key if key is None else key
        signing_headers = {"kid": "test-key"} if headers is None else headers
        return jwt.encode(claims, signing_key, algorithm=algorithm, headers=signing_headers)

    def verify_with_keys(self, encoded, keys):
        return verify_id_token(encoded, self.expected, client_id="test-client",
                               issuer="https://example.invalid", jwks={"keys": keys})

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

    def test_key_rotation_accepts_only_after_new_trusted_key_is_supplied(self):
        encoded = self.token(self.expected, key=self.other_key, headers={"kid": "rotated-key"})
        with self.assertRaises(self.invalid):
            self.verify(encoded, self.expected)
        claims = self.verify_with_keys(encoded, [self.public_key, self.other_public_key])
        self.assertEqual(claims["sub"], "test-owner")

    def test_verified_kid_must_name_the_key_that_verified_the_signature(self):
        encoded = self.token(self.expected, headers={"kid": "rotated-key"})
        for keys in ([self.public_key, self.other_public_key], [self.other_public_key, self.public_key]):
            with self.subTest(first_kid=keys[0]["kid"]), self.assertRaises(self.invalid):
                self.verify_with_keys(encoded, keys)

    def test_same_key_under_another_unique_kid_remains_usable(self):
        alias = {**self.public_key, "kid": "key-alias"}
        encoded = self.token(self.expected, headers={"kid": "key-alias"})
        claims = self.verify_with_keys(encoded, [self.public_key, alias])
        self.assertEqual(claims["sub"], "test-owner")

    def test_duplicate_kid_is_rejected_even_when_one_key_cannot_be_parsed(self):
        encoded = self.token(self.expected)
        duplicates = [self.public_key, {**self.other_public_key, "kid": "test-key"},
                      {"kid": "test-key", "alg": "RS256", "kty": "RSA"}]
        for duplicate in duplicates:
            keys = [duplicate, self.public_key]
            with self.subTest(duplicate=duplicate), self.assertRaises(TelegramKeyUnavailable):
                self.verify_with_keys(encoded, keys)

    def test_malformed_unrelated_key_does_not_hide_a_valid_trusted_key(self):
        malformed = {"kid": "unrelated-key", "alg": "RS256", "kty": "RSA"}
        encoded = self.token(self.expected)
        claims = self.verify_with_keys(encoded, [malformed, self.public_key])
        self.assertEqual(claims["sub"], "test-owner")

    def test_signed_headers_cannot_select_urls_or_critical_extensions(self):
        for extension in ({"crit": []}, {"crit": ["unknown"]},
                          {"jku": "https://untrusted.invalid/keys"},
                          {"x5u": "https://untrusted.invalid/certificate"}):
            encoded = self.token(self.expected, headers={"kid": "test-key", **extension})
            with self.subTest(extension=extension), self.assertRaises(self.invalid):
                self.verify(encoded, self.expected)

    def test_verified_kid_is_required_bounded_and_ascii(self):
        for headers in ({}, {"kid": ""}, {"kid": "é"}, {"kid": "k" * 257}):
            encoded = self.token(self.expected, headers=headers)
            with self.subTest(headers=headers), self.assertRaises(self.invalid):
                self.verify(encoded, self.expected)

    def test_only_rs256_is_accepted_regardless_of_token_header(self):
        for algorithm, key in (("HS256", "synthetic-test-key-" * 4), ("none", ""),
                               ("PS256", self.private_key)):
            encoded = self.token(self.expected, key=key, algorithm=algorithm)
            with self.subTest(algorithm=algorithm), self.assertRaises(self.invalid):
                self.verify(encoded, self.expected)

    def test_key_metadata_must_allow_rsa_signature_verification(self):
        encoded = self.token(self.expected)
        for changes in ({"alg": "HS256"}, {"kty": "EC"}, {"use": "enc"},
                        {"key_ops": []}, {"key_ops": ["sign"]}, {"key_ops": "verify"}):
            keys = [{**self.public_key, **changes}]
            with self.subTest(changes=changes), self.assertRaises(TelegramKeyUnavailable):
                self.verify_with_keys(encoded, keys)

    def test_weak_or_private_rsa_keys_cannot_be_used_to_authenticate(self):
        weak_key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
        encoded = self.token(self.expected)
        for key in (weak_key.public_key(), self.private_key):
            jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key))
            jwk.update(kid="test-key", alg="RS256", use="sig")
            keys = [jwk]
            with self.subTest(key_type=type(key).__name__), self.assertRaises(TelegramKeyUnavailable):
                self.verify_with_keys(encoded, keys)

    def test_jwks_list_size_is_bounded_before_any_key_is_used(self):
        encoded = self.token(self.expected)
        for keys in (None, {}, (), [], [self.public_key] + [None] * 64):
            with self.subTest(keys=keys), self.assertRaises(TelegramKeyUnavailable):
                self.verify_with_keys(encoded, keys)
        claims = self.verify_with_keys(encoded, [self.public_key] + [None] * 63)
        self.assertEqual(claims["sub"], "test-owner")

    def test_verified_token_times_must_be_integers_in_increasing_order(self):
        now = int(time.time())
        for changes in ({"iat": str(now)}, {"exp": str(now + 300)}, {"iat": True},
                        {"exp": True}, {"iat": now, "exp": now}):
            encoded = self.token(self.expected, changes=changes)
            with self.subTest(changes=changes), self.assertRaises(self.invalid):
                self.verify(encoded, self.expected)


if __name__ == "__main__":
    unittest.main()
