"""Read production Kotlin tokens; unrelated passing example colors are not evidence."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[3]
UI = ROOT / 'app/src/main/java/ru/omnicio/app/ui'


def luminance(rgb):
    linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in rgb]
    return sum(c * weight for c, weight in zip(linear, (.2126, .7152, .0722)))

def rgb(expression):
    if expression == 'Color.White':
        return (1.0, 1.0, 1.0)
    match = re.fullmatch(r'Color\(0xFF([0-9A-Fa-f]{6})\)', expression)
    if match is None:
        raise AssertionError('Expected a production opaque color literal')
    value = match.group(1)
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))


def colors(source, declaration):
    block = source.split(declaration, 1)[1].split('\n)', 1)[0]
    return {name: rgb(value) for name, value in re.findall(
        r'\b(\w+)\s*=\s*(Color\(0xFF[0-9A-Fa-f]{6}\)|Color\.White)', block)}


def contrast(first, second):
    high, low = sorted((luminance(first), luminance(second)), reverse=True)
    return (high + .05) / (low + .05)


class SpectrumProductionTokens(unittest.TestCase):

    def test_actual_theme_accents_and_component_text_have_readable_contrast(self):
        source = (UI / 'spectrum/SpectrumDesignSystem.kt').read_text(encoding='utf-8')
        theme = (UI / 'theme/AnalystTheme.kt').read_text(encoding='utf-8')
        schemes = {
            'light': colors(theme, 'private val LightColors = lightColorScheme('),
            'dark': colors(theme, 'private val DarkColors = darkColorScheme('),
        }
        palettes = {
            'light': colors(source, 'val LightSpectrumPalette = SpectrumPalette('),
            'dark': colors(source, 'val DarkSpectrumPalette = SpectrumPalette('),
        }
        self.assertIn('primary = palette.cyan', theme)
        self.assertIn('colorScheme = colors', theme)
        on_primary = re.search(
            r'onPrimary\s*=\s*if \(dark\) (Color\(0xFF[0-9A-Fa-f]{6}\)) else (Color\.White)', theme)
        self.assertIsNotNone(on_primary)
        actual_ink = {'dark': rgb(on_primary.group(1)), 'light': rgb(on_primary.group(2))}
        accent_block = theme.split('private fun workspacePalette(', 1)[1]
        self.assertCountEqual(re.findall(r'AccentStyle\.(\w+)\s*->', accent_block),
                              ['AURORA', 'OCEAN', 'IRIS'])
        self.assertIn('AccentStyle.AURORA -> base.cyan', accent_block)
        accents = {mode: {'AURORA': palette['cyan']} for mode, palette in palettes.items()}
        for accent in ('OCEAN', 'IRIS'):
            match = re.search(
                r'AccentStyle\.' + accent + r'\s*-> if \(dark\) '
                r'(Color\(0xFF[0-9A-Fa-f]{6}\)) else (Color\(0xFF[0-9A-Fa-f]{6}\))',
                accent_block)
            self.assertIsNotNone(match, accent)
            accents['dark'][accent], accents['light'][accent] = rgb(match.group(1)), rgb(match.group(2))
        for mode in ('light', 'dark'):
            with self.subTest(mode=mode):
                self.assertEqual(actual_ink[mode], schemes[mode]['onPrimary'])
                for accent, fill in accents[mode].items():
                    with self.subTest(accent=accent):
                        self.assertGreaterEqual(contrast(fill, actual_ink[mode]), 4.5)
                for background in ('backgroundTop', 'backgroundBottom'):
                    self.assertGreaterEqual(contrast(palettes[mode][background], schemes[mode]['onBackground']), 4.5)
                for card in ('card', 'cardStrong'):
                    for ink in ('onSurface', 'onSurfaceVariant'):
                        self.assertGreaterEqual(contrast(palettes[mode][card], schemes[mode][ink]), 4.5)

        button = source.split('fun SpectrumPrimaryButton(', 1)[1].split(
            '\n@Composable\nfun SpectrumSecondaryButton', 1)[0]
        self.assertIn('color = if (enabled) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surfaceVariant', button)
        self.assertIn('Text(text, color = if (enabled) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurfaceVariant', button)
        self.assertIn('tint = if (enabled) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurfaceVariant', button)
        self.assertIn('role = Role.Button', button)
        self.assertIn('heightIn(min = 54.dp)', button)
        self.assertNotIn('Color.White', button)
        surface = (UI / 'spatial/SpatialComponents.kt').read_text(encoding='utf-8')
        self.assertIn('.clip(shape).background(fill).border(1.dp, border, shape)', surface)
        self.assertNotIn('drawnModels', surface)
        # Token/input contrast does not replace actual light/dark runtime captures.

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
