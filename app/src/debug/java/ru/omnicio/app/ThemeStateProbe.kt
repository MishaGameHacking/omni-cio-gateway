package ru.omnicio.app

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.input.pointer.PointerEventPass
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.unit.dp
import androidx.compose.ui.zIndex
import ru.omnicio.app.ui.*
import ru.omnicio.app.ui.spatial.*
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.theme.LocalThemePreference
import ru.omnicio.app.ui.theme.ThemeMode
import ru.omnicio.app.ui.workspace.*
import ru.omnicio.app.ui.portfolio.Moscow
import ru.omnicio.app.ui.portfolio.PeriodControls
import ru.omnicio.app.ui.portfolio.PortfolioPeriod
import java.time.LocalDate

/** Debug-only, finite observations of production components. No model, account or network. */
internal data class ThemeProbeRequest(
    val group: String, val mode: ThemeMode, val accent: AccentStyle,
    val motion: MotionLevel, val run: String,
) {
    companion object {
        fun parse(group: String?, mode: String?, accent: String?, motion: String?, run: String): ThemeProbeRequest {
            require(group in setOf("actions", "fields", "canvas", "overlay", "calendar"))
            require(run.matches(Regex("[a-f0-9]{32}")))
            return ThemeProbeRequest(requireNotNull(group), ThemeMode.valueOf(requireNotNull(mode)),
                AccentStyle.valueOf(requireNotNull(accent)), MotionLevel.valueOf(requireNotNull(motion)), run)
        }
    }
}

private fun Color.themeHex() = toArgb().toUInt().toString(16).padStart(8, '0')

@Composable
private fun ThemeSample(id: String, modifier: Modifier = Modifier,
    background: Color = MaterialTheme.colorScheme.surface, content: @Composable BoxScope.() -> Unit) {
    Box(modifier.background(background).testTag("theme-sample-$id"), content = content)
}

@Composable
private fun ThemeMarker(request: ThemeProbeRequest, original: String, state: String,
    modifier: Modifier = Modifier) {
    val theme = LocalThemePreference.current
    val workspace = LocalWorkspacePreferences.current.value
    val context = LocalContext.current
    val savedMode = context.getSharedPreferences("analyst_ai_settings", 0).getString("theme_mode", "")
    val savedAccent = context.getSharedPreferences("workspace_appearance", 0).getString("accent", "")
    val savedMotion = context.getSharedPreferences("workspace_appearance", 0).getString("motion", "")
    val colors = themeObservedColors()
    val marker = "theme-probe:production-v1;theme-group:${request.group};theme-run:${request.run};" +
        "theme-mode:${theme.mode.name};theme-accent:${workspace.accent.name};theme-motion:${workspace.motion.name};" +
        "theme-saved-mode:$savedMode;theme-saved-accent:$savedAccent;theme-saved-motion:$savedMotion;" +
        "theme-font-scale:${LocalDensity.current.fontScale};theme-density:${LocalDensity.current.density};" +
        "theme-original:$original;theme-state:$state;theme-colors:$colors"
    Box(modifier.size(2.dp).zIndex(100f).clearAndSetSemantics { contentDescription = marker })
}

