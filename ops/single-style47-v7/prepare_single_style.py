"""Administrative source-text preparation. Application/testing runs only on Windows.

Reads hash-bound reference bytes, composes a reviewable transport and never
imports application/backend/test modules or applies a development checkout.
"""
from pathlib import Path
import ast
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
CONTEXT = HERE.parent
INDEX = json.loads((HERE / 'verified-base45-index.json').read_text())
INVENTORY_RAW = (CONTEXT / 'continued45-40342969750/source-final.json').read_bytes()
assert hashlib.sha256(INVENTORY_RAW).hexdigest() == '43ea60a086d49c4e95d4071bbe76f96801ca6151fa41a1ce3f79acf673cd28e0'
INVENTORY = json.loads(INVENTORY_RAW)
PRIOR = {r['path']: r['content'] for r in json.loads((CONTEXT / 'continued45-40342969750/reviewed-files.json').read_text())['files']}
RAW46 = (CONTEXT / 'candidate46-callback/reviewed-files.json').read_bytes()
assert hashlib.sha256(RAW46).hexdigest() == '9b50e7572769090364b321bd4206c73060cc60898712e25abbcc813d82cab61f'
FILES = {r['path']: r['content'] for r in json.loads(RAW46)['files']}
UI = 'app/src/main/java/ru/omnicio/app/ui/'

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def base(path):
    if path not in INVENTORY['files']:
        return None
    entry = INDEX[path]
    raw = PRIOR[path].encode() if entry.get('kind') == 'reviewed45' else Path(entry['path']).read_bytes()
    assert INVENTORY['files'][path] == {'bytes':len(raw), 'sha256':digest(raw)}, path
    return raw.decode()

def get(path):
    return FILES.get(path, base(path))

def put(path, text):
    assert '\r' not in text and '\0' not in text
    FILES[path] = text

def replace(path, old, new, count=1):
    text = get(path)
    assert text.count(old) == count, (path, old[:100], text.count(old), count)
    put(path, text.replace(old, new))

# One production palette. Legacy parameters are migration inputs, not variants.
path = UI+'theme/AnalystColors.kt'
text = get(path).replace('import androidx.compose.material3.lightColorScheme\n', '')
start, end = text.index('private val LightColors'), text.index('private val DarkColors')
text = text[:start]+text[end:]
colors = {
 'primary':'A99AFF','onPrimary':'1B0D45','primaryContainer':'403199','onPrimaryContainer':'FFFFFF',
 'inversePrimary':'A99AFF','secondary':'69DFFF','onSecondary':'023343','secondaryContainer':'07384B','onSecondaryContainer':'D7F6FF',
 'tertiary':'8FADFF','onTertiary':'09265C','tertiaryContainer':'233C75','onTertiaryContainer':'E1EBFF',
 'background':'050E1C','onBackground':'EDF5FF','surface':'0A1A2C','onSurface':'EDF5FF',
 'surfaceVariant':'132C43','onSurfaceVariant':'ACC3DC','surfaceTint':'A99AFF',
 'inverseSurface':'E3EDFA','inverseOnSurface':'15253C','error':'FF99B2','onError':'510D29',
 'errorContainer':'542136','onErrorContainer':'FFE1EB','outline':'88A4C5','outlineVariant':'294763','scrim':'01060D',
 'surfaceBright':'1A334D','surfaceDim':'050E1C','surfaceContainer':'0D2136','surfaceContainerHigh':'10273E',
 'surfaceContainerHighest':'132C43','surfaceContainerLow':'0A1B2E','surfaceContainerLowest':'030B16',
 'primaryFixed':'E5DEFF','primaryFixedDim':'C4B7FF','onPrimaryFixed':'1B0D45','onPrimaryFixedVariant':'3D286C',
 'secondaryFixed':'CBF5FF','secondaryFixedDim':'8AE6FF','onSecondaryFixed':'022D3B','onSecondaryFixedVariant':'12465B',
 'tertiaryFixed':'DFE8FF','tertiaryFixedDim':'B0C6FF','onTertiaryFixed':'132A58','onTertiaryFixedVariant':'284572',
}
semantics = {
 'success':'55E8B2','onSuccess':'063B2B','successContainer':'0B3C32','onSuccessContainer':'C5FFE7',
 'warning':'FFD177','onWarning':'412B05','warningContainer':'4D3615','onWarningContainer':'FFE7B6',
 'info':'73C7FF','onInfo':'052D4B','infoContainer':'123451','onInfoContainer':'D5EEFF',
 'disabledInk':'99AEC7','disabledContainer':'152B41','chartGrid':'294763','chartAxis':'88A4C5',
 'chartSeparator':'0A1A2C','chartSelectedInner':'050E1C','chartSelectedOuter':'EDF5FF',
}
def literal_block(name, factory, values):
    return 'private val '+name+' = '+factory+'(\n'+''.join('    '+k+' = Color(0xFF'+v+'),\n' for k,v in values.items())+')'
start = text.index('private val DarkColors')
end = text.index('/** Actual state-layer')
text = text[:start]+literal_block('DarkColors','darkColorScheme',colors)+'\n\n'+literal_block('DarkSemantic','AnalystSemanticColors',semantics)+'''

/** One style for every saved legacy mode/accent and every system configuration. */
@Suppress("UNUSED_PARAMETER")
fun analystColors(dark: Boolean = true, accent: AccentStyle = AccentStyle.AURORA): AnalystColorSet =
    AnalystColorSet(DarkColors, DarkSemantic, listOf(DarkColors.secondary, DarkColors.primary,
        DarkSemantic.success, DarkColors.tertiary, DarkSemantic.warning, DarkColors.error))

'''+text[end:]
put(path,text)


# Synchronize only exact user-facing navigation labels in executable probes.
# Their ownership, geometry, stale-frame and mutation rejection rules are retained.
for path in ('.github/scripts/profile_ui_probe.py','.github/scripts/automation_ui_probe.py',
             '.github/scripts/navigation_detail_probe.py','.github/scripts/tests/test_automation_ui_probe.py',
             '.github/scripts/tests/test_navigation_detail_probe.py'):
    text=get(path).replace('"Система"','"Главная"')
    put(path,text)

path='.github/scripts/profile_ui_probe.py'
text=get(path).replace('LIGHT_BACKGROUND = "fff5f7f9"','LIGHT_BACKGROUND = "ff050e1c"')
text=text.replace('DARK_BACKGROUND = "ff101a1f"','DARK_BACKGROUND = "ff050e1c"')
text=text.replace('foreground = "ffe7eff2" if expected == DARK_BACKGROUND else "ff1b2930"',
                  'foreground = "ffedf5ff" if expected == DARK_BACKGROUND else "ffedf5ff"')
start=text.index('    def themes(self):')
end=text.index('    def dialogs(',start)
text=text[:start]+'''    def themes(self):
        # Stable full-suite stage name; owner replaced theme selection with one style.
        # Six real captures cover OS day/night, persisted motion and cancelled preview.
        self.command("shell", "cmd", "uimode", "night", "no")
        self.open()
        self.palette(LIGHT_BACKGROUND)
        self.capture("style-system-day-initial")
        self.tap(THEME_LABEL)
        self.tap("Без движения", "workspace-content")
        self.tap(APPLY_LABEL, "workspace-content", direction="start")
        self.tap_visible(WORKSPACE_BACK)
        self.palette(DARK_BACKGROUND)
        self.capture("style-motion-off")
        self.command("shell", "am", "force-stop", PACKAGE)
        self.open()
        self.palette(DARK_BACKGROUND)
        self.tap(THEME_LABEL)
        self.reveal("Без движения", "workspace-content")
        from portfolio_preferences_probe import selected_control
        self.wait_for(lambda: selected_control(self.tree(), "Без движения"), "Motion setting was not restored")
        self.capture("style-motion-restored")
        self.tap("Сдержанное", "workspace-content")
        self.tap("Отменить", "workspace-content", direction="start")
        self.reveal("Без движения", "workspace-content")
        self.wait_for(lambda: selected_control(self.tree(), "Без движения"), "Cancel did not restore saved motion")
        self.tap("Живое", "workspace-content")
        self.tap(APPLY_LABEL, "workspace-content", direction="start")
        self.tap_visible(WORKSPACE_BACK)
        self.palette(DARK_BACKGROUND)
        self.capture("style-motion-live")
        self.command("shell", "cmd", "uimode", "night", "yes")
        self.palette(DARK_BACKGROUND)
        self.capture("style-system-night")
        self.command("shell", "cmd", "uimode", "night", "no")
        self.palette(LIGHT_BACKGROUND)
        self.capture("style-system-day")

'''+text[end:]
text=text.replace('spectrum-dark-first,light,dark,system,', 'single-style,system-invariance,motion-persistence,')
put(path,text)

