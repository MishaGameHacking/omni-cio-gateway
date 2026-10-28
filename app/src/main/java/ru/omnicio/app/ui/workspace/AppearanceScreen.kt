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
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.theme.*
import ru.omnicio.app.ui.AnalystMenuButton
import ru.omnicio.app.ui.LocalDetailNavigationMenu
import ru.omnicio.app.ui.RegisterPanelExit

@Composable
fun AppearanceScreen(onBack: () -> Unit) {
    val controller = LocalWorkspacePreferences.current
    val draft = controller.value
    val preview: (WorkspacePreferences) -> Unit = controller.update
    val requestExit: (() -> Unit) -> Unit = { proceed -> proceed() }
    val leave = onBack
    RegisterPanelExit(WorkspaceRoute.Appearance, requestExit)
    BackHandler(onBack = leave)
    WorkspaceDetailPage("Экран и удобство", "Изменения сохраняются автоматически", leave, adaptToIme = true) { padding ->
        val compact = LocalCompactWorkspaceInput.current
        LazyColumn(Modifier.fillMaxSize().semantics { testTagsAsResourceId = true }.testTag("workspace-content").padding(padding).consumeWindowInsets(padding),
            contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
            if (compact) item(key = "page-heading") {
                WorkspacePageHeading("Экран и удобство", "Изменения сохраняются автоматически")
            }
            item {
                Text(controller.saveStatus, style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.semantics { liveRegion = androidx.compose.ui.semantics.LiveRegionMode.Polite })
                if (controller.saveFailed) SpectrumSecondaryButton("Повторить сохранение", controller.retrySave, Modifier.fillMaxWidth())
            }
            item { SpectrumCard {
                WorkspaceChoices("Движение", MotionLevel.entries.map { it.title }, draft.motion.ordinal) { preview(draft.copy(motion = MotionLevel.entries[it])) }
                Text(when (draft.motion) {
                    MotionLevel.LIVE -> "Плавные переходы и отклик при касании. Числа остаются неподвижными."
                    MotionLevel.SUBDUED -> "Короткие спокойные переходы; меньше фонового движения."
                    MotionLevel.OFF -> "Цветное оформление сохраняется. Элементы сразу принимают конечное состояние без движения."
                }, style = MaterialTheme.typography.bodySmall)
                if (!android.animation.ValueAnimator.areAnimatorsEnabled()) Text("Системные анимации отключены. Это ограничение имеет приоритет над выбранным режимом.")
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
                preview(draft.resetAppearance())
            }, Modifier.fillMaxWidth()) }
            item { Text("Каждый выбор применяется автоматически. Системный размер шрифта и ограничения движения учитываются.", style = MaterialTheme.typography.bodySmall) }
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
                        menu?.let { AnalystMenuButton(it.open) }
                        SpectrumIconButton(SpectrumSymbol.Back, "Назад", onBack)
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