@Composable
internal fun ThemeStateProbe(request: ThemeProbeRequest) {
    val theme = LocalThemePreference.current
    val preferences = LocalWorkspacePreferences.current
    val original = remember { "${theme.mode.name},${preferences.value.accent.name},${preferences.value.motion.name}" }
    LaunchedEffect(request) {
        // Exercise the same saved preference path as Apply, never a fixture-only ColorScheme.
        theme.select(request.mode)
        preferences.update(preferences.value.copy(accent = request.accent, motion = request.motion))
    }
    var actionCount by rememberSaveable(request.run) { mutableIntStateOf(0) }
    var primaryDown by remember { mutableStateOf(false) }
    var nativeChecked by rememberSaveable(request.run) { mutableStateOf(false) }
    var spatialChecked by rememberSaveable(request.run) { mutableStateOf(false) }
    var choice by rememberSaveable(request.run) { mutableStateOf(false) }
    var tab by rememberSaveable(request.run) { mutableIntStateOf(0) }
    var selected by rememberSaveable(request.run) { mutableIntStateOf(-1) }
    var input by rememberSaveable(request.run) { mutableStateOf("ТЕМА") }
    var selectedTab by rememberSaveable(request.run) { mutableStateOf(AnalystTab.Home) }
    var dialog by rememberSaveable(request.run) { mutableStateOf(false) }
    val calendarToday = remember(request.run) { LocalDate.now(Moscow) }
    var periodStart by rememberSaveable(request.run) { mutableStateOf(calendarToday.minusDays(2).toString()) }
    var periodEnd by rememberSaveable(request.run) { mutableStateOf(calendarToday.minusDays(1).toString()) }
    val overlay = when ((preferences.value.accent.ordinal +
        (if (theme.mode == ThemeMode.DARK) 2 else 0) + (if (LocalDensity.current.fontScale > 1.5f) 1 else 0)) % 3) {
        0 -> "drawer"; 1 -> "dialog"; else -> "rail"
    }
    val state = "clicks=$actionCount,down=$primaryDown,native=$nativeChecked,spatial=$spatialChecked,choice=$choice," +
        "tab=$tab,selected=$selected,input=$input,destination=${selectedTab.name},overlay=$overlay,dialog=$dialog," +
        "period=$periodStart/$periodEnd/$calendarToday"
    SpectrumBackground(Modifier.fillMaxSize().semantics { testTagsAsResourceId = true }) {
        if (request.group == "overlay") {
            BoxWithConstraints(Modifier.fillMaxSize()) {
                val wide = maxWidth >= 600.dp
                CompositionLocalProvider(LocalAnalystTabNavigator provides { selectedTab = it }) {
                    AnalystNavigationPanels(selectedTab, wide = wide,
                        navigateTab = { selectedTab = it }, navigateWorkspace = {}) {
                        Column(Modifier.fillMaxSize().safeDrawingPadding(), verticalArrangement = Arrangement.SpaceBetween) {
                            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                Text("ТЕСТ ЦВЕТА", style = MaterialTheme.typography.labelSmall)
                                SpectrumPrimaryButton("Окно", { dialog = true },
                                    Modifier.fillMaxWidth().testTag("theme-control-dialog-open"))
                                Text("Только синтетические данные", style = MaterialTheme.typography.bodySmall)
                            }
                            AnalystBottomBar(selectedTab, {}, {})
                        }
                    }
                }
            }
        } else {
            Column(Modifier.fillMaxSize().safeDrawingPadding().verticalScroll(rememberScrollState())
                .testTag("workspace-content").padding(8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text("ТЕСТ ЦВЕТА", style = MaterialTheme.typography.labelSmall)
                when (request.group) {
                    "actions" -> {
                        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                            ThemeSample("primary", Modifier.weight(1f).pointerInput(Unit) {
                                // Observe the real pointer without consuming it or setting a control state.
                                awaitPointerEventScope {
                                    while (true) primaryDown = awaitPointerEvent(PointerEventPass.Final).changes.any { it.pressed }
                                }
                            }) {
                                SpectrumPrimaryButton("Да", { actionCount++ }, Modifier.fillMaxWidth()
                                    .testTag("theme-control-primary"))
                            }
                            ThemeSample("primary-disabled", Modifier.weight(1f)) {
                                SpectrumPrimaryButton("Нет", { actionCount++ }, Modifier.fillMaxWidth()
                                    .testTag("theme-control-primary-disabled"), enabled = false)
                            }
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                            ThemeSample("secondary", Modifier.weight(1f)) {
                                SpectrumSecondaryButton("Е", { actionCount++ }, Modifier.fillMaxWidth())
                            }
                            ThemeSample("secondary-disabled", Modifier.weight(1f)) {
                                SpectrumSecondaryButton("Н", { actionCount++ }, Modifier.fillMaxWidth(), enabled = false)
                            }
                            ThemeSample("text", Modifier.weight(1f)) {
                                SpectrumTextButton("Т", { actionCount++ }, Modifier.fillMaxWidth())
                            }
                            ThemeSample("text-disabled", Modifier.weight(1f)) {
                                SpectrumTextButton("Н", {}, Modifier.fillMaxWidth(), enabled = false)
                            }
                        }
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
                            listOf("native-on", "native-off", "native-disabled-on", "native-disabled-off").forEachIndexed { i, id ->
                                ThemeSample(id, Modifier.size(64.dp, 48.dp)) {
                                    SpectrumSwitch(checked = when (i) { 0 -> nativeChecked; 2 -> true; else -> false },
                                        onCheckedChange = { value -> if (i == 0) nativeChecked = value },
                                        enabled = i < 2, modifier = Modifier.align(Alignment.Center)
                                            .testTag("theme-control-$id"))
                                }
                            }
                        }
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
                            listOf("spatial-on", "spatial-off", "spatial-disabled-on", "spatial-disabled-off").forEachIndexed { i, id ->
                                val checked = when (i) { 0 -> spatialChecked; 2 -> true; else -> false }
                                ThemeSample(id, Modifier.size(64.dp, 48.dp)) {
                                    Box(Modifier.fillMaxSize().testTag("theme-control-$id").toggleable(checked,
                                        enabled = i < 2, role = Role.Switch,
                                        onValueChange = { if (i == 0) spatialChecked = it }), contentAlignment = Alignment.Center) {
                                        SpatialToggleVisual(checked, Modifier.size(46.dp, 28.dp), enabled = i < 2)
                                    }
                                }
                            }
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                            ThemeSample("choice", Modifier.weight(1f)) {
                                SpectrumChoiceChip(choice, { choice = !choice }, { Text("Да") },
                                    Modifier.fillMaxWidth().testTag("theme-control-choice"))
                            }
                            ThemeSample("choice-disabled", Modifier.weight(1f)) {
                                SpectrumChoiceChip(true, {}, { Text("Нет") }, Modifier.fillMaxWidth(), enabled = false)
                            }
                        }
                        ThemeSample("tabs", Modifier.fillMaxWidth()) {
                            CompositionLocalProvider(LocalSpectrumTabScrollTag provides "theme-tabs") {
                                SpectrumTabs(listOf("А", "Б"), tab, { tab = it })
                            }
                        }
                    }
                    "fields" -> {
                        ThemeSample("input", Modifier.fillMaxWidth()) {
                            SpectrumTextField(input, { input = it }, Modifier.fillMaxWidth().testTag("theme-control-input"), singleLine = true)
                        }
                        ThemeSample("input-error", Modifier.fillMaxWidth()) {
                            SpectrumTextField("Ошибка", {}, Modifier.fillMaxWidth(), readOnly = true, isError = true, singleLine = true)
                        }
                        ThemeSample("input-disabled", Modifier.fillMaxWidth()) {
                            SpectrumTextField("Недоступно", {}, Modifier.fillMaxWidth(), enabled = false, singleLine = true)
                        }
                        val p = LocalSpectrumPalette.current
                        listOf(listOf("success" to ("Успех" to p.emerald), "warning" to ("Риск" to p.amber)),
                            listOf("error" to ("Ошибка" to p.rose), "info" to ("Инфо" to p.blue))).forEach { row ->
                            Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                                row.forEach { (id, badge) -> ThemeSample(id, Modifier.weight(1f)) {
                                    SpectrumBadge(badge.first, Modifier.fillMaxWidth(), accent = badge.second)
                                } }
                            }
                        }
                        ThemeSample("slider", Modifier.fillMaxWidth()) {
                            SpectrumSlider(.65f, {}, Modifier.fillMaxWidth().testTag("theme-control-slider"))
                        }
                        ThemeSample("slider-disabled", Modifier.fillMaxWidth()) {
                            SpectrumSlider(.65f, {}, Modifier.fillMaxWidth().testTag("theme-control-slider-disabled"), enabled = false)
                        }
                    }
                    "canvas" -> {
                        val p = LocalSpectrumPalette.current
                        val values = listOf(-20.0, 0.0, null, 10.0, 40.0, 80.0)
                        ThemeSample("bars", Modifier.fillMaxWidth().height(130.dp)) {
                            SpatialChartGuides(6, .8f, setOf(2), modifier = Modifier.fillMaxSize())
                            SpatialBars(values, -20.0, 80.0, selected.takeIf { it >= 0 }, Modifier.fillMaxSize(),
                                colors = historyBarColors(p, values))
                        }
                        ThemeSample("ring", Modifier.fillMaxWidth().height(132.dp)) {
                            SpatialRing(listOf(30.0, 20.0, 15.0, 15.0, 10.0, 10.0), p.chartSeries,
                                selected.takeIf { it >= 0 }, Modifier.align(Alignment.Center).size(132.dp))
                        }
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
                            ThemeSample("mono", Modifier.size(64.dp), background = p.colors.primary) {
                                SpatialIcon("home", Modifier.fillMaxSize(), tint = p.colors.onPrimary,
                                    colorMode = SpatialColorMode.Monochrome, motionAllowed = false)
                            }
                            ThemeSample("decorative", Modifier.size(64.dp)) {
                                SpatialIcon("brand", Modifier.fillMaxSize(), colorMode = SpatialColorMode.Decorative, motionAllowed = false)
                            }
                            ThemeSample("decorative-disabled", Modifier.size(64.dp)) {
                                SpatialIcon("brand", Modifier.fillMaxSize(), state = SpatialState.Disabled,
                                    colorMode = SpatialColorMode.Decorative, motionAllowed = false)
                            }
                        }
                        SpectrumPrimaryButton("Выбор", { selected = 4 },
                            Modifier.fillMaxWidth().testTag("theme-control-select"))
                    }
                    "calendar" -> PeriodControls(PortfolioPeriod(periodStart, periodEnd)) { period ->
                        periodStart = period.start.orEmpty(); periodEnd = period.end.orEmpty()
                    }
                }
            }
        }
        ThemeMarker(request, original, state, Modifier.align(Alignment.TopStart))
    }
    if (request.group == "overlay" && dialog) {
        SpectrumAlertDialog(onDismissRequest = { dialog = false },
            title = { Text("Тестовое окно") },
            text = {
                Box {
                    ThemeSample("dialog-label", Modifier.fillMaxWidth()) {
                        Text("Читаемый текст", color = MaterialTheme.colorScheme.onSurface)
                    }
                    ThemeMarker(request, original, state)
                }
            },
            confirmButton = {
                ThemeSample("dialog-primary", Modifier.fillMaxWidth()) {
                    SpectrumPrimaryButton("OK", { dialog = false },
                        Modifier.fillMaxWidth().testTag("theme-control-dialog-close"))
                }
            })
    }
}

