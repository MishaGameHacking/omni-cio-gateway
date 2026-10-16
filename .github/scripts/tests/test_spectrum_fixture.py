"""Screenshots must render production presenters with conspicuous debug-only data."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]


class SpectrumFixtureTests(unittest.TestCase):
    def test_fixture_is_debug_only_and_visibly_labeled(self):
        relative = Path('java/ru/omnicio/app/SpectrumDashboardProbe.kt')
        fixture = (ROOT / 'app/src/debug' / relative).read_text(encoding='utf-8')
        for variant in ('main', 'release', 'preview'):
            self.assertFalse((ROOT / 'app/src' / variant / relative).exists())
        self.assertIn('ВИЗУАЛЬНЫЙ ТЕСТ · НЕ РЕАЛЬНЫЕ ДАННЫЕ', fixture)
        self.assertIn('HomeScreen(', fixture)
        self.assertIn('PortfolioScreen(', fixture)
        self.assertIn('accessToken = ""', fixture)
        self.assertNotIn('WebView', fixture)

    def test_probe_keeps_an_independent_completed_frame_marker(self):
        activity = (
            ROOT / 'app/src/debug/java/ru/omnicio/app/ProfileUiProbeActivity.kt'
        ).read_text(encoding='utf-8')
        self.assertIn('val readinessMarker =', activity)
        self.assertIn('.clearAndSetSemantics { contentDescription = readinessMarker }', activity)
        self.assertIn('.size(2.dp)', activity)
        self.assertIn('.zIndex(100f)', activity)
        self.assertIn('debug-only node', activity)

    def test_capture_stage_checks_foreground_palette_and_screen(self):
        source = (ROOT / '.github/scripts/profile_ui_probe.py').read_text(encoding='utf-8')
        stage = source.split('    def dashboards(self):', 1)[1].split('    def themes(self):', 1)[0]
        for required in ('profile_frame(', 'probe-screen:', 'self.palette(DARK_BACKGROUND)', 'self.capture("spectrum-" + screen)'):
            self.assertIn(required, stage)
        workflow = (ROOT / '.github/workflows/android-ci.yml').read_text(encoding='utf-8')
        for name in ('spectrum-home', 'spectrum-portfolio', 'spectrum-allocation'):
            self.assertIn(name, workflow)


if __name__ == '__main__':
    unittest.main()