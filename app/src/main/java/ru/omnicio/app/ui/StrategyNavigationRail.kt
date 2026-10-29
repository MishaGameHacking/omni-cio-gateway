package ru.omnicio.app.ui

import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.spatial.LocalFlatMotion
import ru.omnicio.app.ui.spatial.SpatialMotion
import ru.omnicio.app.ui.workspace.WorkspaceRoute

/** Persistent desktop rail. Explicit expansion also works with touch/keyboard. */
@Composable
internal fun StrategyNavigationRail(selected: AnalystTab, workspace: WorkspaceRoute?,
    navigateTab: (AnalystTab) -> Unit, navigateWorkspace: (WorkspaceRoute) -> Unit) {
    var expanded by rememberSaveable { mutableStateOf(false) }
    val motion = LocalFlatMotion.current != SpatialMotion.Off
    val width by animateDpAsState(if (expanded) 252.dp else 72.dp,
        tween(if (motion) 220 else 0), label = "navigation-rail-width")
    Column(Modifier.width(width).fillMaxHeight().clipToBounds()
        .background(MaterialTheme.colorScheme.surfaceContainerLow)
        .windowInsetsPadding(WindowInsets.safeDrawing.only(WindowInsetsSides.Vertical))
        .verticalScroll(rememberScrollState()).padding(8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        SpectrumGlyphButton(if (expanded) SpectrumSymbol.Back else SpectrumSymbol.Forward,
            if (expanded) "Свернуть панель" else "Развернуть панель", { expanded = !expanded }, Modifier.size(48.dp))
        analystMenuDestinations.forEach { destination ->
            val active = destination.workspace?.let { it == workspace } ?: (workspace == null && destination.tab == selected)
            val open = { destination.workspace?.let(navigateWorkspace) ?: destination.tab?.let(navigateTab); Unit }
            if (expanded) SpectrumTextButton(destination.title, open, symbol = destination.symbol, modifier = Modifier.fillMaxWidth())
            else SpectrumGlyphButton(destination.symbol, destination.title, open, Modifier.size(56.dp), active = active)
        }
    }
}
