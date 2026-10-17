package ru.omnicio.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.theme.LocalSpectrumMotionPreference
import ru.omnicio.app.ui.workspace.LocalWorkspacePreferences

enum class AnalystTab { Home, Portfolio, Actions, Risk, Education, Profile }
val LocalWideNavigation = staticCompositionLocalOf { false }
val LocalAnalystTabNavigator = staticCompositionLocalOf<(AnalystTab) -> Unit> { {} }

/** Five destinations, with secondary tools one level away. Labels never rely on colour alone. */
@Composable
fun AnalystBottomBar(selected: AnalystTab, onPortfolioClick: () -> Unit,
    onProfileClick: () -> Unit, modifier: Modifier = Modifier) {
    if (LocalWideNavigation.current) return
    val navigate = LocalAnalystTabNavigator.current
    val haptic = LocalHapticFeedback.current
    val prefs = LocalWorkspacePreferences.current.value
    val palette = LocalSpectrumPalette.current
    val tabs = listOf(AnalystTab.Home, AnalystTab.Portfolio, AnalystTab.Actions, AnalystTab.Risk, AnalystTab.Profile)
    Surface(modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.background.copy(alpha = .98f)) {
        Box(Modifier.navigationBarsPadding().padding(horizontal = 12.dp, vertical = 8.dp), contentAlignment = Alignment.Center) {
            Row(Modifier.widthIn(max = 720.dp).fillMaxWidth().clip(RoundedCornerShape(26.dp))
                .background(palette.card).padding(5.dp).selectableGroup()) {
                tabs.forEach { tab ->
                    val active = tab == selected || (selected == AnalystTab.Education && tab == AnalystTab.Profile)
                    Column(Modifier.weight(1f).heightIn(min = 62.dp).clip(RoundedCornerShape(21.dp))
                        .background(if (active) Brush.linearGradient(listOf(palette.cyan.copy(alpha = .17f), palette.violet.copy(alpha = .13f)))
                            else Brush.linearGradient(listOf(Color.Transparent, Color.Transparent)))
                        .selectable(active, role = Role.Tab, onClick = {
                            if (prefs.haptics) haptic.performHapticFeedback(HapticFeedbackType.SegmentTick)
                            when (tab) {
                                AnalystTab.Portfolio -> onPortfolioClick()
                                AnalystTab.Profile -> onProfileClick()
                                else -> Unit
                            }
                            navigate(tab)
                        }).padding(horizontal = 1.dp, vertical = 7.dp),
                        horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(3.dp)) {
                        SpectrumIcon(tab.symbol(), Modifier.size(24.dp), selected = active, tile = false,
                            motionAllowed = false)
                        Text(tab.label(), Modifier.fillMaxWidth(), fontSize = 13.sp, lineHeight = 17.sp,
                            textAlign = TextAlign.Center, softWrap = true,
                            fontWeight = if (active) FontWeight.Bold else FontWeight.Medium,
                            color = if (active) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
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

@Composable
fun AnalystSideRail(selected: AnalystTab, navigate: (AnalystTab) -> Unit) {
    NavigationRail(modifier = Modifier.fillMaxHeight().width(104.dp).statusBarsPadding(), containerColor = MaterialTheme.colorScheme.background) {
        listOf(AnalystTab.Home, AnalystTab.Portfolio, AnalystTab.Actions, AnalystTab.Risk, AnalystTab.Profile).forEach { tab ->
            NavigationRailItem(selected = tab == selected, onClick = { navigate(tab) },
                icon = { SpectrumIcon(tab.symbol(), Modifier.size(24.dp), motionAllowed = false) }, label = { Text(tab.label()) })
        }
    }
}
