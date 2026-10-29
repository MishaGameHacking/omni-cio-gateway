package ru.omnicio.app.ui

import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.platform.testTag
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.foundation.selection.selectable
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.spatial.LocalFlatMotion
import ru.omnicio.app.ui.spatial.SpatialMotion
import ru.omnicio.app.ui.workspace.WorkspaceRoute

/** Persistent desktop rail. Explicit expansion also works with touch/keyboard. */
@Composable
internal fun StrategyNavigationRail(selected: AnalystTab, workspace: WorkspaceRoute?,
    navigateTab: (AnalystTab) -> Unit, navigateWorkspace: (WorkspaceRoute) -> Unit, initiallyExpanded: Boolean = false, onExpand: (() -> Unit)? = null) {
    var expanded by rememberSaveable { mutableStateOf(initiallyExpanded) }
    val motion = LocalFlatMotion.current != SpatialMotion.Off
    val width by animateDpAsState(if (expanded) 252.dp else 72.dp,
        tween(if (motion) 220 else 0), label = "navigation-rail-width")
    val colors = MaterialTheme.colorScheme
    Column(Modifier.width(width).fillMaxHeight()
        .windowInsetsPadding(WindowInsets.safeDrawing.only(WindowInsetsSides.Vertical))
        .padding(start = 8.dp, top = 12.dp, bottom = 12.dp)
        .clip(RoundedCornerShape(24.dp))
        .background(Brush.verticalGradient(listOf(colors.primaryContainer.copy(alpha = .55f), colors.surfaceContainerLow, colors.tertiaryContainer.copy(alpha = .35f))))
        .border(1.dp, colors.outlineVariant.copy(alpha = .7f), RoundedCornerShape(24.dp))
        .testTag(if (expanded) "navigation-rail-expanded" else "navigation-rail-collapsed")
        .verticalScroll(rememberScrollState()).padding(8.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        SpectrumGlyphButton(if (expanded) SpectrumSymbol.Back else SpectrumSymbol.Brain,
            if (expanded) "Свернуть панель" else "Развернуть панель", { if (onExpand != null) onExpand() else expanded = !expanded }, Modifier.size(48.dp))
        analystMenuDestinations.forEach { destination ->
            val active = destination.workspace?.let { it == workspace } ?: (workspace == null && destination.tab == selected)
            val open = { destination.workspace?.let(navigateWorkspace) ?: destination.tab?.let(navigateTab); Unit }
            if (expanded) Row(Modifier.fillMaxWidth().heightIn(min = 56.dp)
                .selectable(active, role = Role.Tab, onClick = open)
                .background(if (active) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceContainerLow)
                .padding(4.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                SpectrumIcon(destination.symbol, Modifier.size(44.dp), selected = active, motionAllowed = false)
                Text(destination.title, Modifier.weight(1f), style = MaterialTheme.typography.labelLarge)
            }
            else SpectrumGlyphButton(destination.symbol, destination.title, open, Modifier.size(48.dp), active = active)
        }
    }
}

