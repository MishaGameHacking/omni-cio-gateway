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


def production_palette(tokens, dark):
    material = colors(tokens, 'private val WorkspaceColors = lightColorScheme(')
    semantic = colors(tokens, 'private val WorkspaceSemantic = AnalystSemanticColors(')
    if not dark:
        return material, semantic
    declaration = 'private val GraphiteColors = darkColorScheme('
    block = tokens.split(declaration, 1)[1].split('\n)', 1)[0]
    actual = colors(tokens, declaration)
    # Resolve only the references actually present in production, never fill missing roles.
    for name, reference in re.findall(r'\b(\w+)\s*=\s*WorkspaceColors\.(\w+)', block):
        actual[name] = material[reference]
    semantic.update(colors(tokens, 'private val GraphiteSemantic = WorkspaceSemantic.copy('))
    return actual, semantic


def contrast(first, second):
    high, low = sorted((luminance(first), luminance(second)), reverse=True)
    return (high + .05) / (low + .05)


class SpectrumProductionTokens(unittest.TestCase):

    def test_production_dark_and_retained_light_tokens_have_readable_contrast(self):
        source = (UI / 'spectrum/SpectrumDesignSystem.kt').read_text(encoding='utf-8')
        theme = (UI / 'theme/AnalystTheme.kt').read_text(encoding='utf-8')
        tokens = (UI / 'theme/AnalystColors.kt').read_text(encoding='utf-8')
        self.assertIn('darkColorScheme(', tokens)
        self.assertNotIn('when (accent)', tokens)
        self.assertIn('val dark = true', theme)
        self.assertIn('ThemePreference(ThemeMode.DARK)', theme)
        startup = (UI / 'theme/ApplicationThemeMode.kt').read_text(encoding='utf-8')
        application = (UI.parent / 'AnalystApplication.kt').read_text(encoding='utf-8')
        self.assertIn('StartupThemeMigration(ThemeMode.DARK, savedName != ThemeMode.DARK.name)', startup)
        self.assertIn('syncSavedApplicationTheme(this, migrateApplicationThemeForStartup(this))', application)
        self.assertIn('spectrumPalette(dark = dark)', theme)
        self.assertNotEqual(production_palette(tokens, False)[0]['background'],
                            production_palette(tokens, True)[0]['background'])
        self.assertIn('val colors = palette.colors', theme)
        self.assertIn('colorScheme = colors', theme)
        self.assertIn('val resolved = analystColors(dark, accent)', source)
        self.assertIn('SpectrumPalette(resolved.material, resolved.semantic, resolved.chartSeries)', source)
        for dark in (False, True):
            with self.subTest(dark=dark):
                c, s = production_palette(tokens, dark)
                self.assertEqual(len(c), 48)
                self.assertEqual(len(s), 19)
                self.assert_palette_contrast(c, s)
        button = source.split('fun SpectrumPrimaryButton(', 1)[1].split('fun SpectrumSecondaryButton', 1)[0]
        self.assertIn('MaterialTheme.colorScheme.primary else', button)
        self.assertIn('MaterialTheme.colorScheme.onPrimary else', button)
        self.assertIn('semantic.disabledInk', button)
        self.assertIn('role = Role.Button', button)
        self.assertIn('heightIn(min = 48.dp)', button)
        surface = (UI / 'spatial/SpatialComponents.kt').read_text(encoding='utf-8')
        self.assertIn('spatialSurfaceColors(palette, color, state', surface)
        self.assertIn('LocalContentColor provides resolved.foreground', surface)
        self.assertIn('.clip(shape).background(fill).border(1.dp, border, shape)', surface)

    def assert_palette_contrast(self, c, s):
        for family in ('Primary', 'Secondary', 'Tertiary', 'Error'):
            role = family[0].lower() + family[1:]
            self.assertGreaterEqual(contrast(c['on' + family], c[role]), 4.5)
            self.assertGreaterEqual(contrast(c['on' + family + 'Container'], c[role + 'Container']), 4.5)
        for family in ('Primary', 'Secondary', 'Tertiary'):
            role = family[0].lower() + family[1:]
            for ink in ('on' + family + 'Fixed', 'on' + family + 'FixedVariant'):
                for fill in (role + 'Fixed', role + 'FixedDim'):
                    self.assertGreaterEqual(contrast(c[ink], c[fill]), 4.5)
        for family in ('Success', 'Warning', 'Info'):
            role = family[0].lower() + family[1:]
            self.assertGreaterEqual(contrast(s['on' + family], s[role]), 4.5)
            self.assertGreaterEqual(contrast(s['on' + family + 'Container'], s[role + 'Container']), 4.5)
        # Check every rendered surface gradient stop/interpolation against both text roles.
        for surface in ('background', 'surface', 'surfaceContainerLowest', 'surfaceContainerLow',
                        'surfaceContainer', 'surfaceContainerHigh', 'surfaceContainerHighest', 'surfaceBright'):
            for tint in ('secondaryContainer', 'surfaceContainerLow'):
                for step in range(8):
                    fraction = step * .05
                    fill = tuple(a * (1 - fraction) + b * fraction for a,b in zip(c[surface],c[tint]))
                    for ink in ('onSurface', 'onSurfaceVariant'):
                        with self.subTest(surface=surface,tint=tint,step=step,ink=ink):
                            self.assertGreaterEqual(contrast(c[ink],fill),4.5)

    def test_real_date_picker_uses_explicit_readable_calendar_state_roles(self):
        caller = (UI / 'portfolio/AccountDataState.kt').read_text(encoding='utf-8')
        factory = (UI / 'spectrum/SpectrumCalendarColors.kt').read_text(encoding='utf-8')
        tokens = (UI / 'theme/AnalystColors.kt').read_text(encoding='utf-8')
        self.assertIn('colors = ru.omnicio.app.ui.spectrum.spectrumDatePickerColors()', caller)
        self.assertIn('utcTimeMillis <= todayMillis', caller)
        self.assertIn('year <= today.year', caller)
        self.assertIn('val c = MaterialTheme.colorScheme', factory)
        self.assertIn('val s = LocalSpectrumPalette.current.semantic', factory)
        block = factory.split('return DatePickerDefaults.colors(', 1)[1].split('dateTextFieldColors =', 1)[0]
        bindings = {name: (kind, role) for name, kind, role in re.findall(r'(\w+)\s*=\s*(c|s)\.(\w+)', block)}
        self.assertEqual(len(bindings), 24)
        for state in ('Day', 'Year'):
            self.assertEqual(bindings['disabled' + state + 'ContentColor'], ('s', 'disabledInk'))
            self.assertEqual(bindings['disabledSelected' + state + 'ContentColor'], ('s', 'disabledInk'))
            self.assertEqual(bindings['disabledSelected' + state + 'ContainerColor'], ('s', 'disabledContainer'))
        for dark in (False, True):
            material, semantic = production_palette(tokens, dark)
            source = {'c': material, 's': semantic}
            actual = {name: source[kind][role] for name, (kind, role) in bindings.items()}
            for state in ('Day', 'Year'):
                self.assertGreaterEqual(contrast(actual['selected' + state + 'ContentColor'],
                                                 actual['selected' + state + 'ContainerColor']), 4.5)
                self.assertGreaterEqual(contrast(actual['disabledSelected' + state + 'ContentColor'],
                                                 actual['disabledSelected' + state + 'ContainerColor']), 3)
                self.assertGreaterEqual(contrast(actual['disabled' + state + 'ContentColor'], actual['containerColor']), 3)
            self.assertGreaterEqual(contrast(actual['dayInSelectionRangeContentColor'],
                                             actual['dayInSelectionRangeContainerColor']), 4.5)

    def test_portfolio_uses_new_presenter_and_live_position_resolution(self):
        screen = (UI / 'portfolio/PortfolioScreen.kt').read_text(encoding='utf-8')
        analytics = (UI / 'portfolio/AnalyticsWorkspace.kt').read_text(encoding='utf-8')
        self.assertIn('AnalyticsWorkspace(', screen)
        self.assertNotIn('PortfolioDashboard(', screen)
        self.assertIn('snapshot?.accounts?.firstOrNull', analytics)
        self.assertIn('account?.positions?.firstOrNull', analytics)
        self.assertIn('InstrumentDetailsScreen(position', analytics)
        self.assertIn('rememberAccountData(token, account.id, "analytics"', analytics)
        self.assertIn('rememberAccountData(token, account.id, "payments"', analytics)
        self.assertNotIn('PortfolioSnapshot(', analytics)

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





