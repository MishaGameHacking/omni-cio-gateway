package ru.omnicio.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ru.omnicio.app.ui.spectrum.LocalSpectrumPalette
import ru.omnicio.app.ui.spectrum.SpectrumIcon
import ru.omnicio.app.ui.spectrum.SpectrumSymbol
import ru.omnicio.app.ui.theme.LocalSpectrumMotionPreference

/** Secondary destinations are deliberately NOT extra items in the five-place bottom bar. */
enum class AnalystTab { Home, Portfolio, Market, Education, Profile, Ideas, Pulse, Chat, Risks }
val LocalAnalystTabNavigator = staticCompositionLocalOf<(AnalystTab) -> Unit> { {} }
internal val PrimaryAnalystTabs = listOf(AnalystTab.Home, AnalystTab.Portfolio, AnalystTab.Market, AnalystTab.Education, AnalystTab.Profile)

internal fun AnalystTab.primaryTab(): AnalystTab = when (this) {
    AnalystTab.Ideas -> AnalystTab.Market
    AnalystTab.Pulse, AnalystTab.Chat, AnalystTab.Risks -> AnalystTab.Home
    else -> this
}

@Composable
fun AnalystBottomBar(selected: AnalystTab, onPortfolioClick: () -> Unit, onProfileClick: () -> Unit, modifier: Modifier = Modifier) {
    val navigate = LocalAnalystTabNavigator.current
    val palette = LocalSpectrumPalette.current
    Surface(modifier, color = MaterialTheme.colorScheme.surface.copy(alpha = .98f), contentColor = MaterialTheme.colorScheme.onSurface) {
        Column {
            Box(Modifier.fillMaxWidth().height(1.dp).background(Brush.horizontalGradient(listOf(
                Color.Transparent, palette.cyan.copy(alpha = .26f), palette.violet.copy(alpha = .20f), Color.Transparent))))
            Row(Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 8.dp, vertical = 5.dp).selectableGroup()) {
                PrimaryAnalystTabs.forEach { tab ->
                    BottomBarItem(tab, selected.primaryTab() == tab, Modifier.weight(1f)) {
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
private fun BottomBarItem(tab: AnalystTab, selected: Boolean, modifier: Modifier, onClick: () -> Unit) {
    val palette = LocalSpectrumPalette.current
    val color = if (selected) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant
    Column(modifier.heightIn(min = 62.dp).clip(RoundedCornerShape(12.dp))
        .background(if (selected) palette.blue.copy(alpha = .09f) else Color.Transparent)
        .selectable(selected = selected, role = Role.Tab, onClick = onClick)
        .padding(horizontal = 1.dp, vertical = 5.dp),
        verticalArrangement = Arrangement.spacedBy(2.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        SpectrumIcon(tab.symbol(), Modifier.size(30.dp), selected = selected, tile = false,
            motionAllowed = LocalSpectrumMotionPreference.current.enabled)
        Text(tab.label(), color = color, fontSize = 11.sp, lineHeight = 14.sp, textAlign = TextAlign.Center,
            fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Normal, modifier = Modifier.fillMaxWidth())
        Box(Modifier.size(width = 14.dp, height = 2.dp).clip(RoundedCornerShape(1.dp))
            .background(if (selected) Brush.horizontalGradient(listOf(palette.cyan, palette.violet)) else Brush.horizontalGradient(listOf(Color.Transparent, Color.Transparent))))
    }
}

private fun AnalystTab.label(): String = when (this) {
    AnalystTab.Home -> "Главная"
    AnalystTab.Portfolio -> "Портфель"
    AnalystTab.Market -> "Рынок"
    AnalystTab.Education -> "Обучение"
    AnalystTab.Profile -> "Профиль"
    AnalystTab.Ideas -> "Рекомендации"
    AnalystTab.Pulse -> "События"
    AnalystTab.Chat -> "Сообщения"
    AnalystTab.Risks -> "Риски"
}
private fun AnalystTab.symbol(): SpectrumSymbol = when (this) {
    AnalystTab.Home -> SpectrumSymbol.Home
    AnalystTab.Portfolio -> SpectrumSymbol.Portfolio
    AnalystTab.Market -> SpectrumSymbol.Market
    AnalystTab.Education -> SpectrumSymbol.Education
    AnalystTab.Profile -> SpectrumSymbol.Profile
    AnalystTab.Ideas -> SpectrumSymbol.Ideas
    AnalystTab.Pulse -> SpectrumSymbol.Bell
    AnalystTab.Chat -> SpectrumSymbol.Messages
    AnalystTab.Risks -> SpectrumSymbol.Risk
}
