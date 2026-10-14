"""Small deterministic WCAG contrast checks for committed Spectrum text tokens."""
from __future__ import annotations

import unittest


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
        palettes = (
            ('F4F4F5', '071A2A', ('36E0FF', '4C8DFF', '8A5CFF', 'FF4FA3', '19E6A2', 'FFC857')),
            ('191A1D', 'FFFFFF', ('007C91', '205FCF', '6E43C8', 'A92A70', '007D63', '8A5A00')),
        )
        for text, card, accents in palettes:
            for accent in accents:
                with self.subTest(text=text, accent=accent):
                    badge = _composite(accent, card, 0.14)
                    self.assertGreaterEqual(_contrast(text, badge), 4.5)

    def test_primary_actions_meet_normal_text_contrast(self):
        pairs = (
            ('FFFFFF', '0077A8'),
            ('FFFFFF', '296DCE'),
            ('001F26', '59E0FF'),
        )
        for text, background in pairs:
            with self.subTest(text=text, background=background):
                self.assertGreaterEqual(_contrast(text, background), 4.5)


if __name__ == '__main__':
    unittest.main()