path='.github/scripts/tests/test_spectrum_foreground.py'
text=get(path)
text=text.replace("for name in ('Light', 'Dark'):", "for mode in ('LIGHT', 'DARK'):\n            name = 'Dark'")
text=text.replace('            mode = name.upper()\n','')
put(path,text)

path='.github/scripts/portfolio_preferences_probe.py'
text=get(path).replace('"accent": "OCEAN", "depth": True, "density": "COMPACT"',
                      '"accent": "AURORA", "depth": True, "density": "COMFORT"')
text=text.replace('("Тема", "Цвет акцента", "Плотность карточек", "Движение", "Яркое освещение", "Приватность")',
                  '("Движение", "Яркое освещение", "Приватность")')
text=text.replace('Предпросмотр цвета, контраста и движения','Единый стиль · движение и удобство')
text=text.replace('    p.tap("Океан", AREA)\n    p.tap("Компактно", AREA)\n','')
put(path,text)

path='.github/scripts/tests/test_unified_update_contract.py'
text=get(path)
start=text.index('        primary = re.search(')
end=text.index('        for screen in (\'Recommendations\', \'Messages\'):',start)
text=text[:start]+'''        catalogue = self.source('ui/NavigationCatalogue.kt')
        self.assertIn('analystPrimaryDestinations.mapNotNull { it.tab }', bar)
        self.assertIn('analystMenuDestinations.groupBy',bar)
        for tab,label,screen in (('Home','Главная','Home'),('Portfolio','Портфель','Portfolio'),
                                 ('Actions','Решения','Recommendations'),('Profile','Настройки','Profile')):
            self.assertIn('AnalystDestination("'+screen+'", "'+label+'"',catalogue)
            self.assertIn('AnalystTab.'+tab+' -> AppScreen.'+screen,main)
        for tab in ('Risk','Education'):
            self.assertIn('AnalystTab.'+tab+' -> AppScreen.'+tab,main)
'''+text[end:]
put(path,text)

path=UI+'theme/AnalystTheme.kt'
text=get(path)
start=text.index('/** Unknown global state')
end=text.index('private val AnalystTypography',start)
text=text[:start]+'''/** Retained for saved legacy callers; the application has one visual style. */
@Suppress("UNUSED_PARAMETER")
internal fun displayedThemeDark(mode: ThemeMode, system: SystemThemeObservation,
    lastDisplayed: Boolean?, appConfigurationDark: Boolean): Boolean = true

'''+text[end:]
start=text.index('    val defaultMode =')
end=text.index('    SideEffect {',start)
text=text[:start]+'''    val workspace = LocalWorkspacePreferences.current
    val dark = true
'''+text[end:]
text=text.replace('        lastDisplayedDark = dark\n','')
start=text.index('    val saveTheme:')
end=text.index('    val motionPreference =',start)
text=text[:start]+'''    // Legacy preference storage is left intact; it no longer selects a colorway.
    val themePreference = ThemePreference(ThemeMode.DARK) { }
'''+text[end:]
text=text.replace('val palette = remember(dark, workspace.value.accent) { spectrumPalette(dark, workspace.value.accent) }',
                  'val palette = remember { spectrumPalette(dark = true) }')
text=text.replace('        LocalSystemThemeObservation provides system,\n','')
for imp in ['import androidx.compose.foundation.isSystemInDarkTheme\n','import androidx.compose.runtime.getValue\n',
            'import androidx.compose.runtime.mutableStateOf\n','import androidx.compose.runtime.saveable.rememberSaveable\n',
            'import androidx.compose.runtime.setValue\n']:
    text=text.replace(imp,'')
put(path,text)

path=UI+'theme/ApplicationThemeMode.kt'
text=get(path)
start=text.index('internal fun applicationNightMode(')
end=text.index('\ninternal fun storedApplicationTheme',start)
text=text[:start]+'''/** App-local override only. Saved LIGHT/SYSTEM values migrate to the single style. */
@Suppress("UNUSED_PARAMETER")
internal fun applicationNightMode(mode: ThemeMode): Int = UiModeManager.MODE_NIGHT_YES
'''+text[end:]
put(path,text)

# Native bootstrap and launch resources match Compose before the first frame.
mapping={
 'analyst_background':'background','analyst_on_background':'onBackground','analyst_surface':'surface',
 'analyst_on_surface':'onSurface','analyst_primary':'primary','analyst_on_primary':'onPrimary',
 'analyst_primary_container':'primaryContainer','analyst_on_primary_container':'onPrimaryContainer',
 'analyst_secondary':'secondary','analyst_on_secondary':'onSecondary','analyst_secondary_container':'secondaryContainer',
 'analyst_on_secondary_container':'onSecondaryContainer','analyst_tertiary':'tertiary','analyst_on_tertiary':'onTertiary',
 'analyst_tertiary_container':'tertiaryContainer','analyst_on_tertiary_container':'onTertiaryContainer',
 'analyst_surface_variant':'surfaceVariant','analyst_on_surface_variant':'onSurfaceVariant',
 'analyst_surface_container':'surfaceContainer','analyst_surface_container_highest':'surfaceContainerHighest',
 'analyst_outline':'outline','analyst_outline_variant':'outlineVariant','analyst_error':'error','analyst_on_error':'onError',
 'analyst_scrim':'scrim','analyst_warning':'warning','analyst_disabled_ink':'disabledInk','analyst_disabled_container':'disabledContainer',
}
xml='<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'+''.join(
    '    <color name="'+name+'">#'+(colors|semantics)[role]+'</color>\n' for name,role in mapping.items())+'''
    <color name="analyst_launcher_background">@color/analyst_surface</color>
</resources>
'''
native=get('app/src/main/res/values-night/themes.xml')
for directory in ('values','values-night'):
    put('app/src/main/res/'+directory+'/colors.xml',xml)
    put('app/src/main/res/'+directory+'/themes.xml',native)

# Preserve the real lint failure from46; use Compose's resource observation API.
path='app/src/debug/java/ru/omnicio/app/ThemeLifecycleProbe.kt'
text=get(path)
text=text.replace('import androidx.compose.ui.platform.LocalContext\n',
                  'import androidx.compose.ui.platform.LocalContext\nimport androidx.compose.ui.platform.LocalResources\n')
text=text.replace('LocalContext.current.resources', 'LocalResources.current')
text=text.replace('context.getColor(R.color.analyst_background)', 'LocalResources.current.getColor(R.color.analyst_background, null)')
put(path,text)

path=UI+'workspace/AppearanceScreen.kt'
text=get(path)
for line in ['    val theme = LocalThemePreference.current\n',
             '    var savedTheme by rememberSaveable { mutableStateOf(theme.mode) }\n',
             '    var draftTheme by rememberSaveable { mutableStateOf(theme.mode) }\n']:
    assert line in text; text=text.replace(line,'')
