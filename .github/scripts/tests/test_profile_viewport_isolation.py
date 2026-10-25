"""Keep scrolling settings content inside its viewport beside fixed navigation.

The device test remains authoritative: it must reveal and activate every full
48dp-or-larger tab after dialogs and with font scale 2.0. These source checks
only prevent accidentally removing the viewport isolation from production.
"""
from pathlib import Path
import re
import unittest


class ProfileViewportIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[3]
        cls.source = (root / 'app/src/main/java/ru/omnicio/app/ui/profile/ProfileScreen.kt').read_text(encoding='utf-8')
        cls.tabs = (root / 'app/src/main/java/ru/omnicio/app/ui/profile/ProfileSectionTabs.kt').read_text(encoding='utf-8')
        cls.bar = (root / 'app/src/main/java/ru/omnicio/app/ui/AnalystBottomBar.kt').read_text(encoding='utf-8')

    def test_fixed_navigation_has_its_own_clipped_foreground_layer(self):
        self.assertIn('bottomBar = { AnalystBottomBar(AnalystTab.Profile', self.source)
        self.assertNotIn('ProfileSectionTabs(', self.source)
        self.assertRegex(self.bar, re.compile(
            r'Surface\(modifier\.fillMaxWidth\(\)\.zIndex\(1f\)\.clipToBounds\(\)',
        ))

    def test_scroll_body_is_clipped_before_accessibility_tag(self):
        body = self.source.split('LazyColumn(', 1)[1].split('contentPadding =', 1)[0]
        self.assertIn('.clipToBounds()', body)
        self.assertLess(body.index('.clipToBounds()'), body.index('.testTag("profile-content")'))

    def test_each_profile_label_gets_its_natural_width(self):
        self.assertIn('val measuredWidths = measured.map', self.tabs)
        self.assertIn('val naturalWidths = measuredWidths.map', self.tabs)
        self.assertIn('val widths = naturalWidths.map', self.tabs)
        self.assertNotIn('measured.maxOf { it.width }', self.tabs)

    def test_selected_tab_is_centered_only_when_the_row_overflows(self):
        self.assertIn('if (scroll.maxValue == 0)', self.tabs)
        self.assertIn('selectedCenterPx', self.tabs)
        self.assertIn('target.coerceIn(0, scroll.maxValue)', self.tabs)


if __name__ == '__main__':
    unittest.main()
