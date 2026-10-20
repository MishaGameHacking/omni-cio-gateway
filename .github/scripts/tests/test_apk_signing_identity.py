"""Strict machine-result boundary; actual SDK cryptographic smoke runs in CI."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from apk_signing_identity import SigningIdentityError, validate_identity

PIN = "ab" * 32
OTHER = "cd" * 32
DIGEST = "ef" * 32


def valid(**changes):
    result = {"schema": 1, "tool": "android-apksig", "android_api": 37,
              "apk_sha256": DIGEST, "bytes": 100, "certificate_sha256": PIN,
              "signers": 1, "signature_v2": True}
    result.update(changes)
    return json.dumps(result).encode()


class SigningIdentityTests(unittest.TestCase):
    def test_exact_byte_and_certificate_identity(self):
        result = validate_identity(valid(), PIN, DIGEST, 100)
        self.assertEqual(result["certificate_sha256"], PIN)
        self.assertEqual(result["apk_sha256"], DIGEST)

    def test_all_security_fields_are_required(self):
        base = json.loads(valid())
        for key in base:
            report = dict(base)
            del report[key]
            raw = json.dumps(report).encode()
            with self.subTest(key=key), self.assertRaises(SigningIdentityError):
                validate_identity(raw, PIN, DIGEST, 100)

    def test_wrong_key_and_artifact_are_not_accepted(self):
        for changes in ({"certificate_sha256": OTHER}, {"apk_sha256": OTHER},
                        {"bytes": 101}, {"signers": 2}, {"android_api": 36},
                        {"tool": "console-output"}, {"signature_v2": False}):
            raw = valid(**changes)
            with self.subTest(changes=changes), self.assertRaises(SigningIdentityError):
                validate_identity(raw, PIN, DIGEST, 100)

    def test_no_boolean_or_string_coercion(self):
        for key in ("schema", "android_api", "signers", "bytes"):
            for value in (True, False, "1", 1.0, None):
                raw = valid(**{key: value})
                with self.subTest(key=key, value=value), self.assertRaises(SigningIdentityError):
                    validate_identity(raw, PIN, DIGEST, 100)
        for value in (1, "true", "false", None):
            raw = valid(signature_v2=value)
            with self.subTest(value=value), self.assertRaises(SigningIdentityError):
                validate_identity(raw, PIN, DIGEST, 100)

    def test_duplicate_fields_cannot_hide_a_different_certificate(self):
        for tail in (b',"signers":1}', b',"certificate_sha256":"' + PIN.encode() + b'"}'):
            raw = valid(certificate_sha256=OTHER)[:-1] + tail
            with self.subTest(tail=tail), self.assertRaises(SigningIdentityError):
                validate_identity(raw, PIN, DIGEST, 100)

    def test_malformed_and_nonfinite_documents(self):
        for raw in (b"[]", b"null", b"true", b"{} trailing", b"\xff", b'{"schema":NaN}',
                    b"[" * 2000 + b"]" * 2000, valid() + b"{}", b"", b"a" * 4097):
            with self.subTest(size=len(raw)), self.assertRaises(SigningIdentityError):
                validate_identity(raw, PIN, DIGEST, 100)

    def test_unexpected_field_is_not_an_unsigned_extension(self):
        raw = valid(source_stamp=PIN)
        with self.assertRaises(SigningIdentityError):
            validate_identity(raw, PIN, DIGEST, 100)

    def test_pin_and_digest_are_not_normalized(self):
        for value in (None, PIN.upper(), PIN + "\n", "a" * 63):
            raw = valid()
            with self.subTest(value=value), self.assertRaises(SigningIdentityError):
                validate_identity(raw, value, DIGEST, 100)
            with self.subTest(digest=value), self.assertRaises(SigningIdentityError):
                validate_identity(raw, PIN, value, 100)

    def test_size_limits_are_explicit(self):
        for size in (0, -1, True, "100", 268435457):
            raw = valid()
            with self.subTest(size=size), self.assertRaises(SigningIdentityError):
                validate_identity(raw, PIN, DIGEST, size)


class OfficialSigningSmokeTests(unittest.TestCase):
    """Use temporary synthetic APK/keys, never the user's installed signing key."""

    def test_actual_sdk_verifies_bytes_and_rejects_wrong_key_and_tampering(self):
        sdk = os.environ.get("ANDROID_SDK_ROOT")
        home = os.environ.get("JAVA_HOME")
        if not sdk or not home:
            if os.environ.get("GITHUB_ACTIONS") == "true":
                self.fail("Android CI must supply the actual SDK and JDK")
            self.skipTest("Actual Android SDK/JDK are required for cryptographic smoke")
        suffix = ".exe" if os.name == "nt" else ""
        java = Path(home) / ("bin/java" + suffix)
        keytool = Path(home) / ("bin/keytool" + suffix)
        tools = Path(sdk) / "build-tools/37.0.0"
        jar = tools / "lib/apksigner.jar"
        aapt = tools / ("aapt2" + suffix)
        android = Path(sdk) / "platforms/android-37.0/android.jar"
        for tool in (java, keytool, jar, aapt, android):
            self.assertTrue(tool.is_file(), f"Missing official smoke tool: {tool.name}")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "AndroidManifest.xml"
            manifest.write_text('<manifest xmlns:android="http://schemas.android.com/apk/res/android" '
                                'package="invalid.example.signingfixture" android:versionCode="1" '
                                'android:versionName="1"><uses-sdk android:minSdkVersion="37" '
                                'android:targetSdkVersion="37"/><application android:hasCode="false"/></manifest>')
            unsigned = root / "unsigned.apk"
            signed = root / "signed.apk"
            key = root / "synthetic.jks"
            cert = root / "certificate.der"
            self._run([aapt, "link", "-o", unsigned, "--manifest", manifest, "-I", android])
            self._run([keytool, "-genkeypair", "-keystore", key, "-storepass", "fixture-only",
                       "-keypass", "fixture-only", "-alias", "fixture", "-keyalg", "RSA",
                       "-keysize", "2048", "-validity", "2", "-dname", "CN=Temporary test only"])
            self._run([keytool, "-exportcert", "-keystore", key, "-storepass", "fixture-only",
                       "-alias", "fixture", "-file", cert])
            pin = hashlib.sha256(cert.read_bytes()).hexdigest()
            self._run([java, "-jar", jar, "sign", "--ks", key, "--ks-key-alias", "fixture",
                       "--ks-pass", "pass:fixture-only", "--key-pass", "pass:fixture-only",
                       "--v2-signing-enabled", "true", "--out", signed, unsigned])
            command = [java, "--class-path", jar, SCRIPTS / "VerifyApkSigning.java", signed]
            good = self._run(command + [pin])
            validate_identity(good.stdout, pin, hashlib.sha256(signed.read_bytes()).hexdigest(), signed.stat().st_size)
            for artifact, expected in ((signed, OTHER), (unsigned, pin)):
                invocation = command[:-1] + [artifact, expected]
                rejected = self._run(invocation, check=False)
                self.assertNotEqual(rejected.returncode, 0)
                self.assertEqual(rejected.stdout, b"")
            tampered = root / "tampered.apk"
            shutil.copyfile(signed, tampered)
            # Change a byte inside the signed ZIP content without rewriting its signature.
            content = bytearray(tampered.read_bytes())
            content[50] ^= 1
            tampered.write_bytes(content)
            rejected = self._run(command[:-1] + [tampered, pin], check=False)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertEqual(rejected.stdout, b"")

    @staticmethod
    def _run(arguments, check=True):
        completed = subprocess.run([str(value) for value in arguments], check=False,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, timeout=60)
        if check and completed.returncode:
            raise AssertionError("Official signing smoke failed: " + completed.stderr.decode("utf-8", errors="replace")[:2000])
        return completed


if __name__ == "__main__":
    unittest.main()
