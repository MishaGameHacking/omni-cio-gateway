package ru.omnicio.app

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spatial.*
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.theme.LocalThemePreference
import ru.omnicio.app.ui.theme.ThemeMode
import ru.omnicio.app.ui.workspace.*
import kotlinx.coroutines.delay

/** Actual renderer observations. This marker never substitutes for captured pixels. */
@Composable
internal fun spatialProbeMarker(): String {
    val stats = spatialDiagnostics()
    val counters = LocalFlatDrawStats.current
    val motion = LocalFlatMotion.current
    val context = androidx.compose.ui.platform.LocalContext.current
    val power = remember(context) { context.getSystemService(android.os.PowerManager::class.java) }
    val draws by produceState(counters?.operations ?: 0L, counters) {
        while (true) { value = counters?.operations ?: 0L; delay(200) }
    }
    return "probe-renderer:native-2d;probe-flat-draws:$draws;" +
        "probe-spatial-engines:0;probe-spatial-windows:0;" +
        "probe-spatial-frames:0;probe-spatial-meshes:0;" +
        "probe-spatial-pending:0;probe-spatial-pool:0;" +
        "probe-spatial-error:none;probe-spatial-motion:" + motion.name + ";" +
        "probe-spatial-cpu-p95:0.0;probe-spatial-interval-p95:0.0;" +
        "probe-spatial-quality:native-2d;probe-spatial-density:" + LocalDensity.current.density + ";" +
        "probe-spatial-font-scale:" + LocalDensity.current.fontScale + ";" +
        "probe-spatial-orientation:" + LocalConfiguration.current.orientation + ";" +
        "probe-spatial-thermal:" + power.currentThermalStatus + ";" +
        "probe-spatial-system-motion:" + android.animation.ValueAnimator.areAnimatorsEnabled() + ";" +
        "probe-spatial-power-save:" + power.isPowerSaveMode + ";" +
        "probe-spatial-back-progress:" + (LocalFlatBack.current?.value ?: 0f)

}

