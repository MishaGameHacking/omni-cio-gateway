"""Read production Kotlin tokens; unrelated passing example colors are not evidence."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[3]
UI = ROOT / 'app/src/main/java/ru/omnicio/app/ui'


def luminance(rgb):
    linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in rgb]
    return sum(c * weight for c, weight in zip(linear, (.2126, .7152, .0722)))


class SpectrumProductionTokens(unittest.TestCase):
    def test_actual_primary_gradient_has_white_text_contrast(self):
        source = (UI / 'spectrum/SpectrumDesignSystem.kt').read_text(encoding='utf-8')
        block = source.split('internal val SpectrumPrimaryStops = listOf(', 1)[1].split('\n)', 1)[0]
        colors = re.findall(r'Color\(0xFF([0-9A-F]{6})\)', block)
        self.assertEqual(len(colors), 3)
        self.assertIn('if (enabled) SpectrumPrimaryStops', source)
        self.assertIn('val labelColor = if (enabled) Color.White', source)
        rgb = [tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)) for c in colors]
        for first, second in zip(rgb, rgb[1:]):
            for sample in range(101):
                t = sample / 100
                blended = tuple(a * (1 - t) + b * t for a, b in zip(first, second))
                self.assertGreaterEqual(1.05 / (luminance(blended) + .05), 4.5)

    def test_portfolio_uses_new_presenter_and_live_position_resolution(self):
        screen = (UI / 'portfolio/PortfolioScreen.kt').read_text(encoding='utf-8')
        dashboard = (UI / 'portfolio/PortfolioDashboard.kt').read_text(encoding='utf-8')
        self.assertIn('PortfolioDashboard(', screen)
        self.assertIn('resolveSelectedPosition(', screen)
        self.assertNotIn('AccountPreviewCard(', screen)
        self.assertIn('listOf("Структура", "Активы", "Динамика")', dashboard)
        self.assertIn('AccountAnalytics(accessToken, account, onCurrency)', dashboard)
        self.assertIn('AssetStructure(snapshot.allocations, snapshot.totalValue)', dashboard)
        self.assertNotIn('PortfolioSnapshot(', dashboard)

    def test_history_keeps_validated_real_points_and_value_table(self):
        source = (UI / 'portfolio/PortfolioComponents.kt').read_text(encoding='utf-8')
        self.assertIn('portfolioHistory(points)', source)
        self.assertIn('HistoryValues(data, currency)', source)
        self.assertIn('Path()', source)
        self.assertNotIn('Random', source)
        self.assertIn('SpectrumTabs(options, selected, onSelect)', source)


if __name__ == '__main__':
    unittest.main()
