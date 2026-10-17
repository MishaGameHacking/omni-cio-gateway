package ru.omnicio.app.ui

import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsFocusedAsState
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ru.omnicio.app.ui.spatial.*
import ru.omnicio.app.ui.spectrum.*

enum class AnalystTab { Home, Portfolio, Actions, Risk, Education, Profile }
val LocalWideNavigation = staticCompositionLocalOf { false }
val LocalAnalystTabNavigator = staticCompositionLocalOf<(AnalystTab) -> Unit> { {} }
private val primaryTabs = listOf(AnalystTab.Home, AnalystTab.Portfolio, AnalystTab.Actions, AnalystTab.Risk, AnalystTab.Profile)

/** One floating mesh dock. Text and tab semantics remain native and always visible. */
@Composable
fun AnalystBottomBar(selected: AnalystTab, onPortfolioClick: () -> Unit,
    onProfileClick: () -> Unit, modifier: Modifier = Modifier) {
    if (LocalWideNavigation.current) return
    val navigate = LocalAnalystTabNavigator.current
    Box(modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 8.dp, vertical = 6.dp),
        contentAlignment = Alignment.Center) {
        SpatialSurface(Modifier.widthIn(max = 720.dp).fillMaxWidth(), SpatialSurfaceKind.Dock,
            color = LocalSpectrumPalette.current.card, emphasized = true) {
            Row(Modifier.fillMaxWidth().padding(4.dp).selectableGroup(),
                horizontalArrangement = Arrangement.spacedBy(3.dp)) {
                primaryTabs.forEach { tab ->
                    val active = tab == selected || (selected == AnalystTab.Education && tab == AnalystTab.Profile)
                    DockDestination(tab, active, Modifier.weight(1f)) {
                        when (tab) {
                            AnalystTab.Portfolio -> onPortfolioClick()
                            AnalystTab.Profile -> onProfileClick()
                            else -> Unit
                        }
                        navigate(tab)
                    }
                }
            }
        }
    }
}

@Composable
private fun DockDestination(tab: AnalystTab, active: Boolean, modifier: Modifier = Modifier, click: () -> Unit) {
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val focused by interaction.collectIsFocusedAsState()
    val state = when { pressed -> SpatialState.Pressed; active || focused -> SpatialState.Selected; else -> SpatialState.Idle }
    val action = rememberSpatialHapticClick(click)
    val palette = LocalSpectrumPalette.current
    SpatialSurface(modifier.heightIn(min = 64.dp).selectable(active,
        interactionSource = interaction, indication = null, role = Role.Tab, onClick = action),
        SpatialSurfaceKind.Chip, color = if (active || focused) palette.cardStrong else palette.card,
        state = state, emphasized = active) {
        Column(Modifier.fillMaxWidth().padding(horizontal = 2.dp, vertical = 8.dp),
            horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(4.dp)) {
            SpatialIcon(tab.symbol().asset, Modifier.size(28.dp),
                tint = if (active) palette.cyan else palette.blue, state = state)
            Text(tab.label(), Modifier.fillMaxWidth(), fontSize = 13.sp, lineHeight = 17.sp,
                textAlign = TextAlign.Center, softWrap = true,
                fontWeight = if (active) FontWeight.Bold else FontWeight.Medium,
                color = if (active || focused) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

private fun AnalystTab.label() = when (this) {
    AnalystTab.Home -> "Капитал"
    AnalystTab.Portfolio -> "Портфель"
    AnalystTab.Actions -> "Действия"
    AnalystTab.Risk -> "Риски"
    AnalystTab.Education -> "Обучение"
    AnalystTab.Profile -> "Профиль"
}
private fun AnalystTab.symbol() = when (this) {
    AnalystTab.Home -> SpectrumSymbol.Home
    AnalystTab.Portfolio -> SpectrumSymbol.Portfolio
    AnalystTab.Actions -> SpectrumSymbol.Goal
    AnalystTab.Risk -> SpectrumSymbol.Risk
    AnalystTab.Education -> SpectrumSymbol.Education
    AnalystTab.Profile -> SpectrumSymbol.Profile
}

/** Same five mesh controls on a scrollable rail for tablets and short split screens. */
@Composable
fun AnalystSideRail(selected: AnalystTab, navigate: (AnalystTab) -> Unit) {
    SpatialSurface(Modifier.fillMaxHeight().width(112.dp), SpatialSurfaceKind.Dock,
        color = LocalSpectrumPalette.current.card, emphasized = true) {
        Column(Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.safeDrawing.only(WindowInsetsSides.Vertical))
            .verticalScroll(rememberScrollState()).padding(8.dp).selectableGroup(),
            verticalArrangement = Arrangement.spacedBy(8.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            SpectrumBrandOrb(Modifier.size(44.dp), compact = true)
            primaryTabs.forEach { tab ->
                val active = tab == selected || (selected == AnalystTab.Education && tab == AnalystTab.Profile)
                DockDestination(tab, active, Modifier.fillMaxWidth()) { navigate(tab) }
            }
        }
    }
}