/** Synthetic geometry/input fixture only. No account, broker, credentials or network. */
@Composable
internal fun SpatialRendererProbe() {
    val preferences = LocalWorkspacePreferences.current
    val theme = LocalThemePreference.current
    val palette = LocalSpectrumPalette.current
    var section by rememberSaveable { mutableIntStateOf(0) }
    var checked by rememberSaveable { mutableStateOf(false) }
    var clicks by rememberSaveable { mutableIntStateOf(0) }
    var input by rememberSaveable { mutableStateOf("native") }
    var shadows by rememberSaveable { mutableStateOf(true) }
    LaunchedEffect(shadows) { preferences.preview(preferences.value.copy(depth = shadows)) }
    var dialog by remember { mutableStateOf(false) }
    var selected by rememberSaveable { mutableIntStateOf(0) }
    var backScreen by rememberSaveable { mutableStateOf(false) }
    var backCommits by rememberSaveable { mutableIntStateOf(0) }
    val list = rememberLazyListState()
    LaunchedEffect(Unit) {
        theme.preview(ThemeMode.DARK)
        preferences.preview(preferences.value.copy(motion = MotionLevel.LIVE, accent = AccentStyle.AURORA))
    }
    DisposableEffect(Unit) { onDispose { theme.cancelPreview(); preferences.cancelPreview() } }
    LaunchedEffect(section) { list.scrollToItem(0) }
    if (backScreen) {
        SpatialBackHandler { backCommits++; backScreen = false }
        Column(Modifier.fillMaxSize().safeDrawingPadding().padding(20.dp),
            horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(20.dp)) {
            Text("ВИЗУАЛЬНЫЙ ТЕСТ · НЕ РЕАЛЬНЫЕ ДАННЫЕ", style = MaterialTheme.typography.labelSmall)
            Text("Экран возврата", style = MaterialTheme.typography.headlineMedium)
            SpatialIcon("back", Modifier.size(128.dp), tint = palette.cyan)
            Text("Подтверждённых возвратов: $backCommits")
            Text("Системный жест управляет настоящей сценой. Отмена оставляет этот экран открытым.")
        }
        return
    }
    Column(Modifier.fillMaxSize().safeDrawingPadding().semantics { testTagsAsResourceId = true }) {
        Text("ВИЗУАЛЬНЫЙ ТЕСТ · НЕ РЕАЛЬНЫЕ ДАННЫЕ", Modifier.padding(12.dp),
            style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onBackground)
        SpectrumTabs(listOf("Форма 2D", "Графики 2D", "Отсечение 2D", "Нагрузка", "Правила 2D"), section, { section = it })
        LazyColumn(Modifier.weight(1f).fillMaxWidth().testTag("workspace-content"), state = list,
            contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            when (section) {
    0 -> {
                    item {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
                            Box(Modifier.size(112.dp).testTag("spatial-mesh-swatch")
                                .semantics { contentDescription = "Изолированная цветная иллюстрация" }) {
                                SpatialIcon("brand", Modifier.align(Alignment.Center).size(88.dp), tint = palette.cyan)
                            }
                            SpectrumAssetMark("stock", "Тест", Modifier.size(72.dp))
                        }
                    }
                    item {
                        SpectrumPrimaryButton("Проверить нажатие", { clicks++ }, Modifier.fillMaxWidth().testTag("spatial-action"))
                        Text("Нажатий: $clicks", Modifier.testTag("spatial-click-result"))
                    }
                    item { WorkspaceToggle("Тестовый переключатель", if (checked) "Включён" else "Выключен", checked) { checked = it } }
                    item { SpectrumTextField(input, { input = it }, Modifier.fillMaxWidth().testTag("spatial-input"),
                        label = { Text("Нативное поле 2D") }, singleLine = true) }
                    item { SpectrumTextButton(if (shadows) "Тени: включены" else "Тени: выключены",
                        { shadows = !shadows }) }
                    item {
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            SpectrumTextButton("Тёмная модель", { theme.preview(ThemeMode.DARK) })
                            SpectrumTextButton("Светлая модель", { theme.preview(ThemeMode.LIGHT) })
                        }
                    }
                    item {
                        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            MotionLevel.entries.forEach { mode -> SpectrumChoiceChip(preferences.value.motion == mode,
                                { preferences.preview(preferences.value.copy(motion = mode)) }, { Text(mode.name) },
                                Modifier.weight(1f)) }
                        }
                        Text("Режим: ${preferences.value.motion.name}")
                    }
                    item { SpectrumTextButton("Открыть окно 2D", { dialog = true }, Modifier.fillMaxWidth().testTag("spatial-open-dialog")) }
                    item {
                        SpectrumSymbol.entries.take(15).chunked(5).forEach { symbols ->
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
                                symbols.forEach { symbol -> SpectrumIcon(symbol, Modifier.size(48.dp), tile = true) }
                            }
                        }
                    }
                } 1 -> {
                    item {
                        Text("Синтетические столбцы: −20, 0, пропуск, 10, 40, 80")
                        SpatialBars(listOf(-20.0, 0.0, null, 10.0, 40.0, 80.0), -20.0, 80.0, selected,
                            Modifier.fillMaxWidth().height(144.dp).testTag("spatial-bars")
                                .semantics { contentDescription = "Столбцы: минус20; ноль; нет наблюдения;10;40;80. Шкала от минус20 до80." })
                    }
                    item {
                        Text("Синтетические OHLC: 100/120/95/115; 115/130/110/112; 112/125/108/112")
                        SpatialCandles(listOf(SpatialCandle(100.0,120.0,95.0,115.0), SpatialCandle(115.0,130.0,110.0,112.0),
                            SpatialCandle(112.0,125.0,108.0,112.0)), 90.0, 140.0, selected,
                            Modifier.fillMaxWidth().height(144.dp).testTag("spatial-candles")
                                .semantics { contentDescription = "Три синтетические свечи. Третья имеет равные открытие и закрытие112." })
                    }
                    item {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(18.dp)) {
                            SpatialRing(listOf(50.0,30.0,20.0), listOf(palette.cyan,palette.violet,palette.amber), selected,
                                Modifier.size(132.dp).testTag("spatial-ring").semantics { contentDescription = "Доли:50 процентов;30 процентов;20 процентов" })
                            Text("Доли: 50% / 30% / 20%")
                        }
                    }
                    item {
                        SpectrumTextButton("Выбрать второй элемент", { selected = 1 },
                            Modifier.fillMaxWidth().testTag("spatial-select-second"))
                        Text("Выбран элемент: ${selected + 1}", Modifier.testTag("spatial-selection-result"))
                    }
                } 2 -> {
                    item {
                        Text("Большая модель ограничена центральным окном. Внешняя область остаётся фоном.")
                        Box(Modifier.fillMaxWidth().height(160.dp).testTag("spatial-clip-region")
                            .semantics { contentDescription = "Внешняя область отсечения" }) {
                            Box(Modifier.align(Alignment.Center).size(144.dp,64.dp).clipToBounds()
                                .testTag("spatial-clip-window").semantics { contentDescription = "Видимая область модели" }) {
                                SpatialIcon("orbit", Modifier.requiredSize(176.dp).align(Alignment.Center), tint = palette.cyan)
                            }
                        }
                    }
                } 3 -> {
                    items(120, key = { "stress-$it" }) { index ->
                        SpectrumCard(Modifier.fillMaxWidth()) {
                            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                                SpectrumIcon(SpectrumSymbol.entries[index % 15], Modifier.size(48.dp))
                                Column(Modifier.weight(1f)) {
                                    Text("Тестовая строка ${index + 1}", style = MaterialTheme.typography.titleMedium)
                                    Text("СИНТЕТИЧЕСКИЙ ТЕСТ · список из 120 строк", style = MaterialTheme.typography.bodySmall)
                                }
                            }
                        }
                    }
                } else -> {
                    item {
                        Text("Синтетическая непрерывная модель", style = MaterialTheme.typography.titleMedium)
                        SpatialIcon("orbit", Modifier.fillMaxWidth().height(132.dp), tint = palette.cyan,
                            state = SpatialState.Loading)
                        Text("Источник политики: настройки Android и настоящий thermal listener.")
                    }
                    item {
                        SpectrumTextButton("Открыть экран возврата", { backScreen = true }, Modifier.fillMaxWidth())
                        Text("Подтверждённых возвратов: $backCommits")
                    }
                }
            }
        }
    }
    if (dialog) WorkspaceDialog("Отдельное окно 2D", { dialog = false }) {
        val marker = spatialProbeMarker()
        Text("Нативное окно с доступным полем ввода", Modifier.semantics { contentDescription = marker })
        SpatialIcon("avatar", Modifier.align(Alignment.CenterHorizontally).size(96.dp), description = "Цветной аватар в диалоге")
        SpectrumTextField(input, { input = it }, label = { Text("Поле в диалоге") }, singleLine = true)
        SpectrumTextButton("Закрыть окно 2D", { dialog = false }, Modifier.fillMaxWidth())
    }
}
