"""A synthetic renderer must use production window/inset policy, not a different screen."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]


class SpectrumWindowParityTests(unittest.TestCase):
    def test_profile_fixture_matches_production_edge_to_edge_before_content(self):
        for source_set, name in (("main", "MainActivity"), ("debug", "ProfileUiProbeActivity")):
            with self.subTest(activity=name):
                source = (ROOT / f"app/src/{source_set}/java/ru/omnicio/app/{name}.kt").read_text(encoding="utf-8")
                self.assertIn("import androidx.activity.enableEdgeToEdge", source)
                start = source.index("override fun onCreate(")
                activate = source.index("enableEdgeToEdge()", start)
                content = source.index("setContent {", start)
                self.assertLess(activate, content)

    def test_profile_fixture_remains_debug_only_and_labeled(self):
        fixture = ROOT / "app/src/debug/java/ru/omnicio/app/ProfileUiProbeActivity.kt"
        source = fixture.read_text(encoding="utf-8")
        self.assertIn("probe-edge-to-edge:true", source)
        self.assertIn("synthetic-ui-test", source)
        self.assertFalse((ROOT / "app/src/main/java/ru/omnicio/app/ProfileUiProbeActivity.kt").exists())
        self.assertFalse((ROOT / "app/src/preview/java/ru/omnicio/app/ProfileUiProbeActivity.kt").exists())


if __name__ == "__main__":
    unittest.main()
