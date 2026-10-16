from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
ARTWORK = ROOT / "app/src/main/java/ru/omnicio/app/ui/spectrum/SpectrumArtwork.kt"
HOME = ROOT / "app/src/main/java/ru/omnicio/app/ui/home/HomeScreen.kt"


class SpectrumAssistantArtworkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artwork = ARTWORK.read_text(encoding="utf-8")
        cls.home = HOME.read_text(encoding="utf-8")

    def test_robot_is_native_compose_artwork(self):
        self.assertIn("fun SpectrumRobot", self.artwork)
        self.assertIn("Canvas(", self.artwork)
        self.assertIn("Brush.linearGradient", self.artwork)
        self.assertIn("Path().apply", self.artwork)
        self.assertNotIn("ImageBitmap", self.artwork)
        self.assertNotIn("painterResource", self.artwork)
        self.assertNotIn("http://", self.artwork)
        self.assertNotIn("https://", self.artwork)

    def test_home_uses_character_in_real_assistant_card(self):
        self.assertIn('item(key = "assistant")', self.home)
        self.assertGreaterEqual(self.home.count("SpectrumRobot("), 2)
        self.assertIn('testTag("spectrum-ai-robot")', self.home)
        self.assertNotIn(
            "SpectrumIcon(SpectrumSymbol.Analyst, Modifier.size(58.dp)",
            self.home,
        )

    def test_assistant_layout_survives_narrow_and_large_font_windows(self):
        self.assertIn("BoxWithConstraints", self.home)
        self.assertIn("LocalDensity.current.fontScale", self.home)
        self.assertIn("maxWidth < 310.dp", self.home)
        self.assertIn("fontScale > 1.35f", self.home)
        self.assertIn("Modifier.fillMaxWidth()", self.home)

    def test_financial_claims_remain_data_bound(self):
        self.assertIn("snapshot.warnings.first()", self.home)
        self.assertIn("snapshot.allocations.maxByOrNull", self.home)
        self.assertIn("Вывод по фактам портфеля", self.home)
        self.assertNotIn("+12%", self.home)
        self.assertNotIn("28/100", self.home)


if __name__ == "__main__":
    unittest.main()
