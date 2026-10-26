package ru.omnicio.app.ui.workspace

import ru.omnicio.app.ui.spatial.SpatialBackHandler as BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.mapSaver
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.theme.*
import ru.omnicio.app.ui.AnalystMenuButton
import ru.omnicio.app.ui.LocalDetailNavigationMenu
import ru.omnicio.app.ui.RegisterPanelExit

private val appearancePreferencesSaver = mapSaver(
    save = { value: WorkspacePreferences -> mapOf("accent" to value.accent.name, "density" to value.density.name,
        "depth" to value.depth, "hidden" to value.hideHomeBalance, "structure" to value.homeStructure,
        "haptics" to value.haptics, "motion" to value.motion.name, "bright" to value.brightLight) },
    restore = { saved -> WorkspacePreferences(
        accent = AccentStyle.entries.firstOrNull { it.name == saved["accent"] } ?: AccentStyle.AURORA,
        density = InterfaceDensity.entries.firstOrNull { it.name == saved["density"] } ?: InterfaceDensity.COMFORT,
        depth = saved["depth"] as? Boolean ?: true, hideHomeBalance = saved["hidden"] as? Boolean ?: false,
        homeStructure = saved["structure"] as? Boolean ?: true, haptics = saved["haptics"] as? Boolean ?: true,
        motion = MotionLevel.entries.firstOrNull { it.name == saved["motion"] } ?: MotionLevel.LIVE,
        brightLight = saved["bright"] as? Boolean ?: false,
    ) },
)

@Composable
fun AppearanceScreen(onBack: () -> Unit) {
    val controller = LocalWorkspacePreferences.current
    val theme = LocalThemePreference.current
    var savedPrefs by rememberSaveable(stateSaver = appearancePreferencesSaver) { mutableStateOf(controller.value) }
    var savedTheme by rememberSaveable { mutableStateOf(theme.mode) }
    var draft by rememberSaveable(stateSaver = appearancePreferencesSaver) { mutableStateOf(controller.value) }
    var draftTheme by rememberSaveable { mutableStateOf(theme.mode) }
    var applied by rememberSaveable { mutableStateOf(false) }
    val dirty = draft != savedPrefs || draftTheme != savedTheme
    val preview: (WorkspacePreferences) -> Unit = { next -> draft = next; controller.preview(next); applied = false }
    val cancel = { controller.cancelPreview(); theme.cancelPreview(); draft = savedPrefs; draftTheme = savedTheme; applied = false }
    val requestExit: (() -> Unit) -> Unit = { proceed -> cancel(); proceed() }
    val leave = { requestExit(onBack) }
    RegisterPanelExit(WorkspaceRoute.Appearance, requestExit)
    BackHandler(onBack = leave)
    LaunchedEffect(draft, draftTheme) {
        if (dirty) { controller.preview(draft); theme.preview(draftTheme) }
    }
    DisposableEffect(Unit) { onDispose { controller.cancelPreview(); theme.cancelPreview() } }
    WorkspaceDetailPage("Оформление", "Просмотр → применить или отменить", leave, adaptToIme = true) { padding ->
        val compact = LocalCompactWorkspaceInput.current
        LazyColumn(Modifier.fillMaxSize().semantics { testTagsAsResourceId = true }.testTag("workspace-content").padding(padding).consumeWindowInsets(padding),
            contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
            if (compact) item(key = "page-heading") {
                WorkspacePageHeading("Оформление", "Просмотр → применить или отменить")
            }
            item {
                SpectrumCard(emphasized = true) {
                    Text("Analyst AI", style = MaterialTheme.typography.headlineMedium)
                    Text("Предпросмотр цвета, контраста и движения", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Row(horizontalArrangement = Arrangement.spacedBy(20.dp)) {
                        SpectrumBrandOrb(Modifier.size(76.dp))
                        SpectrumAssetMark("share", "А", Modifier.size(64.dp))
                        SpectrumAssetMark("bond", "Б", Modifier.size(64.dp))
                    }
                    Text("Аа · 0123456789", style = MaterialTheme.typography.headlineSmall)
                    Text("Образцы оформления без финансовых значений. Проверьте удобство чтения и скорость отклика.", style = MaterialTheme.typography.bodySmall)
                    Text(if (dirty) "Предпросмотр · настройки ещё не сохранены" else if (applied) "Оформление применено" else "Текущие сохранённые настройки", style = MaterialTheme.typography.labelMedium)
                    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        SpectrumPrimaryButton("Применить", {
                            controller.preview(draft); theme.preview(draftTheme)
                            controller.applyPreview(); theme.applyPreview()
                            savedPrefs = draft; savedTheme = draftTheme; applied = true
                        }, Modifier.fillMaxWidth(), enabled = dirty)
                        SpectrumSecondaryButton("Отменить", cancel, Modifier.fillMaxWidth(), enabled = dirty)
                    }
                }
            }
            item { SpectrumCard { WorkspaceChoices("Тема", ThemeMode.entries.map { it.title },
                ThemeMode.entries.indexOf(draftTheme)) { draftTheme = ThemeMode.entries[it]; theme.preview(draftTheme); applied = false } } }
            item { SpectrumCard { WorkspaceChoices("Цвет акцента", AccentStyle.entries.map { it.title },
                draft.accent.ordinal) { preview(draft.copy(accent = AccentStyle.entries[it])) } } }
            item { SpectrumCard { WorkspaceChoices("Плотность карточек", InterfaceDensity.entries.map { it.title },
                draft.density.ordinal) { preview(draft.copy(density = InterfaceDensity.entries[it])) } } }
            item { SpectrumCard {
                WorkspaceChoices("Движение", MotionLevel.entries.map { it.title }, draft.motion.ordinal) { preview(draft.copy(motion = MotionLevel.entries[it])) }
                Text(when (draft.motion) {
                    MotionLevel.LIVE -> "Объекты реагируют на касание и изменение состояния."
                    MotionLevel.SUBDUED -> "Короткие спокойные переходы; меньше фонового движения."
                    MotionLevel.OFF -> "Цветное оформление сохраняется. Элементы сразу принимают конечное состояние без движения."
                }, style = MaterialTheme.typography.bodySmall)
                if (!android.animation.ValueAnimator.areAnimatorsEnabled()) Text("Системные анимации отключены. Это ограничение имеет приоритет над выбранным режимом.")
                WorkspaceToggle("Акцентные карточки", "Мягкие тени и цветные границы карточек", draft.depth) {
                    preview(draft.copy(depth = it))
                }
                WorkspaceToggle("Яркое освещение", "Плотные поверхности и более отчётливые границы", draft.brightLight) { preview(draft.copy(brightLight = it)) }
                WorkspaceToggle("Отклик касаний", "Лёгкая вибрация при смене раздела", draft.haptics) {
                    preview(draft.copy(haptics = it))
                }
            } }
            item { WorkspaceSection("Приватность") }
            item { SpectrumCard {
                WorkspaceToggle("Скрывать сумму", "Во всех финансовых разделах, графиках и подробностях", draft.hideHomeBalance) {
                    preview(draft.copy(hideHomeBalance = it))
                }
            } }
            item { SpectrumSecondaryButton("Вернуть оформление по умолчанию", {
                preview(WorkspacePreferences(hideHomeBalance = draft.hideHomeBalance, homeStructure = draft.homeStructure))
                draftTheme = ThemeMode.DARK; theme.preview(draftTheme)
            }, Modifier.fillMaxWidth()) }
            item { Text("Возврат со страницы отменяет неприменённый просмотр. Системный размер шрифта и ограничения движения учитываются автоматически.", style = MaterialTheme.typography.bodySmall) }
        }
    }
}

