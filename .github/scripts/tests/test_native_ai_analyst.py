from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[3]
AVATAR = ROOT / "app/src/main/java/ru/omnicio/app/ui/spectrum/SpectrumAnalystAvatar.kt"
CARD = ROOT / "app/src/main/java/ru/omnicio/app/ui/home/HomeAnalystCard.kt"
HOME = ROOT / "app/src/main/java/ru/omnicio/app/ui/home/HomeScreen.kt"
PROFILE_TABS = ROOT / "app/src/main/java/ru/omnicio/app/ui/profile/ProfileSectionTabs.kt"
GRADLE = ROOT / "app/build.gradle.kts"


class NativeAiAnalystTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.avatar = AVATAR.read_text(encoding="utf-8")
        cls.card = CARD.read_text(encoding="utf-8")
        cls.home = HOME.read_text(encoding="utf-8")
        cls.profile_tabs = PROFILE_TABS.read_text(encoding="utf-8")
        cls.gradle = GRADLE.read_text(encoding="utf-8")

    def test_avatar_is_native_and_brand_owned(self):
        self.assertIn("fun SpectrumAnalystAvatar", self.avatar)
        self.assertIn("Canvas(", self.avatar)
        self.assertIn("drawRoundRect", self.avatar)
        self.assertIn("AnalystAvatarMood", self.avatar)
        for forbidden in ("AsyncImage", "rememberAsyncImagePainter", "painterResource", "WebView"):
            self.assertNotIn(forbidden, self.avatar)

    def test_avatar_has_no_unbounded_animation_or_fake_model_state(self):
        self.assertNotIn("rememberInfiniteTransition", self.avatar)
        self.assertNotIn("infiniteRepeatable", self.avatar)
        self.assertIn("mood: AnalystAvatarMood", self.avatar)
        self.assertIn("never pretends that a model has completed work", self.avatar)

    def test_home_card_uses_loaded_portfolio_facts(self):
        self.assertIn("HomeAnalystCard(snapshot, refreshError", self.home)
        self.assertIn("snapshot.warnings", self.card)
        self.assertIn("snapshot.allocations", self.card)
        self.assertIn("refreshError != null", self.card)
        for forbidden in ("Random(", "Math.random", "100/100", "+15%"):
            self.assertNotIn(forbidden, self.card)

    def test_profile_tabs_fit_natural_widths_before_scrolling(self):
        self.assertIn("val measuredWidths", self.profile_tabs)
        self.assertIn("val naturalWidths = measuredWidths.map", self.profile_tabs)
        self.assertIn("val spare =", self.profile_tabs)
        self.assertIn("val widths = naturalWidths.map", self.profile_tabs)
        self.assertIn("selectedCenterPx", self.profile_tabs)
        self.assertIn("if (scroll.maxValue == 0)", self.profile_tabs)
        self.assertNotIn("val width = maxOf(equalWidth, labelWidth", self.profile_tabs)

    def test_new_bytes_have_the_next_version_identity(self):
        code = re.search(r"versionCode\s*=\s*(\d+)", self.gradle)
        name = re.search(r'versionName\s*=\s*"([^"]+)"', self.gradle)
        self.assertIsNotNone(code)
        self.assertIsNotNone(name)
        self.assertGreaterEqual(int(code.group(1)), 28)
        self.assertEqual(name.group(1), "0.7.3")


if __name__ == "__main__":
    unittest.main()
