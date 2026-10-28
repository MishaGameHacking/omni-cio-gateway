package ru.omnicio.app.ui

import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsFocusedAsState
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.zIndex
import androidx.compose.ui.Alignment
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spatial.*
import ru.omnicio.app.ui.spectrum.*

enum class AnalystTab { Home, Portfolio, Actions, Risk, Education, Profile }
val LocalWideNavigation = staticCompositionLocalOf { false }
val LocalAnalystTabNavigator = staticCompositionLocalOf<(AnalystTab) -> Unit> { {} }
private val primaryTabs = analystPrimaryDestinations.mapNotNull { it.tab }

/** All four destinations stay visible; narrow large-text layouts use two rows. */
@Suppress("UNUSED_PARAMETER")
@Composable
fun AnalystBottomBar(selected: AnalystTab, onPortfolioClick: () -> Unit,
    onProfileClick: () -> Unit, modifier: Modifier = Modifier) {
    if (LocalWideNavigation.current) return
    val navigate = LocalAnalystTabNavigator.current
    Surface(modifier.fillMaxWidth().zIndex(1f).clipToBounds().testTag("analyst-bottom-bar"),
        color = MaterialTheme.colorScheme.surface) {
        Column {
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            BoxWithConstraints(Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 16.dp, vertical = 6.dp)) {
                val density = LocalDensity.current
                val measurer = rememberTextMeasurer()
                val labelStyle = MaterialTheme.typography.labelSmall.copy(fontWeight = FontWeight.Bold)
                val needed = primaryTabs.maxOf {
                    measurer.measure(AnnotatedString(it.label()), labelStyle, softWrap = false).size.width
                }
                val columns = if (with(density) { needed.toDp() + 12.dp } <= maxWidth / 4) 4 else 2
                Column(Modifier.fillMaxWidth().selectableGroup(), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    primaryTabs.chunked(columns).forEach { row ->
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(4.dp),
                            verticalAlignment = Alignment.CenterVertically) {
                            row.forEach { tab ->
                                DockDestination(tab, tab == selected.primaryDestination(),
                                    Modifier.weight(1f).testTag("bottom-destination-" + tab.name.lowercase())) { navigate(tab) }
                            }
                        }
                    }
                }
            }
        }
    }
}

internal fun AnalystTab.primaryDestination(): AnalystTab = destination().parent

@Composable
internal fun DockDestination(tab: AnalystTab, active: Boolean, modifier: Modifier = Modifier,
    showLabel: Boolean = true, click: () -> Unit) {
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val focused by interaction.collectIsFocusedAsState()
    val state = when { pressed -> SpatialState.Pressed; active || focused -> SpatialState.Selected; else -> SpatialState.Idle }
    val action = rememberSpatialHapticClick(SpatialHaptic.Selection, click)
    val accessible = if (showLabel) modifier else modifier.semantics { contentDescription = tab.label() }
    SpatialSurface(accessible.heightIn(min = 64.dp).selectable(active,
        interactionSource = interaction, indication = null, role = Role.Tab, onClick = action),
        SpatialSurfaceKind.Chip,
        color = if (active) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surface,
        state = state, interactive = true) {
        Column(Modifier.fillMaxWidth().padding(horizontal = 6.dp, vertical = 6.dp),
            horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(3.dp)) {
            SpatialIcon(tab.symbol().asset, Modifier.size(32.dp),
                tint = if (active) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onSurfaceVariant,
                motionAllowed = active, state = state, colorMode = SpatialColorMode.Decorative)
            if (showLabel) Text(tab.label(), Modifier.fillMaxWidth(), style = MaterialTheme.typography.labelSmall,
                textAlign = TextAlign.Center, softWrap = true,
                fontWeight = if (active) FontWeight.Bold else FontWeight.Medium,
                color = if (active) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

private fun AnalystTab.label() = destination().title
private fun AnalystTab.symbol() = destination().symbol

@Suppress("UNUSED_PARAMETER")
@Composable
fun AnalystSideRail(selected: AnalystTab, selectedWorkspace: ru.omnicio.app.ui.workspace.WorkspaceRoute?,
    navigate: (AnalystTab) -> Unit, navigateWorkspace: (ru.omnicio.app.ui.workspace.WorkspaceRoute) -> Unit) {
    Surface(Modifier.fillMaxHeight().width(80.dp).zIndex(1f).clipToBounds().testTag("analyst-side-rail"),
        color = MaterialTheme.colorScheme.surface) {
        Column(Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.safeDrawing.only(WindowInsetsSides.Vertical))
            .verticalScroll(rememberScrollState()).padding(8.dp).selectableGroup(),
            verticalArrangement = Arrangement.spacedBy(12.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            LocalOpenNavigationMenu.current?.let { AnalystMenuButton(it) }
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            primaryTabs.forEach { tab ->
                SpectrumGlyphButton(tab.symbol(), tab.label(), { navigate(tab) },
                    Modifier.size(56.dp).testTag("rail-destination-" + tab.name.lowercase()),
                    active = tab == selected.primaryDestination(), role = Role.Tab)
            }
        }
    }
}

