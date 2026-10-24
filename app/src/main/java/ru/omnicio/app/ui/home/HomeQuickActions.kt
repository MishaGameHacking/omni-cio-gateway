package ru.omnicio.app.ui.home

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.workspace.*

/** Working destinations, with readable one-column layout at large system text sizes. */
@Composable
internal fun HomeQuickActions(onAssets: () -> Unit, onPayments: () -> Unit) {
    val largeFont = LocalDensity.current.fontScale >= 1.4f
    val navigate = LocalWorkspaceNavigator.current
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        SpectrumActionTile("Обсудить с ассистентом", "Вопросы о портфеле и инвестициях",
            SpectrumSymbol.Analyst, { navigate(WorkspaceRoute.Assistant) }, Modifier.fillMaxWidth(),
            accent = LocalSpectrumPalette.current.violet)
        BoxWithConstraints(Modifier.fillMaxWidth()) {
            if (homeActionColumns(maxWidth.value, largeFont) == 1) {
                Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    QuickDestination("Мои активы", SpectrumSymbol.Portfolio, onAssets, Modifier.fillMaxWidth())
                    QuickDestination("Ближайшие выплаты", SpectrumSymbol.Calendar, onPayments, Modifier.fillMaxWidth())
                    QuickDestination("Поиск и наблюдение", SpectrumSymbol.Search, { navigate(WorkspaceRoute.Discovery) }, Modifier.fillMaxWidth())
                    QuickDestination("Мои исследования", SpectrumSymbol.Bookmark, { navigate(WorkspaceRoute.Library) }, Modifier.fillMaxWidth())
                }
            } else Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Row(Modifier.fillMaxWidth().height(IntrinsicSize.Min), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    QuickDestination("Мои активы", SpectrumSymbol.Portfolio, onAssets, Modifier.weight(1f).fillMaxHeight())
                    QuickDestination("Выплаты", SpectrumSymbol.Calendar, onPayments, Modifier.weight(1f).fillMaxHeight())
                }
                Row(Modifier.fillMaxWidth().height(IntrinsicSize.Min), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    QuickDestination("Поиск и наблюдение", SpectrumSymbol.Search, { navigate(WorkspaceRoute.Discovery) }, Modifier.weight(1f).fillMaxHeight())
                    QuickDestination("Мои исследования", SpectrumSymbol.Bookmark, { navigate(WorkspaceRoute.Library) }, Modifier.weight(1f).fillMaxHeight())
                }
            }
        }
    }
}

@Composable
private fun QuickDestination(title: String, symbol: SpectrumSymbol, click: () -> Unit, modifier: Modifier) {
    SpectrumCard(modifier, onClick = click) {
        SpectrumIcon(symbol, Modifier.size(32.dp), selected = true, motionAllowed = true)
        Text(title, style = MaterialTheme.typography.titleSmall)
    }
}
internal fun homeActionColumns(widthDp: Float, largeFont: Boolean): Int = if (largeFont || widthDp < 260f) 1 else 2