text=text.replace('draft != savedPrefs || draftTheme != savedTheme','draft != savedPrefs')
text=text.replace('controller.cancelPreview(); theme.cancelPreview(); draft = savedPrefs; draftTheme = savedTheme;',
                  'controller.cancelPreview(); draft = savedPrefs;')
text=text.replace('LaunchedEffect(draft, draftTheme)', 'LaunchedEffect(draft)')
text=text.replace('controller.preview(draft); theme.preview(draftTheme)', 'controller.preview(draft)')
text=text.replace('controller.cancelPreview(); theme.cancelPreview()', 'controller.cancelPreview()')
text=text.replace('controller.applyPreview(); theme.applyPreview()', 'controller.applyPreview()')
text=text.replace('savedPrefs = draft; savedTheme = draftTheme;', 'savedPrefs = draft;')
start=text.index('            item { SpectrumCard { WorkspaceChoices("Тема"')
end=text.index('            item { SpectrumCard {\n                WorkspaceChoices("Движение"',start)
text=text[:start]+text[end:]
text=text.replace('                draftTheme = ThemeMode.DARK; theme.preview(draftTheme)\n','')
text=text.replace('Предпросмотр цвета, контраста и движения','Единый стиль · движение и удобство')
text=text.replace('Объекты реагируют на касание и изменение состояния.',
                  'Видимые иконки плавно движутся по кругу и реагируют на касание. Числа и подписи остаются неподвижными.')
text=text.replace('Text("Analyst AI", style = MaterialTheme.typography.headlineMedium)',
                  'Text("Analyst AI", style = MaterialTheme.typography.titleLarge)')
put(path,text)

# Next sections add the shared motion, surfaces, destinations and screen hierarchy.
path=UI+'portfolio/PortfolioDashboard.kt'
text=get(path)
text=text.replace('''                        item(key = "sectors") { WorkspaceLink("Отрасли и классы", "Состав ваших вложений", SpectrumSymbol.Market) {
                            openWorkspace(WorkspaceRoute.Market)
                        } }
''','')
text=text.replace('''        CurrencyChoice(selectedCurrency.name)
        val waiting''','''        DetailFold("Валюта и действия") {
        CurrencyChoice(selectedCurrency.name)
        BalanceVisibilityButton()
        val waiting''')
text=text.replace('''        val observed = snapshot.asOf ?: lastUpdatedMillis?.let { java.time.Instant.ofEpochMilli(it).toString() }
''','''        }
''')
text=text.replace('''        Notice("Данные: ${dateText(observed)}" + if (refreshing) " · обновляем" else " · автообновление")
''','')
put(path,text)

path=UI+'auth/TelegramLoginScreen.kt'
text=get(path).replace('motionAllowed = false)', 'motionAllowed = true)')
text=text.replace('Text("Войти в систему"', 'Text("Ваш инвестиционный аналитик"')
text=text.replace('Войдите, чтобы управлять анализом на вашем сервере.',
                  'Портфель, важные изменения и основания решений — в одном месте.')
put(path,text)

# Same static web roles, regardless of the browser's system preference.
css_roles={
 'bg':'background','surface':'surface','text':'onSurface','muted':'onSurfaceVariant',
 'primary':'primary','on-primary':'onPrimary','primary-container':'primaryContainer',
 'on-primary-container':'onPrimaryContainer','surface-container':'surfaceContainer','outline':'outline',
 'outline-variant':'outlineVariant','danger':'error','disabled-ink':'disabledInk','disabled-container':'disabledContainer',
}
for path in ('backend/app.py','backend/telegram_browser_app.py','backend/owner_app.py','.github/scripts/update-help.html'):
    text=get(path)
    start=text.index('  :root {')
    stop=text.index('  body {',start)
    doubled=text[start:].startswith('  :root {{')
    css='  :root {\n    color-scheme: dark;\n'+''.join(
        '    --'+name+': #'+(colors|semantics)[role]+';\n' for name,role in css_roles.items())+'  }\n'
    if doubled: css=css.replace('{','{{').replace('}','}}')
    text=text[:start]+css+text[stop:]
    text=text.replace('name="color-scheme" content="light dark"','name="color-scheme" content="dark"')
    text=text.replace('background:var(--bg);','background:var(--bg); background-image:radial-gradient(ellipse at top,#122449,transparent 65%);')
    if path=='backend/owner_app.py':
        import base64
        tree=ast.parse(text)
        style=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
            and any(isinstance(t,ast.Name) and t.id=='DENIAL_STYLE' for t in n.targets))
        pin=base64.b64encode(hashlib.sha256(style.encode()).digest()).decode()
        text=re.sub(r"DENIAL_STYLE_SHA256 = '[^']+'", "DENIAL_STYLE_SHA256 = '"+pin+"'",text)
    put(path,text)

path='backend/tests/test_owned_web_theme.py'
text=get(path).replace("attrs.get('content') == 'light dark'", "attrs.get('content') == 'dark'")
text=text.replace("variables['color-scheme'], 'dark' if dark else 'light'", "variables['color-scheme'], 'dark'")
text=text.replace('test_all_actual_pages_resolve_the_same_day_and_night_roles_as_android',
                  'test_all_actual_pages_keep_the_same_style_in_both_system_preferences')
put(path,text)

# Update obsolete assertions to the explicit new owner contract, retaining contrast,
# accessibility, provenance and lifecycle rejection checks.
path='app/src/test/java/ru/omnicio/app/ui/theme/DisplayedThemeTest.kt'
put(path,'''package ru.omnicio.app.ui.theme

import org.junit.Assert.assertTrue
import org.junit.Test

class DisplayedThemeTest {
    @Test fun savedModesCannotChangeTheSingleStyleWhenSystemPreferenceChanges() {
        for (mode in ThemeMode.entries) for (systemDark in listOf(false, true))
            for (last in listOf(null, false, true)) for (configuration in listOf(false, true))
                assertTrue(displayedThemeDark(mode, SystemThemeObservation.Known(systemDark), last, configuration))
    }
    @Test fun_unavailableDisplayCannotIntroduceAnotherPalette() {
        for (reason in SystemThemeUnavailableReason.entries) for (mode in ThemeMode.entries)
            assertTrue(displayedThemeDark(mode, SystemThemeObservation.Unknown(reason), false, false))
    }
}
'''.replace('fun_unavailableDisplay','fun unavailableDisplay'))

path='app/src/test/java/ru/omnicio/app/ui/theme/ApplicationThemeModeTest.kt'
text=get(path).replace('assertEquals(1, applicationNightMode(ThemeMode.LIGHT))','assertEquals(2, applicationNightMode(ThemeMode.LIGHT))')
text=text.replace('assertEquals(0, applicationNightMode(ThemeMode.SYSTEM))','assertEquals(2, applicationNightMode(ThemeMode.SYSTEM))')
put(path,text)

path='app/src/test/java/ru/omnicio/app/ui/theme/AnalystColorsTest.kt'
text=get(path).replace('assertEquals(original.material.secondary, analystColors(dark, AccentStyle.OCEAN).material.primary)',
                      'assertEquals(original, analystColors(dark, AccentStyle.OCEAN))')
text=text.replace('assertEquals(original.material.tertiary, analystColors(dark, AccentStyle.IRIS).material.primary)',
                  'assertEquals(original, analystColors(dark, AccentStyle.IRIS))')
put(path,text)

path='.github/scripts/tests/test_spectrum_brand_identity.py'
text=get(path).replace('"@android:style/Theme.Material.NoActionBar" if night else "@android:style/Theme.Material.Light.NoActionBar"',
                      '"@android:style/Theme.Material.NoActionBar"')
