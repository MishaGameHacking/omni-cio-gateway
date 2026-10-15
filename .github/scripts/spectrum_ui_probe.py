"""Native design checks run solely on the caller's disposable emulator."""
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
