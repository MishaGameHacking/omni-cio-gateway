"""Preserve installed identity across supported official apksigner report forms."""
from pathlib import Path
import re
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apk_signature_report import (MAX_REPORT_BYTES, SignatureReportError,
                                  read_signature, validate_signature)

PIN = "ab" * 32
OTHER = "cd" * 32
HEADER = ("Verifies\nVerified using v2 scheme (APK Signature Scheme v2): true\n"
          "Verified using v3.1 scheme (APK Signature Scheme v3.1): false\n"
          "Number of signers: 1\n")
SUFFIX = " certificate SHA-256 digest: "


def report(*, digest=PIN, label="Signer #1"):
    return HEADER + label + SUFFIX + digest + "\n"


def ranged(*, digest=PIN, lower=37, upper=2147483647):
    return report(digest=digest, label=f"Signer (minSdkVersion={lower}, maxSdkVersion={upper})").replace(
        "v3.1): false", "v3.1): true")


class SignatureReportTests(unittest.TestCase):
    def test_numbered_official_report(self):
        result = validate_signature(report(), PIN)
        self.assertEqual(result["certificate_sha256"], PIN)
        self.assertEqual(result["format"], "numbered")
        self.assertTrue(result["signature_v2"])

    def test_sdk_range_official_report_preserves_pin(self):
        text = ranged()
        self.assertEqual(re.findall(r"Signer #\d+ certificate SHA-256 digest: ([0-9a-f]+)", text), [])
        self.assertEqual(validate_signature(text, PIN)["format"], "sdk-range")

    def test_each_sdk_range_must_have_the_same_pin(self):
        text = ranged(lower=33) + "Signer (minSdkVersion=24, maxSdkVersion=32)" + SUFFIX + PIN + "\n"
        self.assertEqual(validate_signature(text, PIN)["records"], 2)
        changed = text.replace("maxSdkVersion=32)" + SUFFIX + PIN, "maxSdkVersion=32)" + SUFFIX + OTHER)
        with self.assertRaisesRegex(SignatureReportError, "Signing certificate changed"):
            validate_signature(changed, PIN)

    def test_actual_changed_certificate_is_not_a_format_error(self):
        text = report(digest=OTHER)
        with self.assertRaisesRegex(SignatureReportError, "observed_sha256=" + OTHER):
            validate_signature(text, PIN)

    def test_uppercase_hex_and_crlf_are_semantically_unchanged(self):
        self.assertEqual(validate_signature(report(digest=PIN.upper()).replace("\n", "\r\n"), PIN)["certificate_sha256"], PIN)

    def test_source_stamp_is_not_application_identity(self):
        text = report() + "Source Stamp Signer" + SUFFIX + OTHER + "\n"
        self.assertEqual(validate_signature(text, PIN)["records"], 1)
        only_stamp = text.replace("Signer #1" + SUFFIX + PIN + "\n", "")
        with self.assertRaises(SignatureReportError):
            validate_signature(only_stamp, OTHER)

    def test_public_key_hash_is_not_certificate(self):
        text = report().replace("certificate SHA-256", "public key SHA-256")
        with self.assertRaises(SignatureReportError):
            validate_signature(text, PIN)

    def test_multiple_signers_are_rejected(self):
        text = report().replace("Number of signers: 1", "Number of signers: 2")
        with self.assertRaises(SignatureReportError):
            validate_signature(text, PIN)

    def test_hidden_extra_signer_and_duplicate_are_rejected(self):
        for label in ("Signer #1", "Signer #2", "Signer #01", " Signer #2"):
            text = report() + label + SUFFIX + PIN + "\n"
            with self.subTest(label=label), self.assertRaises(SignatureReportError):
                validate_signature(text, PIN)

    def test_summary_must_be_unique_and_successful(self):
        for line in ("Verifies", "Number of signers: 1", "Number of signers: 2",
                     "Verified using v2 scheme (APK Signature Scheme v2): false", "DOES NOT VERIFY", "ERROR: invalid"):
            text = report() + line + "\n"
            with self.subTest(line=line), self.assertRaises(SignatureReportError):
                validate_signature(text, PIN)

    def test_required_lines_cannot_be_missing(self):
        for line in ("Verifies\n", "Number of signers: 1\n", "Verified using v2 scheme (APK Signature Scheme v2): true\n"):
            text = report().replace(line, "")
            with self.subTest(line=line), self.assertRaises(SignatureReportError):
                validate_signature(text, PIN)

    def test_malformed_digest_is_not_truncated_to_a_valid_prefix(self):
        for digest in (PIN + "ff", PIN + " extra", PIN[:-1], "g" * 64, "", "é" * 64):
            text = report(digest=digest)
            with self.subTest(digest=digest), self.assertRaises(SignatureReportError):
                validate_signature(text, PIN)

    def test_invalid_pin_is_not_normalized(self):
        for pin in (None, PIN.upper(), PIN + "\n", "", "a" * 63):
            text = report()
            with self.subTest(pin=pin), self.assertRaises(SignatureReportError):
                validate_signature(text, pin)

    def test_range_requires_v31_verification(self):
        text = ranged().replace("v3.1): true", "v3.1): false")
        with self.assertRaises(SignatureReportError):
            validate_signature(text, PIN)

    def test_required_platform_must_be_covered(self):
        text = ranged(lower=24, upper=36)
        with self.assertRaises(SignatureReportError):
            validate_signature(text, PIN)

    def test_invalid_or_preview_only_ranges_are_rejected(self):
        labels = ("Signer (minSdkVersion=37, maxSdkVersion=36)",
                  "Signer (minSdkVersion=0, maxSdkVersion=37)",
                  "Signer (minSdkVersion=37, maxSdkVersion=2147483648)",
                  "Signer (minSdkVersion=37 (dev release=true), maxSdkVersion=2147483647)",
                  "Signer (minSdkVersion=٣٧, maxSdkVersion=2147483647)")
        for label in labels:
            text = report(label=label).replace("v3.1): false", "v3.1): true")
            with self.subTest(label=label), self.assertRaises(SignatureReportError):
                validate_signature(text, PIN)

    def test_overlapping_ranges_are_rejected(self):
        text = ranged() + "Signer (minSdkVersion=24, maxSdkVersion=37)" + SUFFIX + PIN + "\n"
        with self.assertRaises(SignatureReportError):
            validate_signature(text, PIN)

    def test_mixed_formats_are_rejected(self):
        text = ranged() + "Signer #1" + SUFFIX + PIN + "\n"
        with self.assertRaises(SignatureReportError):
            validate_signature(text, PIN)

    def test_invalid_minimum_sdk_is_rejected(self):
        for sdk in (True, 0, "37", -1, 2147483648):
            text = report()
            with self.subTest(sdk=sdk), self.assertRaises(SignatureReportError):
                validate_signature(text, PIN, min_sdk=sdk)

    def test_bounded_report_and_encoding(self):
        for text in (None, "", "a" * (MAX_REPORT_BYTES + 1), "é" * MAX_REPORT_BYTES, report() + "\x00", "\ud800"):
            with self.subTest(size=len(text) if text is not None else None), self.assertRaises(SignatureReportError):
                validate_signature(text, PIN)

    def test_file_read_is_bounded_and_utf8_bom_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "signature.txt"
            path.write_bytes(b"\xef\xbb\xbf" + report().encode("utf-8"))
            self.assertEqual(read_signature(path), report())
            path.write_bytes(b"a" * (MAX_REPORT_BYTES + 1))
            with self.assertRaises(SignatureReportError):
                read_signature(path)
            path.write_bytes(b"\xff")
            with self.assertRaises(SignatureReportError):
                read_signature(path)


if __name__ == "__main__":
    unittest.main()