text=text.replace('str(not night).lower()', '"false"')
text=text.replace('self.assertNotEqual(resolved_color("@color/analyst_background", False),',
                  'self.assertEqual(resolved_color("@color/analyst_background", False),')
put(path,text)

path='.github/scripts/tests/test_spectrum_contrast.py'
replace(path, "for name in ('Light', 'Dark'):", "for name in ('Dark',):")

path='.github/scripts/tests/test_spectrum_production_tokens.py'
text=get(path)
start=text.index('    def test_actual_theme_accents_and_component_text_have_readable_contrast(self):')
end=text.index('    def test_real_date_picker_',start)
text=text[:start]+'''    def test_actual_single_style_and_gradient_surfaces_have_readable_contrast(self):
        source = (UI / 'spectrum/SpectrumDesignSystem.kt').read_text(encoding='utf-8')
        theme = (UI / 'theme/AnalystTheme.kt').read_text(encoding='utf-8')
        tokens = (UI / 'theme/AnalystColors.kt').read_text(encoding='utf-8')
        c = colors(tokens, 'private val DarkColors = darkColorScheme(')
        s = colors(tokens, 'private val DarkSemantic = AnalystSemanticColors(')
        self.assertEqual(len(c), 48)
        self.assertEqual(len(s), 19)
        self.assertNotIn('lightColorScheme(', tokens)
        self.assertNotIn('when (accent)', tokens)
        self.assertNotIn('isSystemInDarkTheme()', theme)
        self.assertIn('spectrumPalette(dark = true)', theme)
        self.assertIn('val colors = palette.colors', theme)
        self.assertIn('colorScheme = colors', theme)
        self.assertIn('val resolved = analystColors(dark, accent)', source)
        self.assertIn('SpectrumPalette(resolved.material, resolved.semantic, resolved.chartSeries)', source)
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
        button = source.split('fun SpectrumPrimaryButton(', 1)[1].split('fun SpectrumSecondaryButton', 1)[0]
        self.assertIn('MaterialTheme.colorScheme.primaryContainer else', button)
        self.assertIn('MaterialTheme.colorScheme.onPrimaryContainer else', button)
        self.assertIn('semantic.disabledInk', button)
        self.assertIn('role = Role.Button', button)
        self.assertIn('heightIn(min = 54.dp)', button)
        surface = (UI / 'spatial/SpatialComponents.kt').read_text(encoding='utf-8')
        self.assertIn('spatialSurfaceColors(palette, color, state', surface)
        self.assertIn('LocalContentColor provides resolved.foreground', surface)
        self.assertIn('.clip(shape).background(gradient).border(borderWidth, border, shape)', surface)

'''+text[end:]
text=text.replace("for mode in ('Light', 'Dark'):", "for mode in ('Dark',):")
put(path,text)

path='.github/scripts/tests/test_spectrum_compact_home.py'
text=get(path)
text=text.replace('test_system_state_and_blockers_precede_results_without_raw_portfolio',
                  'test_real_portfolio_precedes_analysis_without_hiding_blockers')
text=text.replace('self.assertEqual(order[:2], ["system-header", "automation-state"])',
                  'self.assertEqual(order[:4], ["system-header", "portfolio-overview", "portfolio-actions", "automation-state"])')
text=text.replace('Text("Система"','Text("Главная"')
put(path,text)

path='.github/scripts/tests/test_android17_live_spectrum.py'
text=get(path).replace('test_system_home_uses_confirmed_analysis_and_three_native_destinations',
                      'test_home_uses_confirmed_analysis_and_shared_primary_destinations')
text=text.replace("'\"Система\"'", "'\"Главная\"'")
start=text.index('        primary = re.search(')
end=text.index('        self.assertIn("role = Role.Tab", bar)',start)
text=text[:start]+'''        catalogue = self.source("ui/NavigationCatalogue.kt")
        self.assertIn('analystPrimaryDestinations.mapNotNull { it.tab }', bar)
        for destination,label in (("Home","Главная"),("Portfolio","Портфель"),
                                  ("Recommendations","Решения"),("Profile","Настройки")):
            self.assertIn('AnalystDestination("'+destination+'", "'+label+'"', catalogue)
        self.assertNotIn('showLabel = !compact',bar)
        self.assertIn('primaryTabs.chunked(2)',bar)
'''+text[end:]
put(path,text)

put('app/src/test/java/ru/omnicio/app/ui/NavigationCatalogueTest.kt','''package ru.omnicio.app.ui

import org.junit.Assert.*
import org.junit.Test
import ru.omnicio.app.ui.workspace.WorkspaceRoute

class NavigationCatalogueTest {
    @Test fun everyRestorableWorkspaceHasExactlyOneDestinationAndReachableParent() {
        assertEquals(analystDestinations.size, analystDestinations.map { it.id }.distinct().size)
        for (route in WorkspaceRoute.entries) {
            val matches = analystDestinations.filter { it.workspace == route }
            assertEquals(route.name, 1, matches.size)
            assertEquals(route.name, matches.single().id)
            assertTrue(analystPrimaryDestinations.any { it.tab == matches.single().parent })
        }
    }
    @Test fun portfolioIsADirectRootAndSectionSwitchesDoNotAccumulateSiblingHistory() {
        assertEquals(listOf("Home","Portfolio","Recommendations","Profile"), analystPrimaryDestinations.map { it.id })
        for (root in analystPrimaryDestinations) assertEquals(emptyList<String>(),sectionBackStack(root.id))
        assertEquals(listOf("Portfolio"),sectionBackStack("Strategies"))
        assertEquals(listOf("Recommendations"),sectionBackStack("Assistant"))
        assertEquals(listOf("Profile"),sectionBackStack("Appearance"))
        assertNull(sectionBackStack("unknown_saved_route"))
    }
    @Test fun drawerAndRailCanReachEveryExistingWorkingDestination() {
        assertTrue(analystMenuDestinations.containsAll(analystPrimaryDestinations))
        assertEquals(WorkspaceRoute.entries.toSet(),analystMenuDestinations.mapNotNull { it.workspace }.toSet())
        assertTrue(analystMenuDestinations.any { it.tab == AnalystTab.Risk })
        assertEquals("Портфель",AnalystTab.Portfolio.destination().title)
    }
}
''')

put('app/src/test/java/ru/omnicio/app/ui/spatial/LiveIconClockTest.kt','''package ru.omnicio.app.ui.spatial

import org.junit.Assert.*
import org.junit.Test

class LiveIconClockTest {
    @Test fun sharedClockOwnsOnlyDistinctVisibleRegistrations() {
        val clock=LiveIconClock(); val first=Any(); val second=Any()
        clock.attach(first);clock.attach(first);clock.attach(second)
        assertEquals(2,clock.activeCount)
        clock.detach(first);clock.detach(first)
        assertEquals(1,clock.activeCount)
        clock.detach(second)
        assertEquals(0,clock.activeCount)
    }
    @Test fun phaseIsBoundedAndWrapsWithoutAccumulatingTimeOrChangingValues() {
        assertEquals(0f,decorativeLoopPhase(-1),0f)
        assertEquals(0f,decorativeLoopPhase(0),0f)
        assertEquals(.5f,decorativeLoopPhase(2_400_000_000L),.0001f)
        assertEquals(0f,decorativeLoopPhase(4_800_000_000L),0f)
        assertEquals(.5f,decorativeLoopPhase(7_200_000_000L),.0001f)
        assertTrue(decorativeLoopPhase(Long.MAX_VALUE) in 0f..1f)
    }
}
''')

