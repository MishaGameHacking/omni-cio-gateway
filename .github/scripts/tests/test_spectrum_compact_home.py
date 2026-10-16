"""Guard compact dashboard wiring; emulator captures remain the rendering gate."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[3]
HOME = ROOT / "app/src/main/java/ru/omnicio/app/ui/home"
PROFILE = ROOT / "app/src/main/java/ru/omnicio/app/ui/profile/ProfileSectionTabs.kt"


class CompactHomeTests(unittest.TestCase):
    def test_quick_actions_precede_the_analyst_without_another_large_heading(self):
        source = (HOME / "HomeScreen.kt").read_text(encoding="utf-8")
        order = re.findall(r'item\(key = "([\w-]+)"\)', source)
        self.assertEqual(order[:4], ["brand-header", "portfolio-hero", "capabilities", "assistant"])
        self.assertNotIn("heightIn(max = 150.dp)", source)
        self.assertNotIn("SpectrumMetricPill", source)
        self.assertIn("onClick = onCurrencyClick", source)

    def test_four_original_actions_keep_real_navigation_callbacks(self):
        source = (HOME / "HomeQuickActions.kt").read_text(encoding="utf-8")
        for callback in ("onPortfolio", "onRecommendations", "onRisk", "onMessages"):
            self.assertIn(callback + ")", source)
        for live_feature in ("Charts", "Recommendations", "RiskControl", "Notifications"):
            self.assertIn("SpectrumLiveFeature." + live_feature, source)
        self.assertIn("SpectrumLiveFeatureIcon(", source)
        self.assertIn("fontScale >= 1.4f", source)
        self.assertIn("widthDp < 260f", source)
        self.assertIn("Modifier.size(56.dp)", source)

    def test_profile_semantics_preserve_full_cell_state_and_activation(self):
        source = PROFILE.read_text(encoding="utf-8")
        self.assertIn("coerceAtLeast(52.dp)", source)
        self.assertIn(".clearAndSetSemantics", source)
        self.assertIn("contentDescription = label", source)
        self.assertIn("this.selected = chosen", source)
        self.assertIn("role = Role.Tab", source)
        self.assertIn('onClick(label = "Открыть $label")', source)
        self.assertNotIn('testTag("profile-tab-label-', source)


if __name__ == "__main__":
    unittest.main()
