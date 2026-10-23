"""Guard compact dashboard wiring; emulator captures remain the rendering gate."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[3]
HOME = ROOT / "app/src/main/java/ru/omnicio/app/ui/home"
PROFILE = ROOT / "app/src/main/java/ru/omnicio/app/ui/profile/ProfileSectionTabs.kt"


class CompactHomeTests(unittest.TestCase):
    def test_capital_and_attention_precede_shortcuts_with_persistent_dashboard_order(self):
        source = (HOME / "HomeScreen.kt").read_text(encoding="utf-8")
        order = re.findall(r'item\(key = "([\w-]+)"\)', source)
        self.assertEqual(order[:2], ["brand-header", "portfolio-hero"])
        self.assertLess(order.index("attention"), order.index("capabilities"))
        self.assertLess(order.index("attention"), order.index("release-introduction"))
        for wiring in ('normalizedDashboardOrder(personal.dashboardOrder)',
                       'items(order, key = { "dashboard:$it" })', 'saveDashboardOrder', 'undoOrder'):
            self.assertIn(wiring, source)
        self.assertNotIn("heightIn(max = 150.dp)", source)
        self.assertNotIn("SpectrumMetricPill", source)
        self.assertIn("onClick = onCurrency", source)

    def test_workspace_shortcuts_keep_real_navigation_callbacks(self):
        source = (HOME / "HomeQuickActions.kt").read_text(encoding="utf-8")
        for callback in ("onAssets", "onPayments"):
            self.assertIn(callback, source)
        self.assertNotIn("SpectrumLiveFeatureIcon(", source)
        self.assertIn("fontScale >= 1.4f", source)
        self.assertIn("widthDp < 260f", source)
        self.assertIn("else 2", source)

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