put(UI+'spatial/LiveIconClock.kt', '''package ru.omnicio.app.ui.spatial

import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.boundsInWindow
import androidx.compose.ui.layout.onGloballyPositioned
import kotlinx.coroutines.isActive

/** One frame source per visible scene, independent of portfolio or network state. */
internal class LiveIconClock {
    val phase = mutableFloatStateOf(0f)
    private val owners = mutableStateMapOf<Any, Unit>()
    val activeCount: Int get() = owners.size
    fun attach(owner: Any) { owners[owner] = Unit }
    fun detach(owner: Any) { owners.remove(owner) }
}

internal val LocalLiveIconClock = staticCompositionLocalOf<LiveIconClock?> { null }

internal fun decorativeLoopPhase(elapsedNanos: Long): Float =
    (elapsedNanos.coerceAtLeast(0L) % 4_800_000_000L).toFloat() / 4_800_000_000f

@Composable
internal fun rememberLiveIconClock(motion: SpatialMotion): LiveIconClock {
    val clock = remember { LiveIconClock() }
    val running = motion == SpatialMotion.Live && clock.activeCount > 0
    LaunchedEffect(running) {
        clock.phase.floatValue = 0f
        if (running) {
            var origin: Long? = null
            while (isActive) withFrameNanos { now ->
                val start = origin ?: now.also { origin = it }
                clock.phase.floatValue = decorativeLoopPhase(now - start)
            }
        }
    }
    return clock
}

internal data class LiveDecoration(val modifier: Modifier, val phase: State<Float>)

/** Clipped bounds become empty when a lazy/scrolling item leaves its viewport. */
@Composable
internal fun rememberLiveDecoration(enabled: Boolean): LiveDecoration {
    val clock = LocalLiveIconClock.current
    val motion = LocalFlatMotion.current
    val owner = remember { Any() }
    var visible by remember { mutableStateOf(false) }
    val active = enabled && visible && motion == SpatialMotion.Live && clock != null
    DisposableEffect(clock, active) {
        if (active) clock?.attach(owner)
        onDispose { clock?.detach(owner) }
    }
    val still = rememberUpdatedState(0f)
    return LiveDecoration(Modifier.onGloballyPositioned {
        val clipped = it.boundsInWindow()
        visible = clipped.width > 0f && clipped.height > 0f
    }, if (active) clock!!.phase else still)
}
''')

path=UI+'spatial/SpatialScene.kt'
text=get(path)
text=text.replace('import androidx.compose.ui.graphics.graphicsLayer\n',
                  'import androidx.compose.ui.graphics.graphicsLayer\nimport androidx.compose.ui.graphics.Brush\n')
text=text.replace('    val effective = flatMotionPolicy(motion, foreground, systemMotion, constrained, severeThermal)\n',
                  '    val effective = flatMotionPolicy(motion, foreground, systemMotion, constrained, severeThermal)\n    val clock = rememberLiveIconClock(effective)\n')
text=text.replace('CompositionLocalProvider(LocalFlatContrast provides opaque, LocalFlatDrawStats provides counters,',
                  'CompositionLocalProvider(LocalLiveIconClock provides clock, LocalFlatContrast provides opaque, LocalFlatDrawStats provides counters,')
text=text.replace('.background(LocalSpectrumPalette.current.backgroundTop)',
                  '.background(Brush.verticalGradient(listOf(LocalSpectrumPalette.current.backgroundTop, LocalSpectrumPalette.current.colors.surfaceContainerLowest)))')
start=text.index('    val loading = primitives.any')
end=text.index('    Canvas(modifier.onGloballyPositioned',start)
text=text[:start]+'''    val live = rememberLiveDecoration(canMove)
    LaunchedEffect(states, canMove, motion) {
        phase.snapTo(0f)
        if (canMove && motion == SpatialMotion.Subdued) {
            phase.animateTo(1f, tween(220, easing = FastOutSlowInEasing))
            phase.snapTo(0f)
        }
    }
'''+text[end:]
text=text.replace('    Canvas(modifier.onGloballyPositioned {','    Canvas(modifier.then(live.modifier).onGloballyPositioned {')
text=text.replace('val progress = if (canMove) phase.value else 0f',
                  'val progress = if (!canMove) 0f else if (motion == SpatialMotion.Live) live.phase.value else phase.value')
text=text.replace('import androidx.compose.animation.core.LinearEasing\n','').replace('import kotlinx.coroutines.delay\n','')
put(path,text)

path=UI+'spatial/FlatArtwork.kt'
text=get(path).replace('import androidx.compose.ui.graphics.Color\n',
                       'import androidx.compose.ui.graphics.Color\nimport androidx.compose.ui.graphics.Brush\n')
text=text.replace('val pulse = sin(phase * PI).toFloat()',
                  'val pulse = ((1.0 - cos(phase * PI * 2.0)) / 2.0).toFloat()')
text=text.replace('}) { flatIcon(asset.name, artwork, phase, item.state, item.outlineColor) }', '''}) {
                    if (item.colorMode == SpatialColorMode.Decorative && item.state != SpatialState.Disabled) {
                        drawCircle(Brush.radialGradient(listOf(artwork.teal.copy(alpha = .14f + .05f * pulse),
                            artwork.violet.copy(alpha = .07f), Color.Transparent), Offset(50f, 50f), 50f),
                            radius = 50f, center = Offset(50f, 50f))
                        drawArc(artwork.teal.copy(alpha = .25f), 205f, 90f, false,
                            Offset(5f, 5f), Size(90f, 90f), style = Stroke(1.2f))
                    }
                    flatIcon(asset.name, artwork, phase, item.state, item.outlineColor)
                }''')
put(path,text)

