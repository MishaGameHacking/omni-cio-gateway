"""Android 16-only manifest contract and modern navigation/security defaults."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]


class Android16ManifestTests(unittest.TestCase):
    def test_manifest_uses_strict_intent_matching_and_predictive_back(self):
        manifest = (ROOT / "app/src/main/AndroidManifest.xml").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            'android:intentMatchingFlags="enforceIntentFilter"',
            manifest,
        )
        self.assertEqual(
            manifest.count('android:enableOnBackInvokedCallback="true"'),
            2,
        )
        self.assertNotIn("screenOrientation", manifest)
        self.assertNotIn("resizeableActivity", manifest)
        self.assertNotIn("maxAspectRatio", manifest)
        self.assertNotIn("minAspectRatio", manifest)

    def test_launcher_allows_only_the_deliberate_actionless_entry(self):
        manifest = (ROOT / "app/src/main/AndroidManifest.xml").read_text(
            encoding="utf-8"
        )
        bootstrap_start = manifest.index('android:name=".BootstrapActivity"')
        bootstrap_end = manifest.index("</activity>", bootstrap_start)
        bootstrap = manifest[bootstrap_start:bootstrap_end]
        self.assertIn(
            'android:intentMatchingFlags="enforceIntentFilter|allowNullAction"',
            bootstrap,
        )
        self.assertEqual(manifest.count("allowNullAction"), 1)
        self.assertNotIn("allowNullAction", manifest[bootstrap_end:])

    def test_only_bootstrap_is_exported_and_deep_link_is_exact(self):
        manifest = (ROOT / "app/src/main/AndroidManifest.xml").read_text(
            encoding="utf-8"
        )
        self.assertEqual(manifest.count('android:exported="true"'), 1)
        self.assertIn('android:name=".BootstrapActivity"', manifest)
        self.assertIn(
            '<data android:host="auth" android:scheme="analystai" />',
            manifest,
        )
        for component in (
            ".MainActivity",
            ".data.updates.InstallResultReceiver",
            ".data.updates.AppReplacedReceiver",
        ):
            self.assertIn(component, manifest)


if __name__ == "__main__":
    unittest.main()
