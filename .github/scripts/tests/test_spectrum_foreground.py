"""Regress inherited foreground, not merely the palette's unused color values."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]


class SpectrumForegroundTests(unittest.TestCase):
    def test_theme_provides_actual_inherited_text_color(self):
        theme = (ROOT / 'app/src/main/java/ru/omnicio/app/ui/theme/AnalystTheme.kt').read_text(encoding='utf-8')
        self.assertIn('LocalContentColor provides MaterialTheme.colorScheme.onBackground', theme)

    def test_emulator_reads_inherited_foreground_and_checks_both_themes(self):
        fixture = (ROOT / 'app/src/debug/java/ru/omnicio/app/ProfileUiProbeActivity.kt').read_text(encoding='utf-8')
        self.assertIn('LocalContentColor.current.toArgb()', fixture)
        self.assertIn('probe-foreground:$foreground', fixture)
        driver = (ROOT / '.github/scripts/profile_ui_probe.py').read_text(encoding='utf-8')
        self.assertIn('self.marker("probe-foreground:"', driver)
        self.assertIn('"fff4f7ff" if expected == DARK_BACKGROUND else "ff101722"', driver)


if __name__ == '__main__':
    unittest.main()