internal val LocalCompactWorkspaceInput = staticCompositionLocalOf { false }

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun WorkspaceDetailPage(title: String, subtitle: String, onBack: () -> Unit,
    symbol: SpectrumSymbol = SpectrumSymbol.Allocation,
    adaptToIme: Boolean = false,
    content: @Composable (PaddingValues) -> Unit) {
    val menu = LocalDetailNavigationMenu.current
    SpectrumBackground(Modifier.fillMaxSize()) {
        // Measure the actual safe viewport, including any insets already consumed
        // by a parent. Reading the screen height and subtracting IME again would
        // reserve its space twice in an embedded workspace.
        val insets = if (adaptToIme) WindowInsets.safeDrawing else WindowInsets(0, 0, 0, 0)
        BoxWithConstraints(Modifier.fillMaxSize().windowInsetsPadding(insets)) {
            // Large text can consume the safe viewport even with the IME hidden.
            // Keep the same content slot while the header yields its height.
            val compact = adaptToIme && maxHeight < 240.dp * LocalDensity.current.fontScale
            CompositionLocalProvider(LocalCompactWorkspaceInput provides compact) {
                Row(Modifier.fillMaxSize()) {
                    if (compact) Column(Modifier.width(56.dp).fillMaxHeight()
                        .verticalScroll(rememberScrollState()).padding(top = 4.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        SpectrumIconButton(SpectrumSymbol.Back, "Назад", onBack)
                        menu?.let { AnalystMenuButton(it.open) }
                    }
                    // Keep the content at one composition location while the
                    // header gives its height to the focused native editor.
                    Scaffold(Modifier.weight(1f).fillMaxHeight(),
                        containerColor = androidx.compose.ui.graphics.Color.Transparent,
                        contentWindowInsets = WindowInsets.safeDrawing,
                        topBar = {
                            if (!compact) WorkspaceHeader(title, subtitle, onBack, symbol, onOpenMenu = menu?.open)
                        }, content = content)
                }
            }
        }
    }
}
