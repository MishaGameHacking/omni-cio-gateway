package ru.omnicio.app.ui.workspace

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
    val prefs = controller.value
    val theme = LocalThemePreference.current
    val motion = LocalSpectrumMotionPreference.current
    WorkspaceDetailPage("Оформление", "Ваш ритм и пространство", onBack) { padding ->
        LazyColumn(Modifier.fillMaxSize().semantics { testTagsAsResourceId = true }.testTag("workspace-content").padding(padding).consumeWindowInsets(padding),
            contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
            item {
                SpectrumCard(emphasized = true) {
                    Text("Analyst AI", style = MaterialTheme.typography.headlineMedium)
                    Text("Спокойный фокус. Живые детали.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    SpectrumProgressBar(.64f, accent = LocalSpectrumPalette.current.cyan)
                    Text("Предпросмотр оформления", style = MaterialTheme.typography.labelMedium)
                }
            }
            item { SpectrumCard { WorkspaceChoices("Тема", ThemeMode.entries.map { it.title },
                ThemeMode.entries.indexOf(theme.mode)) { theme.select(ThemeMode.entries[it]) } } }
            item { SpectrumCard { WorkspaceChoices("Цвет акцента", AccentStyle.entries.map { it.title },
                prefs.accent.ordinal) { controller.update(prefs.copy(accent = AccentStyle.entries[it])) } } }
            item { SpectrumCard { WorkspaceChoices("Плотность карточек", InterfaceDensity.entries.map { it.title },
                prefs.density.ordinal) { controller.update(prefs.copy(density = InterfaceDensity.entries[it])) } } }
            item { SpectrumCard {
                WorkspaceToggle("Движение", "Иконки и переходы", motion.enabled, motion.select)
                WorkspaceToggle("Глубина", "Мягкие тени и пространственные акценты", prefs.depth) {
                    controller.update(prefs.copy(depth = it))
                }
                WorkspaceToggle("Отклик касаний", "Лёгкая вибрация при смене раздела", prefs.haptics) {
                    controller.update(prefs.copy(haptics = it))
                }
            } }
            item { WorkspaceSection("Главный экран") }
            item { SpectrumCard {
                WorkspaceToggle("Скрывать сумму", "Во всех финансовых разделах, графиках и подробностях", prefs.hideHomeBalance) {
                    controller.update(prefs.copy(hideHomeBalance = it))
                }
                WorkspaceToggle("Структура капитала", "Краткое распределение на главном экране", prefs.homeStructure) {
                    controller.update(prefs.copy(homeStructure = it))
                }
            } }
            item { SpectrumSecondaryButton("Вернуть оформление по умолчанию", {
                controller.update(WorkspacePreferences()); theme.select(ThemeMode.DARK); motion.select(true)
            }, Modifier.fillMaxWidth()) }
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