put(UI+'NavigationCatalogue.kt', '''package ru.omnicio.app.ui

import androidx.compose.runtime.staticCompositionLocalOf
import ru.omnicio.app.ui.spectrum.SpectrumSymbol
import ru.omnicio.app.ui.workspace.WorkspaceRoute

enum class NavigationGroup(val title: String) { Main("Основное"), Portfolio("Портфель и рынок"),
    Research("Анализ и исследования"), Personal("Личное") }

data class AnalystDestination(val id: String, val title: String, val symbol: SpectrumSymbol,
    val group: NavigationGroup, val parent: AnalystTab, val tab: AnalystTab? = null,
    val workspace: WorkspaceRoute? = null)

/** IDs remain compatible with restored navigation, notifications and saved drafts. */
val analystDestinations: List<AnalystDestination> = listOf(
    AnalystDestination("Home", "Главная", SpectrumSymbol.Home, NavigationGroup.Main, AnalystTab.Home, tab = AnalystTab.Home),
    AnalystDestination("Portfolio", "Портфель", SpectrumSymbol.Portfolio, NavigationGroup.Main, AnalystTab.Portfolio, tab = AnalystTab.Portfolio),
    AnalystDestination("Recommendations", "Решения", SpectrumSymbol.Goal, NavigationGroup.Main, AnalystTab.Actions, tab = AnalystTab.Actions),
    AnalystDestination("Profile", "Настройки", SpectrumSymbol.Settings, NavigationGroup.Main, AnalystTab.Profile, tab = AnalystTab.Profile),
    AnalystDestination("Risk", "Риски", SpectrumSymbol.Risk, NavigationGroup.Portfolio, AnalystTab.Portfolio, tab = AnalystTab.Risk),
    AnalystDestination("Strategies", "Стратегия", SpectrumSymbol.Goal, NavigationGroup.Portfolio, AnalystTab.Portfolio, workspace = WorkspaceRoute.Strategies),
    AnalystDestination("Market", "Рынок", SpectrumSymbol.Market, NavigationGroup.Portfolio, AnalystTab.Portfolio, workspace = WorkspaceRoute.Market),
    AnalystDestination("Discovery", "Поиск инструментов", SpectrumSymbol.Search, NavigationGroup.Portfolio, AnalystTab.Portfolio, workspace = WorkspaceRoute.Discovery),
    AnalystDestination("Goals", "Цель и резерв", SpectrumSymbol.Goal, NavigationGroup.Portfolio, AnalystTab.Portfolio, workspace = WorkspaceRoute.Goals),
    AnalystDestination("Assistant", "Аналитик", SpectrumSymbol.Analyst, NavigationGroup.Research, AnalystTab.Actions, workspace = WorkspaceRoute.Assistant),
    AnalystDestination("Reports", "Выводы аналитика", SpectrumSymbol.Ideas, NavigationGroup.Research, AnalystTab.Actions, workspace = WorkspaceRoute.Reports),
    AnalystDestination("Library", "Исследования", SpectrumSymbol.Sources, NavigationGroup.Research, AnalystTab.Actions, workspace = WorkspaceRoute.Library),
    AnalystDestination("AnalysisTimeline", "История проверок", SpectrumSymbol.Pulse, NavigationGroup.Research, AnalystTab.Actions, workspace = WorkspaceRoute.AnalysisTimeline),
    AnalystDestination("Messages", "События", SpectrumSymbol.Notifications, NavigationGroup.Research, AnalystTab.Home, workspace = WorkspaceRoute.Messages),
    AnalystDestination("AnalysisSettings", "Правила анализа", SpectrumSymbol.Settings, NavigationGroup.Personal, AnalystTab.Profile, workspace = WorkspaceRoute.AnalysisSettings),
    AnalystDestination("NotificationSettings", "Уведомления", SpectrumSymbol.Notifications, NavigationGroup.Personal, AnalystTab.Profile, workspace = WorkspaceRoute.NotificationSettings),
    AnalystDestination("Appearance", "Оформление", SpectrumSymbol.Settings, NavigationGroup.Personal, AnalystTab.Profile, workspace = WorkspaceRoute.Appearance),
    AnalystDestination("Devices", "Устройства", SpectrumSymbol.Profile, NavigationGroup.Personal, AnalystTab.Profile, workspace = WorkspaceRoute.Devices),
    AnalystDestination("ActivityHistory", "Недавно открыто", SpectrumSymbol.Pulse, NavigationGroup.Personal, AnalystTab.Home, workspace = WorkspaceRoute.ActivityHistory),
    AnalystDestination("Education", "Обучение", SpectrumSymbol.Education, NavigationGroup.Personal, AnalystTab.Profile, tab = AnalystTab.Education, workspace = WorkspaceRoute.Education),
    AnalystDestination("NewFeatures", "Что нового", SpectrumSymbol.Ideas, NavigationGroup.Personal, AnalystTab.Profile, workspace = WorkspaceRoute.NewFeatures),
    AnalystDestination("TApi", "Подключение Т-Инвестиций", SpectrumSymbol.Sources, NavigationGroup.Personal, AnalystTab.Profile),
)

val analystPrimaryDestinations = analystDestinations.filter { it.group == NavigationGroup.Main }
val analystMenuDestinations = analystDestinations.filter { it.tab != null || it.workspace != null }
fun analystDestination(id: String): AnalystDestination? = analystDestinations.firstOrNull { it.id == id }
internal fun AnalystTab.destination(): AnalystDestination = analystDestinations.first { it.tab == this }
internal fun WorkspaceRoute.destination(): AnalystDestination = analystDestinations.first { it.workspace == this }

/** Section switches return to their root; contextual drill-down uses the ordinary Back stack. */
fun sectionBackStack(destinationId: String): List<String>? {
    val destination = analystDestination(destinationId) ?: return null
    return if (destination.group == NavigationGroup.Main) emptyList() else listOf(destination.parent.destination().id)
}

val LocalAnalystSectionNavigator = staticCompositionLocalOf<(String) -> Unit> { {} }
''')

path=UI+'AnalystBottomBar.kt'
text=get(path)
text=text.replace('private val primaryTabs = listOf(AnalystTab.Home, AnalystTab.Actions, AnalystTab.Profile)',
                  'private val primaryTabs = analystPrimaryDestinations.mapNotNull { it.tab }')
text=text.replace('/ 3 - 12.dp', '/ primaryTabs.size - 12.dp')
start=text.index('            val menuWidth =')
end=text.index('            Column {',start)
text=text[:start]+'''            val compact = density.fontScale >= 1.5f || maxWidth < 320.dp
'''+text[end:]
text=text.replace('/** Three stable destinations;', '/** Four direct destinations;')
start=text.index('                if (compact) Text(')
end=text.index('                Row(Modifier.fillMaxWidth()',start)
text=text[:start]+text[end:]
start=text.index('                    primaryTabs.forEach { tab ->')
end=text.index('\n                }\n            }',start)
text=text[:start]+'''                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        val rows = if (compact) primaryTabs.chunked(2) else listOf(primaryTabs)
                        rows.forEach { tabs ->
                            Row(Modifier.fillMaxWidth().height(IntrinsicSize.Min), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                                tabs.forEach { tab ->
                                    DockDestination(tab, tab == selected.primaryDestination(), Modifier.weight(1f).fillMaxHeight()
                                        .testTag("bottom-destination-" + tab.name.lowercase())) { navigate(tab) }
                                }
                            }
                        }
                    }'''+text[end:]
start=text.index('internal fun AnalystTab.primaryDestination():')
end=text.index('\n@Composable\nprivate fun DockDestination',start)
text=text[:start]+'''internal fun AnalystTab.primaryDestination(): AnalystTab = destination().parent
'''+text[end:]
text=text.replace('private fun DockDestination(', 'internal fun DockDestination(')
text=text.replace('motionAllowed = false, state = state, colorMode = SpatialColorMode.Monochrome',
                  'motionAllowed = active, state = state, colorMode = SpatialColorMode.Decorative')
start=text.index('private fun AnalystTab.label()')
end=text.index('\n@Composable\nfun AnalystSideRail',start)
text=text[:start]+'''private fun AnalystTab.label() = destination().title
private fun AnalystTab.symbol() = destination().symbol
'''+text[end:]
start=text.index('@Composable\nfun AnalystSideRail')
text=text[:start]+'''@Composable
fun AnalystSideRail(selected: AnalystTab, selectedWorkspace: ru.omnicio.app.ui.workspace.WorkspaceRoute?,
    navigate: (AnalystTab) -> Unit, navigateWorkspace: (ru.omnicio.app.ui.workspace.WorkspaceRoute) -> Unit) {
    val width = (128f * maxOf(1f, LocalDensity.current.fontScale)).dp
    Surface(Modifier.fillMaxHeight().width(width).zIndex(1f).clipToBounds().testTag("analyst-side-rail"), color = MaterialTheme.colorScheme.surface) {
        Column(Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.safeDrawing.only(WindowInsetsSides.Vertical))
            .verticalScroll(rememberScrollState()).padding(10.dp).selectableGroup(),
            verticalArrangement = Arrangement.spacedBy(8.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Text("Analyst AI", style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(vertical = 12.dp))
            analystMenuDestinations.groupBy { it.group }.forEach { (group, destinations) ->
                Text(group.title, style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                destinations.forEach { destination ->
                    if (destination.workspace != null) {
                        val route = destination.workspace
                        SpectrumTextButton(destination.title, {
                            navigateWorkspace(route)
                        }, Modifier.fillMaxWidth().heightIn(min = 48.dp)
                            .testTag("rail-workspace-" + route.name.lowercase())
                            .semantics { this.selected = selectedWorkspace == route }, symbol = destination.symbol)
                    } else destination.tab?.let { tab ->
                        DockDestination(tab, selectedWorkspace == null && tab == selected,
                            Modifier.fillMaxWidth().testTag("rail-destination-" + tab.name.lowercase())) { navigate(tab) }
                    }
                }
            }
        }
    }
}
'''
text=text.replace('import androidx.compose.ui.semantics.semantics\n',
                  'import androidx.compose.ui.semantics.semantics\nimport androidx.compose.ui.semantics.selected\n')
