"""Keep scrolling profile content below the fixed accessible navigation rail.

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

    def test_fixed_rail_has_its_own_clipped_foreground_layer(self):
        self.assertRegex(self.source, re.compile(
            r'Column\(Modifier\.fillMaxWidth\(\)\.zIndex\(1f\)\.clipToBounds\(\).*?ProfileSectionTabs\(section\)',
            re.DOTALL,
        ))

    def test_scroll_body_is_clipped_before_accessibility_tag(self):
        body = self.source.split('LazyColumn(', 1)[1].split('state = contentState', 1)[0]
        self.assertIn('.clipToBounds()', body)
        self.assertLess(body.index('.clipToBounds()'), body.index('.testTag("profile-content")'))


if __name__ == '__main__':
    unittest.main()
