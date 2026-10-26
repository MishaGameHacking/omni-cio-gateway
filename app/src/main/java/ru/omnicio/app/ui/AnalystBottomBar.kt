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
private val primaryTabs = listOf(AnalystTab.Home, AnalystTab.Actions, AnalystTab.Profile)

/** Three stable destinations; labels can wrap at the user's font size. */
@Suppress("UNUSED_PARAMETER")
@Composable
fun AnalystBottomBar(selected: AnalystTab, onPortfolioClick: () -> Unit,
    onProfileClick: () -> Unit, modifier: Modifier = Modifier) {
    if (LocalWideNavigation.current) return
    val navigate = LocalAnalystTabNavigator.current
    val openMenu = LocalOpenNavigationMenu.current
    val measurer = rememberTextMeasurer()
    val density = LocalDensity.current
    val labelStyle = MaterialTheme.typography.labelMedium.copy(fontWeight = FontWeight.Bold)
    Surface(modifier.fillMaxWidth().zIndex(1f).clipToBounds().testTag("analyst-bottom-bar"), color = MaterialTheme.colorScheme.surface) {
        BoxWithConstraints(Modifier.fillMaxWidth()) {
            val menuWidth = if (openMenu == null) 0.dp else 56.dp
            val available = with(density) { ((maxWidth - 32.dp - menuWidth) / 3 - 12.dp).toPx() }
            val compact = primaryTabs.any { tab ->
                measurer.measure(AnnotatedString(tab.label()), style = labelStyle,
                    softWrap = false, maxLines = 1).size.width > available
            }
            Column {
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                if (compact) Text(selected.primaryDestination().label(),
                    Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 6.dp)
                        .clearAndSetSemantics {},
                    textAlign = TextAlign.Center, style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.onSurface)
                Row(Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 8.dp, vertical = 8.dp)
                    .selectableGroup(), horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically) {
                    if (openMenu != null) AnalystMenuButton(openMenu)
                    primaryTabs.forEach { tab ->
                        DockDestination(tab, tab == selected.primaryDestination(), Modifier.weight(1f)
                            .testTag("bottom-destination-" + tab.name.lowercase()),
                            showLabel = !compact) {
                            if (tab == AnalystTab.Profile) onProfileClick()
                            navigate(tab)
                        }
                    }
                }
            }
        }
    }
}

internal fun AnalystTab.primaryDestination(): AnalystTab = when (this) {
    AnalystTab.Home -> AnalystTab.Home
    AnalystTab.Portfolio, AnalystTab.Actions, AnalystTab.Risk -> AnalystTab.Actions
    AnalystTab.Education, AnalystTab.Profile -> AnalystTab.Profile
}

@Composable
private fun DockDestination(tab: AnalystTab, active: Boolean, modifier: Modifier = Modifier,
    showLabel: Boolean = true, click: () -> Unit) {
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val focused by interaction.collectIsFocusedAsState()
    val state = when { pressed -> SpatialState.Pressed; active || focused -> SpatialState.Selected; else -> SpatialState.Idle }
    val action = rememberSpatialHapticClick(SpatialHaptic.Selection, click)
    val accessible = if (showLabel) modifier else modifier.semantics { contentDescription = tab.label() }
    SpatialSurface(accessible.heightIn(min = 68.dp).selectable(active,
        interactionSource = interaction, indication = null, role = Role.Tab, onClick = action),
        SpatialSurfaceKind.Chip,
        color = if (active) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surface,
        state = state) {
        Column(Modifier.fillMaxWidth().padding(horizontal = 6.dp, vertical = 10.dp),
            horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(5.dp)) {
            SpatialIcon(tab.symbol().asset, Modifier.size(26.dp),
                tint = if (active) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                motionAllowed = false, state = state)
            if (showLabel) Text(tab.label(), Modifier.fillMaxWidth(), style = MaterialTheme.typography.labelMedium,
                textAlign = TextAlign.Center, softWrap = true,
                fontWeight = if (active) FontWeight.Bold else FontWeight.Medium,
                color = if (active) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

private fun AnalystTab.label() = when (this) {
    AnalystTab.Home -> "Система"
    AnalystTab.Actions -> "Решения"
    AnalystTab.Profile -> "Настройки"
    AnalystTab.Portfolio -> "Данные"
    AnalystTab.Risk -> "Риски"
    AnalystTab.Education -> "Обучение"
}

private fun AnalystTab.symbol() = when (this) {
    AnalystTab.Home -> SpectrumSymbol.Home
    AnalystTab.Actions -> SpectrumSymbol.Goal
    AnalystTab.Profile -> SpectrumSymbol.Settings
    AnalystTab.Portfolio -> SpectrumSymbol.Portfolio
    AnalystTab.Risk -> SpectrumSymbol.Risk
    AnalystTab.Education -> SpectrumSymbol.Education
}

@Composable
fun AnalystSideRail(selected: AnalystTab, navigate: (AnalystTab) -> Unit) {
    val width = (128f * maxOf(1f, LocalDensity.current.fontScale)).dp
    Surface(Modifier.fillMaxHeight().width(width).zIndex(1f).clipToBounds().testTag("analyst-side-rail"), color = MaterialTheme.colorScheme.surface) {
        Column(Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.safeDrawing.only(WindowInsetsSides.Vertical))
            .verticalScroll(rememberScrollState()).padding(10.dp).selectableGroup(),
            verticalArrangement = Arrangement.spacedBy(12.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Text("Analyst AI", style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(vertical = 16.dp))
            primaryTabs.forEach { tab ->
                DockDestination(tab, tab == selected.primaryDestination(), Modifier.fillMaxWidth()
                    .testTag("rail-destination-" + tab.name.lowercase())) { navigate(tab) }
            }
        }
    }
}
