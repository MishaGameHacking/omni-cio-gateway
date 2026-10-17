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
    def test_actual_primary_material_input_and_native_fallback_have_white_text_contrast(self):
        source = (UI / 'spectrum/SpectrumDesignSystem.kt').read_text(encoding='utf-8')
        block = source.split('internal val SpectrumPrimaryStops = listOf(', 1)[1].split('\n)', 1)[0]
        colors = re.findall(r'Color\(0xFF([0-9A-F]{6})\)', block)
        self.assertEqual(len(colors), 3)
        self.assertIn('color = SpectrumPrimaryStops.first()', source)
        self.assertIn('Text(text, color = if (enabled) Color.White', source)
        rgb = tuple(int(colors[0][i:i + 2], 16) / 255 for i in (0, 2, 4))
        self.assertGreaterEqual(1.05 / (luminance(rgb) + .05), 4.5)
        surface = (UI / 'spatial/SpatialComponents.kt').read_text(encoding='utf-8')
        self.assertIn('if (unavailable) modifier.background(color)', surface)
        self.assertIn('drawnModels', surface)
        # Material input/token contrast is distinct from rendered PBR contrast.
        # Actual light/dark screenshots remain required before publication.

    def test_portfolio_uses_new_presenter_and_live_position_resolution(self):
        screen = (UI / 'portfolio/PortfolioScreen.kt').read_text(encoding='utf-8')
        dashboard = (UI / 'portfolio/PortfolioDashboard.kt').read_text(encoding='utf-8')
        self.assertIn('PortfolioDashboard(', screen)
        self.assertIn('resolveSelectedPosition(', screen)
        self.assertNotIn('AccountPreviewCard(', screen)
        self.assertIn('listOf("Структура", "Активы", "Динамика")', dashboard)
        self.assertIn('AccountAnalytics(accessToken, account, historyOnly = true)', dashboard)
        self.assertIn('AssetStructure(snapshot.allocations, snapshot.totalValue)', dashboard)
        self.assertNotIn('PortfolioSnapshot(', dashboard)

    def test_history_keeps_validated_real_points_and_value_table(self):
        source = (UI / 'portfolio/HistoryChart.kt').read_text(encoding='utf-8')
        geometry = (UI / 'portfolio/HistoryBars.kt').read_text(encoding='utf-8')
        self.assertIn('portfolioHistory(points)', geometry)
        self.assertIn('val selectedPoint = historySelectedObservation(model, selected, selectedObservation)', source)
        self.assertIn('HistoryValues(model.source.coordinates, currency, selectedStart, selectedPoint?.date)', source)
        self.assertIn('selectedInstant?.let { sameHistoryInstant(point.date, it) } == true', source)
        self.assertIn('onSelect(point.date)', source)
        self.assertIn('SpatialBars(model.bars.map { it.close?.value?.toDouble() }', source)
        self.assertIn('model.source.low.toDouble(), model.source.high.toDouble()', source)
        self.assertNotIn('drawRoundRect(', source)
        self.assertNotIn('drawPath(', source)
        self.assertNotIn('Random', source)


if __name__ == '__main__':
    unittest.main()
