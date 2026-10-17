package ru.omnicio.app.ui.workspace

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.theme.*

@Composable
fun AppearanceScreen(onBack: () -> Unit) {
    val controller = LocalWorkspacePreferences.current
    val theme = LocalThemePreference.current
    var savedPrefs by remember { mutableStateOf(controller.value) }
    var savedTheme by remember { mutableStateOf(theme.mode) }
    var draft by remember { mutableStateOf(controller.value) }
    var draftTheme by remember { mutableStateOf(theme.mode) }
    var applied by remember { mutableStateOf(false) }
    val dirty = draft != savedPrefs || draftTheme != savedTheme
    val preview: (WorkspacePreferences) -> Unit = { next -> draft = next; controller.preview(next); applied = false }
    val cancel = { controller.cancelPreview(); theme.cancelPreview(); draft = savedPrefs; draftTheme = savedTheme; applied = false }
    val leave = { cancel(); onBack() }
    BackHandler(onBack = leave)
    DisposableEffect(Unit) { onDispose { controller.cancelPreview(); theme.cancelPreview() } }
    WorkspaceDetailPage("Оформление", "Просмотр → применить или отменить", leave) { padding ->
        LazyColumn(Modifier.fillMaxSize().semantics { testTagsAsResourceId = true }.testTag("workspace-content").padding(padding).consumeWindowInsets(padding),
            contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
            item {
                SpectrumCard(emphasized = true) {
                    Text("Analyst AI", style = MaterialTheme.typography.headlineMedium)
                    Text("Предпросмотр объёма, контраста и движения", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Row(horizontalArrangement = Arrangement.spacedBy(20.dp)) {
                        SpectrumBrandOrb(Modifier.size(76.dp))
                        SpectrumAssetMark("share", "А", Modifier.size(64.dp))
                        SpectrumAssetMark("bond", "Б", Modifier.size(64.dp))
                    }
                    Text("Аа · 0123456789", style = MaterialTheme.typography.headlineSmall)
                    Text("Образцы оформления без финансовых значений. Проверьте удобство чтения и скорость отклика.", style = MaterialTheme.typography.bodySmall)
                    Text(if (dirty) "Предпросмотр · настройки ещё не сохранены" else if (applied) "Оформление применено" else "Текущие сохранённые настройки", style = MaterialTheme.typography.labelMedium)
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        SpectrumPrimaryButton("Применить", {
                            controller.preview(draft); theme.preview(draftTheme)
                            controller.applyPreview(); theme.applyPreview()
                            savedPrefs = draft; savedTheme = draftTheme; applied = true
                        }, Modifier.weight(1f), enabled = dirty)
                        SpectrumSecondaryButton("Отменить", cancel, Modifier.weight(1f), enabled = dirty)
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
                    MotionLevel.OFF -> "Объём сохраняется. Объекты сразу принимают конечное состояние без движения."
                }, style = MaterialTheme.typography.bodySmall)
                if (!android.animation.ValueAnimator.areAnimatorsEnabled()) Text("Системные анимации отключены. Это ограничение имеет приоритет над выбранным режимом.")
                WorkspaceToggle("Выраженная глубина", "Пространственные акценты и разделение поверхностей", draft.depth) {
                    preview(draft.copy(depth = it))
                }
                WorkspaceToggle("Яркое освещение", "Плотные поверхности и более отчётливые границы", draft.brightLight) { preview(draft.copy(brightLight = it)) }
                WorkspaceToggle("Отклик касаний", "Лёгкая вибрация при смене раздела", draft.haptics) {
                    preview(draft.copy(haptics = it))
                }
            } }
            item { WorkspaceSection("Главный экран") }
            item { SpectrumCard {
                WorkspaceToggle("Скрывать сумму", "Во всех финансовых разделах, графиках и подробностях", draft.hideHomeBalance) {
                    preview(draft.copy(hideHomeBalance = it))
                }
                WorkspaceToggle("Структура капитала", "Краткое распределение на главном экране", draft.homeStructure) {
                    preview(draft.copy(homeStructure = it))
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

@Composable
fun WorkspaceDetailPage(title: String, subtitle: String, onBack: () -> Unit,
    symbol: SpectrumSymbol = SpectrumSymbol.Allocation,
    content: @Composable (PaddingValues) -> Unit) {
    SpectrumBackground(Modifier.fillMaxSize()) {
        Scaffold(containerColor = androidx.compose.ui.graphics.Color.Transparent,
            contentWindowInsets = WindowInsets.safeDrawing,
            topBar = {
                WorkspaceHeader(title, subtitle, onBack, symbol)
            }, content = content)
    }
}