put(path,text)

path=UI+'AnalystNavigationPanels.kt'
text=get(path)
start=text.index('private val detailDestinations = listOf(')
end=text.index('\nprivate val menuIcon',start)
text=text[:start]+'''private val detailDestinations = analystMenuDestinations.mapNotNull { destination ->
    destination.workspace?.let { it to destination.title }
}
'''+text[end:]
text=text.replace('listOf(AnalystTab.Home to "Система", AnalystTab.Actions to "Решения",\n                            AnalystTab.Profile to "Настройки")',
                  'analystPrimaryDestinations.map { it.tab!! to it.title }')
text=text.replace('    LaunchedEffect(wide) {', '''    val selectWideWorkspace: (WorkspaceRoute) -> Unit = { route ->
        val source = currentDestination
        guard.requestDestination(source, { currentDestination }, source.second == route) { navigateWorkspace(route) }
    }
    LaunchedEffect(wide) {''')
text=text.replace('if (wide) AnalystSideRail(selected, selectWideTab)',
                  'if (wide) AnalystSideRail(selected, selectedWorkspace, selectWideTab, selectWideWorkspace)')
start=text.index('                        detailDestinations.forEach { (route, title) ->')
end=text.index('\n                    }\n                }',start)
text=text[:start]+'''                        analystMenuDestinations.filter { it.group != NavigationGroup.Main }
                            .groupBy { it.group }.forEach { (group, destinations) ->
                            Text(group.title, Modifier.padding(horizontal = 12.dp, vertical = 8.dp).semantics { heading() },
                                style = MaterialTheme.typography.labelLarge, color = colors.onSurfaceVariant)
                            destinations.forEach { destination ->
                                val route = destination.workspace
                                val tab = destination.tab
                                val active = if (route != null) route == selectedWorkspace else selectedWorkspace == null && tab == selected
                                NavigationDrawerItem(
                                    label = { Text(destination.title, softWrap = true) },
                                    selected = active, colors = itemColors,
                                    onClick = { closeThen(active) {
                                        if (route != null) navigateWorkspace(route) else if (tab != null) navigateTab(tab)
                                    } },
                                    modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp).testTag(
                                        if (route != null) "navigation-workspace-" + route.name.lowercase()
                                        else "navigation-primary-" + tab!!.name.lowercase()),
                                )
                            }
                        }'''+text[end:]
put(path,text)

path='app/src/main/java/ru/omnicio/app/MainActivity.kt'
text=get(path)
text=text.replace('import ru.omnicio.app.ui.AnalystTab\n', '''import ru.omnicio.app.ui.AnalystTab
import ru.omnicio.app.ui.analystDestination
import ru.omnicio.app.ui.sectionBackStack
import ru.omnicio.app.ui.LocalAnalystSectionNavigator
''')
text=text.replace('enabled = screen !in setOf(AppScreen.Home, AppScreen.Recommendations, AppScreen.Profile)',
                  'enabled = screen !in setOf(AppScreen.Recommendations, AppScreen.Profile)')
anchor='    CompositionLocalProvider(LocalWorkspaceBackProgress provides backProgress, LocalReauthenticate provides reauthenticate,'
assert text.count(anchor)==1
text=text.replace(anchor,'''    val selectSection: (String) -> Unit = { id ->
        val destination = AppScreen.entries.firstOrNull { it.name == id }
        val parentStack = sectionBackStack(id)
        if (destination != null && parentStack != null && destination != screen) {
            navigate(destination)
            backStack = ArrayList(parentStack)
        }
    }
    CompositionLocalProvider(LocalAnalystSectionNavigator provides selectSection,
        LocalWorkspaceBackProgress provides backProgress, LocalReauthenticate provides reauthenticate,''')
text=text.replace('    val navigateToTab: (AnalystTab) -> Unit = { onScreenChange(it.toAppScreen()) }',
                  '    val selectSection = LocalAnalystSectionNavigator.current\n    val navigateToTab: (AnalystTab) -> Unit = { selectSection(it.toAppScreen().name) }')
text=text.replace('wide = wide, navigateTab = navigateToTab, navigateWorkspace = navigateWorkspace,',
                  'wide = wide, navigateTab = navigateToTab, navigateWorkspace = { route ->\n                    if (route == WorkspaceRoute.Reports) reportId = null\n                    selectSection(route.name)\n                },')
start=text.index('private fun screenTitle(name: String): String = when (name)')
end=text.index('\nprivate fun AnalystTab.toAppScreen',start)
text=text[:start]+'''private fun screenTitle(name: String): String = analystDestination(name)?.title ?: "Analyst AI"
'''+text[end:]
put(path,text)

path=UI+'profile/ProfileScreen.kt'
text=get(path).replace('    val theme = LocalThemePreference.current\n','')
text=text.replace('theme.mode.title + " · размер и плотность элементов"', '"Единый стиль · движение и удобство"')
start=text.index('                item(key = "tools-settings")')
end=text.index('                item(key = ',start+30)
text=text[:start]+text[end:]
put(path,text)

path=UI+'home/HomeScreen.kt'
text=get(path)
text=text.replace('/** The home describes server work. Portfolio values stay in the analysis pipeline. */',
                  '/** Real capital first; analysis state and its blockers retain their own source/time. */')
text=text.replace('Text("Система", style = MaterialTheme.typography.headlineLarge,',
                  'Text("Главная", style = MaterialTheme.typography.headlineLarge,')
anchor='                item(key = "automation-state") {'
assert text.count(anchor)==1
text=text.replace(anchor,'''                item(key = "portfolio-overview") {
                    HomePortfolioHero(state, selectedCurrency, refreshing, refreshError,
                        onOpenPortfolio, onConnect)
                }
                item(key = "portfolio-actions") {
                    HomePortfolioActions(onOpenRisk, { navigate(WorkspaceRoute.Strategies) },
                        { navigate(WorkspaceRoute.Assistant) })
                }
'''+anchor)
text=text.replace('Text(title, style = MaterialTheme.typography.headlineMedium,',
                  'Text(title, style = MaterialTheme.typography.titleLarge,')
text=text.replace('Text("Подключения и режим", style = MaterialTheme.typography.titleLarge)',
                  'DetailFold("Подключения и режим") {')
anchor='                item(key = "system-history") {'
pos=text.index(anchor)
text=text[:pos]+text[pos:]
before=text[:pos]
closing='                    }\n                }\n'
assert before.endswith(closing)
text=before[:-len(closing)]+'                        }\n'+closing+text[pos:]
put(path,text)