// The complete map is read from the live Material/Spectrum composition, never from requested inputs.
@Composable
private fun themeObservedColors(): String {
    val m = MaterialTheme.colorScheme
    val p = LocalSpectrumPalette.current
    val s = p.semantic
    val actual = listOf(
        "primary" to m.primary,
        "onPrimary" to m.onPrimary,
        "primaryContainer" to m.primaryContainer,
        "onPrimaryContainer" to m.onPrimaryContainer,
        "inversePrimary" to m.inversePrimary,
        "secondary" to m.secondary,
        "onSecondary" to m.onSecondary,
        "secondaryContainer" to m.secondaryContainer,
        "onSecondaryContainer" to m.onSecondaryContainer,
        "tertiary" to m.tertiary,
        "onTertiary" to m.onTertiary,
        "tertiaryContainer" to m.tertiaryContainer,
        "onTertiaryContainer" to m.onTertiaryContainer,
        "background" to m.background,
        "onBackground" to m.onBackground,
        "surface" to m.surface,
        "onSurface" to m.onSurface,
        "surfaceVariant" to m.surfaceVariant,
        "onSurfaceVariant" to m.onSurfaceVariant,
        "surfaceTint" to m.surfaceTint,
        "inverseSurface" to m.inverseSurface,
        "inverseOnSurface" to m.inverseOnSurface,
        "error" to m.error,
        "onError" to m.onError,
        "errorContainer" to m.errorContainer,
        "onErrorContainer" to m.onErrorContainer,
        "outline" to m.outline,
        "outlineVariant" to m.outlineVariant,
        "scrim" to m.scrim,
        "surfaceBright" to m.surfaceBright,
        "surfaceDim" to m.surfaceDim,
        "surfaceContainer" to m.surfaceContainer,
        "surfaceContainerHigh" to m.surfaceContainerHigh,
        "surfaceContainerHighest" to m.surfaceContainerHighest,
        "surfaceContainerLow" to m.surfaceContainerLow,
        "surfaceContainerLowest" to m.surfaceContainerLowest,
        "primaryFixed" to m.primaryFixed,
        "primaryFixedDim" to m.primaryFixedDim,
        "onPrimaryFixed" to m.onPrimaryFixed,
        "onPrimaryFixedVariant" to m.onPrimaryFixedVariant,
        "secondaryFixed" to m.secondaryFixed,
        "secondaryFixedDim" to m.secondaryFixedDim,
        "onSecondaryFixed" to m.onSecondaryFixed,
        "onSecondaryFixedVariant" to m.onSecondaryFixedVariant,
        "tertiaryFixed" to m.tertiaryFixed,
        "tertiaryFixedDim" to m.tertiaryFixedDim,
        "onTertiaryFixed" to m.onTertiaryFixed,
        "onTertiaryFixedVariant" to m.onTertiaryFixedVariant,
        "success" to s.success,
        "onSuccess" to s.onSuccess,
        "successContainer" to s.successContainer,
        "onSuccessContainer" to s.onSuccessContainer,
        "warning" to s.warning,
        "onWarning" to s.onWarning,
        "warningContainer" to s.warningContainer,
        "onWarningContainer" to s.onWarningContainer,
        "info" to s.info,
        "onInfo" to s.onInfo,
        "infoContainer" to s.infoContainer,
        "onInfoContainer" to s.onInfoContainer,
        "disabledInk" to s.disabledInk,
        "disabledContainer" to s.disabledContainer,
        "chartGrid" to s.chartGrid,
        "chartAxis" to s.chartAxis,
        "chartSeparator" to s.chartSeparator,
        "chartSelectedInner" to s.chartSelectedInner,
        "chartSelectedOuter" to s.chartSelectedOuter,
    ) + p.chartSeries.mapIndexed { index, color -> "series$index" to color } + listOf(
        "pressedPrimary" to spatialSurfaceColors(p, m.primary, SpatialState.Pressed,
            interactive = true, emphasized = false, highContrast = false).fill,
    )
    return actual.joinToString(",") { (name, color) -> "$name=${color.themeHex()}" }
}
