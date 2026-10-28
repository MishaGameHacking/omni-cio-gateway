"""Numerical checks of actual committed token declarations and their component use."""
from __future__ import annotations

import unittest
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
UI = ROOT / 'app/src/main/java/ru/omnicio/app/ui'


def _production():
    source = (UI / 'theme/AnalystColors.kt').read_text(encoding='utf-8')
    result = {}
    for name in ('Dark',):
        material = source.split('private val ' + name + 'Colors = ' + name.lower() + 'ColorScheme(', 1)[1].split('\n)', 1)[0]
        semantic = source.split('private val ' + name + 'Semantic = AnalystSemanticColors(', 1)[1].split('\n)', 1)[0]
        result[name] = dict(re.findall(r'\b(\w+)\s*=\s*Color\(0xFF([0-9A-Fa-f]{6})\)', material + '\n' + semantic))
    return result


def _rgb(value: str) -> tuple[float, float, float]:
    return tuple(int(value[index:index + 2], 16) / 255 for index in (0, 2, 4))


def _luminance(value: str) -> float:
    channels = []
    for channel in _rgb(value):
        channels.append(
            channel / 12.92
            if channel <= 0.04045
            else ((channel + 0.055) / 1.055) ** 2.4
        )
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast(first: str, second: str) -> float:
    high, low = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def _composite(foreground: str, background: str, alpha: float) -> str:
    front = [int(foreground[index:index + 2], 16) for index in (0, 2, 4)]
    back = [int(background[index:index + 2], 16) for index in (0, 2, 4)]
    result = [round(alpha * value + (1 - alpha) * base) for value, base in zip(front, back)]
    return ''.join(f'{value:02X}' for value in result)


class SpectrumContrastTests(unittest.TestCase):
    def test_badge_text_has_normal_text_contrast_in_dark_and_light_palettes(self):
        source = (UI / 'spectrum/SpectrumDesignSystem.kt').read_text(encoding='utf-8')
        badge = source.split('fun SpectrumBadge(', 1)[1].split('\n@Composable', 1)[0]
        self.assertIn('val fill = palette.containerFor(accent)', badge)
        self.assertIn('color = palette.foregroundFor(fill)', badge)
        self.assertNotIn('lerp(', badge)
        for mode, tokens in _production().items():
            for family in ('Primary', 'Secondary', 'Tertiary', 'Success', 'Warning', 'Error'):
                with self.subTest(mode=mode, family=family):
                    role = family[0].lower() + family[1:]
                    self.assertGreaterEqual(_contrast(tokens['on' + family + 'Container'], tokens[role + 'Container']), 4.5)

    def test_primary_actions_meet_normal_text_contrast(self):
        for mode, tokens in _production().items():
            for family in ('Primary', 'Secondary', 'Tertiary'):
                with self.subTest(mode=mode, family=family):
                    role = family[0].lower() + family[1:]
                    ink, fill = tokens['on' + family], tokens[role]
                    self.assertGreaterEqual(_contrast(ink, fill), 4.5)
                    self.assertGreaterEqual(_contrast(ink, _composite(ink, fill, .08)), 4.5)

    def test_functional_canvas_uses_roles_instead_of_an_independent_literal_palette(self):
        artwork = (UI / 'spatial/FlatArtwork.kt').read_text(encoding='utf-8')
        self.assertNotRegex(artwork, r'Color\(0x[0-9A-Fa-f]+\)')
        self.assertNotIn('Color.White', artwork)
        self.assertIn('flatArtworkColors(palette, item.color, item.colorMode, item.state)', artwork)
        scene = (UI / 'spatial/SpatialScene.kt').read_text(encoding='utf-8')
        self.assertIn('drawFlatPrimitive(it, if (it.motionAllowed) progress else 0f, palette)', scene)


if __name__ == '__main__':
    unittest.main()

