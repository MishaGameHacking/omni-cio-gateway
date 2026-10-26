"""Regress inherited foreground, not merely the palette's unused color values."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[3]


class SpectrumForegroundTests(unittest.TestCase):
    def test_theme_provides_actual_inherited_text_color(self):
        theme = (ROOT / 'app/src/main/java/ru/omnicio/app/ui/theme/AnalystTheme.kt').read_text(encoding='utf-8')
        self.assertIn('LocalContentColor provides MaterialTheme.colorScheme.onBackground', theme)


    def test_emulator_reads_actual_foreground_and_checks_both_theme_contrasts(self):
        fixture = (ROOT / 'app/src/debug/java/ru/omnicio/app/ProfileUiProbeActivity.kt').read_text(encoding='utf-8')
        self.assertIn('LocalContentColor.current.toArgb()', fixture)
        self.assertIn('MaterialTheme.colorScheme.background.toArgb()', fixture)
        self.assertIn('probe-foreground:$foreground', fixture)
        driver = (ROOT / '.github/scripts/profile_ui_probe.py').read_text(encoding='utf-8')
        theme = (ROOT / 'app/src/main/java/ru/omnicio/app/ui/theme/AnalystColors.kt').read_text(encoding='utf-8')
        backgrounds = dict(re.findall(r'^(LIGHT|DARK)_BACKGROUND = "([a-f0-9]{8})"$', driver, re.MULTILINE))
        self.assertEqual(set(backgrounds), {'LIGHT', 'DARK'})
        foregrounds = re.search(
            r'foreground = "([a-f0-9]{8})" if expected == DARK_BACKGROUND else "([a-f0-9]{8})"', driver)
        self.assertIsNotNone(foregrounds)
        observed_ink = {'DARK': foregrounds.group(1), 'LIGHT': foregrounds.group(2)}
        self.assertIn('self.marker("probe-background:" + expected)', driver)
        self.assertIn('self.marker("probe-foreground:" + foreground)', driver)

        def light(argb):
            rgb = [int(argb[i:i + 2], 16) / 255 for i in (2, 4, 6)]
            linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in rgb]
            return sum(c * w for c, w in zip(linear, (.2126, .7152, .0722)))

        for mode in ('LIGHT', 'DARK'):
            name = 'Dark'
            block = theme.split('private val ' + name + 'Colors = ' + name.lower() + 'ColorScheme(', 1)[1].split('\n)', 1)[0]
            tokens = dict(re.findall(r'\b(background|onBackground)\s*=\s*Color\(0x(FF[0-9A-Fa-f]{6})\)', block))
            with self.subTest(mode=mode):
                self.assertEqual(backgrounds[mode], tokens['background'].lower())
                self.assertEqual(observed_ink[mode], tokens['onBackground'].lower())
                self.assertIn('self.palette(' + mode + '_BACKGROUND)', driver)
                high, low = sorted((light(backgrounds[mode]), light(observed_ink[mode])), reverse=True)
                self.assertGreaterEqual((high + .05) / (low + .05), 4.5)


if __name__ == '__main__':
    unittest.main()
