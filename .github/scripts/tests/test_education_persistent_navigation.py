"""Production navigation stays outside the virtualized education catalog.

The existing device test still opens a lesson, checks its actual body, changes
categories, returns through the real callback, and repeats with font scale 2.0.
These source guards do not substitute for that native UI verification.
"""
from pathlib import Path
import unittest


class EducationNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[3]
        cls.source = (root / 'app/src/main/java/ru/omnicio/app/ui/education/EducationScreen.kt').read_text(encoding='utf-8')

    def test_back_action_is_outside_catalog_and_calls_real_navigation(self):
        fixed, catalog = self.source.split('key(category)', 1)
        self.assertIn('text = "Вернуться на главную"', fixed)
        self.assertIn('onClick = onBack', fixed)
        self.assertIn('.testTag("education-back")', fixed)
        self.assertNotIn('item(key = "back-home")', catalog)
        self.assertEqual(self.source.count('text = "Вернуться на главную"'), 1)

    def test_descriptive_header_scrolls_instead_of_consuming_large_font_viewport(self):
        catalog = self.source.split('LazyColumn(', 1)[1]
        self.assertIn('item(key = "education-header")', catalog)
        self.assertIn('SpectrumPageHeader(', catalog)
        self.assertIn('items(lessons, key = EducationLesson::id)', catalog)

    def test_fixed_controls_are_isolated_from_scrolling_content(self):
        fixed, catalog = self.source.split('key(category)', 1)
        self.assertIn('.zIndex(1f).clipToBounds()', fixed)
        self.assertIn('.clipToBounds().testTag("education-content")', catalog)
        self.assertIn('BackHandler(onBack = onBack)', self.source)


if __name__ == '__main__':
    unittest.main()