put(UI+'home/HomePortfolioHero.kt', '''package ru.omnicio.app.ui.home

import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import ru.omnicio.app.data.portfolio.*
import ru.omnicio.app.ui.portfolio.SignedAmount
import ru.omnicio.app.ui.portfolio.moneyText
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.workspace.*

@Composable
internal fun HomePortfolioHero(state: PortfolioUiState, currency: PortfolioCurrency,
    refreshing: Boolean, error: String?, onPortfolio: () -> Unit, onConnect: () -> Unit) {
    val snapshot = (state as? PortfolioUiState.Ready)?.snapshot
    SpectrumCard(Modifier.testTag("home-real-portfolio"), emphasized = true) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            SpectrumIcon(SpectrumSymbol.Portfolio, Modifier.size(40.dp), selected = true)
            Text("Мой портфель", Modifier.weight(1f), style = MaterialTheme.typography.titleLarge)
        }
        if (snapshot != null) {
            Text(snapshot.totalValue.moneyText(), style = MaterialTheme.typography.headlineLarge,
                fontWeight = FontWeight.Bold, modifier = Modifier.testTag("home-portfolio-balance"))
            if (snapshot.expectedYieldAmount != null || snapshot.expectedYieldPercent != null) {
                SignedAmount(snapshot.expectedYieldAmount, snapshot.expectedYieldPercent)
                Text("Текущий результат брокера", style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text("Данные: " + relativeObservation(snapshot.asOf) + if (refreshing) " · обновляем" else "",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (snapshot.totalValue.currency != currency.name)
                Text("Оценка в ${snapshot.totalValue.currency}; запрошена ${currency.name}", style = MaterialTheme.typography.bodySmall)
            if (error != null) Text("Сохранённый срез · $error", color = MaterialTheme.colorScheme.error)
            if (snapshot.warnings.isNotEmpty()) SpectrumBadge("Есть ограничения данных", accent = LocalSpectrumPalette.current.amber)
            SpectrumPrimaryButton("Открыть портфель", onPortfolio, Modifier.fillMaxWidth())
        } else when (state) {
            PortfolioUiState.Loading, PortfolioUiState.ApiConnected -> {
                SpectrumLoadingIndicator(description = "Получаем портфель")
                Text("Получаем счета и активы", style = MaterialTheme.typography.titleMedium)
                Text("Стоимость появится после ответа источника.", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            is PortfolioUiState.Error -> {
                Text("Данные пока недоступны", style = MaterialTheme.typography.titleMedium)
                Text(state.message, color = MaterialTheme.colorScheme.error)
                SpectrumSecondaryButton("Открыть портфель", onPortfolio, Modifier.fillMaxWidth())
            }
            else -> {
                Text("Ваш капитал в одном месте", style = MaterialTheme.typography.titleMedium)
                Text("Подключите данные счёта, чтобы видеть стоимость, состав и изменения.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                SpectrumPrimaryButton("Подключить портфель", onConnect, Modifier.fillMaxWidth())
            }
        }
    }
}

@Composable
internal fun HomePortfolioActions(onRisk: () -> Unit, onStrategy: () -> Unit, onAnalyst: () -> Unit) {
    val font = LocalDensity.current.fontScale
    BoxWithConstraints(Modifier.fillMaxWidth()) {
        val actions = listOf(Triple("Риски", SpectrumSymbol.Risk, onRisk),
            Triple("Стратегия", SpectrumSymbol.Goal, onStrategy), Triple("Аналитик", SpectrumSymbol.Analyst, onAnalyst))
        if (font >= 1.5f || maxWidth < 320.dp) {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                actions.forEach { (title, symbol, click) ->
                    SpectrumTextButton(title, click, Modifier.fillMaxWidth(), symbol = symbol)
                }
            }
        } else Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            actions.forEach { (title, symbol, click) ->
                SpectrumCard(Modifier.weight(1f), onClick = click) {
                    SpectrumIcon(symbol, Modifier.align(Alignment.CenterHorizontally).size(32.dp), selected = true)
                    Text(title, Modifier.align(Alignment.CenterHorizontally), style = MaterialTheme.typography.labelMedium)
                }
            }
        }
    }
}
''')

path=UI+'spatial/SpatialComponents.kt'
text=get(path).replace('import androidx.compose.ui.graphics.Color\n',
                       'import androidx.compose.ui.graphics.Color\nimport androidx.compose.ui.graphics.Brush\nimport androidx.compose.ui.graphics.lerp\n')
text=text.replace('SpatialSurfaceKind.Card -> 18.dp','SpatialSurfaceKind.Card -> 22.dp')
text=text.replace('val borderWidth = if (state == SpatialState.Selected) 2.dp else 1.dp', '''val borderWidth = if (state == SpatialState.Selected) 2.dp else 1.dp
    val tint = if (emphasized) palette.colors.secondaryContainer else palette.colors.surfaceContainerLow
    val gradient = Brush.verticalGradient(listOf(fill, if (kind == SpatialSurfaceKind.Card && !highContrast)
        lerp(fill, tint, .35f) else fill))''')
text=text.replace('.clip(shape).background(fill).border(borderWidth, border, shape)',
                  '.clip(shape).background(gradient).border(borderWidth, border, shape)')
put(path,text)

path=UI+'spectrum/SpectrumDesignSystem.kt'
text=get(path)
text=text.replace('import androidx.compose.foundation.clickable\n',
                  'import androidx.compose.foundation.clickable\nimport androidx.compose.foundation.Canvas\n')
text=text.replace('import androidx.compose.ui.graphics.Color\n',
                  'import androidx.compose.ui.graphics.Color\nimport androidx.compose.ui.graphics.Brush\nimport androidx.compose.ui.geometry.CornerRadius\nimport androidx.compose.ui.geometry.Offset\nimport androidx.compose.ui.geometry.Size\nimport androidx.compose.ui.graphics.drawscope.clipRect\n')
text=text.replace('val LightSpectrumPalette = spectrumPalette(dark = false)',
                  '// Legacy preview alias: there is no second production colorway.\nval LightSpectrumPalette = DarkSpectrumPalette')
text=text.replace('    val compact = LocalWorkspacePreferences.current.value.density == InterfaceDensity.COMPACT\n','')
text=text.replace('padding(if (compact) 12.dp else 18.dp)', 'padding(16.dp)')
text=text.replace('Arrangement.spacedBy(if (compact) 8.dp else 10.dp)', 'Arrangement.spacedBy(10.dp)')
# Buttons keep a paired opaque foreground while the surface supplies restrained depth.
start=text.index('fun SpectrumPrimaryButton(')
end=text.index('\n@Composable\nfun SpectrumSecondaryButton',start)
block=text[start:end].replace('MaterialTheme.colorScheme.primary else', 'MaterialTheme.colorScheme.primaryContainer else')
block=block.replace('MaterialTheme.colorScheme.onPrimary else', 'MaterialTheme.colorScheme.onPrimaryContainer else')
text=text[:start]+block+text[end:]
start=text.index('@Composable\nfun SpectrumProgressBar(')
end=text.index('/** Original vector illustration',start)
text=text[:start]+'''/** The fill always represents the supplied fraction; only its light cycles. */
@Composable
fun SpectrumProgressBar(fraction: Float, modifier: Modifier = Modifier, accent: Color = LocalSpectrumPalette.current.cyan,
    enabled: Boolean = true) {
    if (!fraction.isFinite()) return
    val progress = fraction.coerceIn(0f, 1f)
    val palette = LocalSpectrumPalette.current
    val light = rememberLiveDecoration(enabled && progress > 0f && progress < 1f)
    Canvas(modifier.fillMaxWidth().height(10.dp).then(light.modifier).semantics {
        progressBarRangeInfo = ProgressBarRangeInfo(progress, 0f..1f)
    }) {
        val radius = CornerRadius(size.height / 2)
        drawRoundRect(if (enabled) palette.colors.surfaceContainerHighest else palette.semantic.disabledContainer, cornerRadius = radius)
        if (progress > 0f) {
            val width = size.width * progress
            drawRoundRect(Brush.horizontalGradient(if (enabled) listOf(accent, palette.colors.secondary)
                else listOf(palette.semantic.disabledInk, palette.semantic.disabledInk)),
                size = Size(width, size.height), cornerRadius = radius)
            // A draw-only highlight stays within the real filled fraction.
            val phase = light.phase.value
            if (phase > 0f) clipRect(right = width) {
                val band = size.height * 3f
                val x = (width + band * 2) * phase - band
                drawRect(Brush.horizontalGradient(listOf(Color.Transparent,
                    palette.colors.onBackground.copy(alpha = .32f), Color.Transparent), x - band, x + band),
                    topLeft = Offset(x - band, 1f), size = Size(band * 2, (size.height - 2).coerceAtLeast(0f)))
            }
        }
    }
}

'''+text[end:]
put(path,text)
