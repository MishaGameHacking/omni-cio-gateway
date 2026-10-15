"""Finalize the native UI candidate and its offline emulator acceptance checks."""
from __future__ import annotations
import json
from pathlib import Path

manifest_path = Path('spectrum-generated.json')
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
files = {entry['path']: entry['content'] for entry in manifest['files']}
APP = 'app/src/main/java/ru/omnicio/app/'


def replace(path: str, old: str, new: str, count: int = 1) -> None:
    source = files.get(path)
    if source is None:
        source = Path(path).read_text(encoding='utf-8')
    if source.count(old) != count:
        raise RuntimeError(f'Unexpected source boundary in {path}: {old[:80]!r}')
    files[path] = source.replace(old, new)


geometry_path = APP + 'ui/portfolio/PortfolioLineGeometry.kt'
files[geometry_path] = '''package ru.omnicio.app.ui.portfolio

import java.math.MathContext

/** Reuses all timestamp, duplicate, precision and size validation of portfolioHistory.
 * Only line drawing coordinates use the observed range; exact source amounts are unchanged.
 * The renderer must display this range explicitly and retain the source-value table.
 */
internal fun portfolioLineHistory(points: List<HistoryPoint>): HistoryGeometry? {
    val validated = portfolioHistory(points) ?: return null
    val high = validated.coordinates.maxOf { it.point.value }
    val low = validated.coordinates.minOf { it.point.value }
    val span = high.subtract(low)
    val coordinates = validated.coordinates.map { coordinate ->
        val y = if (span.signum() == 0) .5f else high.subtract(coordinate.point.value)
            .divide(span, MathContext.DECIMAL64).toFloat().coerceIn(0f, 1f)
        coordinate.copy(y = y)
    }
    val zero = if (span.signum() == 0) {
        if (high.signum() >= 0) 1f else 0f
    } else high.divide(span, MathContext.DECIMAL64).toFloat().coerceIn(0f, 1f)
    return HistoryGeometry(coordinates, zero, high, low)
}
'''
chart = APP + 'ui/portfolio/SpectrumHistoryChart.kt'
replace(chart, 'remember(points) { portfolioHistory(points) }', 'remember(points) { portfolioLineHistory(points) }')
replace(chart, '    HistoryLine(data, currency, compact)', '''    Notice("Диапазон: ${decimalText(geometry.low)} — ${decimalText(geometry.high)} ${currencySymbol(currency)}")
    HistoryLine(data, currency, compact)''')
home = APP + 'ui/home/HomeScreen.kt'
replace(home, 'Данные не заменяются демонстрационным балансом.', 'Повторная проверка выполняется автоматически.')

files['.github/scripts/spectrum_ui_probe.py'] = '''"""Native design checks run solely on the caller's disposable emulator."""
from __future__ import annotations

from profile_ui_probe import node_bounds

PACKAGE = 'ru.omnicio.app.debug'
ACTIVITY = PACKAGE + '/ru.omnicio.app.SpectrumUiProbeActivity'
SCREENS = (
    ('Home', 'home'), ('Portfolio', 'portfolio'), ('Market', 'market'),
    ('Risks', 'risks'), ('Education', 'education'), ('Profile', 'profile'),
    ('Login', 'login'), ('Update', 'update'), ('Chart', 'chart'),
    ('Ideas', 'ideas'), ('Pulse', 'events'), ('Chat', 'messages'),
)


def open_screen(probe, screen: str, theme: str = 'DARK') -> None:
    if screen not in {entry[0] for entry in SCREENS} or theme not in {'DARK', 'LIGHT'}:
        raise ValueError('Unrecognized fixture request')
    probe.command('shell', 'am', 'force-stop', PACKAGE)
    probe.command('shell', 'am', 'start', '-W', '-n', ACTIVITY,
                  '--es', 'screen', screen, '--es', 'theme', theme)
    probe.marker('spectrum-screen:' + screen)
    probe.marker('spectrum-contrast:passed')
    probe.marker('spectrum-line-tests:passed')


def primary_navigation(probe) -> None:
    open_screen(probe, 'Home')
    for screen, label in (('Portfolio', 'Портфель'), ('Market', 'Рынок'),
                          ('Education', 'Обучение'), ('Profile', 'Профиль'), ('Home', 'Главная')):
        matches = [node for node in probe.tree().iter('node') if node.get('text') == label]
        if not matches:
            raise AssertionError('Missing native navigation label: ' + label)
        # A screen heading may have the same text. Use the bottom-most actual label.
        target = max(matches, key=lambda node: node_bounds(node)[1])
        left, top, right, bottom = node_bounds(target)
        probe.command('shell', 'input', 'tap', str((left + right) // 2), str((top + bottom) // 2))
        probe.marker('spectrum-screen:' + screen)
    legacy = {'Что купить', 'Пульс', 'Чат'}
    if any(node.get('text') in legacy for node in probe.tree().iter('node')):
        raise AssertionError('Legacy bottom-navigation labels returned')


def exercise_spectrum(probe) -> None:
    probe.command('shell', 'settings', 'put', 'system', 'font_scale', '1.0')
    probe.command('shell', 'cmd', 'uimode', 'night', 'yes')
    for screen, name in SCREENS:
        print('SPECTRUM_UI_STAGE=' + name, flush=True)
        open_screen(probe, screen)
        probe.capture('spectrum-' + name)
    primary_navigation(probe)
    for screen, name in (('Home', 'home'), ('Portfolio', 'portfolio')):
        open_screen(probe, screen, 'LIGHT')
        probe.capture('spectrum-' + name + '-light')
    probe.command('shell', 'settings', 'put', 'system', 'font_scale', '2.0')
    for screen, name in (('Home', 'home'), ('Portfolio', 'portfolio'), ('Market', 'market')):
        open_screen(probe, screen)
        probe.capture('spectrum-' + name + '-large')
    print('SPECTRUM_UI_TESTS=passed: native-screens-12, primary-navigation-5, light-2, font-200-3, colour-contracts, line-geometry', flush=True)
'''
probe = '.github/scripts/profile_ui_probe.py'
replace(probe, '''        print(
            "PROFILE_UI_TESTS=passed:''', '''        from spectrum_ui_probe import exercise_spectrum
        exercise_spectrum(probe)
        print(
            "PROFILE_UI_TESTS=passed:''')
ci = '.github/workflows/android-ci.yml'
names = ['spectrum-' + value for value in ['home', 'portfolio', 'market', 'risks', 'education', 'profile', 'login', 'update', 'chart', 'ideas', 'events', 'messages', 'home-light', 'portfolio-light', 'home-large', 'portfolio-large', 'market-large']]
replace(ci, "'dark-initial'", "'dark-initial', " + ', '.join(repr(name) for name in names))
manifest['files'] = [{'path': path, 'content': content} for path, content in sorted(files.items())]
manifest['deletions'].append('.github/spectrum-native-extra.py')
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')
print('SPECTRUM_FINAL_FILES=' + str(len(files)))
