from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1] / "build_release_manifest.py"
SPEC = importlib.util.spec_from_file_location("build_release_manifest", MODULE)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


def report() -> dict:
    return {
        "version_code": 23,
        "version_name": "0.6.0-preview",
        "package": "ru.omnicio.app.debug",
        "min_sdk": 33,
        "sha256": "a" * 64,
        "certificate_sha256": "b" * 64,
        "bytes": 4_000_000,
        "device_install_test": "passed_on_emulators_not_a_physical_phone",
        "signature_v2": True,
    }


class ReleaseManifestTests(unittest.TestCase):
    def test_builds_mandatory_first_party_manifest(self):
        result = module.build_manifest(
            report(),
            published_at=datetime(2026, 10, 13, tzinfo=timezone.utc),
            notes="Updater bootstrap",
        )
        self.assertEqual(result["minimum_supported"], 23)
        self.assertEqual(result["version_code"], 23)
        self.assertEqual(
            result["url"],
            "https://176.98.178.81.sslip.io/releases/23/" + "a" * 64 + ".apk",
        )
        self.assertEqual(result["published_at"], "2026-10-13T00:00:00Z")

    def test_rejects_unverified_installation(self):
        value = report()
        value["device_install_test"] = "not_run"
        published_at = datetime.now(timezone.utc)
        with self.assertRaisesRegex(module.ManifestError, "installation_not_verified"):
            module.build_manifest(value, published_at=published_at, notes="x")

    def test_rejects_package_or_digest_change(self):
        for key, value in (("package", "other"), ("sha256", "xyz"), ("certificate_sha256", "0")):
            candidate = report()
            candidate[key] = value
            published_at = datetime.now(timezone.utc)
            with self.subTest(key=key), self.assertRaises(module.ManifestError):
                module.build_manifest(candidate, published_at=published_at, notes="x")

    def test_requires_timezone(self):
        candidate, published_at = report(), datetime(2026, 1, 1)
        with self.assertRaisesRegex(module.ManifestError, "published_at_timezone_required"):
            module.build_manifest(candidate, published_at=published_at, notes="x")


if __name__ == "__main__":
    unittest.main()
